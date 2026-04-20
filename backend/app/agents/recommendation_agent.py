# backend/app/agents/recommendation_agent.py
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService


RECOMMENDATION_SYSTEM_PROMPT = """You are the CONNECTA coaching recommendation engine.
Based on retrieved coaching data, historical patterns, and CONNECTA methodology:

1. Provide specific, actionable coaching recommendations
2. Align suggestions with CONNECTA framework principles
3. Prioritize recommendations by impact
4. Include specific steps the coach/rep can take immediately

Structure your response as:
- **Priority Recommendations** (top 3)
- **Supporting Actions**
- **Expected Outcomes**
- **Timeline**
"""


class RecommendationAgent:
    """
    Role: Generate CONNECTA-aligned coaching recommendations.
    Input:
        - state.search_query
        - state.retrieved_documents (optional, from prior retrieval)
        - state.analytics_result (optional, from prior analytics)
    Output: state.recommendation, state.final_response
    Tools: Azure OpenAI GPT-4o
    LangGraph node logic:
        1. Aggregate context from retrieval + analytics (if available)
        2. Generate structured recommendations via GPT-4o
        3. Set final_response
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def recommend(self, state: AgentState) -> AgentState:
        """LangGraph node function — generates recommendations."""
        # Collect all available context
        context_parts = []

        if state.get("top_k_results"):
            for doc in state["top_k_results"]:
                context_parts.append(
                    f"[Data: {doc.get('file_name', '')}] {doc['content']}"
                )

        if state.get("analytics_result"):
            context_parts.append(
                f"[Analytics] {str(state['analytics_result'])}"
            )

        context = "\n\n".join(context_parts) if context_parts else \
            "No specific data available. Provide general CONNECTA recommendations."

        prompt = ChatPromptTemplate.from_messages([
            ("system", RECOMMENDATION_SYSTEM_PROMPT),
            ("human",
             "User request: {query}\n\n"
             "Available context:\n{context}\n\n"
             "Generate coaching recommendations."),
        ])

        chain = prompt | self.llm_service.get_chat_model(
            temperature=0.4, max_tokens=2000
        )

        result = await chain.ainvoke({
            "query": state["search_query"],
            "context": context,
        })

        return {
            **state,
            "recommendation": result.content,
            "final_response": result.content,
            "requires_safety_check": True,
            "messages": state["messages"] + [
                AIMessage(content=result.content, name="recommendation_agent")
            ],
        }
