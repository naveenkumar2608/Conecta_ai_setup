# backend/app/agents/graph.py
import json
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.state import AgentState
from app.agents.supervisor import SupervisorAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.coaching_agent import CoachingInsightsAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.services.content_safety import ContentSafetyService

logger = logging.getLogger(__name__)


class RedisCheckpointer:
    """
    LangGraph checkpoint persistence using Azure Redis Cache.
    Stores graph state between invocations for multi-turn conversations.

    Replaces MemorySaver for production deployments where
    multiple Container Apps instances need shared state.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 3600  # 1 hour TTL for conversation state

    async def aget(self, config: dict) -> dict | None:
        """Load checkpoint from Redis."""
        thread_id = config.get("configurable", {}).get("thread_id", "")
        key = f"langgraph:checkpoint:{thread_id}"
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
        return None

    async def aput(self, config: dict, data: dict) -> None:
        """Save checkpoint to Redis."""
        thread_id = config.get("configurable", {}).get("thread_id", "")
        key = f"langgraph:checkpoint:{thread_id}"
        try:
            await self.redis.setex(key, self.ttl, json.dumps(data, default=str))
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    async def alist(self, config: dict) -> list:
        """List checkpoints (not needed for basic usage)."""
        return []


class CoachingGraphBuilder:
    """Constructs the LangGraph multi-agent state machine."""

    def __init__(
        self,
        supervisor: SupervisorAgent,
        retrieval_agent: RetrievalAgent,
        coaching_agent: CoachingInsightsAgent,
        analytics_agent: AnalyticsAgent,
        recommendation_agent: RecommendationAgent,
        content_safety: ContentSafetyService,
        redis_client=None,
    ):
        self.supervisor = supervisor
        self.retrieval_agent = retrieval_agent
        self.coaching_agent = coaching_agent
        self.analytics_agent = analytics_agent
        self.recommendation_agent = recommendation_agent
        self.content_safety = content_safety
        self.redis_client = redis_client

    def build(self) -> StateGraph:
        """
        Graph topology:

        START → supervisor → (conditional routing)
                    ├─→ retrieval_agent → coaching_agent → safety_check → END
                    ├─→ coaching_agent → safety_check → END
                    ├─→ analytics_agent → safety_check → END
                    └─→ recommendation_agent (via retrieval first) → safety_check → END
        """
        workflow = StateGraph(AgentState)

        # ── Register nodes ──────────────────────────────────
        workflow.add_node("supervisor", self.supervisor.route)
        workflow.add_node("retrieval_agent", self.retrieval_agent.retrieve)
        workflow.add_node("coaching_agent", self.coaching_agent.generate_insights)
        workflow.add_node("analytics_agent", self.analytics_agent.compute_analytics)
        workflow.add_node("recommendation_agent", self.recommendation_agent.recommend)
        workflow.add_node("safety_check", self._safety_check)

        # ── Entry point ─────────────────────────────────────
        workflow.set_entry_point("supervisor")

        # ── Conditional routing from supervisor ─────────────
        workflow.add_conditional_edges(
            "supervisor",
            self._route_by_intent,
            {
                "retrieval_agent": "retrieval_agent",
                "coaching_agent": "coaching_agent",
                "analytics_agent": "analytics_agent",
                "recommendation_agent": "retrieval_agent",
            },
        )

        # ── Post-retrieval routing ──────────────────────────
        workflow.add_conditional_edges(
            "retrieval_agent",
            self._post_retrieval_routing,
            {
                "coaching_agent": "coaching_agent",
                "recommendation_agent": "recommendation_agent",
            },
        )

        # ── Terminal agents → safety check ──────────────────
        workflow.add_edge("coaching_agent", "safety_check")
        workflow.add_edge("analytics_agent", "safety_check")
        workflow.add_edge("recommendation_agent", "safety_check")

        # ── Safety check → END ──────────────────────────────
        workflow.add_edge("safety_check", END)

        # ── Checkpointer: Redis for production, Memory for dev ──
        if self.redis_client:
            checkpointer = RedisCheckpointer(self.redis_client)
            logger.info("Using Redis checkpointer for LangGraph state")
        else:
            checkpointer = MemorySaver()
            logger.info("Using in-memory checkpointer (dev mode)")

        return workflow.compile(checkpointer=checkpointer)

    @staticmethod
    def _route_by_intent(state: AgentState) -> str:
        """Conditional edge: routes based on classified intent."""
        intent = state.get("intent", "unknown")
        mapping = {
            "retrieval": "retrieval_agent",
            "coaching_insights": "coaching_agent",
            "analytics": "analytics_agent",
            "recommendation": "recommendation_agent",
            "unknown": "coaching_agent",
        }
        return mapping.get(intent, "coaching_agent")

    @staticmethod
    def _post_retrieval_routing(state: AgentState) -> str:
        """After retrieval, route to the appropriate synthesis agent."""
        intent = state.get("intent", "retrieval")
        if intent == "recommendation":
            return "recommendation_agent"
        return "coaching_agent"

    async def _safety_check(self, state: AgentState) -> AgentState:
        """Content safety node — PII filtering and guardrails."""
        if not state.get("requires_safety_check"):
            return state

        response = state.get("final_response", "")
        safety_result = await self.content_safety.analyze_text(response)

        if safety_result.is_flagged:
            return {
                **state,
                "final_response": (
                    "I'm unable to provide that response due to content "
                    "safety guidelines. Please rephrase your question."
                ),
                "error": f"Content flagged: {safety_result.categories}",
            }

        filtered_response = await self.content_safety.filter_pii(response)
        return {**state, "final_response": filtered_response}
