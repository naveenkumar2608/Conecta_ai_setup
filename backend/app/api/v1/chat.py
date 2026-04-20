# backend/app/api/v1/chat.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.models.api_models import (
    ChatRequest, ChatResponse, StreamChatRequest
)
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service, get_current_user
from app.models.api_models import UserContext
import json

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: UserContext = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Main chat endpoint — routes through LangGraph multi-agent system.
    
    Flow:
    1. Validate request & user context
    2. Check Redis cache for recent identical queries
    3. Translate input if non-English
    4. Invoke LangGraph pipeline
    5. Cache response
    6. Store conversation in PostgreSQL
    7. Return response
    """
    try:
        response = await chat_service.process_chat(
            user_id=user.user_id,
            session_id=request.session_id,
            message=request.message,
            language=request.language or "en",
        )
        return ChatResponse(
            session_id=response.session_id,
            message=response.message,
            intent=response.intent,
            sources=response.sources,
            metadata=response.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    request: StreamChatRequest,
    user: UserContext = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Server-Sent Events streaming endpoint for real-time responses."""
    
    async def event_generator():
        async for chunk in chat_service.process_chat_stream(
            user_id=user.user_id,
            session_id=request.session_id,
            message=request.message,
            language=request.language or "en",
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
