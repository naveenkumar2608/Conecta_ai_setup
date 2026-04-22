from __future__ import annotations
from typing import TypedDict, Annotated, Optional, Dict, Any, List, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):

    # ─────────────────────────────────────────────
    #  Conversation
    # ─────────────────────────────────────────────
    messages: Annotated[List[BaseMessage], add_messages]

    # ─────────────────────────────────────────────
    #  User Context
    # ─────────────────────────────────────────────
    user_id: str
    session_id: str
    language: str

    # ─────────────────────────────────────────────
    #  Intent (MULTI-INTENT SUPPORTED)
    # ─────────────────────────────────────────────
    intent: Optional[List[
        Literal[
            "retrieval",
            "coaching_insights",
            "analytics",
            "recommendation",
            "unknown",
        ]
    ]]

    # ─────────────────────────────────────────────
    #  Query Context
    # ─────────────────────────────────────────────
    search_query: Optional[str]
    top_k_results: Optional[List[Dict]]

    # ─────────────────────────────────────────────
    #  Orchestration (CORE)
    # ─────────────────────────────────────────────

    # Planner output (set after planner runs)
    execution_plan: Optional[List[str]]

    # Current step index in execution
    current_step: Optional[int]

    # Store outputs from all agents
    agent_outputs: Optional[Dict[str, Any]]

    # ─────────────────────────────────────────────
    #  Safety & Errors
    # ─────────────────────────────────────────────
    requires_safety_check: bool
    error: Optional[str]

    # ─────────────────────────────────────────────
    #  Final Output
    # ─────────────────────────────────────────────
    final_response: Optional[str]