# functions/blob_trigger/__init__.py
import azure.functions as func
import logging
import json
import asyncio
from datetime import datetime, timezone
from shared.parser import CSVParser
from shared.metadata_extractor import MetadataExtractor
from shared.chunker import SemanticChunker
from shared.embedder import EmbeddingGenerator
from shared.search_uploader import SearchUploader
from shared.postgres_writer import PostgresWriter
from shared.keyvault_loader import load_secrets
from azure.servicebus import ServiceBusClient, ServiceBusMessage

logger = logging.getLogger(__name__)

# ── Retry configuration ──────────────────────────────
MAX_RETRIES = 3
RETRYABLE_STEPS = {"embedding", "search_upload", "db_update"}


class IngestionError(Exception):
    """Custom error with step tracking for retry logic."""
    def __init__(self, message: str, step: str, retryable: bool = False):
        super().__init__(message)
        self.step = step
        self.retryable = retryable


async def _run_with_retry(func_to_run, step_name: str, max_retries: int = MAX_RETRIES):
    """
    Run a coroutine with exponential backoff retry.
    Only retries for steps marked as retryable (network calls).
    """
    last_error = None
    retries = max_retries if step_name in RETRYABLE_STEPS else 1

    for attempt in range(retries):
        try:
            result = func_to_run()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                logger.warning(
                    f"Step '{step_name}' failed (attempt {attempt + 1}/{retries}), "
                    f"retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"Step '{step_name}' failed after {retries} attempts: {e}"
                )

    raise IngestionError(
        message=str(last_error),
        step=step_name,
        retryable=step_name in RETRYABLE_STEPS,
    )


async def _publish_event(sb_client, event: dict):
    """Publish an event to Service Bus ingestion-status queue."""
    try:
        sender = sb_client.get_queue_sender("ingestion-status")
        async with sender:
            message = ServiceBusMessage(
                body=json.dumps(event, default=str),
                subject=event.get("event_type", "unknown"),
                content_type="application/json",
            )
            await sender.send_messages(message)
            logger.info(
                f"Published event: {event['event_type']} "
                f"for upload_id={event.get('upload_id', 'unknown')}"
            )
    except Exception as e:
        # Don't fail ingestion if event publish fails
        logger.error(f"Failed to publish Service Bus event: {e}")


async def main(blob: func.InputStream):
    """
    Azure Function — Blob Trigger
    Triggered when a CSV file is uploaded to 'csv-uploads' container.

    Pipeline: Parse → Extract Metadata → Chunk → Embed → Store
    Includes: Retry logic, Service Bus events, dead letter support.
    """
    blob_name = blob.name
    blob_data = blob.read()

    logger.info(f"Processing blob: {blob_name}, size: {len(blob_data)} bytes")

    # Extract identifiers from blob path
    # Path format: csv-uploads/{user_id}/{upload_id}/{filename}
    path_parts = blob_name.split("/")
    user_id = path_parts[1] if len(path_parts) > 2 else "unknown"
    upload_id = path_parts[2] if len(path_parts) > 3 else path_parts[1]
    file_name = path_parts[-1]

    # Initialize services with Key Vault secrets
    secrets = load_secrets()
    postgres = PostgresWriter(secrets.postgres_connection_string)
    search_uploader = SearchUploader(
        endpoint=secrets.search_endpoint,
        api_key=secrets.search_api_key,
        index_name="connecta-coaching-index",
    )
    embedder = EmbeddingGenerator(
        endpoint=secrets.openai_endpoint,
        api_key=secrets.openai_api_key,
        deployment="text-embedding-3-large",
    )
    sb_client = ServiceBusClient.from_connection_string(
        secrets.service_bus_connection_string
    )

    try:
        # Update status to processing
        await postgres.update_ingestion_status(
            upload_id=upload_id,
            status="processing",
            processing_started_at=datetime.now(timezone.utc),
        )

        # Publish "processing started" event
        await _publish_event(sb_client, {
            "event_type": "ingestion_started",
            "upload_id": upload_id,
            "user_id": user_id,
            "file_name": file_name,
        })

        # ── STEP 1: PARSING (not retryable — deterministic) ──
        logger.info(f"Step 1: Parsing CSV - {file_name}")
        parser = CSVParser()
        df = await _run_with_retry(
            lambda: parser.parse(blob_data, file_name),
            "parsing",
        )
        logger.info(f"Parsed {len(df)} rows, {len(df.columns)} columns")

        # ── STEP 2: METADATA EXTRACTION (not retryable) ──────
        logger.info("Step 2: Extracting metadata")
        extractor = MetadataExtractor()
        metadata = await _run_with_retry(
            lambda: extractor.extract(
                df=df,
                file_name=file_name,
                upload_id=upload_id,
                user_id=user_id,
            ),
            "metadata",
        )
        logger.info(f"Metadata: {json.dumps(metadata, default=str)}")

        # ── STEP 3: SEMANTIC CHUNKING (not retryable) ────────
        logger.info("Step 3: Chunking data")
        chunker = SemanticChunker(max_chunk_size=500, overlap_rows=2)
        chunks = await _run_with_retry(
            lambda: chunker.chunk(df=df, metadata=metadata),
            "chunking",
        )
        logger.info(f"Generated {len(chunks)} chunks")

        # ── STEP 4: EMBEDDING (retryable — network call) ─────
        logger.info("Step 4: Generating embeddings")
        embedded_chunks = await _run_with_retry(
            lambda: embedder.embed_chunks(chunks),
            "embedding",
        )
        logger.info(
            f"Generated {len(embedded_chunks)} embeddings "
            f"(dim={len(embedded_chunks[0]['embedding'])})"
        )

        # ── STEP 5: SEARCH UPLOAD (retryable — network call) ─
        logger.info("Step 5: Storing in Azure AI Search")
        await _run_with_retry(
            lambda: search_uploader.upload_documents(embedded_chunks),
            "search_upload",
        )
        logger.info(f"Uploaded {len(embedded_chunks)} documents to AI Search")

        # ── STEP 6: UPDATE DB (retryable — network call) ─────
        logger.info("Step 6: Updating PostgreSQL")
        await _run_with_retry(
            lambda: postgres.update_ingestion_status(
                upload_id=upload_id,
                status="completed",
                row_count=len(df),
                chunk_count=len(chunks),
                column_names=list(df.columns),
                domain_tags=metadata.get("domain_tags", []),
                processing_completed_at=datetime.now(timezone.utc),
            ),
            "db_update",
        )

        # Publish "completed" event
        await _publish_event(sb_client, {
            "event_type": "ingestion_completed",
            "upload_id": upload_id,
            "user_id": user_id,
            "file_name": file_name,
            "row_count": len(df),
            "chunk_count": len(chunks),
        })

        logger.info(
            f"Ingestion complete for {file_name}: "
            f"{len(df)} rows → {len(chunks)} chunks"
        )

    except IngestionError as e:
        logger.error(
            f"Ingestion failed at step '{e.step}' for {file_name}: {e}"
        )
        await postgres.update_ingestion_status(
            upload_id=upload_id,
            status="failed",
            error_message=f"Failed at step '{e.step}': {str(e)}",
            processing_completed_at=datetime.now(timezone.utc),
        )
        await _publish_event(sb_client, {
            "event_type": "ingestion_failed",
            "upload_id": upload_id,
            "user_id": user_id,
            "file_name": file_name,
            "failed_step": e.step,
            "error": str(e),
            "retryable": e.retryable,
        })
        raise

    except Exception as e:
        logger.error(f"Unexpected ingestion failure for {file_name}: {str(e)}")
        await postgres.update_ingestion_status(
            upload_id=upload_id,
            status="failed",
            error_message=str(e),
            processing_completed_at=datetime.now(timezone.utc),
        )
        await _publish_event(sb_client, {
            "event_type": "ingestion_failed",
            "upload_id": upload_id,
            "user_id": user_id,
            "file_name": file_name,
            "failed_step": "unknown",
            "error": str(e),
            "retryable": False,
        })
        raise

    finally:
        await sb_client.close()
        await postgres.close()
