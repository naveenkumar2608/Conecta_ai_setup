from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService
import json


VALID_AGENTS = [
    "retrieval_agent",
    "coaching_agent",
    "recommendation_agent",
]



PLANNER_PROMPT = """
You are an AI workflow planner.

Available agents:
- retrieval_agent → fetch documents/data
- coaching_agent → generate insights
- recommendation_agent → suggest improvements/actions

You will receive:

- user query
- detected intents

Your job:
- Create an execution plan (ordered list of agents)
- Use one or more agents as needed
- Order matters

Planning Rules:
- If recommendation is present → include retrieval_agent BEFORE recommendation_agent
- If coaching_insights is present → include coaching_agent
- If retrieval is present → include retrieval_agent
- Avoid duplicates
- Keep plan minimal and logical


Return JSON ONLY:
{
  "plan": ["agent1", "agent2", "..."]
}
"""


class PlannerAgent:
    """
    Role: Generate execution plan using multi-intent input.

    Input:
        - state.intent (List[str])
        - state.search_query

    Output:
        - state.execution_plan
        - state.current_step
        - state.agent_outputs
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_PROMPT),
            ("human", "Query: {query}\nIntents: {intents}")
        ])

    async def plan(self, state: AgentState) -> AgentState:
        query = state.get("search_query", "")
        intents = state.get("intent", [])

        # ─────────────────────────────────────────────
        # LLM Planning
        # ─────────────────────────────────────────────
        chain = self.prompt | self.llm_service.get_chat_model(
            temperature=0.0,
            max_tokens=200
        )

        result = await chain.ainvoke({
            "query": query,
            "intents": intents
        })

        # ─────────────────────────────────────────────
        #  Parse LLM Output
        # ─────────────────────────────────────────────
        try:
            parsed = json.loads(result.content)
            plan = parsed.get("plan", [])
        except Exception:
            plan = []

        # ─────────────────────────────────────────────
        # VALIDATION (CRITICAL)
        # ─────────────────────────────────────────────

        # Keep only valid agents
        plan = [p for p in plan if p in VALID_AGENTS]

        # Remove duplicates while preserving order
        seen = set()
        plan = [x for x in plan if not (x in seen or seen.add(x))]

        # ─────────────────────────────────────────────
        # RULE ENFORCEMENT (SAFETY LAYER)
        # ─────────────────────────────────────────────

        # Ensure retrieval before recommendation
        if "recommendation_agent" in plan and "retrieval_agent" not in plan:
            plan.insert(0, "retrieval_agent")

        # Ensure at least one agent
        if not plan:
            plan = ["coaching_agent"]

        # Limit steps (prevent abuse)
        MAX_STEPS = 4
        plan = plan[:MAX_STEPS]

        # ─────────────────────────────────────────────
        # RETURN STATE
        # ─────────────────────────────────────────────
        return {
            **state,
            "execution_plan": plan,
            "current_step": 0,
            "agent_outputs": {}
        }