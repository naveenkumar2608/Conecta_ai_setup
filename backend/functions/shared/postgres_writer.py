# functions/shared/postgres_writer.py
import asyncpg
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class PostgresWriter:
    """Handles all PostgreSQL write operations for ingestion pipeline."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.connection_string, 
                min_size=2, 
                max_size=10
            )
        return self._pool

    async def insert_file_metadata(
        self,
        upload_id: str,
        user_id: str,
        file_name: str,
        blob_url: str,
        blob_name: str,
        file_size_bytes: int,
        status: str,
        uploaded_at: datetime,
    ):
        """Insert initial file metadata record."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO file_metadata (
                    upload_id, user_id, file_name, blob_url, 
                    blob_name, file_size_bytes, status, uploaded_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (upload_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    uploaded_at = EXCLUDED.uploaded_at
                """,
                upload_id, user_id, file_name, blob_url,
                blob_name, file_size_bytes, status, uploaded_at,
            )
        logger.info(f"Inserted file_metadata for upload_id={upload_id}")

    async def update_ingestion_status(
        self,
        upload_id: str,
        status: str,
        row_count: int = None,
        chunk_count: int = None,
        column_names: list[str] = None,
        domain_tags: list[str] = None,
        error_message: str = None,
        processing_started_at: datetime = None,
        processing_completed_at: datetime = None,
    ):
        """Update ingestion status and metadata after processing."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE file_metadata SET
                    status = $2,
                    row_count = COALESCE($3, row_count),
                    chunk_count = COALESCE($4, chunk_count),
                    column_names = COALESCE($5, column_names),
                    domain_tags = COALESCE($6, domain_tags),
                    error_message = $7,
                    processing_started_at = COALESCE(
                        $8, processing_started_at
                    ),
                    processing_completed_at = $9,
                    updated_at = NOW()
                WHERE upload_id = $1
                """,
                upload_id, status, row_count, chunk_count,
                json.dumps(column_names) if column_names else None,
                json.dumps(domain_tags) if domain_tags else None,
                error_message,
                processing_started_at, processing_completed_at,
            )

            # Insert ingestion log
            await conn.execute(
                """
                INSERT INTO ingestion_logs (
                    upload_id, status, message, created_at
                ) VALUES ($1, $2, $3, NOW())
                """,
                upload_id, status,
                error_message or f"Status changed to {status}",
            )

        logger.info(
            f"Updated ingestion status: upload_id={upload_id}, "
            f"status={status}"
        )

    async def close(self):
        if self._pool:
            await self._pool.close()