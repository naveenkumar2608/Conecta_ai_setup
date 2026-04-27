# backend/app/repositories/search_repo.py
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from app.config import get_settings, get_secrets
import logging

logger = logging.getLogger(__name__)


class SearchRepository:
    """
    Azure AI Search data access layer.
    Handles CRUD operations on search index documents.
    Distinct from SearchService — this is raw data access,
    while SearchService handles query logic.
    """

    def __init__(self):
        secrets = get_secrets()
        self.credential = AzureKeyCredential(secrets.search_api_key)
        self.endpoint = secrets.azure_search_endpoint
        self.index_name = secrets.search_index_name


        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential,
        )
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential,
        )

    async def upload_documents(
        self, documents: list[dict]
    ) -> dict:
        """Upload or merge documents into the search index."""
        try:
            result = await self.search_client.upload_documents(
                documents=documents
            )
            succeeded = sum(1 for r in result if r.succeeded)
            failed = sum(1 for r in result if not r.succeeded)
            logger.info(
                f"Search upload: {succeeded} succeeded, {failed} failed"
            )
            return {"succeeded": succeeded, "failed": failed}
        except Exception as e:
            logger.error(f"Search upload failed: {e}")
            raise

    async def delete_documents(
        self, document_ids: list[str]
    ) -> dict:
        """Delete documents from the search index by their keys."""
        try:
            documents = [
                {"chunk_id": doc_id} for doc_id in document_ids
            ]
            result = await self.search_client.delete_documents(
                documents=documents
            )
            succeeded = sum(1 for r in result if r.succeeded)
            logger.info(
                f"Search delete: {succeeded}/{len(document_ids)} succeeded"
            )
            return {"succeeded": succeeded}
        except Exception as e:
            logger.error(f"Search delete failed: {e}")
            raise

    async def get_document(self, chunk_id: str) -> dict | None:
        """Retrieve a single document by its key."""
        try:
            doc = await self.search_client.get_document(key=chunk_id)
            return dict(doc)
        except Exception:
            return None

    async def get_document_count(self) -> int:
        """Get the total number of documents in the index."""
        try:
            return await self.search_client.get_document_count()
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0

    async def close(self):
        """Close async clients."""
        await self.search_client.close()
        await self.index_client.close()
