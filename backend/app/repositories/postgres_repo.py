# backend/app/repositories/postgres_repo.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import text, select, delete, func
from app.models.db_models import (
    FileMetadata,
    IngestionLog,
    ConversationSession,
    ConversationMessage,
    CoachingAnalytics,
)
from app.models.api_models import MessageItem, SessionSummary
from datetime import datetime, timezone
import uuid
import json
import logging

logger = logging.getLogger(__name__)


class PostgresRepository:
    """
    PostgreSQL data access layer.
    Uses SQLAlchemy async ORM for type-safe queries.
    """

    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: PostgreSQL async connection string
                e.g., postgresql+asyncpg://user:pass@host:5432/db
        """
        # Convert standard postgres:// to async driver URL if needed
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        self.engine = create_async_engine(
            connection_string,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=False,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    # ──────────────────────────────────────────────
    # FILE METADATA OPERATIONS
    # ──────────────────────────────────────────────

    async def insert_file_metadata(
        self,
        upload_id: str,
        user_id: str,
        file_name: str,
        blob_url: str,
        blob_name: str,
        file_size_bytes: int,
        status: str,
        uploaded_at: datetime,
    ):
        """Insert a new file metadata record."""
        async with self.async_session() as session:
            record = FileMetadata(
                upload_id=uuid.UUID(upload_id),
                user_id=user_id,
                file_name=file_name,
                blob_url=blob_url,
                blob_name=blob_name,
                file_size_bytes=file_size_bytes,
                status=status,
                uploaded_at=uploaded_at,
            )
            session.add(record)
            await session.commit()
            logger.info(
                f"Inserted file_metadata: upload_id={upload_id}"
            )

    async def get_file_metadata(
        self, upload_id: str, user_id: str
    ) -> FileMetadata | None:
        """Retrieve file metadata by upload_id scoped to user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(FileMetadata).where(
                    FileMetadata.upload_id == uuid.UUID(upload_id),
                    FileMetadata.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def update_file_status(
        self,
        upload_id: str,
        status: str,
        **kwargs,
    ):
        """Update file metadata status and optional fields."""
        async with self.async_session() as session:
            result = await session.execute(
                select(FileMetadata).where(
                    FileMetadata.upload_id == uuid.UUID(upload_id)
                )
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = status
                for key, value in kwargs.items():
                    if hasattr(record, key) and value is not None:
                        setattr(record, key, value)
                record.updated_at = datetime.now(timezone.utc)
                await session.commit()

    # ──────────────────────────────────────────────
    # CONVERSATION OPERATIONS
    # ──────────────────────────────────────────────

    async def save_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        sources: list[dict] | None = None,
        metadata: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """
        Save a conversation message.
        Creates the session if it doesn't exist.
        """
        async with self.async_session() as session:
            # Ensure session exists
            sess_result = await session.execute(
                select(ConversationSession).where(
                    ConversationSession.session_id == uuid.UUID(session_id)
                )
            )
            conv_session = sess_result.scalar_one_or_none()

            if not conv_session:
                # Create new conversation session
                title = content[:100] if role == "user" else "New Conversation"
                conv_session = ConversationSession(
                    session_id=uuid.UUID(session_id),
                    user_id=user_id,
                    title=title,
                )
                session.add(conv_session)

            # Update session timestamp
            conv_session.updated_at = datetime.now(timezone.utc)

            # Create message
            message = ConversationMessage(
                session_id=uuid.UUID(session_id),
                user_id=user_id,
                role=role,
                content=content,
                intent=intent,
                sources=sources,
                msg_metadata=metadata,

                created_at=timestamp or datetime.now(timezone.utc),
            )
            session.add(message)
            await session.commit()

    async def get_session_messages(
        self,
        session_id: str,
        user_id: str,
    ) -> list[MessageItem]:
        """Retrieve all messages for a conversation session."""
        async with self.async_session() as session:
            result = await session.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == uuid.UUID(session_id),
                    ConversationMessage.user_id == user_id,
                )
                .order_by(ConversationMessage.created_at.asc())
            )
            messages = result.scalars().all()
            return [
                MessageItem(
                    message_id=msg.message_id,
                    role=msg.role,
                    content=msg.content,
                    intent=msg.intent,
                    sources=msg.sources,
                    created_at=msg.created_at,
                )
                for msg in messages
            ]

    async def list_user_sessions(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[SessionSummary]:
        """List conversation sessions for a user with pagination."""
        async with self.async_session() as session:
            # Get sessions with message count
            result = await session.execute(
                select(
                    ConversationSession,
                    func.count(ConversationMessage.message_id).label(
                        "message_count"
                    ),
                )
                .outerjoin(ConversationMessage)
                .where(
                    ConversationSession.user_id == user_id,
                    ConversationSession.is_active == True,
                )
                .group_by(ConversationSession.session_id)
                .order_by(ConversationSession.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = result.all()

            return [
                SessionSummary(
                    session_id=str(row[0].session_id),
                    title=row[0].title,
                    message_count=row[1],
                    created_at=row[0].created_at,
                    updated_at=row[0].updated_at,
                )
                for row in rows
            ]

    async def count_user_sessions(self, user_id: str) -> int:
        """Count total sessions for a user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(func.count(ConversationSession.session_id))
                .where(
                    ConversationSession.user_id == user_id,
                    ConversationSession.is_active == True,
                )
            )
            return result.scalar() or 0

    async def delete_session(
        self, session_id: str, user_id: str
    ):
        """Soft delete a conversation session."""
        async with self.async_session() as session:
            result = await session.execute(
                select(ConversationSession).where(
                    ConversationSession.session_id == uuid.UUID(session_id),
                    ConversationSession.user_id == user_id,
                )
            )
            conv_session = result.scalar_one_or_none()
            if conv_session:
                conv_session.is_active = False
                conv_session.updated_at = datetime.now(timezone.utc)
                await session.commit()

    # ──────────────────────────────────────────────
    # LIFECYCLE
    # ──────────────────────────────────────────────

    async def close(self):
        """Dispose of the engine and connection pool."""
        await self.engine.dispose()
