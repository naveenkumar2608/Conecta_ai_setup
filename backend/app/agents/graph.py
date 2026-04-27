from langgraph.graph import StateGraph, END

from app.agents.state import AgentState

# Orchestrator
from app.agents.orchestrator.intent_agent import IntentAgent
from app.agents.orchestrator.planner_agent import PlannerAgent
from app.agents.orchestrator.executor import Executor
from app.agents.orchestrator.aggregator import Aggregator

# Agents
from app.agents.implementations.retrieval_agent import RetrievalAgent
from app.agents.implementations.coaching_agent import CoachingInsightsAgent
from app.agents.implementations.recommendation_agent import RecommendationAgent



class AgentGraph:

    def __init__(
        self,
        intent_agent: IntentAgent,
        planner_agent: PlannerAgent,
        executor: Executor,
        aggregator: Aggregator,
        retrieval_agent: RetrievalAgent,
        coaching_agent: CoachingInsightsAgent,
        recommendation_agent: RecommendationAgent,
    ):

        self.intent_agent = intent_agent
        self.planner_agent = planner_agent
        self.executor = executor
        self.aggregator = aggregator
        self.retrieval_agent = retrieval_agent
        self.coaching_agent = coaching_agent
        self.recommendation_agent = recommendation_agent


    def build(self):
        workflow = StateGraph(AgentState)

        # ─────────────────────────────────────────────
        # Nodes
        # ─────────────────────────────────────────────
        workflow.add_node("intent_agent", self.intent_agent.classify)
        workflow.add_node("planner_agent", self.planner_agent.plan)
        workflow.add_node("executor", self.executor.run)
        workflow.add_node("aggregator", self.aggregator.run)

        # Agents
        workflow.add_node("retrieval_agent", self.retrieval_agent.retrieve)
        workflow.add_node("coaching_agent", self.coaching_agent.generate_insights)
        workflow.add_node("recommendation_agent", self.recommendation_agent.recommend)


        # ─────────────────────────────────────────────
        # Edges (Linear Start)
        # ─────────────────────────────────────────────
        workflow.set_entry_point("intent_agent")

        workflow.add_edge("intent_agent", "planner_agent")
        workflow.add_edge("planner_agent", "executor")

        # ─────────────────────────────────────────────
        # Dynamic Routing from Executor
        # ─────────────────────────────────────────────
        workflow.add_conditional_edges(
            "executor",
            lambda state: state.get("next_node"),
            {
                "retrieval_agent": "retrieval_agent",
                "coaching_agent": "coaching_agent",
                "recommendation_agent": "recommendation_agent",
                "aggregator": "aggregator",
            }

        )

        # ─────────────────────────────────────────────
        # Loop back to executor after each agent
        # ─────────────────────────────────────────────
        workflow.add_edge("retrieval_agent", "executor")

        workflow.add_edge("coaching_agent", "executor")
        workflow.add_edge("recommendation_agent", "executor")

        # ─────────────────────────────────────────────
        # Final Step
        # ─────────────────────────────────────────────
        workflow.add_edge("aggregator", END)

        return workflow.compile()