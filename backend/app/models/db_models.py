# 6.1 PostgreSQL Schema
# -- ============================================
# -- FILE METADATA TABLE
# -- ============================================
# CREATE TABLE file_metadata (
#     upload_id           UUID PRIMARY KEY,
#     user_id             VARCHAR(255) NOT NULL,
#     file_name           VARCHAR(500) NOT NULL,
#     blob_url            TEXT NOT NULL,
#     blob_name           TEXT NOT NULL,
#     file_size_bytes     BIGINT,
#     status              VARCHAR(50) NOT NULL DEFAULT 'pending',
#         -- pending | processing | completed | failed
#     row_count           INTEGER,
#     chunk_count         INTEGER,
#     column_names        JSONB,               -- ["col1", "col2", ...]
#     domain_tags         JSONB,               -- ["coaching", "sales"]
#     error_message       TEXT,
#     uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#     processing_started_at  TIMESTAMPTZ,
#     processing_completed_at TIMESTAMPTZ,
#     updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
#     -- Indexes
#     CONSTRAINT chk_status CHECK (
#         status IN ('pending', 'processing', 'completed', 'failed')
#     )
# );

# CREATE INDEX idx_file_metadata_user_id ON file_metadata(user_id);
# CREATE INDEX idx_file_metadata_status ON file_metadata(status);
# CREATE INDEX idx_file_metadata_uploaded_at 
#     ON file_metadata(uploaded_at DESC);


# -- ============================================
# -- INGESTION LOGS TABLE
# -- ============================================
# CREATE TABLE ingestion_logs (
#     log_id              BIGSERIAL PRIMARY KEY,
#     upload_id           UUID NOT NULL REFERENCES file_metadata(upload_id)
#                             ON DELETE CASCADE,
#     status              VARCHAR(50) NOT NULL,
#     message             TEXT,
#     details             JSONB,               -- Additional structured info
#     created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# CREATE INDEX idx_ingestion_logs_upload_id 
#     ON ingestion_logs(upload_id);
# CREATE INDEX idx_ingestion_logs_created_at 
#     ON ingestion_logs(created_at DESC);


# -- ============================================
# -- CONVERSATION SESSIONS TABLE
# -- ============================================
# CREATE TABLE conversation_sessions (
#     session_id          UUID PRIMARY KEY,
#     user_id             VARCHAR(255) NOT NULL,
#     title               VARCHAR(500),        -- Auto-generated from first message
#     created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#     updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#     is_active           BOOLEAN DEFAULT TRUE
# );

# CREATE INDEX idx_sessions_user_id 
#     ON conversation_sessions(user_id, updated_at DESC);


# -- ============================================
# -- CONVERSATION MESSAGES TABLE
# -- ============================================
# CREATE TABLE conversation_messages (
#     message_id          BIGSERIAL PRIMARY KEY,
#     session_id          UUID NOT NULL REFERENCES conversation_sessions(session_id)
#                             ON DELETE CASCADE,
#     user_id             VARCHAR(255) NOT NULL,
#     role                VARCHAR(20) NOT NULL,   -- 'user' | 'assistant' | 'system'
#     content             TEXT NOT NULL,
#     intent              VARCHAR(50),            -- classified intent
#     sources             JSONB,                  -- referenced documents
#     metadata            JSONB,                  -- agent path, timing, etc.
#     created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# CREATE INDEX idx_messages_session_id 
#     ON conversation_messages(session_id, created_at ASC);
# CREATE INDEX idx_messages_user_id 
#     ON conversation_messages(user_id);


# -- ============================================
# -- COACHING ANALYTICS TABLE (for KPI queries)
# -- ============================================
# CREATE TABLE coaching_analytics (
#     id                  BIGSERIAL PRIMARY KEY,
#     upload_id           UUID REFERENCES file_metadata(upload_id),
#     user_id             VARCHAR(255) NOT NULL,
#     metric_name         VARCHAR(255) NOT NULL,
#     metric_value        DECIMAL(15, 4),
#     metric_unit         VARCHAR(50),
#     region              VARCHAR(100),
#     period_start        DATE,
#     period_end          DATE,
#     dimensions          JSONB,               -- {"coach": "...", "rep": "..."}
#     created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# CREATE INDEX idx_analytics_user_metric 
#     ON coaching_analytics(user_id, metric_name);
# CREATE INDEX idx_analytics_period 
#     ON coaching_analytics(period_start, period_end);
# CREATE INDEX idx_analytics_region 
#     ON coaching_analytics(region);





# backend/app/models/db_models.py
from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Boolean,
    DateTime, Numeric, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
import uuid

Base = declarative_base()


class FileMetadata(Base):
    __tablename__ = "file_metadata"

    upload_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id = Column(String(255), nullable=False, index=True)
    file_name = Column(String(500), nullable=False)
    blob_url = Column(Text, nullable=False)
    blob_name = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger)
    status = Column(
        String(50), nullable=False, default="pending"
    )
    row_count = Column(Integer)
    chunk_count = Column(Integer)
    column_names = Column(JSONB)
    domain_tags = Column(JSONB)
    error_message = Column(Text)
    uploaded_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    ingestion_logs = relationship(
        "IngestionLog", back_populates="file_metadata", 
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name="chk_status",
        ),
    )


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    upload_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("file_metadata.upload_id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(50), nullable=False)
    message = Column(Text)
    details = Column(JSONB)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    file_metadata = relationship(
        "FileMetadata", back_populates="ingestion_logs"
    )


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    session_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id = Column(String(255), nullable=False)
    title = Column(String(500))
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active = Column(Boolean, default=True)

    messages = relationship(
        "ConversationMessage", back_populates="session",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "idx_sessions_user_id", 
            "user_id", 
            updated_at.desc()
        ),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    message_id = Column(
        BigInteger, primary_key=True, autoincrement=True
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "conversation_sessions.session_id", 
            ondelete="CASCADE"
        ),
        nullable=False,
    )
    user_id = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(50))
    sources = Column(JSONB)
    metadata = Column(JSONB)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    session = relationship(
        "ConversationSession", back_populates="messages"
    )


class CoachingAnalytics(Base):
    __tablename__ = "coaching_analytics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    upload_id = Column(
        UUID(as_uuid=True),
        ForeignKey("file_metadata.upload_id"),
    )
    user_id = Column(String(255), nullable=False)
    metric_name = Column(String(255), nullable=False)
    metric_value = Column(Numeric(15, 4))
    metric_unit = Column(String(50))
    region = Column(String(100))
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    dimensions = Column(JSONB)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
