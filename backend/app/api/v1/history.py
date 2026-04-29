# backend/app/api/v1/history.py
from fastapi import APIRouter, Depends, Query
from app.models.api_models import (
    ConversationHistoryResponse, ConversationListResponse
)
from app.repositories.postgres_repo import PostgresRepository
from app.services.cache_service import CacheService
from app.dependencies import (
    get_postgres_repo, get_cache_service, get_current_user
)
from app.models.api_models import UserContext

router = APIRouter()


@router.get("/sessions", response_model=ConversationListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    postgres_repo: PostgresRepository = Depends(get_postgres_repo),
):
    """List all conversation sessions for the authenticated user."""
    sessions = await postgres_repo.list_user_sessions(
        user_id=user.user_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    total = await postgres_repo.count_user_sessions(user_id=user.user_id)
    
    return ConversationListResponse(
        sessions=sessions,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/sessions/{session_id}", 
    response_model=ConversationHistoryResponse
)
async def get_session_history(
    session_id: str,
    user: UserContext = Depends(get_current_user),
    postgres_repo: PostgresRepository = Depends(get_postgres_repo),
    cache_service: CacheService | None = Depends(get_cache_service),
):
    """
    Retrieve full conversation history for a session.
    Checks Redis cache first, falls back to PostgreSQL.
    """
    # Check cache
    cache_key = f"history:{user.user_id}:{session_id}"
    if cache_service:
        cached = await cache_service.get(cache_key)
        if cached:
            return ConversationHistoryResponse.model_validate_json(cached)

    # Fetch from DB
    messages = await postgres_repo.get_session_messages(
        session_id=session_id,
        user_id=user.user_id,
    )

    response = ConversationHistoryResponse(
        session_id=session_id,
        messages=messages,
    )

    # Cache for 5 minutes
    if cache_service:
        await cache_service.set(
            cache_key, response.model_dump_json(), ttl=300
        )

    return response


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: UserContext = Depends(get_current_user),
    postgres_repo: PostgresRepository = Depends(get_postgres_repo),
    cache_service: CacheService | None = Depends(get_cache_service),
):
    """Delete a conversation session and its history."""
    await postgres_repo.delete_session(
        session_id=session_id, user_id=user.user_id
    )
    if cache_service:
        await cache_service.delete(f"history:{user.user_id}:{session_id}")
    return {"status": "deleted", "session_id": session_id}
