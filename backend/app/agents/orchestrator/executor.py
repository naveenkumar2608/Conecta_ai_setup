from app.agents.state import AgentState


MAX_STEPS = 4  # safety limit


class Executor:
    """
    Role: Execute agent plan step-by-step.

    Input:
        - state.execution_plan
        - state.current_step

    Output:
        - state.current_step (incremented)
        - state.next step decision (handled in graph)
    """

    async def run(self, state: AgentState) -> AgentState:
        plan = state.get("execution_plan")
        step = state.get("current_step")

        # ─────────────────────────────────────────────
        #  SAFETY CHECKS
        # ─────────────────────────────────────────────

        if not plan:
            return {
                **state,
                "error": "Execution plan missing",
                "final_response": "Something went wrong. Please try again.",
                "requires_safety_check": True,
            }

        if step is None:
            step = 0

        # Prevent infinite loops
        if step >= MAX_STEPS:
            return {
                **state,
                "error": "Max execution steps exceeded",
                "requires_safety_check": True,
            }

        # ─────────────────────────────────────────────
        #  CHECK IF PLAN COMPLETED
        # ─────────────────────────────────────────────

        if step >= len(plan):
            # Move to aggregator
            return {
                **state,
                "next_node": "aggregator"
            }

        # ─────────────────────────────────────────────
        #  EXECUTE NEXT AGENT
        # ─────────────────────────────────────────────

        next_agent = plan[step]

        return {
            **state,
            "current_step": step + 1,   # increment step
            "next_node": next_agent     # dynamic routing
        }