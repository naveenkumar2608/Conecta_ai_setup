from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService


COACHING_SYSTEM_PROMPT = """You are an expert coaching analytics assistant for the CONNECTA platform.

You help field teams understand their coaching performance.

Your task:
1. Generate clear coaching insights
2. Summarize performance trends
3. Provide actionable interpretations

If data is available, be data-driven.
If not, provide general coaching guidance.

Keep responses structured, concise, and actionable.
"""


class CoachingInsightsAgent:
    """
    Role: Generate coaching insights.

    Input:
        - state.messages
        - state.search_query
        - state.top_k_results (retrieval output)

    Output:
        - state.agent_outputs["coaching"]
        - state.final_response (temporary)
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def generate_insights(self, state: AgentState) -> AgentState:
        query = state.get("search_query", "")
        messages = state.get("messages", [])

        # ─────────────────────────────────────────────
        # 1. Build Context
        # ─────────────────────────────────────────────
        context_parts = []

        # Retrieval context
        if state.get("top_k_results"):
            for doc in state["top_k_results"]:
                content = doc.get("content", "")
                source = doc.get("source", "unknown")
                context_parts.append(f"[Source: {source}] {content}")

        # Analytics context (optional enhancement)
        if state.get("analytics_result"):
            context_parts.append(
                f"[Analytics Data]\n{str(state['analytics_result'])}"
            )

        context = "\n\n".join(context_parts) if context_parts else ""

        # ─────────────────────────────────────────────
        # 2. Build Prompt
        # ─────────────────────────────────────────────
        prompt = ChatPromptTemplate.from_messages([
            ("system", COACHING_SYSTEM_PROMPT),
            ("system", f"Context:\n{context}" if context else 
                       "No external data provided."),
            ("placeholder", "{chat_history}"),
            ("human", "{query}"),
        ])

        # ─────────────────────────────────────────────
        # 3. LLM Call
        # ─────────────────────────────────────────────
        chain = prompt | self.llm_service.get_chat_model(
            temperature=0.3,
            max_tokens=1500
        )

        chat_history = messages[:-1] if len(messages) > 1 else []

        result = await chain.ainvoke({
            "chat_history": chat_history,
            "query": query,
        })

        coaching_response = result.content

        # ─────────────────────────────────────────────
        # 4. Store Output
        # ─────────────────────────────────────────────
        agent_outputs = state.get("agent_outputs") or {}
        agent_outputs["coaching"] = coaching_response

        return {
            **state,
            "coaching_response": coaching_response,   # keep existing
            "agent_outputs": agent_outputs,           # NEW
            "final_response": coaching_response,      # temporary
            "requires_safety_check": True,
            "messages": state["messages"] + [
                AIMessage(
                    content=coaching_response,
                    name="coaching_agent"
                )
            ],
        }