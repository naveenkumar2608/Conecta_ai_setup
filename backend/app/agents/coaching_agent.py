# backend/app/agents/coaching_agent.py
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService


COACHING_SYSTEM_PROMPT = """You are an expert coaching analytics assistant for the 
Abbott CONNECTA platform. You help field teams understand their coaching data.

When provided with retrieved documents as context, synthesize them into:
1. Clear coaching insights
2. Performance summaries
3. Actionable feedback interpretations

If no documents are provided, use your coaching expertise to provide general 
guidance aligned with CONNECTA methodology.

Always be specific, data-driven when data is available, and actionable.
Format responses with clear headings and bullet points when appropriate.
"""


class CoachingInsightsAgent:
    """
    Role: Generate coaching insights, recommendations, summaries from
          retrieved context and/or direct analysis.
    Input: 
        - state.messages (conversation history)
        - state.retrieved_documents (from retrieval agent, may be None)
        - state.search_query (original user query)
    Output: state.coaching_response, state.final_response
    Tools: Azure OpenAI GPT-4o
    LangGraph node logic:
        1. Build prompt with retrieved context (if available)
        2. Call GPT-4o with full conversation context
        3. Generate coaching insight
        4. Set as final_response (or pass forward)
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def generate_insights(self, state: AgentState) -> AgentState:
        """LangGraph node function — generates coaching insights."""
        # Build context from retrieved documents
        context = ""
        if state.get("top_k_results"):
            context_parts = []
            for doc in state["top_k_results"]:
                context_parts.append(
                    f"[{doc.get('file_name', 'Unknown')}]: {doc['content']}"
                )
            context = (
                "\n\n--- Retrieved Context ---\n\n" 
                + "\n\n".join(context_parts)
            )

        # Build prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", COACHING_SYSTEM_PROMPT),
            ("system", f"Retrieved context:\n{context}" if context else 
                       "No specific documents retrieved. Use general expertise."),
            ("placeholder", "{chat_history}"),
            ("human", "{query}"),
        ])

        # Invoke LLM
        chain = prompt | self.llm_service.get_chat_model(
            temperature=0.3,
            max_tokens=2000
        )

        # Convert state messages to chat history format
        chat_history = state["messages"][:-1]  # exclude current query
        query = state["search_query"]

        result = await chain.ainvoke({
            "chat_history": chat_history,
            "query": query,
        })

        coaching_response = result.content

        return {
            **state,
            "coaching_response": coaching_response,
            "final_response": coaching_response,
            "requires_safety_check": True,
            "messages": state["messages"] + [
                AIMessage(
                    content=coaching_response, 
                    name="coaching_agent"
                )
            ],
        }