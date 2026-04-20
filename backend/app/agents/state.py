# backend/app/agents/state.py
from __future__ import annotations
from typing import TypedDict, Literal, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Shared state across all LangGraph nodes."""
    
    # Chat messages (accumulated via reducer)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # User context
    user_id: str
    session_id: str
    language: str  # ISO 639-1 code for translation
    
    # Routing
    intent: Literal[
        "retrieval", 
        "coaching_insights", 
        "analytics", 
        "recommendation", 
        "unknown"
    ] | None
    
    # Agent outputs
    retrieved_documents: list[dict] | None
    coaching_response: str | None
    analytics_result: dict | None
    recommendation: str | None
    
    # RAG context
    search_query: str | None
    top_k_results: list[dict] | None
    
    # Control flow
    next_agent: str | None
    requires_safety_check: bool
    iteration_count: int
    error: str | None
    
    # Final response
    final_response: str | None
