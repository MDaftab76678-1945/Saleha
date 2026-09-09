"""
Saleha Core: Project Scaffolder

Copies one of the starter service templates in `templates/` into a new
directory, substituting the project name, and verifies the result runs.

This is deterministic file copying, not code generation -- there is no
model call here and the output is byte-identical for the same inputs
(`create-react-app` works the same way). `saleha build` is the LLM path
for bespoke multi-file projects; this is the fast path for the boilerplate
that never changes: a health endpoint and a root endpoint.

Templates and how each is verified after copy:
  python_fastapi  -> pytest templates' own test_main.py against the copy
  nodejs_express  -> tsc --noEmit if a TypeScript compiler is on PATH
  go_service      -> go build ./... if the go toolchain is on PATH
A verification step that cannot run (toolchain absent) is reported as
skipped, not as a pass.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Repo-root/templates, resolved relative to this file.
_TEMPLATES_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "templates")
)

TEMPLATES: Dict[str, str] = {
    "fastapi": "python_fastapi",
    "express": "nodejs_express",
    "go": "go_service",
}


@dataclass
class ScaffoldResult:
    success: bool
    stack: str
    project_dir: str
    files_written: List[str] = field(default_factory=list)
    verify_ran: bool = False
    verify_ok: Optional[bool] = None
    verify_detail: str = ""
    error: str = ""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "service"


def _substitute(text: str, project_name: str, project_slug: str) -> str:
    return (
        text.replace("{{PROJECT_NAME}}", project_name)
        .replace("{{PROJECT_SLUG}}", project_slug)
    )


class ProjectScaffolder:
    """Deterministic starter-project generator from bundled templates."""

    def __init__(self, templates_root: str = _TEMPLATES_ROOT):
        self.templates_root = templates_root

    def available_stacks(self) -> List[str]:
        """Stack keys whose template directory actually exists on disk."""
        return [
            key
            for key, folder in TEMPLATES.items()
            if os.path.isdir(os.path.join(self.templates_root, folder))
        ]

    def scaffold(self, stack: str, project_name: str, dest_parent: str = ".",
                 force: bool = False) -> ScaffoldResult:
        """Copies the `stack` template into `dest_parent/<slug>`, substituting
        the project name, then verifies it."""
        stack = stack.lower()
        if stack not in TEMPLATES:
            return ScaffoldResult(
                success=False, stack=stack, project_dir="",
                error=f"Unknown stack '{stack}'. Available: {', '.join(TEMPLATES)}.",
            )

        src = os.path.join(self.templates_root, TEMPLATES[stack])
        if not os.path.isdir(src):
            return ScaffoldResult(
                success=False, stack=stack, project_dir="",
                error=f"Template directory missing: {src}",
            )

        slug = _slugify(project_name)
        project_dir = os.path.abspath(os.path.join(dest_parent, slug))
        if os.path.exists(project_dir):
            if not force:
                return ScaffoldResult(
                    success=False, stack=stack, project_dir=project_dir,
                    error=f"{project_dir} already exists. Pass force=True to overwrite.",
                )
            shutil.rmtree(project_dir)

        written = self._copy_tree(src, project_dir, project_name, slug)

        verify_ran, verify_ok, detail = self._verify(stack, project_dir)
        # A copy with a verification that ran and failed is not a success.
        success = verify_ok is not False
        return ScaffoldResult(
            success=success, stack=stack, project_dir=project_dir,
            files_written=written, verify_ran=verify_ran, verify_ok=verify_ok,
            verify_detail=detail,
        )

    def _copy_tree(self, src: str, dest: str, project_name: str, slug: str) -> List[str]:
        """Copies src -> dest, applying substitution to every text file."""
        written: List[str] = []
        for root, _dirs, files in os.walk(src):
            rel_root = os.path.relpath(root, src)
            target_root = dest if rel_root == "." else os.path.join(dest, rel_root)
            os.makedirs(target_root, exist_ok=True)
            for fname in files:
                src_path = os.path.join(root, fname)
                target_path = os.path.join(target_root, fname)
                try:
                    with open(src_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    content = _substitute(content, project_name, slug)
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(content)
                except UnicodeDecodeError:
                    # Binary file: copy verbatim, no substitution.
                    shutil.copy2(src_path, target_path)
                written.append(os.path.relpath(target_path, dest))
        return written

    def _verify(self, stack: str, project_dir: str) -> tuple[bool, Optional[bool], str]:
        """Runs the stack's verification. Returns (ran, ok, detail)."""
        if stack == "fastapi":
            return self._verify_fastapi(project_dir)
        if stack == "express":
            return self._verify_express(project_dir)
        if stack == "go":
            go = self._which("go")
            return self._verify_cmd(
                project_dir,
                [go, "build", "./..."] if go else ["go", "build", "./..."],
                "go build", needs=go,
            )
        return (False, None, "no verification defined for this stack")

    @staticmethod
    def _which(cmd: str) -> Optional[str]:
        """Resolves a command to its full executable path.

        On Windows this picks up `.CMD` / `.EXE` wrappers (npx.CMD, ...) that
        subprocess cannot launch by bare name. Also checks a couple of
        well-known install dirs that a minimal shell PATH can omit even when
        the tool is installed and on the persistent PATH.
        """
        found = shutil.which(cmd)
        if found:
            return found
        fallbacks = {
            "go": [r"C:\Program Files\Go\bin\go.exe"],
        }
        for candidate in fallbacks.get(cmd, []):
            if os.path.isfile(candidate):
                return candidate
        return None

    def _verify_fastapi(self, project_dir: str) -> tuple[bool, Optional[bool], str]:
        import sys

        test_file = os.path.join(project_dir, "test_main.py")
        if not os.path.isfile(test_file):
            return (False, None, "template has no test_main.py; skipped")

        # The template's test imports fastapi and httpx. If the interpreter
        # that would run it cannot import them, the check cannot run -- that
        # is a skip, not a failed scaffold.
        probe = subprocess.run(
            [sys.executable, "-c",
             "import fastapi, httpx, pytest"],
            capture_output=True, text=True,
        )
        if probe.returncode != 0:
            missing = (probe.stderr.strip().splitlines() or ["fastapi/httpx/pytest"])[-1]
            return (False, None, f"{missing}; fastapi check skipped "
                                 f"(pip install fastapi httpx pytest)")

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_main.py", "-q"],
                cwd=project_dir, capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return (True, False, "pytest timed out after 120s")
        ok = proc.returncode == 0
        return (True, ok, (proc.stdout + proc.stderr).strip()[-800:])

    def _verify_express(self, project_dir: str) -> tuple[bool, Optional[bool], str]:
        """Runs `npm install` then the project's own `tsc --noEmit`.

        TypeScript is a declared devDependency of the template, so the
        correct check is to install the project and compile with its local
        compiler -- not to pull a global or ad-hoc one.
        """
        npm = self._which("npm")
        npx = self._which("npx")
        if npm is None or npx is None:
            return (False, None, "npm/npx not on PATH; tsc check skipped")

        try:
            inst = subprocess.run(
                [npm, "install", "--no-audit", "--no-fund"],
                cwd=project_dir, capture_output=True, text=True, timeout=300,
            )
        except FileNotFoundError:
            return (False, None, "npm could not be launched; tsc check skipped")
        except subprocess.TimeoutExpired:
            return (True, False, "npm install timed out after 300s")
        if inst.returncode != 0:
            return (True, False, ("npm install failed:\n"
                                  + (inst.stdout + inst.stderr).strip()[-800:]))

        try:
            proc = subprocess.run(
                [npx, "--no-install", "tsc", "--noEmit"],
                cwd=project_dir, capture_output=True, text=True, timeout=180,
            )
        except subprocess.TimeoutExpired:
            return (True, False, "tsc timed out after 180s")
        ok = proc.returncode == 0
        return (True, ok, (proc.stdout + proc.stderr).strip()[-800:])

    def _verify_cmd(self, project_dir: str, cmd: List[str], label: str,
                    needs: Optional[str]) -> tuple[bool, Optional[bool], str]:
        if needs is None:
            return (False, None, f"{cmd[0]} not on PATH; {label} check skipped")
        try:
            proc = subprocess.run(
                cmd, cwd=project_dir, capture_output=True, text=True, timeout=180,
            )
        except FileNotFoundError:
            return (False, None, f"{cmd[0]} could not be launched; {label} check skipped")
        except subprocess.TimeoutExpired:
            return (True, False, f"{label} timed out after 180s")
        ok = proc.returncode == 0
        return (True, ok, (proc.stdout + proc.stderr).strip()[-800:])


project_scaffolder = ProjectScaffolder()
