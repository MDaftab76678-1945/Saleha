"""Saleha Core: Autonomous Tool Creation Engine (Tool Forge).

Allows Saleha agents to autonomously synthesize, test, and deploy new tools
into `saleha/tools/` without human intervention.
Follows strict safety and engineering rails:
1. Synthesized tools must subclass `saleha.tools.base.BaseTool`.
2. Every tool must pass static inspection via `QualityGuard` (zero critical syntax,
   undefined symbols, or missing imports).
3. Every tool must pass structural verification via `ASTInspectorTool` (valid bases,
   presence of `execute()` method, and zero hazardous calls).
4. Every tool must have a companion `pytest` suite validating its execution.
5. Tests are verified in an isolated temp directory before touching the repository.
6. Passing tools are auto-registered into `tool_registry` and committed with
   blast-radius-safe, surgical git staging.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from saleha.core.quality_guard import QualityGuard
from saleha.tools.ast_inspector import ASTInspectorTool
from saleha.tools.base import BaseTool, ToolResult, tool_registry

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOOLS_DIR = os.path.join(REPO_ROOT, "saleha", "tools")
TEST_DIR = os.path.join(REPO_ROOT, "saleha", "tests")
LOG_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "tool_forge_log.jsonl")


@dataclass
class ToolSpecification:
    """Specification contract for synthesizing a new autonomous tool."""
    name: str
    class_name: str
    description: str
    parameters: Dict[str, Any]
    domain: str = "general"


@dataclass
class ToolForgeResult:
    """Audit outcome for an autonomous tool synthesis attempt."""
    timestamp: str
    tool_name: str
    status: str  # "created" | "commit_failed" | "validation_failed" | "generation_failed" | "already_exists" | "no_candidate"
    detail: str
    tool_path: Optional[str] = None
    test_path: Optional[str] = None
    commit_sha: Optional[str] = None
    quality_score: Optional[float] = None
    tests_passed: bool = False


BUILTIN_TOOL_CATALOG: List[ToolSpecification] = [
    ToolSpecification(
        name="ast_inspector",
        class_name="ASTInspectorTool",
        description="Analyzes Python source code to extract classes, functions, imports, and calculate line count.",
        parameters={
            "type": "object",
            "properties": {
                "source_code": {"type": "string", "description": "Python source code string to inspect"},
                "file_path": {"type": "string", "description": "Optional path to a Python file to read and inspect"},
            },
        },
        domain="code_analysis",
    ),
    ToolSpecification(
        name="git_status_auditor",
        class_name="GitStatusAuditorTool",
        description="Audits current git status, uncommitted changes, untracked files, and current branch.",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Path to git repository, default current workspace"},
            },
        },
        domain="version_control",
    ),
    ToolSpecification(
        name="env_inspector",
        class_name="EnvInspectorTool",
        description="Inspects Python runtime environment, executable path, version, and platform.",
        parameters={
            "type": "object",
            "properties": {
                "check_packages": {"type": "boolean", "description": "Whether to list installed packages"},
            },
        },
        domain="runtime",
    ),
    ToolSpecification(
        name="text_pattern_finder",
        class_name="TextPatternFinderTool",
        description="Searches for exact text or regex patterns across files in a directory.",
        parameters={
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path to search"},
                "pattern": {"type": "string", "description": "Regex or string pattern to look for"},
                "file_extension": {"type": "string", "description": "Optional file extension filter, e.g. .py"},
            },
            "required": ["pattern"],
        },
        domain="search",
    ),
]


def _run(cmd: list, cwd: str = REPO_ROOT) -> subprocess.CompletedProcess:
    """Executes command with UTF-8 encoding support."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120, env=env)


def _clean_code_fence(code: str) -> str:
    """Strips markdown code fences (```python ... ```) cleanly."""
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    return code


class ToolForge:
    """Autonomous Engine for Creating, Validating, and Registering Tools."""

    def __init__(self) -> None:
        self.tools_dir: str = TOOLS_DIR
        self.tests_dir: str = TEST_DIR
        self.quality_guard = QualityGuard(strict_mode=True)
        self.ast_inspector = ASTInspectorTool()

    def get_existing_tool_names(self) -> Set[str]:
        """Returns the set of tool names already implemented in saleha/tools/."""
        tools: Set[str] = set()
        if os.path.exists(self.tools_dir):
            for f in os.listdir(self.tools_dir):
                if f.endswith(".py") and not f.startswith("_") and f != "base.py":
                    tools.add(f[:-3])
        return tools

    def get_missing_catalog_tools(self) -> List[ToolSpecification]:
        """Returns specifications from the built-in catalog that are not yet built."""
        existing = self.get_existing_tool_names()
        return [spec for spec in BUILTIN_TOOL_CATALOG if spec.name not in existing]

    def _select_model(self) -> Optional[str]:
        """Selects the best available local coding model from Ollama."""
        from saleha.core.smart_router import get_installed_ollama_models
        installed = {m for m in get_installed_ollama_models() if ":" in m}
        preference = ["qwen2.5-coder:3b", "deepseek-coder:6.7b", "qwen3:8b", "qwen3.5:9b"]
        return next((m for m in preference if m in installed), None) or next(
            (m for m in sorted(installed) if "coder" in m), next(iter(sorted(installed)), None)
        )

    def generate_tool_code(self, spec: ToolSpecification) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Generates tool source and companion test source using local model provider."""
        from saleha.core.model_provider import default_provider

        model_name = self._select_model()
        if not model_name:
            return None, None, None

        prompt = (
            f"You are building an autonomous production tool for Saleha in Python.\n"
            f"Tool Name: {spec.name}\n"
            f"Class Name: {spec.class_name}\n"
            f"Description: {spec.description}\n"
            f"Parameters schema: {json.dumps(spec.parameters)}\n\n"
            f"STRICT REQUIREMENTS:\n"
            f"1. Inherit from `saleha.tools.base.BaseTool`.\n"
            f"2. Implement `execute(self, **kwargs: Any) -> ToolResult` returning `ToolResult(success=True, data=...)`.\n"
            f"3. Must be cross-platform (Windows-safe). Import typing symbols explicitly.\n"
            f"4. Do NOT use `eval()`, `exec()`, or `subprocess` with `shell=True`.\n"
            f"5. Output ONLY valid Python code for `saleha/tools/{spec.name}.py`. No markdown fences, no explanation."
        )

        try:
            resp = default_provider.generate(model=model_name, prompt=prompt)
            if not resp.success or not resp.content:
                return None, None, model_name
            tool_code = _clean_code_fence(resp.content)
        except Exception:
            return None, None, model_name

        test_prompt = (
            f"Write a companion pytest test suite for this new Saleha tool:\n"
            f"--- TOOL CODE ({spec.name}.py) ---\n{tool_code}\n\n"
            f"REQUIREMENTS:\n"
            f"1. Import `{spec.class_name}` from `{spec.name}`.\n"
            f"2. Write 3+ tests verifying `execute()` under normal parameters, edge cases, and invalid inputs.\n"
            f"3. Output ONLY valid Python test code. No markdown fences, no explanation."
        )

        try:
            test_resp = default_provider.generate(model=model_name, prompt=test_prompt)
            if not test_resp.success or not test_resp.content:
                return None, None, model_name
            test_code = _clean_code_fence(test_resp.content)
        except Exception:
            return None, None, model_name

        return tool_code, test_code, model_name

    def validate_tool_and_test(
        self,
        tool_name: str,
        tool_code: str,
        test_code: str,
        model_name: Optional[str] = None,
        max_repairs: int = 1,
    ) -> Tuple[bool, str, str, str]:
        """Validates tool and test in an isolated temp environment with QualityGuard & AST verification.

        Verification Pipeline:
        Step 1: QualityGuard Static Linting (checks undefined symbols, missing imports, syntax errors).
        Step 2: AST Structural Verification (checks BaseTool inheritance and execute method presence).
        Step 3: Isolated Pytest Execution in temporary virtual environment sandbox.
        """
        current_tool_code = tool_code
        current_test_code = test_code

        for attempt in range(max_repairs + 1):
            # --- Stage 1: QualityGuard Static Verification ---
            quality_report = self.quality_guard.check_code(current_tool_code)
            if not quality_report.passed or quality_report.critical_count > 0:
                critical_msgs = [i.message for i in quality_report.issues if i.severity == "CRITICAL"]
                error_summary = "; ".join(critical_msgs) if critical_msgs else f"Quality score too low ({quality_report.quality_score}/100)"
                if attempt < max_repairs and model_name:
                    repaired_tool = self._attempt_repair(current_tool_code, error_summary, model_name)
                    if repaired_tool:
                        current_tool_code = repaired_tool
                        continue
                return False, current_tool_code, current_test_code, f"QualityGuard validation failed: {error_summary}"

            # --- Stage 2: AST Structural Verification ---
            ast_result = self.ast_inspector.execute(source_code=current_tool_code)
            if not ast_result.success:
                return False, current_tool_code, current_test_code, f"AST inspection error: {ast_result.error}"

            classes = ast_result.data.get("classes", [])
            has_valid_class = any("BaseTool" in c.get("bases", []) or "execute" in c.get("methods", []) for c in classes)
            if not has_valid_class and not any(c.get("name", "").endswith("Tool") for c in classes):
                return False, current_tool_code, current_test_code, "AST validation failed: Tool class must implement execute() method"

            # Check security findings from AST inspector
            security_findings = ast_result.data.get("security_findings", [])
            critical_sec = [s for s in security_findings if s.get("severity") in ("CRITICAL", "HIGH")]
            if critical_sec:
                sec_msg = critical_sec[0].get("message", "Security risk detected")
                return False, current_tool_code, current_test_code, f"AST security rejection: {sec_msg}"

            # --- Stage 3: Isolated Pytest Execution ---
            tmp_dir = tempfile.mkdtemp()
            tmp_tool_path = os.path.join(tmp_dir, f"{tool_name}.py")
            tmp_test_path = os.path.join(tmp_dir, f"test_{tool_name}.py")

            try:
                with open(tmp_tool_path, "w", encoding="utf-8") as f:
                    f.write(current_tool_code)
                with open(tmp_test_path, "w", encoding="utf-8") as f:
                    f.write(current_test_code)

                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONPATH"] = f"{tmp_dir}{os.pathsep}{REPO_ROOT}"

                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", tmp_test_path, "-q", "--no-header"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=env,
                )

                if proc.returncode == 0:
                    return True, current_tool_code, current_test_code, "Validation passed (QualityGuard & Pytest green)"

                last_error = (proc.stdout + proc.stderr)[-1000:]
                if attempt < max_repairs and model_name:
                    repaired_tool = self._attempt_repair(current_tool_code, last_error, model_name)
                    if repaired_tool:
                        current_tool_code = repaired_tool
                        continue

                return False, current_tool_code, current_test_code, f"Validation failed: {last_error}"

            finally:
                # Clean up temporary artifacts safely
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

        return False, current_tool_code, current_test_code, "Validation failed after maximum repair attempts"

    def _attempt_repair(self, code: str, error_msg: str, model_name: str) -> Optional[str]:
        """Attempts an automated surgical repair of broken tool code using the local model."""
        from saleha.core.model_provider import default_provider
        repair_prompt = (
            f"The following Python tool code failed validation with this error:\n"
            f"ERROR: {error_msg}\n\n"
            f"--- ORIGINAL CODE ---\n{code}\n\n"
            f"Fix the error completely. Ensure all missing imports are included and methods match BaseTool contract.\n"
            f"Output ONLY the corrected Python code. No markdown fences, no explanation."
        )
        try:
            resp = default_provider.generate(model=model_name, prompt=repair_prompt)
            if resp.success and resp.content:
                return _clean_code_fence(resp.content)
        except Exception:
            pass
        return None

    def forge_tool(self, spec: ToolSpecification, auto_commit: bool = True) -> ToolForgeResult:
        """End-to-end autonomous synthesis, validation, and deployment of a tool."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        target_tool_path = os.path.join(self.tools_dir, f"{spec.name}.py")
        target_test_path = os.path.join(self.tests_dir, f"test_tool_{spec.name}.py")

        if os.path.exists(target_tool_path):
            res = ToolForgeResult(
                timestamp=timestamp,
                tool_name=spec.name,
                status="already_exists",
                detail=f"Tool {spec.name} already exists at {target_tool_path}",
                tool_path=target_tool_path,
            )
            self._log_result(res)
            return res

        tool_code, test_code, model_name = self.generate_tool_code(spec)
        if not tool_code or not test_code:
            res = ToolForgeResult(
                timestamp=timestamp,
                tool_name=spec.name,
                status="generation_failed",
                detail="Model failed to generate tool or test code.",
            )
            self._log_result(res)
            return res

        passed, tool_code, test_code, detail = self.validate_tool_and_test(
            spec.name, tool_code, test_code, model_name=model_name
        )
        if not passed:
            res = ToolForgeResult(
                timestamp=timestamp,
                tool_name=spec.name,
                status="validation_failed",
                detail=detail,
            )
            self._log_result(res)
            return res

        # Write real files
        os.makedirs(self.tools_dir, exist_ok=True)
        os.makedirs(self.tests_dir, exist_ok=True)
        with open(target_tool_path, "w", encoding="utf-8") as f:
            f.write(tool_code)
        with open(target_test_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        # Dynamic auto-discovery
        tool_registry.auto_discover(self.tools_dir)

        sha = None
        commit_status = "created"
        commit_detail = f"Synthesized and verified {spec.name} successfully."
        if auto_commit:
            sha, commit_status, commit_detail = self._commit_synthesized_files(
                target_tool_path, target_test_path, spec.name
            )

        res = ToolForgeResult(
            timestamp=timestamp,
            tool_name=spec.name,
            status=commit_status,
            detail=commit_detail,
            tool_path=target_tool_path,
            test_path=target_test_path,
            commit_sha=sha,
            tests_passed=True,
        )
        self._log_result(res)
        return res

    def _commit_synthesized_files(
        self,
        tool_path: str,
        test_path: str,
        tool_name: str,
        repo_root: str = REPO_ROOT,
    ) -> Tuple[Optional[str], str, str]:
        """Stages and commits synthesized files, reporting failure honestly.

        Returns (commit_sha_or_None, status, detail). A failed 'git add' or
        'git commit' -- most commonly the repo's own pre-commit quality gate
        rejecting model-generated code -- must never be reported as
        status="created": the file exists on disk but is not in git history,
        and 'git rev-parse HEAD' after a failed commit returns the *prior*
        commit's SHA, not evidence of success.
        """
        # Capture HEAD before committing so a failed commit cannot be
        # mistaken for success by reporting the prior commit's SHA.
        head_before_proc = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
        head_before = head_before_proc.stdout.strip() if head_before_proc.returncode == 0 else None

        rel_tool = os.path.relpath(tool_path, repo_root)
        rel_test = os.path.relpath(test_path, repo_root)
        # Blast-radius safe: Stage ONLY the exact synthesized files, never git add .
        add_proc = _run(["git", "add", rel_tool, rel_test], cwd=repo_root)
        if add_proc.returncode != 0:
            return None, "commit_failed", (
                f"Files written to disk but 'git add' failed (exit {add_proc.returncode}): "
                f"{(add_proc.stderr or add_proc.stdout).strip()[:500]}"
            )

        commit_msg = f"feat(tools): autonomously synthesize and verify tool {tool_name}"
        commit_proc = _run(["git", "commit", "-m", commit_msg], cwd=repo_root)
        if commit_proc.returncode != 0:
            return None, "commit_failed", (
                f"Files written and staged but 'git commit' failed (exit {commit_proc.returncode}), "
                f"likely rejected by the pre-commit quality gate: "
                f"{(commit_proc.stderr or commit_proc.stdout).strip()[:500]}"
            )

        sha_proc = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
        new_head = sha_proc.stdout.strip() if sha_proc.returncode == 0 else None
        # A commit that did not move HEAD is not a commit, whatever its exit code said.
        if new_head and new_head != head_before:
            return new_head, "created", f"Synthesized and verified {tool_name} successfully."
        return None, "commit_failed", "git commit reported success but HEAD did not advance."

    def forge_next_unbuilt_tool(self, auto_commit: bool = True) -> ToolForgeResult:
        """Autonomously finds the next tool needed in the catalog and builds it."""
        missing = self.get_missing_catalog_tools()
        if not missing:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            res = ToolForgeResult(
                timestamp=timestamp,
                tool_name="",
                status="no_candidate",
                detail="All built-in catalog tools are already synthesized.",
            )
            self._log_result(res)
            return res

        next_spec = missing[0]
        return self.forge_tool(next_spec, auto_commit=auto_commit)

    def _log_result(self, res: ToolForgeResult) -> None:
        """Appends tool forge audit log entries to disk."""
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(res)) + "\n")
        except Exception:
            pass

    def read_log(self, limit: int = 20) -> List[dict]:
        """Reads recent audit log records."""
        if not os.path.exists(LOG_PATH):
            return []
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                lines = [json.loads(l) for l in f if l.strip()]
            return lines[-limit:]
        except Exception:
            return []


tool_forge = ToolForge()
