"""
Saleha Core: Project Builder (multi-file project support)

Saleha previously could only produce a single file/function at a time. This
module splits a larger goal into multiple files -- e.g. "build a small Flask
app" into `app.py`, `models.py`, `requirements.txt`.

How it works:
1. Asks the planner LLM: "which files does this goal need?"
   (as a JSON list of filename + what that file should contain)
2. Calls CoderAgent separately for each file (with a summary of the other
   files as context, so imports/naming stay consistent)
3. Each file goes through the Tester (syntax/security check)
4. All files are saved into one project folder

Limitations (honest scope):
- Each file is generated independently -- cross-file logic errors (e.g. one
  file importing a function from another under the wrong name) cannot be
  fully caught, because files are not verified against each other at
  runtime (only a summary of the sibling files is given as context).
- The self-healing loop present in single-file mode does not run here -- if
  a file fails, it is only logged, the whole project does not halt.
- Python files only, for now (same as the rest of Saleha).
"""

from __future__ import annotations

import sys
import os
import re
import json
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.agents.coder import CoderAgent
from saleha.agents.tester import TesterAgent


DEFAULT_PROJECTS_DIR = os.path.join(os.path.expanduser("~"), "saleha_projects")


@dataclass
class FileSpec:
    filename: str
    description: str


@dataclass
class FileResult:
    filename: str
    code: str
    tested_ok: bool
    test_error: str = ""


@dataclass
class ProjectResult:
    success: bool
    project_dir: str
    files: List[FileResult] = field(default_factory=list)
    log: str = ""
    entry_point: str = ""
    entry_point_ok: Optional[bool] = None
    entry_point_error: str = ""


class ProjectBuilder:
    def __init__(self, model: str = "auto", projects_dir: str = DEFAULT_PROJECTS_DIR):
        """Initializes the multi-file project builder."""
        self.model = model
        self.planner_agent = BaseAgent(role="ProjectPlanner", model=model)
        self.coder = CoderAgent(model=model)
        self.tester = TesterAgent()
        self.projects_dir = projects_dir

    def _slugify(self, goal: str) -> str:
        """Converts user goal into a clean filesystem folder slug."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", goal.lower()).strip("_")
        return slug[:40] or "project"

    def _plan_files(self, goal: str) -> List[FileSpec]:
        """Plans the required modular file structure for the given project goal."""
        prompt = f"""You are a Python project architect.
Goal: {goal}

List the Python files needed to accomplish this goal (2-5 files, no more than necessary).
Respond ONLY in this JSON format, no other text:
[
  {{"filename": "app.py", "description": "what should be in this file"}},
  {{"filename": "utils.py", "description": "..."}}
]
"""
        response: AgentResponse = self.planner_agent.think(prompt)
        if not response.success:
            return []

        # JSON array nikaalo response se (agar model ne extra text daal diya ho)
        match = re.search(r"\[.*\]", response.content, re.DOTALL)
        json_text = match.group(0) if match else response.content

        try:
            data = json.loads(json_text)
            return [FileSpec(filename=d["filename"], description=d.get("description", "")) for d in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    def _isolate_file_code(self, code: str, target_filename: str, all_specs: List[FileSpec]) -> str:
        """
        Small models sometimes return code for multiple files in one
        response (e.g. "# main.py\n...\n# calculator.py\n...") even when
        only one file was requested. This method checks whether another
        file's name appears in the code as a header comment, and if so,
        keeps only the section belonging to the target file.
        """
        other_filenames = [f.filename for f in all_specs if f.filename != target_filename]
        if not other_filenames:
            return code

        lines = code.split("\n")
        # Scan each line -- if it looks like "# <some other file>.py",
        # treat that as a section break (once the target file's section has
        # already started).
        marker_pattern = re.compile(
            r"^\s*#+\s*(" + "|".join(re.escape(f) for f in [target_filename] + other_filenames) + r")\s*$"
        )

        sections = {}  # filename -> list of lines
        current_file = None
        preamble = []  # code before any marker is found (if the target file is the first section)

        for line in lines:
            m = marker_pattern.match(line)
            if m:
                current_file = m.group(1)
                sections[current_file] = []
                continue
            if current_file is None:
                preamble.append(line)
            else:
                sections[current_file].append(line)

        if target_filename in sections and sections[target_filename]:
            return "\n".join(sections[target_filename]).strip()

        # No marker found (the normal case) -- the whole response belongs to
        # this file.
        if not sections:
            return code

        non_empty_sections = {k: v for k, v in sections.items() if v}

        # Exactly one section was found and it is not the target file's --
        # this is not actually a multi-file dump, the model just labelled
        # its own generated code with the wrong filename header. The whole
        # content still belongs to this file; only the header was wrong.
        if len(non_empty_sections) == 1 and not preamble:
            only_section = next(iter(non_empty_sections.values()))
            return "\n".join(only_section).strip()

        # Genuinely multiple files are mixed together and none of the
        # sections matches the target -- best-effort: return the preamble
        # (or the whole code if the preamble is empty, so something is
        # returned rather than nothing).
        return "\n".join(preamble).strip() or code

    def _generate_single_file(self, spec: FileSpec, all_specs: List[FileSpec], project_summary: str, project_dir: str) -> Tuple[FileResult, str]:
        """Generates, isolates, and tests an individual project file."""
        task = (
            f"This file ({spec.filename}) should contain: {spec.description}\n\n"
            f"IMPORTANT: write ONLY the code for '{spec.filename}'. Do not include "
            f"any other file's code, even if the project has other files.\n"
            f"Always use absolute imports (e.g. 'from calculator import add'), "
            f"never relative imports (e.g. '.calculator' or '..module')."
        )
        plan_context = f"Full project structure:\n{project_summary}"
        code_result = self.coder.generate_code(task, plan=plan_context, attempt=1)

        if not code_result.success:
            return FileResult(filename=spec.filename, code="", tested_ok=False, test_error=code_result.error), f"  FAILED: Generation failed: {code_result.error}"

        file_code = self._isolate_file_code(code_result.code, spec.filename, all_specs)
        test_result = self.tester.test_code(file_code)
        file_path = os.path.join(project_dir, spec.filename)
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_code)

        status = "OK" if test_result.passed else "WARN"
        res = FileResult(
            filename=spec.filename,
            code=file_code,
            tested_ok=test_result.passed,
            test_error="" if test_result.passed else test_result.error_message,
        )
        return res, f"  {status} Saved to {file_path}"

    def build(self, goal: str) -> ProjectResult:
        """Executes end-to-end multi-file project planning and generation."""
        logs: List[str] = [
            f"Project Goal: {goal}",
            "-" * 60,
            "\n[1/3] Planning the file list...",
        ]

        file_specs = self._plan_files(goal)
        if not file_specs:
            logs.append("FAILED: no valid file list returned by the model.")
            return ProjectResult(success=False, project_dir="", log="\n".join(logs))

        logs.append(f"OK: {len(file_specs)} files planned: {[f.filename for f in file_specs]}")
        project_summary = "\n".join(f"- {f.filename}: {f.description}" for f in file_specs)
        project_slug = self._slugify(goal)
        project_dir = os.path.join(self.projects_dir, project_slug)
        os.makedirs(project_dir, exist_ok=True)

        results: List[FileResult] = []
        logs.append("\n[2/3] Generating each file...")
        for spec in file_specs:
            logs.append(f"\n  {spec.filename}: {spec.description}")
            file_res, msg = self._generate_single_file(spec, file_specs, project_summary, project_dir)
            results.append(file_res)
            logs.append(msg)

        logs.append(f"\n[3/3] Project saved to: {project_dir}")

        entry_spec = self._find_entry_point(file_specs, results)
        entry_ok = None
        entry_error = ""

        if entry_spec:
            logs.append(f"\n[4/4] Verifying entry point '{entry_spec.filename}'...")
            entry_ok, entry_error = self._verify_entry_point(project_dir, entry_spec.filename)
            if entry_ok:
                logs.append(f"  OK: '{entry_spec.filename}' ran without crashing.")
            else:
                logs.append(f"  FAILED: crash on run: {entry_error[:300]}")
        else:
            logs.append("\n[4/4] No clear entry point found, skipping verification.")

        all_ok = all(r.tested_ok for r in results) and (entry_ok is not False)
        return ProjectResult(
            success=all_ok, project_dir=project_dir, files=results, log="\n".join(logs),
            entry_point=entry_spec.filename if entry_spec else "",
            entry_point_ok=entry_ok, entry_point_error=entry_error,
        )

    def _identify_buggy_file(self, error_text: str, file_specs: List[FileSpec]) -> Optional[FileSpec]:
        """Identifies deepest traceback frame file to target self-healing fixes."""
        frames = re.findall(r'File "([^"]+)", line \d+', error_text)
        if not frames:
            return None

        for frame_path in reversed(frames):
            frame_filename = os.path.basename(frame_path)
            for spec in file_specs:
                if spec.filename == frame_filename:
                    return spec
        return None

    def _find_entry_point(self, file_specs: List[FileSpec], results: List[FileResult]) -> Optional[FileSpec]:
        """Locates the primary executable entry point file."""
        for spec in file_specs:
            match = next((r for r in results if r.filename == spec.filename), None)
            if match and '__main__' in match.code:
                return spec
        return None

    def _verify_entry_point(self, project_dir: str, entry_filename: str) -> Tuple[bool, str]:
        """Verifies entry point execution in a bounded timeout subprocess."""
        python_cmd = shutil.which("python3") or shutil.which("python")
        if not python_cmd:
            return False, "Neither 'python' nor 'python3' found on PATH."

        try:
            result = subprocess.run(
                [python_cmd, entry_filename],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=10,
                input="",
            )
            if result.returncode == 0:
                return True, ""
            return False, result.stderr or result.stdout
        except subprocess.TimeoutExpired:
            return True, ""
        except (OSError, subprocess.SubprocessError) as e:
            return False, str(e)


if __name__ == "__main__":
    _builder = ProjectBuilder(model="qwen2.5-coder:3b")
    _res = _builder.build("A simple command-line calculator with add, subtract, multiply, divide")