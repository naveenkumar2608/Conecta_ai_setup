# backend/app/agents/analytics_agent.py
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService
from app.services.analytics_service import AnalyticsService


ANALYTICS_SYSTEM_PROMPT = """You are the CONNECTA analytics engine.
Given a user query about metrics, KPIs, or statistics, you will:

1. Determine which KPI or aggregation is requested
2. Use the provided analytics data to formulate a precise answer
3. Present numbers clearly with context and trends where available

Available KPIs:
- coaching_sessions_count: Total coaching sessions
- avg_session_score: Average coaching quality score
- completion_rate: Percentage of completed coaching plans  
- top_performers: Highest-scoring coaches/reps
- trend_data: Period-over-period comparisons
- region_breakdown: Performance by region

Always cite the data source and time period.
"""


class AnalyticsAgent:
    """
    Role: Perform aggregations and compute KPIs from PostgreSQL data.
    Input: 
        - state.search_query (user's analytics question)
        - state.messages (conversation context)
    Output: state.analytics_result, state.final_response
    Tools: 
        - PostgreSQL (via AnalyticsService — parameterized queries)
        - Azure OpenAI GPT-4o (for natural language answer generation)
    LangGraph node logic:
        1. Parse user query to identify requested KPI(s)
        2. Execute safe, parameterized SQL aggregations
        3. Format results into natural language with GPT-4o
        4. Set final_response
    """

    def __init__(
        self, 
        llm_service: LLMService, 
        analytics_service: AnalyticsService
    ):
        self.llm_service = llm_service
        self.analytics_service = analytics_service

    async def compute_analytics(self, state: AgentState) -> AgentState:
        """LangGraph node function — computes KPIs and analytics."""
        query = state["search_query"]

        # Step 1: Identify which KPIs to compute using LLM
        kpi_classifier_prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "Extract the KPI type from the user query. "
             "Respond with one or more of: coaching_sessions_count, "
             "avg_session_score, completion_rate, top_performers, "
             "trend_data, region_breakdown. Comma-separated."),
            ("human", "{query}"),
        ])

        classifier_chain = kpi_classifier_prompt | self.llm_service.get_chat_model(
            temperature=0.0, max_tokens=100
        )
        kpi_result = await classifier_chain.ainvoke({"query": query})
        requested_kpis = [
            k.strip() for k in kpi_result.content.split(",")
        ]

        # Step 2: Execute analytics queries
        analytics_data = {}
        for kpi in requested_kpis:
            try:
                result = await self.analytics_service.compute_kpi(
                    kpi_name=kpi,
                    user_id=state["user_id"],
                )
                analytics_data[kpi] = result
            except ValueError:
                analytics_data[kpi] = {"error": "Unknown KPI"}

        # Step 3: Generate natural language response
        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", ANALYTICS_SYSTEM_PROMPT),
            ("human", 
             "User asked: {query}\n\n"
             "Analytics data:\n{data}\n\n"
             "Provide a clear, formatted answer."),
        ])

        answer_chain = answer_prompt | self.llm_service.get_chat_model(
            temperature=0.2, max_tokens=1500
        )
        answer = await answer_chain.ainvoke({
            "query": query,
            "data": str(analytics_data),
        })

        return {
            **state,
            "analytics_result": analytics_data,
            "final_response": answer.content,
            "requires_safety_check": True,
            "messages": state["messages"] + [
                AIMessage(content=answer.content, name="analytics_agent")
            ],
        }
