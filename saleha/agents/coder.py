"""
Saleha Agents: Coder Agent (Fixed Version)

Fix vs original: `generate_code` no longer hardcodes attempts=1. It now
accepts the attempt number it's being called as part of (from the
self-healing retry loop) and reports it accurately, so `CodeResult.attempts`
reflects reality instead of always showing "1 attempt" in the CLI.

NOTE: I don't have the full current self_healing.py / orchestrator.py from
the transcript, so I can't rewire the retry loop itself here. What this file
does: (a) fixes the attempts field to actually be threaded through instead
of hardcoded, and (b) keeps the same _extract_code robustness fix that was
already in place. When you wire this into your orchestrator, pass the
current attempt number into generate_code() -- see the __main__ demo below
for the expected call pattern.
"""

import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from saleha.agents.base_agent import BaseAgent, AgentResponse


class CodeResult:
    def __init__(self, success: bool, code: str, error: str = "", attempts: int = 1, model_used: str = ""):
        self.success = success
        self.code = code
        self.error = error
        self.attempts = attempts  # now actually set by caller, not hardcoded
        self.model_used = model_used  # real model name (e.g. "qwen3.5:0.8b"), not "auto"


class CoderAgent(BaseAgent):
    # C2: multi-language support -- pehle prompts Hindi/Python-only the,
    # JS/Go/Rust codegen quality untested thi. Task se language detect karke
    # language-specific rules inject hote hain.
    LANGUAGE_KEYWORDS = {
        "typescript": ("typescript", " ts ", "tsx", "type-safe"),
        "javascript": ("javascript", " js ", "jsx", "node.js", "nodejs"),
        "go": (" golang", "go lang", "goroutine", "go routine"),
        "rust": ("rust", "cargo", "ownership"),
        "java": ("java ", "jvm", "spring"),
        "bash": ("bash", "shell script", "zsh"),
    }

    LANGUAGE_RULES = {
        "python": "Standard library `unittest` use karo. Full type hints do.",
        "typescript": (
            "Use strict TypeScript with explicit types/interfaces. "
            "Prefer async/await. Export via ES modules. No `any` types."
        ),
        "javascript": (
            "Modern ES2022+ JavaScript (CommonJS or ESM consistent rakho). "
            "JSDoc comments for public functions. Prefer async/await."
        ),
        "go": (
            "Idiomatic Go: error values return karo (panic nahi), "
            "`if err != nil` pattern, context.Context for cancellation, "
            "table-driven tests with `testing` package."
        ),
        "rust": (
            "Idiomatic Rust: Result<T, E> for fallible ops, ownership/borrow "
            "respect karo, `#[cfg(test)]` mod tests with assert! macros."
        ),
        "java": "Modern Java (17+): records where apt, streams for collections, JUnit 5 tests.",
        "bash": "POSIX-safe bash: set -euo pipefail, functions, quotes on all expansions.",
    }

    def __init__(self, model: str = "auto", max_attempts: int = 3):
        super().__init__(role="Coder", model=model)
        self.max_attempts = max_attempts

    @classmethod
    def detect_language(cls, task: str) -> str:
        t = f" {task.lower()} "
        for lang, keywords in cls.LANGUAGE_KEYWORDS.items():
            if any(kw in t for kw in keywords):
                return lang
        return "python"

    def generate_code(self, task: str, plan: str = "", attempt: int = 1,
                      complexity_score: float = 0.0, language: str = "auto",
                      on_token=None) -> CodeResult:
        """
        `attempt` = which try this is within the self-healing retry loop
        (1-indexed). The orchestrator/self-healing engine should pass this
        in on each retry so the final CodeResult reports the real count.

        `complexity_score` Planner ke MathLogicEngine se aata hai aur
        SmartRouter ko pass hota hai -- taaki task-complexity ke hisaab se
        sahi model tier chune (chhota script -> fast model, bada system ->
        flagship model).

        `language="auto"`: task text se language detect hoti hai (C2) aur
        prompt me language-specific rules inject hote hain.

        `on_token`: diya jaye to STREAMING generation (v1.2 `--stream`) --
        har token chunk callback ko milta hai.
        """
        if language == "auto":
            language = self.detect_language(task)
        lang_rules = self.LANGUAGE_RULES.get(language, self.LANGUAGE_RULES["python"])
        fence_lang = {"javascript": "javascript", "typescript": "typescript",
                      "go": "go", "rust": "rust", "java": "java", "bash": "bash",
                      "python": "python"}.get(language, language)
        plan_section = f"\nयोजना: {plan}" if plan and len(plan) > 10 else ""

        prompt = f"""
आप एक विशेषज्ञ {language} डेवलपर हैं।
टास्क: {task}{plan_section}
नियम:
- केवल कोड दें। ```{fence_lang} और ``` का उपयोग करें।
- {lang_rules}
"""
        print(f"  [Coder] Generating code... (Attempt {attempt}/{self.max_attempts}, lang={language})")

        if on_token is not None:
            response: AgentResponse = self.think_stream(prompt, on_token=on_token,
                                                        complexity_score=complexity_score)
        else:
            response = self.think(prompt, complexity_score=complexity_score)

        if not response.success:
            return CodeResult(
                success=False, code="", error=response.error_message,
                attempts=attempt, model_used=response.model_used,
            )

        code = self._extract_code(response.content)
        if not code:
            return CodeResult(
                success=False,
                code="",
                error="Model returned no extractable code.",
                attempts=attempt,
                model_used=response.model_used,
            )

        return CodeResult(success=True, code=code, error="", attempts=attempt, model_used=response.model_used)

    def generate_tests(self, code: str, goal: str = "", complexity_score: float = 0.0) -> CodeResult:
        """Given solution code ke liye unittest suite generate karta hai
        (--tests mode). Same extraction pipeline reuse karta hai."""
        prompt = f"""
आप एक विशेषज्ञ QA इंजीनियर हैं।
नीचे दिए गए कोड के लिए Python `unittest` टेस्ट सूट लिखें।
लक्ष्य: {goal}

कोड:
```python
{code}
```

नियम:
1. Standard library `unittest` ही use करें।
2. Normal paths + boundary/edge cases cover करें।
3. केवल टेस्ट कोड दें, ```python और ``` block में।
4. कोई `unittest.main()` call न करें।
"""
        print("  [Coder] Generating test suite...")
        response: AgentResponse = self.think(prompt, complexity_score=min(complexity_score, 5.0))

        if not response.success:
            return CodeResult(success=False, code="", error=response.error_message,
                              attempts=1, model_used=response.model_used)

        extracted = self._extract_code(response.content)
        if not extracted or "def test" not in extracted.replace(" ", ""):
            return CodeResult(success=False, code="", error="No runnable tests found in model output.",
                              attempts=1, model_used=response.model_used)

        return CodeResult(success=True, code=extracted, error="", attempts=1, model_used=response.model_used)

    def _extract_code(self, response: str) -> str:
        """
        Robust extraction:
        1. Try ```python ... ```
        2. Try ``` ... ```
        3. Fallback: return raw text (lets the Tester catch syntax errors,
           prevents the "empty code" retry loop the original had)
        """
        if not response:
            return ""

        match = re.search(r"```python\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        return response.strip()


if __name__ == "__main__":
    # Demonstrates the fixed attempts-tracking contract. This will fail to
    # actually run end-to-end without base_agent.py / self_healing.py
    # present, but shows how the orchestrator should call generate_code
    # across retries so CodeResult.attempts is accurate.
    print("CoderAgent fixed-version contract demo (attempts is now real, not hardcoded):")
    print("  coder.generate_code(task, plan, attempt=1)  # first try")
    print("  coder.generate_code(task, plan, attempt=2)  # retry after failure")
    print("  -> result.attempts will correctly show 2, not always 1")