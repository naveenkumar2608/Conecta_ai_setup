from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService


RECOMMENDATION_SYSTEM_PROMPT = """You are the CONNECTA coaching recommendation engine.

Based on available data:
- Retrieved documents (if any)
- Analytics insights (if any)

Your task:
1. Provide specific, actionable coaching recommendations
2. Align suggestions with CONNECTA framework principles
3. Prioritize recommendations by impact
4. Be concise but practical

Structure your response as:
- Priority Recommendations
- Supporting Actions
- Expected Outcomes
- Timeline
"""


class RecommendationAgent:
    """
    Role: Generate coaching recommendations.

    Input:
        - state.search_query
        - state.top_k_results (from retrieval)
        - state.analytics_result (from analytics)

    Output:
        - state.agent_outputs["recommendation"]
        - state.final_response (temporary, aggregator will override)
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def recommend(self, state: AgentState) -> AgentState:
        query = state.get("search_query", "")

        # ─────────────────────────────────────────────
        # 1. Collect Context
        # ─────────────────────────────────────────────
        context_parts = []

        # Retrieval context (documents + structured data)
        if state.get("top_k_results"):
            for doc in state["top_k_results"]:
                content = doc.get("content", "")
                source = doc.get("source", "unknown")
                context_parts.append(f"[Source: {source}] {content}")

        # Analytics context
        if state.get("analytics_result"):
            context_parts.append(
                f"[Analytics Data]\n{str(state['analytics_result'])}"
            )

        context = (
            "\n\n".join(context_parts)
            if context_parts
            else "No specific data available. Provide general recommendations."
        )

        # ─────────────────────────────────────────────
        # 2. Build Prompt
        # ─────────────────────────────────────────────
        prompt = ChatPromptTemplate.from_messages([
            ("system", RECOMMENDATION_SYSTEM_PROMPT),
            ("human",
             "User request: {query}\n\n"
             "Available context:\n{context}\n\n"
             "Generate recommendations.")
        ])

        # ─────────────────────────────────────────────
        # 3. LLM Call
        # ─────────────────────────────────────────────
        chain = prompt | self.llm_service.get_chat_model(
            temperature=0.4,
            max_tokens=1500
        )

        result = await chain.ainvoke({
            "query": query,
            "context": context,
        })

        recommendation_text = result.content

        # ─────────────────────────────────────────────
        # 4. Store Output
        # ─────────────────────────────────────────────
        agent_outputs = state.get("agent_outputs") or {}
        agent_outputs["recommendation"] = recommendation_text

        return {
            **state,
            "recommendation": recommendation_text,  # keep existing
            "agent_outputs": agent_outputs,         # NEW
            "final_response": recommendation_text,  # temporary
            "requires_safety_check": True,
            "messages": state["messages"] + [
                AIMessage(
                    content=recommendation_text,
                    name="recommendation_agent"
                )
            ],
        }