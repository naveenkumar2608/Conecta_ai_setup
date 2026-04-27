# backend/app/repositories/blob_repo.py
from azure.storage.blob.aio import BlobServiceClient
from azure.identity.aio import DefaultAzureCredential
from app.config import get_settings, get_secrets

import logging

logger = logging.getLogger(__name__)


class BlobRepository:
    """
    Azure Blob Storage data access layer.
    Uses Managed Identity for authentication (no API keys).
    """

    def __init__(self):
        secrets = get_secrets()
        self.client = BlobServiceClient.from_connection_string(
            secrets.blob_connection_string
        )



    async def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """
        Upload a blob to Azure Blob Storage.
        
        Args:
            container_name: Target container (e.g., "csv-uploads")
            blob_name: Full blob path (e.g., "user123/uuid/file.csv")
            data: Raw bytes to upload
            content_type: MIME type
            metadata: Key-value pairs stored with the blob
            
        Returns:
            Full blob URL
        """
        try:
            container_client = self.client.get_container_client(
                container_name
            )

            # Ensure container exists
            try:
                await container_client.get_container_properties()
            except Exception:
                await container_client.create_container()
                logger.info(
                    f"Created container: {container_name}"
                )

            blob_client = container_client.get_blob_client(blob_name)

            await blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings={
                    "content_type": content_type,
                },
                metadata=metadata,
            )

            blob_url = blob_client.url
            logger.info(
                f"Uploaded blob: {blob_name} "
                f"({len(data)} bytes) to {container_name}"
            )
            return blob_url

        except Exception as e:
            logger.error(f"Blob upload failed: {e}")
            raise

    async def download_blob(
        self,
        container_name: str,
        blob_name: str,
    ) -> bytes:
        """Download a blob's content as bytes."""
        try:
            container_client = self.client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            download_stream = await blob_client.download_blob()
            data = await download_stream.readall()
            logger.info(
                f"Downloaded blob: {blob_name} ({len(data)} bytes)"
            )
            return data
        except Exception as e:
            logger.error(f"Blob download failed: {e}")
            raise

    async def delete_blob(
        self,
        container_name: str,
        blob_name: str,
    ):
        """Delete a blob."""
        try:
            container_client = self.client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.delete_blob()
            logger.info(f"Deleted blob: {blob_name}")
        except Exception as e:
            logger.error(f"Blob deletion failed: {e}")
            raise

    async def list_blobs(
        self,
        container_name: str,
        prefix: str | None = None,
    ) -> list[dict]:
        """List blobs in a container with optional prefix filter."""
        try:
            container_client = self.client.get_container_client(
                container_name
            )
            blobs = []
            async for blob in container_client.list_blobs(
                name_starts_with=prefix
            ):
                blobs.append({
                    "name": blob.name,
                    "size": blob.size,
                    "last_modified": blob.last_modified.isoformat()
                    if blob.last_modified
                    else None,
                    "metadata": blob.metadata,
                })
            return blobs
        except Exception as e:
            logger.error(f"Blob listing failed: {e}")
            raise

    async def close(self):
        """Close the blob service client."""
        await self.client.close()
        await self.credential.close()
