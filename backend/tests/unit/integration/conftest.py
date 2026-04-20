# backend/tests/conftest.py
"""
Shared test fixtures for the CONNECTA backend test suite.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client():
    """FastAPI test client with mocked auth."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing agents."""
    service = MagicMock()
    mock_model = AsyncMock()
    mock_model.ainvoke = AsyncMock(
        return_value=MagicMock(content="test response")
    )
    service.get_chat_model.return_value = mock_model
    return service


@pytest.fixture
def mock_search_service():
    """Mock Azure AI Search service."""
    service = AsyncMock()
    service.hybrid_search = AsyncMock(return_value=[
        {
            "chunk_text": "Sample coaching data",
            "file_name": "test.csv",
            "domain_tags": ["coaching"],
            "@search.score": 0.95,
            "@search.reranker_score": 3.8,
        }
    ])
    return service


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = AsyncMock()
    service.generate_embedding = AsyncMock(
        return_value=[0.1] * 3072
    )
    return service


@pytest.fixture
def mock_cache_service():
    """Mock Redis cache service."""
    service = AsyncMock()
    service.get = AsyncMock(return_value=None)
    service.set = AsyncMock(return_value=True)
    service.delete = AsyncMock(return_value=True)
    return service


@pytest.fixture
def sample_user_context():
    """Sample authenticated user context."""
    from app.models.api_models import UserContext
    return UserContext(
        user_id="test-user-123",
        email="test@abbott.com",
        display_name="Test User",
        roles=["Coach"],
        region="North America",
    )