# backend/app/services/embedding_service.py
from openai import AsyncAzureOpenAI
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Azure OpenAI Embedding service for query-time embedding generation.
    Uses text-embedding-3-large with 3072 dimensions.
    
    Note: The ingestion pipeline has its own EmbeddingGenerator in
    functions/shared/embedder.py — this service is for the FastAPI backend.
    """

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAzureOpenAI(
            azure_endpoint=settings.openai_embedding_endpoint,
            api_key=settings.openai_embedding_api_key,
            api_version="2024-06-01",
        )
        self.deployment = settings.openai_embedding_deployment


    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate a single embedding vector for a query string.
        Used at query-time by the Retrieval Agent.
        """
        try:
            response = await self.client.embeddings.create(
                input=[text],
                model=self.deployment,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def generate_batch_embeddings(
        self, texts: list[str]
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single call."""
        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=self.deployment,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise
