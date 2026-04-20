# backend/app/models/search_models.py
"""Schema definitions for Azure AI Search index."""

from pydantic import BaseModel
from datetime import datetime


class SearchDocument(BaseModel):
    """Represents a single document in the Azure AI Search index."""
    chunk_id: str
    chunk_text: str
    embedding: list[float] | None = None
    file_name: str
    upload_id: str
    user_id: str
    row_start: int
    row_end: int
    domain_tags: list[str] = []
    upload_time: datetime | None = None
    column_names: list[str] = []


class SearchQuery(BaseModel):
    """Parameters for a search query."""
    query_text: str
    query_vector: list[float] | None = None
    top_k: int = 10
    filters: str | None = None
    semantic_config: str = "connecta-semantic-config"
    select_fields: list[str] = [
        "chunk_text", "file_name", "domain_tags",
        "row_start", "row_end", "upload_time",
    ]


class SearchResult(BaseModel):
    """A single result from a search query."""
    chunk_id: str
    chunk_text: str
    file_name: str
    domain_tags: list[str] = []
    score: float = 0.0
    reranker_score: float = 0.0
    caption: str | None = None
    caption_highlights: str | None = None
