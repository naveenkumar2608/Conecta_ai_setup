# backend/app/agents/supervisor.py
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService


SUPERVISOR_SYSTEM_PROMPT = """You are the CONNECTA Coaching Platform supervisor.
Your job is to classify the user's intent and route to the correct specialist agent.

Classification rules:
- "retrieval": User asks about specific data, documents, uploaded CSV content, 
  CONNECTA docs, historical coaching records.
- "coaching_insights": User wants coaching analysis, performance insights, 
  coaching summaries, or feedback interpretations.
- "analytics": User asks for KPIs, metrics, aggregated statistics, trends, 
  comparisons, or numerical computations.
- "recommendation": User asks for coaching recommendations, improvement 
  suggestions, or action plans aligned with CONNECTA methodology.
- "unknown": Cannot classify clearly.

Respond with ONLY one of: retrieval, coaching_insights, analytics, recommendation, unknown
"""


class SupervisorAgent:
    """
    Role: Intent classifier and query router.
    Input: Raw user message from AgentState.messages
    Output: Updates state.intent and state.next_agent
    Tools: Azure OpenAI GPT-4o (lightweight classification call)
    LangGraph node logic: First node in graph. Reads last user message,
                          classifies intent, sets routing destination.
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_SYSTEM_PROMPT),
            ("human", "Classify this query: {query}")
        ])

    async def route(self, state: AgentState) -> AgentState:
        """LangGraph node function — classifies and routes."""
        # Extract latest user message
        last_message = state["messages"][-1]
        user_query = last_message.content

        # Classify intent via LLM
        classification_chain = self.prompt | self.llm_service.get_chat_model(
            temperature=0.0,
            max_tokens=20
        )
        result = await classification_chain.ainvoke({"query": user_query})
        intent = result.content.strip().lower()

        # Validate intent
        valid_intents = {
            "retrieval", "coaching_insights", 
            "analytics", "recommendation", "unknown"
        }
        if intent not in valid_intents:
            intent = "unknown"

        # Map intent → next agent node name
        intent_to_agent = {
            "retrieval": "retrieval_agent",
            "coaching_insights": "coaching_agent",
            "analytics": "analytics_agent",
            "recommendation": "recommendation_agent",
            "unknown": "coaching_agent",  
        }

        return {
            **state,
            "intent": intent,
            "next_agent": intent_to_agent[intent],
            "search_query": user_query,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }
