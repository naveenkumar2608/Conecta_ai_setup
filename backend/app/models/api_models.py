# backend/app/models/api_models.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Auth Models ──────────────────────────────────
class UserContext(BaseModel):
    user_id: str
    email: str
    display_name: str
    roles: list[str] = []
    region: str | None = None


class TokenValidationResponse(BaseModel):
    valid: bool
    user_id: str
    email: str
    name: str
    roles: list[str]
    expires_at: int


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    roles: list[str]
    region: str | None


# ── Chat Models ──────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None
    language: str = "en"


class StreamChatRequest(ChatRequest):
    pass


class ChatResponse(BaseModel):
    session_id: str
    message: str
    intent: str | None
    sources: list[dict] = []
    metadata: dict = {}


class ChatResult(BaseModel):
    session_id: str
    message: str
    intent: str | None
    sources: list[dict] = []
    metadata: dict = {}


# ── Upload Models ────────────────────────────────
class UploadResponse(BaseModel):
    upload_id: str
    file_name: str
    status: str
    message: str


class UploadStatusResponse(BaseModel):
    upload_id: str
    file_name: str
    status: str
    row_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ── History Models ───────────────────────────────
class MessageItem(BaseModel):
    message_id: int
    role: str
    content: str
    intent: str | None = None
    sources: list[dict] | None = None
    created_at: datetime


class SessionSummary(BaseModel):
    session_id: str
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationHistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageItem] = []


class ConversationListResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int
    page: int
    page_size: int
