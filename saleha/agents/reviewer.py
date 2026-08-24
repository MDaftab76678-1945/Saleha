"""
Saleha Agents: Reviewer Agent (New -- pehle ye file khaali thi)

Ye agent Tester se aage jaata hai. Tester sirf check karta hai:
  - Syntax sahi hai?
  - Koi khatarnak command to nahi?
  - Kuch keywords maujood hain?

Lekin Tester ye nahi keh sakta: "ye code kaam to karega, lekin edge case
X me fail hoga" ya "variable naming bekar hai" ya "ye O(n^2) hai jab O(n)
me ho sakta tha". Ye judgement-based review hai -- isliye Reviewer khud LLM
se poochta hai, jaise koi senior developer PR review karta hai.

Design: BaseAgent se inherit karta hai (jaisa Coder karta hai), taaki wahi
Ollama connection aur SmartRouter use ho jo already kaam kar raha hai.
"""

import sys
import os
import re
from dataclasses import dataclass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from saleha.agents.base_agent import BaseAgent, AgentResponse


@dataclass
class ReviewResult:
    approved: bool
    feedback: str
    model_used: str = ""


class ReviewerAgent(BaseAgent):
    def __init__(self, model: str = "auto"):
        super().__init__(role="Reviewer", model=model)

    def review_code(self, task: str, code: str) -> ReviewResult:
        """
        Code ko ek senior-developer nazariye se review karta hai. Agar koi
        real problem mile (bug, edge case, bad practice), to approved=False
        aur feedback me kya theek karna hai wo milta hai -- ye feedback
        seedha Coder ke agle attempt ko diya ja sakta hai, self-healing
        loop ki tarah.
        """
        prompt = f"""आप एक अनुभवी Python code reviewer हैं। नीचे दिए गए कोड की समीक्षा करें।

टास्क: {task}

कोड:
```python
{code}
```

निर्देश:
- अगर कोड सही है और कोई गंभीर समस्या नहीं है, तो पहली लाइन में केवल लिखें: APPROVED
- अगर कोई bug, edge case, या स्पष्ट improvement है, तो पहली लाइन में लिखें: NEEDS_WORK
  उसके बाद संक्षेप में बताएं क्या सुधारना है (2-3 lines, code मत लिखें, सिर्फ feedback)।

केवल APPROVED या NEEDS_WORK से शुरू करें, कुछ और नहीं।
"""
        response: AgentResponse = self.think(prompt)

        if not response.success:
            # SECURITY: fail-closed. Pehle LLM error par approved=True milta tha
            # -- matlab Ollama down hone par bina review ke code "approve" ho
            # jaata tha. Ab review unavailable = NOT approved, jab tak operator
            # explicitly SALEHA_REVIEW_OFFLINE_PASS=1 se legacy behavior na
            # chunne (offline dev convenience ke liye escape hatch).
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

        # NEEDS_WORK ya kuch bhi unclear response -- safe default: feedback ke saath pass on
        feedback = content
        if content.upper().startswith("NEEDS_WORK"):
            feedback = "\n".join(content.split("\n")[1:]).strip()

        return ReviewResult(approved=False, feedback=feedback, model_used=response.model_used)


if __name__ == "__main__":
    print("=" * 70)
    print("👀 SALEHA REVIEWER AGENT TEST")
    print("=" * 70)
    print("Note: is test ke liye Ollama chalu hona chahiye.")

    reviewer = ReviewerAgent(model="qwen2.5-coder:1.5b")

    task = "Create a function to divide two numbers"
    code_with_bug = """def divide(a, b):
    return a / b
"""

    result = reviewer.review_code(task, code_with_bug)
    print(f"\nApproved: {result.approved}")
    print(f"Feedback: {result.feedback}")
    print(f"Model used: {result.model_used}")