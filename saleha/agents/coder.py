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

import re

from saleha.agents.base_agent import BaseAgent, AgentResponse


class CodeResult:
    def __init__(
        self,
        success: bool,
        code: str,
        error: str = "",
        attempts: int = 1,
        model_used: str = "",
        language: str = "python",
    ):
        self.success = success
        self.code = code
        self.error = error
        self.attempts = attempts  # now actually set by caller, not hardcoded
        self.model_used = model_used  # real model name (e.g. "qwen3.5:4b"), not "auto"
        self.language = language


class CoderAgent(BaseAgent):
    LANGUAGE_KEYWORDS = {
        "typescript": ("typescript", " ts ", "tsx", "type-safe"),
        "javascript": ("javascript", " js ", "jsx", "node.js", "nodejs"),
        "go": (" golang", "go lang", "goroutine", "go routine"),
        "rust": ("rust", "cargo", "ownership"),
        "java": ("java ", "jvm", "spring"),
        "bash": ("bash", "shell script", "zsh"),
    }

    LANGUAGE_RULES = {
        "python": "Use standard library unittest with full type annotations.",
        "typescript": (
            "Use strict TypeScript with explicit types/interfaces. "
            "Prefer async/await. Export via ES modules. No `any` types."
        ),
        "javascript": (
            "Modern ES2022+ JavaScript (consistent CommonJS or ESM). "
            "JSDoc comments for public functions. Prefer async/await."
        ),
        "go": (
            "Idiomatic Go: return error values (do not panic), "
            "`if err != nil` pattern, context.Context for cancellation, "
            "table-driven tests with `testing` package."
        ),
        "rust": (
            "Idiomatic Rust: Result<T, E> for fallible ops, adhere to "
            "ownership/borrow rules, `#[cfg(test)]` mod tests with assert! macros."
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
        if language == "auto":
            language = self.detect_language(task)
        lang_rules = self.LANGUAGE_RULES.get(language, self.LANGUAGE_RULES["python"])
        fence_lang = {"javascript": "javascript", "typescript": "typescript",
                      "go": "go", "rust": "rust", "java": "java", "bash": "bash",
                      "python": "python"}.get(language, language)
        plan_section = f"\nPlan:\n{plan}" if plan and len(plan) > 10 else ""

        prompt = f"""You are an expert {language} developer.
Task: {task}{plan_section}
Rules:
- Provide only code wrapped in ```{fence_lang} and ``` fences.
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
                language=language,
            )

        code = self._extract_code(response.content)
        if not code:
            return CodeResult(
                success=False,
                code="",
                error="Model returned no extractable code.",
                attempts=attempt,
                model_used=response.model_used,
                language=language,
            )

        return CodeResult(
            success=True, code=code, error="", attempts=attempt,
            model_used=response.model_used, language=language,
        )

    def generate_tests(self, code: str, goal: str = "", complexity_score: float = 0.0, language: str = "python") -> CodeResult:
        """Generates a test suite for given solution code (--tests mode)."""
        fence_lang = {"javascript": "javascript", "typescript": "typescript",
                      "go": "go", "rust": "rust", "java": "java", "bash": "bash",
                      "python": "python"}.get(language, language)
        prompt = f"""You are an expert QA engineer.
Write a comprehensive test suite for the following {language} code.
Goal: {goal}

Code:
```{fence_lang}
{code}
```

Rules:
1. Cover happy paths, boundary conditions, and edge cases.
2. Provide only runnable test code inside ```{fence_lang} and ``` blocks.
3. No unnecessary conversational text.
"""
        print(f"  [Coder] Generating test suite... (lang={language})")
        response: AgentResponse = self.think(prompt, complexity_score=min(complexity_score, 5.0))

        if not response.success:
            return CodeResult(success=False, code="", error=response.error_message,
                              attempts=1, model_used=response.model_used, language=language)

        extracted = self._extract_code(response.content)
        if language == "python":
            has_test = bool(re.search(r"\b(?:async\s+)?def\s+test\w*\s*\(", extracted or ""))
        elif language in ("javascript", "typescript"):
            has_test = bool(re.search(r"\b(?:test|it|describe)\s*\(", extracted or ""))
        elif language == "go":
            has_test = bool(re.search(r"\bfunc\s+Test\w*\s*\(", extracted or ""))
        elif language == "rust":
            has_test = bool(re.search(r"#\[test\]", extracted or ""))
        else:
            has_test = bool(extracted and len(extracted.strip()) > 10)

        if not extracted or not has_test:
            return CodeResult(success=False, code="", error="No runnable tests found in model output.",
                              attempts=1, model_used=response.model_used, language=language)

        return CodeResult(success=True, code=extracted, error="", attempts=1,
                          model_used=response.model_used, language=language)

    def _extract_code(self, response: str) -> str:
        """
        Robust extraction:
        1. Extract code block matching markdown fences: ```lang ... ```
        2. Fallback: return raw text if no code fence found.
        """
        if not response:
            return ""

        # Match any fenced code block, stripping language identifier e.g. ```python\n
        match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?\s*\n?(.*?)\s*```", response, re.DOTALL)
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