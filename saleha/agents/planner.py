"""
Saleha Agents: Planner Agent

Purpose: understand the user's goal, measure its complexity, and if needed
break it into small, manageable steps (a DAG).
"""

from typing import Optional

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.core.active_inference import active_inference_gate
from saleha.core.math_logic import MathLogicEngine


# ==============================================================================
# 1. Data structures
# ==============================================================================

class PlanResult:
    def __init__(self, success: bool, steps: list, recommendation: str, raw_response: str = "",
                 complexity_score: float = 0.0, clarifying_question: str = "",
                 uncertainty_reasons: Optional[list] = None):
        self.success = success
        self.steps = steps
        self.recommendation = recommendation
        self.raw_response = raw_response
        # The MathLogicEngine complexity score now travels through to the
        # router (it used to be computed and then discarded -- SmartRouter's
        # complexity tiers were effectively dead).
        self.complexity_score = complexity_score
        # Set when the goal was too vague to act on: recommendation becomes
        # NEEDS_CLARIFICATION and this carries the one question worth asking.
        self.clarifying_question = clarifying_question
        self.uncertainty_reasons = uncertainty_reasons or []

    @property
    def needs_clarification(self) -> bool:
        return self.recommendation == "NEEDS_CLARIFICATION"


# ==============================================================================
# 2. Core Logic
# ==============================================================================

class PlannerAgent(BaseAgent):
    def __init__(self, model: str = "qwen2.5-coder:3b"):
        # Initialise BaseAgent with the "Planner" role.
        super().__init__(role="Planner", model=model)
        self.math_engine = MathLogicEngine()

    def create_plan(self, user_goal: str, context_has_target: bool = False,
                    skip_clarity_check: bool = False) -> PlanResult:
        """
        Builds a plan for the user's goal.

        `context_has_target`: the caller already knows which file is being
        worked on (an open file, or a prior turn) -- so a bare "fix it" is
        valid.
        `skip_clarity_check`: bypass the gate (batch / non-interactive runs).
        """
        # 0. Is the goal clear enough to start?
        #
        # This is a separate axis from complexity. Measured: create_plan("fix
        # it") returned success=True and EXECUTE with complexity 0.0 -- without
        # naming a file, repo or bug. Being small and being clear are
        # different things; one question beats guessing at wrong code.
        if not skip_clarity_check:
            unc = active_inference_gate.assess(
                user_goal, context_has_target=context_has_target)
            if unc.should_ask:
                print(f"  [Planner] Goal too vague to act on "
                      f"(uncertainty {unc.score}). Asking instead of guessing.")
                return PlanResult(
                    success=False,
                    steps=[],
                    recommendation="NEEDS_CLARIFICATION",
                    raw_response=unc.question,
                    complexity_score=0.0,
                    clarifying_question=unc.question,
                    uncertainty_reasons=list(unc.reasons),
                )

        # 1. Check complexity first.
        complexity_result = self.math_engine.estimate_complexity(user_goal)

        # 2. Build the prompt based on complexity.
        if complexity_result.recommendation == "REQUIRES_APPROVAL":
            prompt = f"""
User goal: {user_goal}
Warning: this task is very large and risky (Complexity Score: {complexity_result.complexity_score}).
Instruction: do NOT execute this task now. Tell the user clearly that it must be broken into
small, specific pieces. Give only a clear warning and 2-3 suggestions for how to break it down.
Strict instruction: never repeat my instructions back.
"""
        elif complexity_result.recommendation == "BREAK_DOWN":
            prompt = f"""
User goal: {user_goal}
Complexity: medium/high (Score: {complexity_result.complexity_score}). Estimated files: {complexity_result.estimated_files}
Instruction: break this task into 3 to 5 small, logical, sequential steps.
Each step must be clear (for example: Step 1: create the file structure, Step 2: write the base code).
The output must be only a list of steps.
Strict instruction: never repeat my instructions back. Give only the list of steps.
"""
        else:
            prompt = f"""
User goal: {user_goal}
Complexity: low (Score: {complexity_result.complexity_score}).

Instruction:
This task can be executed directly.
Please state only how you will complete this task (in 1-2 sentences).
Strict instruction: never repeat my instructions back in your answer. Write only your plan.
Example: "I will write a Python function that adds two numbers."
"""

        # 3. BaseAgent
        print(f"  [Planner] Complexity Analysis: {complexity_result.recommendation} (Score: {complexity_result.complexity_score})")
        print("  [Planner] Requesting plan from local AI...")

        response: AgentResponse = self.think(prompt)

        if response.success:
            # Turn the steps into a plain list.
            steps = [line.strip() for line in response.content.split('\n') if line.strip()]
            return PlanResult(
                success=True,
                steps=steps,
                recommendation=complexity_result.recommendation,
                raw_response=response.content,
                complexity_score=complexity_result.complexity_score
            )
        else:
            return PlanResult(
                success=False,
                steps=[],
                recommendation="ERROR",
                raw_response=response.error_message,
                complexity_score=complexity_result.complexity_score
            )


# ==============================================================================
# 3. Testing
# ==============================================================================

if __name__ == "__main__":
    print("="*70)
    print("SALEHA PLANNER AGENT - LIVE TEST")
    print("="*70)

    planner = PlannerAgent(model="qwen2.5-coder:3b")

    test_goals = [
        "Create a simple Python script that prints hello world.",
        "Refactor the whole project: go through every file, make the database "
        "connections async, and write new tests.",
        "Create a new React component and integrate it into the main app."
    ]

    for i, goal in enumerate(test_goals, 1):
        print(f"\n[Test {i}] Goal: '{goal}'")
        print("-" * 70)

        result = planner.create_plan(goal)

        if result.success:
            print(f"Recommendation: {result.recommendation}")
            print("Plan Steps:")
            for step in result.steps[:5]:
                print(f"  -> {step}")
            if len(result.steps) > 5:
                print("  ... (more steps)")
        else:
            print(f"Failed: {result.raw_response}")
        print("-" * 70)
