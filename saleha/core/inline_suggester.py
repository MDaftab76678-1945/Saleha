"""
Saleha Core: Real-Time Inline Code Suggestion Engine

Analyzes newly written code in real-time and generates instant inline
suggestions for security issues, syntax errors, and improvements.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class InlineSuggestion:
    line: int
    severity: str       # "error" | "warning" | "hint"
    message: str
    fix: str
    category: str       # "syntax" | "security" | "style" | "performance"

    def format(self) -> str:
        icon = {"error": "🔴", "warning": "🟡", "hint": "💡"}.get(self.severity, "ℹ️")
        return f"{icon} Line {self.line} [{self.category}]: {self.message}\n   Fix: {self.fix}"


class InlineSuggester:
    """Generates instant inline suggestions for code changes."""

    def analyze(self, content: str, file_ext: str = ".py") -> List[InlineSuggestion]:
        """Analyze file content and return inline suggestions."""
        suggestions: List[InlineSuggestion] = []
        if file_ext == ".py":
            suggestions.extend(self._check_python(content))
        return suggestions

    def _check_python(self, content: str) -> List[InlineSuggestion]:
        suggestions: List[InlineSuggestion] = []
        lines = content.splitlines()

        # 1. Syntax check
        try:
            ast.parse(content)
        except SyntaxError as e:
            suggestions.append(InlineSuggestion(
                line=e.lineno or 1, severity="error",
                message=f"Syntax Error: {e.msg}",
                fix="Fix the syntax error before continuing.",
                category="syntax"
            ))
            return suggestions  # No point checking further

        # 2. Quick pattern checks for real-time suggestions
        quick_checks: List[Tuple[str, int, str, str, str, str]] = [
            ("eval(", 0, "error", "security", "eval() is a code injection risk", "Use ast.literal_eval() for safe evaluation."),  # noqa
            ("exec(", 0, "error", "security", "exec() executes arbitrary code", "Avoid exec(). Use specific function calls instead."),  # noqa
            ("import *", 0, "warning", "style", "Wildcard import pollutes namespace", "Import specific names: from module import name1, name2"),  # noqa
            ("TODO", 0, "hint", "style", "TODO comment found", "Track in your issue tracker and resolve before release."),  # noqa
            ("FIXME", 0, "warning", "style", "FIXME marker in code", "This marks a known bug — fix before shipping."),  # noqa
            ("except:", 0, "warning", "style", "Bare except catches all exceptions", "Catch specific exceptions: except (ValueError, TypeError) as e:"),  # noqa
            ("print(", 0, "hint", "style", "print() in production code", "Use logging.info/debug() for structured logging."),  # noqa
            ("password = \"", 0, "error", "security", "Hardcoded password detected", "Use os.getenv('PASSWORD') or encrypted vault."),  # noqa
            ("secret = \"", 0, "error", "security", "Hardcoded secret detected", "Use environment variables or Saleha vault."),  # noqa
        ]

        for lineno, line in enumerate(lines, start=1):
            for pattern, _, severity, category, message, fix in quick_checks:
                if pattern in line:
                    suggestions.append(InlineSuggestion(
                        line=lineno, severity=severity,
                        message=message, fix=fix, category=category
                    ))
        return suggestions

    def has_errors(self, content: str, file_ext: str = ".py") -> bool:
        """Quick check: does content have any error-level issues?"""
        return any(s.severity == "error" for s in self.analyze(content, file_ext))


# Global instance
inline_suggester = InlineSuggester()

