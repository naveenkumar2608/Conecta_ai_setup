# functions/shared/embedder.py
from openai import AsyncAzureOpenAI
import logging
import asyncio

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings using Azure OpenAI text-embedding-3-large.
    Handles batching and rate limiting.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str = "text-embedding-3-large",
        api_version: str = "2024-06-01",
        batch_size: int = 16,
        dimensions: int = 3072,
    ):
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self.deployment = deployment
        self.batch_size = batch_size
        self.dimensions = dimensions

    async def embed_chunks(
        self, chunks: list[dict]
    ) -> list[dict]:
        """
        Generate embeddings for all chunks.
        Processes in batches to respect rate limits.
        
        Returns chunks with 'embedding' field added.
        """
        embedded_chunks = []
        total_batches = (
            len(chunks) + self.batch_size - 1
        ) // self.batch_size

        for batch_idx in range(0, len(chunks), self.batch_size):
            batch = chunks[batch_idx : batch_idx + self.batch_size]
            texts = [chunk["chunk_text"] for chunk in batch]

            current_batch = batch_idx // self.batch_size + 1
            logger.info(
                f"Embedding batch {current_batch}/{total_batches} "
                f"({len(texts)} texts)"
            )

            try:
                response = await self.client.embeddings.create(
                    input=texts,
                    model=self.deployment,
                    dimensions=self.dimensions,
                )

                for i, embedding_data in enumerate(response.data):
                    chunk_with_embedding = {
                        **batch[i],
                        "embedding": embedding_data.embedding,
                    }
                    embedded_chunks.append(chunk_with_embedding)

            except Exception as e:
                logger.error(
                    f"Embedding batch {current_batch} failed: {e}"
                )
                # Retry with exponential backoff
                await asyncio.sleep(2 ** (batch_idx // self.batch_size))
                response = await self.client.embeddings.create(
                    input=texts,
                    model=self.deployment,
                    dimensions=self.dimensions,
                )
                for i, embedding_data in enumerate(response.data):
                    chunk_with_embedding = {
                        **batch[i],
                        "embedding": embedding_data.embedding,
                    }
                    embedded_chunks.append(chunk_with_embedding)

            # Rate limiting: brief pause between batches
            if batch_idx + self.batch_size < len(chunks):
                await asyncio.sleep(0.5)

        logger.info(
            f"Generated {len(embedded_chunks)} embeddings "
            f"(dim={self.dimensions})"
        )
        return embedded_chunks

    async def generate_single_embedding(
        self, text: str
    ) -> list[float]:
        """Generate embedding for a single text (for query-time use)."""
        response = await self.client.embeddings.create(
            input=[text],
            model=self.deployment,
            dimensions=self.dimensions,
        )
        return response.data[0].embedding
