from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService
import json


INTENT_PROMPT = """
You are an intent classifier for an AI system.

Classify the user query into one or more of the following intents:

- retrieval
- coaching_insights
- recommendation

Rules:
- Multiple intents are allowed
- Be precise
- If unsure, return ["coaching_insights"]

Return JSON ONLY:
{
  "intents": ["intent1", "intent2"]
}
"""


VALID_INTENTS = {
    "retrieval",
    "coaching_insights",
    "recommendation",
}



class IntentAgent:
    """
    Role: Detect ALL intents (multi-intent capable)

    Output:
        state.intent -> List[str]
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", INTENT_PROMPT),
            ("human", "{query}")
        ])

    async def classify(self, state: AgentState) -> AgentState:
        query = state["messages"][-1].content

        chain = self.prompt | self.llm_service.get_chat_model(
            temperature=0.0,
            max_tokens=100
        )

        result = await chain.ainvoke({"query": query})

        # ─────────────────────────────────────────────
        #  Parse output
        # ─────────────────────────────────────────────
        try:
            parsed = json.loads(result.content)
            intents = parsed.get("intents", [])
        except Exception:
            intents = []

        # ─────────────────────────────────────────────
        #  Validate intents
        # ─────────────────────────────────────────────
        intents = [i for i in intents if i in VALID_INTENTS]

        if not intents:
            intents = ["coaching_insights"]

        return {
            **state,
            "intent": intents,  # LIST now
            "search_query": query
        }