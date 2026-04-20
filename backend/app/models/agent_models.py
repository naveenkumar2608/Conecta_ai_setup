# backend/app/models/agent_models.py
"""Pydantic models specific to agent interactions and internal state."""

from pydantic import BaseModel, Field
from typing import Literal


class IntentClassification(BaseModel):
    """Result of supervisor agent's intent classification."""
    intent: Literal[
        "retrieval",
        "coaching_insights",
        "analytics",
        "recommendation",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str | None = None


class RetrievedDocument(BaseModel):
    """A single document retrieved from Azure AI Search."""
    chunk_id: str
    content: str
    file_name: str
    domain_tags: list[str] = []
    score: float = 0.0
    reranker_score: float = 0.0
    row_start: int | None = None
    row_end: int | None = None


class AgentResponse(BaseModel):
    """Standard response format from any agent node."""
    agent_name: str
    response_text: str
    sources: list[RetrievedDocument] = []
    metadata: dict = {}
    error: str | None = None


class AnalyticsKPI(BaseModel):
    """A computed KPI result."""
    kpi_name: str
    value: float | str | None
    unit: str | None = None
    period: str | None = None
    details: dict = {}


class CoachingRecommendation(BaseModel):
    """A structured coaching recommendation."""
    title: str
    description: str
    priority: Literal["high", "medium", "low"]
    expected_outcome: str | None = None
    timeline: str | None = None
    supporting_data: list[str] = []
