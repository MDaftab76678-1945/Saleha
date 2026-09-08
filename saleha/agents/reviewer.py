"""
Saleha Agents: Reviewer Agent (New -- this file was previously empty)

This agent goes further than the Tester. The Tester only checks:
  - Is the syntax correct?
  - Is there any dangerous command?
  - Are certain keywords present?

But the Tester cannot say: "this code will run, but will fail on edge case
X" or "the variable naming is poor" or "this is O(n^2) when O(n) was
possible". That is judgement-based review -- so the Reviewer asks an LLM
directly, the way a senior developer would review a PR.

Design: inherits from BaseAgent (like the Coder does), so it reuses the
same Ollama connection and SmartRouter that already work.
"""

import os
from dataclasses import dataclass

from saleha.agents.base_agent import BaseAgent, AgentResponse


@dataclass
class ReviewResult:
    approved: bool
    feedback: str
    model_used: str = ""


class ReviewerAgent(BaseAgent):
    def __init__(self, model: str = "auto"):
        super().__init__(role="Reviewer", model=model)

    def review_code(self, task: str, code: str, language: str = "python") -> ReviewResult:
        """
        Reviews code from a senior developer perspective. Returns approved=True
        if clean, or approved=False with actionable feedback for the self-healing loop.
        """
        fence_lang = language.lower() if language else "python"
        prompt = f"""You are an experienced {language} code reviewer. Review the following code.

Task: {task}

Code:
```{fence_lang}
{code}
```

Instructions:
- If the code is correct, robust, and has no critical issues, write only 'APPROVED' on the first line.
- If there is a bug, edge case, or obvious defect, write 'NEEDS_WORK' on the first line.
  Then briefly explain what needs to be fixed (2-3 lines of feedback, do not write full code).

Begin your response with either APPROVED or NEEDS_WORK only.
"""
        response: AgentResponse = self.think(prompt)

        if not response.success:
            # SECURITY: fail-closed. Previously an LLM error returned
            # approved=True -- meaning code got "approved" with no review at
            # all whenever Ollama was down. Now a review that could not run
            # counts as NOT approved, unless the operator explicitly opts
            # into the legacy behavior via SALEHA_REVIEW_OFFLINE_PASS=1
            # (an escape hatch for offline dev convenience).
            if os.getenv("SALEHA_REVIEW_OFFLINE_PASS", "").strip() == "1":
                return ReviewResult(
                    approved=True,
                    feedback=f"Review skipped (LLM error: {response.error_message})",
                    model_used=response.model_used,
                )
            return ReviewResult(
                approved=False,
                feedback=(
                    f"Review could not be completed (LLM error: {response.error_message}). "
                    "Failing closed -- fix the model connection or set "
                    "SALEHA_REVIEW_OFFLINE_PASS=1 to explicitly allow unreviewed code."
                ),
                model_used=response.model_used,
            )

        content = response.content.strip()
        first_line = content.split("\n")[0].strip().upper()

        if "APPROVED" in first_line:
            return ReviewResult(approved=True, feedback="", model_used=response.model_used)

        # NEEDS_WORK or any unclear response -- safe default: pass through with feedback
        feedback = content
        if content.upper().startswith("NEEDS_WORK"):
            feedback = "\n".join(content.split("\n")[1:]).strip()

        return ReviewResult(approved=False, feedback=feedback, model_used=response.model_used)


if __name__ == "__main__":
    print("=" * 70)
    print("SALEHA REVIEWER AGENT TEST")
    print("=" * 70)
    print("Note: Ollama must be running for this test.")

    reviewer = ReviewerAgent(model="qwen2.5-coder:3b")

    task = "Create a function to divide two numbers"
    code_with_bug = """def divide(a, b):
    return a / b
"""

    result = reviewer.review_code(task, code_with_bug)
    print(f"\nApproved: {result.approved}")
    print(f"Feedback: {result.feedback}")
    print(f"Model used: {result.model_used}")