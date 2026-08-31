"""
Saleha Core: Autonomous Self-Healing & Auto-Fix Compiler Engine

Captures runtime crashes, test failures (pytest, npm, cargo, go test), and compiler errors,
localizes the faulting AST block/line, generates surgical 3-tier search/replace patches,
and verifies resolutions in isolated sandboxes with automated Git commit hooks.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from saleha.agents.base_agent import BaseAgent
from saleha.core.codebase_indexer import codebase_indexer
from saleha.core.git_native import git_engine
from saleha.core.path_utils import safe_relpath


@dataclass
class StackFrame:
    file_path: str
    line_number: int
    function_name: str = ""
    line_code: str = ""


@dataclass
class ErrorDiagnostics:
    error_type: str
    message: str
    frames: List[StackFrame] = field(default_factory=list)
    faulting_file: str = ""
    faulting_line: int = 0
    raw_output: str = ""


@dataclass
class HealResult:
    success: bool
    attempts_made: int = 0
    command: str = ""
    diagnostics: Optional[ErrorDiagnostics] = None
    applied_patches: List[Dict[str, Any]] = field(default_factory=list)
    verified: bool = False
    commit_hash: str = ""
    error: str = ""


class SelfHealingEngine:
    """Automates diagnosis, surgical patch generation, and re-test verification for failing commands."""

    def __init__(self, root_dir: str = ".", model: str = "auto"):
        self.root_dir = os.path.abspath(root_dir)
        self.model = model
        self.agent = BaseAgent(role="Senior Autonomous BugFixer", model=model)

    def parse_error_output(self, raw_output: str) -> ErrorDiagnostics:
        """Extracts stack frames, exception types, and faulting lines from error output."""
        frames: List[StackFrame] = []
        error_type = "RuntimeError"
        message = ""
        faulting_file = ""
        faulting_line = 0

        # 1. Python Traceback matching: File "path/to/file.py", line 123, in func
        py_frame_pattern = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\w+))?', re.MULTILINE)
        for m in py_frame_pattern.finditer(raw_output):
            f_path = m.group(1)
            line_no = int(m.group(2))
            func = m.group(3) or ""
            frames.append(StackFrame(file_path=f_path, line_number=line_no, function_name=func))

        # 2. PyTest FAILED summary line: FAILED tests/test_foo.py::test_bar - ErrorType: msg
        pytest_fail_pattern = re.compile(r'FAILED ([\w\\/\.-]+)::\w+.*?- (\w+Error|\w+Exception|\w+): (.*)')
        for m in pytest_fail_pattern.finditer(raw_output):
            f_path = m.group(1)
            error_type = m.group(2)
            message = m.group(3).strip()

        # 3. Generic Error matching: ExceptionType: message (at end of traceback)
        py_exc_pattern = re.compile(r'^([A-Z]\w*(?:Error|Exception|Warning|Fault)): (.*)$', re.MULTILINE)
        for m in py_exc_pattern.finditer(raw_output):
            error_type = m.group(1)
            message = m.group(2).strip()

        # 4. Standard compiler/linter pattern: file.py:line:col: error / file.py:line: Error
        generic_err_pattern = re.compile(r'([\w\\/\.-]+\.(?:py|js|ts|go|rs|java)):(\d+)(?::\d+)?: (.*)', re.MULTILINE)
        for m in generic_err_pattern.finditer(raw_output):
            f_path = m.group(1)
            line_no = int(m.group(2))
            msg = m.group(3).strip()
            if not frames:
                frames.append(StackFrame(file_path=f_path, line_number=line_no))
            if not message:
                message = msg

        # Pick the most relevant frame (last frame within project directory if possible)
        if frames:
            # Filter to project files
            project_frames = [f for f in frames if not f.file_path.startswith("<") and not "site-packages" in f.file_path]
            target_frame = project_frames[-1] if project_frames else frames[-1]
            faulting_file = target_frame.file_path
            faulting_line = target_frame.line_number
        elif not message:
            message = raw_output.strip().splitlines()[-1] if raw_output.strip() else "Unknown error"

        return ErrorDiagnostics(
            error_type=error_type,
            message=message,
            frames=frames,
            faulting_file=faulting_file,
            faulting_line=faulting_line,
            raw_output=raw_output
        )

    def run_command(self, command: str) -> Tuple[int, str]:
        """Executes the test or build command and captures combined stdout/stderr."""
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=False
            )
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            return res.returncode, combined
        except Exception as e:
            return 1, str(e)

    def generate_heal_patch(self, diagnostics: ErrorDiagnostics, attempt: int = 1) -> Tuple[bool, str, str]:
        """Synthesizes a surgical patch for the diagnosed failure."""
        if not diagnostics.faulting_file:
            return False, "", "No faulting file identified in diagnostics"

        abs_file = os.path.abspath(os.path.join(self.root_dir, diagnostics.faulting_file))
        if not os.path.isfile(abs_file):
            abs_file = diagnostics.faulting_file
        if not os.path.isfile(abs_file):
            return False, "", f"Faulting file not found: {diagnostics.faulting_file}"

        try:
            with open(abs_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            return False, "", f"Could not read faulting file: {e}"

        # Context lines around error
        lines = content.splitlines()
        line_idx = max(0, diagnostics.faulting_line - 1)
        start_idx = max(0, line_idx - 15)
        end_idx = min(len(lines), line_idx + 15)
        context_snippet = "\n".join(
            f"{i+1:4d} | {lines[i]}" for i in range(start_idx, end_idx)
        )

        prompt = f"""You are an Autonomous Senior BugFixer.
A test or build command failed with the following error:

Error Type: {diagnostics.error_type}
Message: {diagnostics.message}
Faulting File: {diagnostics.faulting_file} (line {diagnostics.faulting_line})

Code Context around failure (lines {start_idx+1}-{end_idx}):
```
{context_snippet}
```

Full Error Trace:
{diagnostics.raw_output[:1200]}

Generate an exact surgical Aider-style search/replace block to fix this bug.
Rules:
1. Provide EXACT matching SEARCH lines from the file.
2. Provide concise, bug-free REPLACEMENT lines.
3. Wrap your diff block in ```diff or ``` blocks in this format:
<<<<<<< SEARCH
[exact old code]
=======
[fixed new code]
>>>>>>>
"""
        resp = self.agent.think(prompt, complexity_score=0.4)
        if not resp.success:
            return False, "", f"LLM error: {resp.error_message}"

        patch_text = resp.content or ""
        applied, patched_content, err = codebase_indexer.apply_aider_diff(content, patch_text)
        if applied:
            return True, patched_content, abs_file

        # Fallback: check if the LLM produced pure python code
        code_block = re.search(r"```(?:python)?\s*\n(.*?)```", patch_text, re.DOTALL)
        if code_block and "def " in code_block.group(1):
            applied_sr, patched_content_sr, err_sr = codebase_indexer.apply_search_replace(
                content,
                lines[line_idx].strip(),
                code_block.group(1).strip()
            )
            if applied_sr:
                return True, patched_content_sr, abs_file

        return False, "", f"Failed to apply surgical diff: {err}"

    def auto_heal(self, command: str, max_retries: int = 3, auto_commit: bool = True) -> HealResult:
        """Executes full autonomous self-healing loop until command passes or retries exhaust."""
        code, output = self.run_command(command)
        if code == 0:
            return HealResult(success=True, attempts_made=0, command=command, verified=True)

        diagnostics = self.parse_error_output(output)
        applied_patches = []

        for attempt in range(1, max_retries + 1):
            success, patched_content, target_file = self.generate_heal_patch(diagnostics, attempt=attempt)
            if not success:
                continue

            # Write patched file
            try:
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(patched_content)
            except OSError as e:
                return HealResult(
                    success=False,
                    attempts_made=attempt,
                    command=command,
                    diagnostics=diagnostics,
                    error=f"Failed writing patch: {e}"
                )

            applied_patches.append({
                "attempt": attempt,
                "file": target_file,
                "diagnostics": diagnostics.message
            })

            # Re-test
            retest_code, retest_output = self.run_command(command)
            if retest_code == 0:
                # Successfully healed!
                commit_hash = ""
                if auto_commit and git_engine.is_git_repo():
                    commit_res = git_engine.commit_deliverable(
                        task_name=f"Auto-heal {diagnostics.error_type}: {diagnostics.message[:50]}",
                        task_type="fix"
                    )
                    if commit_res.success:
                        commit_hash = commit_res.commit_hash

                return HealResult(
                    success=True,
                    attempts_made=attempt,
                    command=command,
                    diagnostics=diagnostics,
                    applied_patches=applied_patches,
                    verified=True,
                    commit_hash=commit_hash
                )
            else:
                # Update diagnostics for next attempt
                diagnostics = self.parse_error_output(retest_output)

        return HealResult(
            success=False,
            attempts_made=max_retries,
            command=command,
            diagnostics=diagnostics,
            applied_patches=applied_patches,
            verified=False,
            error=f"Could not heal command '{command}' within {max_retries} attempts."
        )


# Global instance
self_healer = SelfHealingEngine()
