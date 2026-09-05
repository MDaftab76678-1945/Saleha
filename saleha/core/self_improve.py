"""Saleha Self-Improvement Engine.

Fully autonomous, narrowly scoped: on each cycle, picks one saleha/core/
module with no dedicated test file, writes a real pytest test for its actual
public API (using the live model provider against the module's real source,
not a template), runs it for real, and only commits if it genuinely passes.

Safety rails, non-negotiable regardless of how this is invoked:
- Only ever ADDS a new test file. Never edits existing source, since a
  regression in what it writes should never be able to break saleha itself.
- Commits to a local branch (auto/self-improve), never to the branch that
  was checked out when the cycle started, and never force-pushes.
- Never pushes to a remote. Pushing is a shared-system action; a human
  decides when this branch's history is worth publishing.
- A cycle that fails (bad generation, test doesn't pass after retries) is
  logged and discarded -- nothing broken is ever committed.

Every cycle is appended to ~/.saleha/self_improve_log.jsonl for a full,
inspectable audit trail of what it decided to do and what happened.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CORE_DIR = os.path.join(REPO_ROOT, "saleha", "core")
TEST_DIR = os.path.join(REPO_ROOT, "saleha", "tests")
LOG_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "self_improve_log.jsonl")
BRANCH_NAME = "auto/self-improve"
MAX_GENERATION_ATTEMPTS = 2


@dataclass
class SelfImproveResult:
    timestamp: str
    module: str
    goal: str
    status: str  # "committed" | "test_failed" | "generation_failed" | "no_candidate"
    detail: str
    branch: Optional[str] = None
    commit_sha: Optional[str] = None


def _run(cmd: list, cwd: str = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)


def _tested_on_auto_branch() -> set:
    """Tests already committed to auto/self-improve don't exist in the
    working tree once we switch back to the branch we started on (git
    checkout removes files tracked only on the branch being left) -- without
    this, the same module would be picked again on every subsequent cycle."""
    proc = _run(["git", "ls-tree", "-r", "--name-only", BRANCH_NAME, "--", "saleha/tests"])
    if proc.returncode != 0:
        return set()
    names = set()
    for line in proc.stdout.splitlines():
        base = os.path.basename(line.strip())
        if base.startswith("test_") and base.endswith(".py"):
            names.add(base[len("test_"):-len(".py")])
    return names


def find_untested_module(skip: Optional[set] = None) -> Optional[str]:
    """Returns one saleha/core/*.py filename with no saleha/tests/test_<name>.py,
    skipping __init__ files and anything already covered (including tests
    already committed to auto/self-improve but not present on this branch).
    `skip` lets a caller exclude modules that repeatedly failed generation in
    the same run, without writing anything to disk."""
    tested = {
        f[len("test_"):-len(".py")]
        for f in os.listdir(TEST_DIR)
        if f.startswith("test_") and f.endswith(".py")
    }
    tested |= _tested_on_auto_branch()
    tested |= (skip or set())
    candidates = sorted(
        f for f in os.listdir(CORE_DIR)
        if f.endswith(".py") and not f.startswith("__") and f[:-3] not in tested
    )
    return candidates[0] if candidates else None


def _generate_test_source(module_filename: str) -> Optional[str]:
    """Asks the live model provider to write a real pytest file against the
    module's actual source. Returns None if generation clearly failed (empty,
    or doesn't look like a test) rather than committing garbage."""
    from saleha.core.model_provider import default_provider
    from saleha.core.smart_router import get_installed_ollama_models

    # get_installed_ollama_models() includes bare aliases without a tag
    # (e.g. "deepseek-coder" alongside the real "deepseek-coder:6.7b"); the
    # bare form 404s against Ollama's /api/generate, so only tagged names
    # are valid picks here.
    installed = {m for m in get_installed_ollama_models() if ":" in m}
    # Smaller models load and respond faster locally; a large model cold-
    # starting can exceed the provider's request timeout on this hardware.
    preference = ["qwen2.5-coder:1.5b", "qwen2.5-coder:3b", "deepseek-coder:6.7b"]
    model_name = next((m for m in preference if m in installed), None) or next(
        (m for m in sorted(installed) if "coder" in m), next(iter(sorted(installed)), None)
    )
    if not model_name:
        return None

    module_path = os.path.join(CORE_DIR, module_filename)
    with open(module_path, "r", encoding="utf-8") as f:
        source = f.read()[:6000]  # keep the prompt bounded

    module_name = module_filename[:-3]
    prompt = (
        f"Write a pytest test file for this Python module (saleha.core.{module_name}).\n"
        f"Import only what actually exists below. Test real public functions/classes "
        f"with simple, realistic inputs -- no mocks unless the module does network/file I/O. "
        f"Output ONLY valid Python code, no markdown fences, no explanation.\n\n"
        f"--- saleha/core/{module_filename} ---\n{source}\n"
    )

    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            resp = default_provider.generate(model=model_name, prompt=prompt)
        except Exception:
            continue
        if not resp.success or not resp.content:
            continue
        code = resp.content.strip()
        if code.startswith("```"):
            code = code.split("```")[1]
            if code.startswith("python"):
                code = code[len("python"):]
        code = code.strip()
        if "def test_" in code and "import" in code:
            return code
    return None


def run_self_improvement_cycle(skip: Optional[set] = None) -> SelfImproveResult:
    module = find_untested_module(skip=skip)
    if module is None:
        result = SelfImproveResult(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            module="",
            goal="",
            status="no_candidate",
            detail="Every saleha/core module already has a dedicated test file.",
        )
        _log(result)
        return result

    goal = f"Write a real pytest test for saleha/core/{module}"
    test_source = _generate_test_source(module)
    if test_source is None:
        result = SelfImproveResult(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            module=module,
            goal=goal,
            status="generation_failed",
            detail="Model did not produce a usable test after retries.",
        )
        _log(result)
        return result

    module_name = module[:-3]
    test_filename = f"test_{module_name}.py"
    test_path = os.path.join(TEST_DIR, test_filename)

    # pytest only auto-collects files matching test_*.py; verify in an
    # isolated temp dir under that name before touching the real tests dir.
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, test_filename)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(test_source)

    proc = _run([sys.executable, "-m", "pytest", tmp_path, "-q", "--no-header"], cwd=REPO_ROOT)
    if proc.returncode != 0:
        result = SelfImproveResult(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            module=module,
            goal=goal,
            status="test_failed",
            detail=(proc.stdout + proc.stderr)[-800:],
        )
        _log(result)
        return result

    with open(test_path, "w", encoding="utf-8") as f:
        f.write(test_source)

    original_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    # `checkout -B` resets an EXISTING branch to the current HEAD, discarding
    # every prior commit on it -- this silently destroyed every earlier
    # cycle's commit except the last one until this check was added. Only
    # create with -b the first time; otherwise a plain checkout that keeps
    # the branch's own history.
    branch_exists = _run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{BRANCH_NAME}"]).returncode == 0
    _run(["git", "checkout", BRANCH_NAME] if branch_exists else ["git", "checkout", "-b", BRANCH_NAME])
    _run(["git", "add", os.path.relpath(test_path, REPO_ROOT)])
    commit_msg = f"test: autonomous test for saleha/core/{module}\n\nGenerated and verified passing by saleha's self-improvement engine."
    commit_proc = _run(["git", "commit", "-m", commit_msg])
    sha = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    if original_branch and original_branch != BRANCH_NAME:
        _run(["git", "checkout", original_branch])

    result = SelfImproveResult(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        module=module,
        goal=goal,
        status="committed",
        detail=commit_proc.stdout.strip() or "committed",
        branch=BRANCH_NAME,
        commit_sha=sha,
    )
    _log(result)
    return result


def _log(result: SelfImproveResult) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(result)) + "\n")


def read_log(limit: int = 20) -> list:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    return lines[-limit:]
