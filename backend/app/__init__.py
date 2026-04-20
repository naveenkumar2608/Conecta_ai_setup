# backend/app/__init__.py
"""Abbott CONNECTA AI Coaching Analytics Platform — Backend Application."""
# backend/app/api/__init__.py
"""API layer — routes, middleware, and request/response handling."""
# backend/app/api/v1/__init__.py
"""API v1 routes."""
# backend/app/agents/__init__.py
"""
LangGraph multi-agent orchestration layer.
Contains the supervisor, specialized agents, and graph definition.
"""

from app.agents.graph import CoachingGraphBuilder
from app.agents.supervisor import SupervisorAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.coaching_agent import CoachingInsightsAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.recommendation_agent import RecommendationAgent

__all__ = [
    "CoachingGraphBuilder",
    "SupervisorAgent",
    "RetrievalAgent",
    "CoachingInsightsAgent",
    "AnalyticsAgent",
    "RecommendationAgent",
]
# backend/app/models/__init__.py
"""Data models — Pydantic, SQLAlchemy, and search index schemas."""
# functions/shared/__init__.py
"""Shared modules for Azure Functions ingestion pipeline."""
