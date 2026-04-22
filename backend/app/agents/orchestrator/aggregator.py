from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import AgentState
from app.services.llm_service import LLMService


AGGREGATOR_PROMPT = """
You are an AI assistant responsible for generating the final response.

You are given outputs from multiple agents:
- analytics
- coaching insights
- recommendations

Your job:
- Combine all outputs into a single coherent response
- Avoid repetition
- Maintain logical flow
- Prioritize clarity and usefulness

Agent Outputs:
{agent_outputs}

User Query:
{query}

Generate a clean, natural, and structured final response.
"""


class Aggregator:

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", AGGREGATOR_PROMPT),
            ("human", "Generate final response")
        ])

    async def run(self, state: AgentState) -> AgentState:
        outputs = state.get("agent_outputs") or {}
        query = state.get("search_query", "")

        # If no outputs, fallback
        if not outputs:
            return {
                **state,
                "final_response": "No meaningful output could be generated.",
                "requires_safety_check": True
            }

        chain = self.prompt | self.llm_service.get_chat_model(
            temperature=0.3,
            max_tokens=1500
        )

        result = await chain.ainvoke({
            "agent_outputs": str(outputs),
            "query": query
        })

        return {
            **state,
            "final_response": result.content,
            "requires_safety_check": True
        }