# backend/app/services/search_service.py
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import (
    VectorizedQuery,
    QueryType,
    QueryCaptionType,
    QueryAnswerType,
)
from azure.core.credentials import AzureKeyCredential
from app.config import get_settings, get_secrets
import logging

logger = logging.getLogger(__name__)


class SearchService:
    """
    Azure AI Search client for the FastAPI backend.
    Supports hybrid search (vector + keyword + semantic reranker).
    """

    def __init__(self):
        settings = get_settings()
        secrets = get_secrets()
        self.client = SearchClient(
            endpoint=secrets.azure_search_endpoint,
            index_name=secrets.search_index_name,
            credential=AzureKeyCredential(secrets.search_api_key),
        )

        self.semantic_config = settings.search_semantic_config


    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        top_k: int = 10,
        semantic_configuration: str | None = None,
        select_fields: list[str] | None = None,
        filters: str | None = None,
    ) -> list[dict]:
        """
        Execute a hybrid search combining:
        1. Full-text keyword search (BM25)
        2. Vector similarity search (HNSW cosine)
        3. Semantic reranking (Microsoft semantic ranker)
        
        Args:
            query_text: Natural language query for keyword + semantic
            query_vector: Pre-computed embedding vector
            top_k: Number of results to return
            semantic_configuration: Name of semantic config (defaults to settings)
            select_fields: Fields to include in results
            filters: OData filter expression (e.g., "user_id eq 'abc'")
        
        Returns:
            List of result dicts with score and reranker_score
        """
        sem_config = semantic_configuration or self.semantic_config

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="embedding",
        )

        try:
            results = await self.client.search(
                search_text=query_text,
                vector_queries=[vector_query],
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name=sem_config,
                query_caption=QueryCaptionType.EXTRACTIVE,
                query_answer=QueryAnswerType.EXTRACTIVE,
                select=select_fields,
                filter=filters,
                top=top_k,
            )

            documents = []
            async for result in results:
                doc = {}
                for field in (select_fields or []):
                    doc[field] = result.get(field)
                doc["@search.score"] = result.get("@search.score", 0)
                doc["@search.reranker_score"] = result.get(
                    "@search.reranker_score", 0
                )
                # Extract captions if available
                captions = result.get("@search.captions")
                if captions:
                    doc["caption"] = captions[0].text
                    doc["caption_highlights"] = captions[0].highlights
                documents.append(doc)

            logger.info(
                f"Hybrid search returned {len(documents)} results "
                f"for query: '{query_text[:50]}...'"
            )
            return documents

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def vector_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        select_fields: list[str] | None = None,
        filters: str | None = None,
    ) -> list[dict]:
        """Pure vector search (no keyword component)."""
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="embedding",
        )

        try:
            results = await self.client.search(
                search_text=None,
                vector_queries=[vector_query],
                select=select_fields,
                filter=filters,
                top=top_k,
            )

            documents = []
            async for result in results:
                doc = {}
                for field in (select_fields or []):
                    doc[field] = result.get(field)
                doc["@search.score"] = result.get("@search.score", 0)
                documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise

    async def close(self):
        """Close the async search client."""
        await self.client.close()