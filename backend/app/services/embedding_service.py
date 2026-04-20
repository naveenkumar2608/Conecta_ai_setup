# backend/app/services/embedding_service.py
from openai import AsyncAzureOpenAI
from app.config import get_settings, get_secrets
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
        secrets = get_secrets()
        self.client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=secrets.openai_api_key,
            api_version="2024-06-01",
        )
        self.deployment = settings.openai_embedding_deployment
        self.dimensions = settings.embedding_dimensions

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate a single embedding vector for a query string.
        Used at query-time by the Retrieval Agent.
        """
        try:
            response = await self.client.embeddings.create(
                input=[text],
                model=self.deployment,
                dimensions=self.dimensions,
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
                dimensions=self.dimensions,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise
