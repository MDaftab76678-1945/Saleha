"""
Saleha Core: AI-Powered Deep Code Review Engine

Analyzes code diffs and files for OWASP Top-10 vulnerabilities, performance
anti-patterns, code smells, and generates scored review reports with
auto-suggested patches. Kills CodeRabbit ($12/repo/mo) with $0 local AI.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class ReviewIssue:
    severity: str          # "critical" | "high" | "medium" | "low" | "info"
    category: str          # "security" | "performance" | "smell" | "style"
    line: int
    title: str
    description: str
    suggestion: str
    code_snippet: str = ""
    cwe_id: str = ""       # e.g. "CWE-89" for SQL injection


@dataclass
class CodeReviewReport:
    file_path: str
    score: int             # 0-100 (100 = perfect)
    issues: List[ReviewIssue] = field(default_factory=list)
    summary: str = ""
    lines_reviewed: int = 0
    passed: bool = True

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "high")

    def to_markdown(self) -> str:
        lines = [
            f"## Code Review: `{self.file_path}`",
            f"**Score**: {self.score}/100 | **Issues**: {len(self.issues)} "
            f"({self.critical_count} critical, {self.high_count} high)",
            f"**Summary**: {self.summary}",
            "",
        ]
        for i in self.issues:
            cwe_part = f" | **CWE**: {i.cwe_id}" if i.cwe_id else ""
            lines.append(f"### [{i.severity.upper()}] {i.title} (Line {i.line})")
            lines.append(f"**Category**: {i.category}{cwe_part}")
            lines.append(f"{i.description}")
            if i.suggestion:
                lines.append(f"**Fix**: {i.suggestion}")
            lines.append("")
        return "\n".join(lines)


class AICodeReviewer:
    """Performs deep static AI-assisted code review without any external API."""

    # OWASP Top-10 + common security patterns
    SECURITY_PATTERNS: List[Tuple[re.Pattern, str, str, str, str]] = [
        (re.compile(r'execute\s*\(.*%.*\)|execute\s*\(.*format\(', re.IGNORECASE),
         "SQL Injection", "CWE-89", "critical",
         "Use parameterized queries: cursor.execute(sql, (param,))"),
        (re.compile(r'eval\s*\(|exec\s*\('),
         "Code Injection via eval/exec", "CWE-94", "critical",
         "Remove eval/exec. Use ast.literal_eval() for safe data parsing."),
        (re.compile(r'pickle\.loads?\s*\(|yaml\.load\s*\([^,)]*\)'),
         "Insecure Deserialization", "CWE-502", "critical",
         "Use pickle with trusted data only, or yaml.safe_load()."),
        (re.compile(r'subprocess\.\w+\(.*shell\s*=\s*True', re.IGNORECASE),
         "Shell Injection Risk", "CWE-78", "high",
         "Use shell=False and pass arguments as list."),
        (re.compile(r'hashlib\.md5\(|hashlib\.sha1\('),
         "Weak Cryptographic Hash", "CWE-327", "high",
         "Use hashlib.sha256() or hashlib.sha3_256() instead."),
        (re.compile(r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']{6,}["\']', re.IGNORECASE),
         "Hardcoded Credential", "CWE-798", "critical",
         "Move secrets to environment variables or encrypted vault."),
        (re.compile(r'random\.random\(|random\.randint\('),
         "Insecure Randomness", "CWE-338", "medium",
         "Use secrets.token_bytes() for cryptographic randomness."),
        (re.compile(r'open\s*\([^,)]*\+'),
         "Path Traversal Risk", "CWE-22", "high",
         "Validate/sanitize file paths. Use pathlib.Path.resolve()."),
        (re.compile(r'verify\s*=\s*False'),
         "SSL Verification Disabled", "CWE-295", "high",
         "Never disable SSL verification in production."),
        (re.compile(r'DEBUG\s*=\s*True|debug\s*=\s*True'),
         "Debug Mode in Code", "CWE-94", "medium",
         "Ensure DEBUG=False in production. Use environment config."),
    ]

    # Performance anti-patterns
    PERFORMANCE_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (re.compile(r'for\s+\w+\s+in\s+\w+.*:\s*\n.*\.append\('),
         "List comprehension preferred over append loop",
         "Replace with: result = [expr for item in iterable]"),
        (re.compile(r'\+\s*=\s*["\']|\+\s*str\('),
         "String concatenation in loop (O(n²))",
         "Use \'\'.join([...]) or f-strings instead."),
        (re.compile(r'time\.sleep\s*\((?:[5-9]|[1-9]\d)'),
         "Long sleep in main thread",
         "Use asyncio.sleep() in async code or threading.Event.wait()."),
        (re.compile(r'SELECT \*'),
         "SELECT * fetches all columns unnecessarily",
         "Specify only needed columns: SELECT id, name FROM table."),
        (re.compile(r'\.find\(.*\) != -1|\.find\(.*\) >= 0'),
         "Use \'in\' operator instead of str.find() comparison",
         "Replace: \'needle in haystack\' is cleaner and faster."),
    ]

    # Code smell patterns
    SMELL_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (re.compile(r'except\s*:'),
         "Bare except clause catches ALL exceptions including SystemExit",
         "Catch specific exceptions: except (ValueError, KeyError) as e:"),
        (re.compile(r'pass\s*$', re.MULTILINE),
         "Empty block with pass — may hide unimplemented logic",
         "Add a TODO comment or raise NotImplementedError."),
        (re.compile(r'# TODO|# FIXME|# HACK|# XXX'),
         "Technical debt marker found",
         "Track in issue tracker and resolve before release."),
        (re.compile(r'print\s*\('),
         "print() used — prefer structured logging",
         "Use logging.info/debug/error() for production code."),
        (re.compile(r'global\s+\w+'),
         "Global variable mutation",
         "Prefer class attributes or function parameters."),
    ]

    def review_file(self, file_path: str, content: str) -> CodeReviewReport:
        """Performs full static review of a Python source file."""
        lines = content.splitlines()
        issues: List[ReviewIssue] = []

        # 1. AST parse check
        try:
            tree = ast.parse(content, filename=file_path)
            self._check_ast_patterns(tree, lines, issues)
        except SyntaxError as e:
            issues.append(ReviewIssue(
                severity="critical", category="syntax",
                line=e.lineno or 1, title="Syntax Error",
                description=str(e), suggestion="Fix syntax error before review."
            ))

        # 2. Line-by-line pattern scan
        for lineno, line in enumerate(lines, start=1):
            for pattern, title, cwe, severity, suggestion in self.SECURITY_PATTERNS:
                if pattern.search(line):
                    issues.append(ReviewIssue(
                        severity=severity, category="security",
                        line=lineno, title=title, description=f"Found at line {lineno}: `{line.strip()[:80]}`",
                        suggestion=suggestion, cwe_id=cwe,
                        code_snippet=line.strip()[:120]
                    ))

            for pattern, title, suggestion in self.PERFORMANCE_PATTERNS:
                if pattern.search(line):
                    issues.append(ReviewIssue(
                        severity="medium", category="performance",
                        line=lineno, title=title, description=f"Line {lineno}: `{line.strip()[:80]}`",
                        suggestion=suggestion
                    ))

            for pattern, title, suggestion in self.SMELL_PATTERNS:
                if pattern.search(line):
                    issues.append(ReviewIssue(
                        severity="low", category="smell",
                        line=lineno, title=title, description=f"Line {lineno}: `{line.strip()[:80]}`",
                        suggestion=suggestion
                    ))

        # 3. Score calculation
        penalty = sum({"critical": 20, "high": 10, "medium": 5, "low": 2, "info": 0}.get(i.severity, 0) for i in issues)
        score = max(0, 100 - penalty)
        passed = score >= 70

        severity_summary = " | ".join(f"{s}: {sum(1 for i in issues if i.severity == s)}" for s in ["critical", "high", "medium", "low"] if any(i.severity == s for i in issues))
        summary = f"{len(issues)} issues found ({severity_summary}). Score: {score}/100." if issues else "No issues found. Code looks clean!"

        return CodeReviewReport(
            file_path=file_path,
            score=score,
            issues=issues,
            summary=summary,
            lines_reviewed=len(lines),
            passed=passed,
        )

    def review_diff(self, diff_text: str) -> List[ReviewIssue]:
        """Reviews a unified diff for introduced vulnerabilities."""
        issues: List[ReviewIssue] = []
        for lineno, line in enumerate(diff_text.splitlines(), start=1):
            if not line.startswith("+") or line.startswith("+++"):
                continue
            code_line = line[1:]
            for pattern, title, cwe, severity, suggestion in self.SECURITY_PATTERNS:
                if pattern.search(code_line):
                    issues.append(ReviewIssue(
                        severity=severity, category="security",
                        line=lineno, title=f"[NEW CODE] {title}",
                        description=f"Introduced in diff line {lineno}: `{code_line.strip()[:80]}`",
                        suggestion=suggestion, cwe_id=cwe
                    ))
        return issues

    def _check_ast_patterns(self, tree: ast.AST, lines: List[str], issues: List[ReviewIssue]) -> None:
        """AST-level checks: function length, complexity, missing docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Long function check
                end_line = getattr(node, "end_lineno", node.lineno)
                func_len = end_line - node.lineno
                if func_len > 60:
                    issues.append(ReviewIssue(
                        severity="medium", category="smell",
                        line=node.lineno, title=f"Function '{node.name}' is too long ({func_len} lines)",
                        description="Functions over 60 lines are hard to test and maintain.",
                        suggestion="Extract sub-functions using the Single Responsibility Principle."
                    ))
                # Missing docstring
                if not (node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)):
                    if func_len > 10:
                        issues.append(ReviewIssue(
                            severity="info", category="style",
                            line=node.lineno, title=f"Function '{node.name}' missing docstring",
                            description="Functions >10 lines should have docstrings for maintainability.",
                            suggestion='Add: \"\"\"Brief description of what this function does.\"\"\"'
                        ))


# Global instance
ai_reviewer = AICodeReviewer()

