# backend/app/dependencies.py
"""
Dependency injection container.
Initializes all services at startup and provides FastAPI Depends() functions.
"""

from fastapi import HTTPException, Request
from app.config import get_settings, get_secrets
from app.models.api_models import UserContext

from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService
from app.services.content_safety import ContentSafetyService
from app.services.translation_service import TranslationService
from app.services.analytics_service import AnalyticsService
from app.services.cache_service import CacheService
from app.services.chat_service import ChatService
from app.services.service_bus_client import ServiceBusPublisher
from app.repositories.postgres_repo import PostgresRepository
from app.repositories.blob_repo import BlobRepository
from app.repositories.search_repo import SearchRepository

from app.agents.supervisor import SupervisorAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.coaching_agent import CoachingInsightsAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.graph import CoachingGraphBuilder

import logging

logger = logging.getLogger(__name__)

# ── Global service instances ────────────────────────
_llm_service: LLMService | None = None
_embedding_service: EmbeddingService | None = None
_search_service: SearchService | None = None
_content_safety: ContentSafetyService | None = None
_translation_service: TranslationService | None = None
_analytics_service: AnalyticsService | None = None
_cache_service: CacheService | None = None
_chat_service: ChatService | None = None
_service_bus: ServiceBusPublisher | None = None
_postgres_repo: PostgresRepository | None = None
_blob_repo: BlobRepository | None = None
_search_repo: SearchRepository | None = None


async def init_services():
    """Initialize all service singletons at application startup."""
    global _llm_service, _embedding_service, _search_service
    global _content_safety, _translation_service, _analytics_service
    global _cache_service, _chat_service, _service_bus
    global _postgres_repo, _blob_repo, _search_repo

    logger.info("Initializing services...")

    secrets = get_secrets()

    # ── Initialize repositories ─────────────────────
    _postgres_repo = PostgresRepository(
        connection_string=secrets.postgres_connection_string
    )
    _blob_repo = BlobRepository()
    _search_repo = SearchRepository()

    # ── Initialize services ─────────────────────────
    _llm_service = LLMService()
    _embedding_service = EmbeddingService()
    _search_service = SearchService()
    _content_safety = ContentSafetyService()
    _translation_service = TranslationService()
    _cache_service = CacheService()
    _service_bus = ServiceBusPublisher()

    _analytics_service = AnalyticsService(
        db_session_factory=_postgres_repo.async_session
    )

    # ── Initialize agents ───────────────────────────
    supervisor = SupervisorAgent(llm_service=_llm_service)
    retrieval_agent = RetrievalAgent(
        search_service=_search_service,
        embedding_service=_embedding_service,
    )
    coaching_agent = CoachingInsightsAgent(llm_service=_llm_service)
    analytics_agent = AnalyticsAgent(
        llm_service=_llm_service,
        analytics_service=_analytics_service,
    )
    recommendation_agent = RecommendationAgent(llm_service=_llm_service)

    # ── Build LangGraph with Redis checkpointer ────
    graph_builder = CoachingGraphBuilder(
        supervisor=supervisor,
        retrieval_agent=retrieval_agent,
        coaching_agent=coaching_agent,
        analytics_agent=analytics_agent,
        recommendation_agent=recommendation_agent,
        content_safety=_content_safety,
        redis_client=_cache_service.client,  # Redis for state persistence
    )

    # ── Initialize chat service ─────────────────────
    _chat_service = ChatService(
        graph=graph_builder,
        cache_service=_cache_service,
        translation_service=_translation_service,
        postgres_repo=_postgres_repo,
    )

    logger.info("All services initialized successfully")


async def shutdown_services():
    """Gracefully shutdown all services."""
    logger.info("Shutting down services...")

    if _search_service:
        await _search_service.close()
    if _content_safety:
        await _content_safety.close()
    if _cache_service:
        await _cache_service.close()
    if _service_bus:
        await _service_bus.close()
    if _postgres_repo:
        await _postgres_repo.close()
    if _blob_repo:
        await _blob_repo.close()
    if _search_repo:
        await _search_repo.close()

    logger.info("All services shut down")


# ── FastAPI Depends() providers ─────────────────────

async def get_current_user(request: Request) -> UserContext:
    """Extract authenticated user from request state."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return UserContext(
        user_id=user_id,
        email=getattr(request.state, "user_email", ""),
        display_name=getattr(request.state, "user_name", ""),
        roles=getattr(request.state, "user_roles", []),
        region=None,
    )


def get_chat_service() -> ChatService:
    if _chat_service is None:
        raise HTTPException(status_code=503, detail="Chat service not initialized")
    return _chat_service


def get_postgres_repo() -> PostgresRepository:
    if _postgres_repo is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _postgres_repo


def get_blob_repo() -> BlobRepository:
    if _blob_repo is None:
        raise HTTPException(status_code=503, detail="Blob storage not initialized")
    return _blob_repo


def get_search_repo() -> SearchRepository:
    if _search_repo is None:
        raise HTTPException(status_code=503, detail="Search not initialized")
    return _search_repo


def get_cache_service() -> CacheService:
    if _cache_service is None:
        raise HTTPException(status_code=503, detail="Cache not initialized")
    return _cache_service


def get_analytics_service() -> AnalyticsService:
    if _analytics_service is None:
        raise HTTPException(status_code=503, detail="Analytics service not initialized")
    return _analytics_service


def get_service_bus() -> ServiceBusPublisher:
    if _service_bus is None:
        raise HTTPException(status_code=503, detail="Service bus not initialized")
    return _service_bus
