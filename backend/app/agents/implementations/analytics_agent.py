from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService
from app.services.analytics_service import AnalyticsService


ANALYTICS_SYSTEM_PROMPT = """You are the CONNECTA analytics engine.

Given a user query about metrics, KPIs, or statistics:

1. Identify requested KPIs
2. Use provided analytics data
3. Generate a clear, structured answer
4. Include trends and insights if possible

Always present numbers clearly with context.
"""


class AnalyticsAgent:
    """
    Role: Compute KPIs and generate analytics insights.

    Input:
        - state.search_query
        - state.user_id

    Output:
        - state.agent_outputs["analytics"]
        - state.analytics_result (existing)
    """

    def __init__(
        self,
        llm_service: LLMService,
        analytics_service: AnalyticsService
    ):
        self.llm_service = llm_service
        self.analytics_service = analytics_service

    async def compute_analytics(self, state: AgentState) -> AgentState:
        query = state.get("search_query")

        if not query:
            return {
                **state,
                "error": "Query missing for analytics",
            }

        # ─────────────────────────────────────────────
        # 1. KPI Detection (LLM)
        # ─────────────────────────────────────────────
        kpi_prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Extract KPI names from the query. "
             "Return comma-separated values from:\n"
             "coaching_sessions_count, avg_session_score, "
             "completion_rate, top_performers, trend_data, region_breakdown."),
            ("human", "{query}"),
        ])

        kpi_chain = kpi_prompt | self.llm_service.get_chat_model(
            temperature=0.0,
            max_tokens=100
        )

        kpi_result = await kpi_chain.ainvoke({"query": query})

        requested_kpis = [
            k.strip() for k in kpi_result.content.split(",") if k.strip()
        ]

        # ─────────────────────────────────────────────
        # 2. Fetch Data from PostgreSQL
        # ─────────────────────────────────────────────
        analytics_data = {}

        for kpi in requested_kpis:
            try:
                result = await self.analytics_service.compute_kpi(
                    kpi_name=kpi,
                    user_id=state["user_id"],
                )
                analytics_data[kpi] = result
            except Exception:
                analytics_data[kpi] = {"error": "Failed to compute KPI"}

        # ─────────────────────────────────────────────
        # 3. Generate Natural Language Response
        # ─────────────────────────────────────────────
        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", ANALYTICS_SYSTEM_PROMPT),
            ("human",
             "User query: {query}\n\n"
             "Analytics data:\n{data}\n\n"
             "Generate a clear response."),
        ])

        answer_chain = answer_prompt | self.llm_service.get_chat_model(
            temperature=0.2,
            max_tokens=1200
        )

        answer = await answer_chain.ainvoke({
            "query": query,
            "data": str(analytics_data),
        })

        analytics_response = answer.content

        # ─────────────────────────────────────────────
        # 4. Store Output
        # ─────────────────────────────────────────────
        agent_outputs = state.get("agent_outputs") or {}
        agent_outputs["analytics"] = {
            "raw_data": analytics_data,
            "summary": analytics_response
        }

        return {
            **state,
            "analytics_result": analytics_data,   # keep existing
            "agent_outputs": agent_outputs,       # NEW
            "final_response": analytics_response, # temporary
            "requires_safety_check": True,
            "messages": state["messages"] + [
                AIMessage(
                    content=analytics_response,
                    name="analytics_agent"
                )
            ],
        }