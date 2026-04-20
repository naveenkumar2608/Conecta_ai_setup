# backend/app/repositories/__init__.py
"""
Repository layer — data access abstraction over Azure services.
Each repository encapsulates all operations for a specific data store.
"""

from app.repositories.postgres_repo import PostgresRepository
from app.repositories.blob_repo import BlobRepository
from app.repositories.search_repo import SearchRepository

__all__ = [
    "PostgresRepository",
    "BlobRepository",
    "SearchRepository",
]
