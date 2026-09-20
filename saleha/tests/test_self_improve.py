"""Unit tests for saleha.core.self_improve module."""

import subprocess
from pathlib import Path

import pytest

from saleha.core import self_improve
from saleha.core.self_improve import (
    _extract_public_api,
    _clean_code_fence,
    _heal_test_source,
    _prune_failing_tests,
    SelfImproveResult,
    find_untested_module,
)


def test_extract_public_api() -> None:
    sample_code = """
import os

A_CONSTANT = 10
_PRIVATE_VAR = 20

def public_func(x):
    return x * 2

def _private_func():
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass
"""
    symbols = _extract_public_api(sample_code)
    assert "A_CONSTANT" in symbols
    assert "public_func" in symbols
    assert "PublicClass" in symbols
    assert "_PRIVATE_VAR" not in symbols
    assert "_private_func" not in symbols
    assert "_PrivateClass" not in symbols


def test_clean_code_fence() -> None:
    fenced = "```python\nimport os\nprint('hello')\n```"
    cleaned = _clean_code_fence(fenced)
    assert cleaned == "import os\nprint('hello')"

    plain = "import os\nprint('hello')"
    assert _clean_code_fence(plain) == plain


def test_heal_test_source_injects_missing_module_import() -> None:
    # Test code calls `approve` and `get_mode` from target module, but only imported `ApprovalGate`
    raw_code = """
from saleha.core.approval_gate import ApprovalGate

def test_approve_function():
    res = approve("shell_exec", "rm -rf")
    mode = get_mode()
    assert mode is not None
"""
    public_symbols = ["ApprovalGate", "approve", "get_mode", "requires_approval"]
    healed = _heal_test_source(raw_code, "approval_gate", public_symbols)

    assert "from saleha.core.approval_gate import approve, get_mode" in healed
    assert "def test_approve_function():" in healed


def test_heal_test_source_injects_pytest_if_missing() -> None:
    raw_code = """
def test_raises():
    with pytest.raises(ValueError):
        pass
"""
    healed = _heal_test_source(raw_code, "my_mod", ["my_func"])
    assert "import pytest" in healed


def test_self_improve_result_dataclass() -> None:
    res = SelfImproveResult(
        timestamp="2026-09-08 04:00:00",
        module="approval_gate.py",
        goal="Write a real pytest test",
        status="committed",
        detail="committed successfully",
        branch="auto/self-improve",
        commit_sha="abc1234",
    )
    assert res.status == "committed"
    assert res.module == "approval_gate.py"
    assert res.commit_sha == "abc1234"


def test_find_untested_module() -> None:
    candidate = find_untested_module()
    # Candidate should either be a python filename ending in .py or None
    if candidate is not None:
        assert candidate.endswith(".py")
        assert not candidate.startswith("__")


def test_prune_failing_tests() -> None:
    code = """
def test_passing_one():
    assert 1 == 1

def test_failing_one():
    assert 1 == 2

def test_passing_two():
    assert True
"""
    pruned = _prune_failing_tests(code, ["test_failing_one"])
    assert pruned is not None
    assert "test_failing_one" not in pruned
    assert "test_passing_one" in pruned
    assert "test_passing_two" in pruned


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, timeout=60
    )


@pytest.fixture
def sandbox_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway git repo wired up as self_improve's target.

    The cycle runs real `git checkout`/`add`/`commit`, so it needs a real repo.
    Pointing the module at a temp one keeps the test off this repository's own
    branches and makes the pre-commit hook something the test controls.
    """
    repo = tmp_path / "repo"
    core = repo / "saleha" / "core"
    tests = repo / "saleha" / "tests"
    core.mkdir(parents=True)
    tests.mkdir(parents=True)
    (core / "widget.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")

    _git(str(repo), "init", "-b", "main")
    _git(str(repo), "config", "user.email", "test@example.com")
    _git(str(repo), "config", "user.name", "Test")
    _git(str(repo), "add", "-A")
    _git(str(repo), "commit", "-m", "seed")

    monkeypatch.setattr(self_improve, "REPO_ROOT", str(repo))
    monkeypatch.setattr(self_improve, "CORE_DIR", str(core))
    monkeypatch.setattr(self_improve, "TEST_DIR", str(tests))
    monkeypatch.setattr(self_improve, "LOG_PATH", str(tmp_path / "log.jsonl"))
    monkeypatch.setattr(
        self_improve, "_run",
        lambda cmd, cwd=str(repo): subprocess.run(
            cmd, cwd=str(repo), capture_output=True, text=True, timeout=120
        ),
    )
    # A passing test, so the cycle always reaches the git stage.
    monkeypatch.setattr(
        self_improve, "_generate_test_source",
        lambda module_filename, public_symbols=None: (
            "def test_generated():\n    assert True\n", "fake-model"
        ),
    )
    return repo


def _block_commits(repo: Path) -> None:
    """Installs a pre-commit hook that always rejects, like this repo's own
    quality gate does when it cannot run."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'COMMIT BLOCKED by gate'\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)


def test_blocked_commit_is_not_reported_as_committed(sandbox_repo: Path) -> None:
    """A pre-commit hook rejecting the commit used to be reported as success,
    because the commit's return code was never checked and `git rev-parse HEAD`
    then returned the PREVIOUS commit's sha."""
    _block_commits(sandbox_repo)
    head_before = _git(str(sandbox_repo), "rev-parse", "HEAD").stdout.strip()

    result = self_improve.run_self_improvement_cycle()

    assert result.status == "commit_failed", (
        f"blocked commit reported as {result.status!r}"
    )
    assert result.commit_sha is None
    assert result.detail.strip() != "committed"
    # The stale-sha symptom specifically: never report the pre-existing HEAD.
    assert head_before not in (result.commit_sha or "")


def test_blocked_commit_leaves_no_file_on_the_working_branch(sandbox_repo: Path) -> None:
    """The generated test used to be left written and staged on the branch the
    cycle started from -- the branch the safety rails promise never to touch."""
    _block_commits(sandbox_repo)

    self_improve.run_self_improvement_cycle()

    assert _git(str(sandbox_repo), "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    assert _git(str(sandbox_repo), "status", "--short").stdout.strip() == ""
    assert not (sandbox_repo / "saleha" / "tests" / "test_widget.py").exists()


def test_successful_commit_lands_on_the_auto_branch(sandbox_repo: Path) -> None:
    """The success path must still work, and must report a real new sha."""
    head_before = _git(str(sandbox_repo), "rev-parse", "HEAD").stdout.strip()

    result = self_improve.run_self_improvement_cycle()

    assert result.status == "committed", result.detail
    assert result.commit_sha and result.commit_sha != head_before
    assert result.branch == self_improve.BRANCH_NAME
    # Returned to the starting branch, and the commit is on the auto branch.
    assert _git(str(sandbox_repo), "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    listed = _git(
        str(sandbox_repo), "ls-tree", "-r", "--name-only",
        self_improve.BRANCH_NAME, "--", "saleha/tests",
    ).stdout
    assert "test_widget.py" in listed
    assert not (sandbox_repo / "saleha" / "tests" / "test_widget.py").exists()


def test_run_self_improvement_batch_success(sandbox_repo: Path) -> None:
    results = self_improve.run_self_improvement_batch(cycles=2)
    assert len(results) == 2
    assert results[0].status == "committed"
    assert results[1].status == "no_candidate"


def test_run_self_improvement_batch_skips_persistent_failures(
    sandbox_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        self_improve, "_generate_test_source",
        lambda module_filename, public_symbols=None: (None, None),
    )
    results = self_improve.run_self_improvement_batch(cycles=3, max_tries_per_module=2)
    assert len(results) == 3
    assert results[0].status == "generation_failed"
    assert results[1].status == "generation_failed"
    assert results[2].status == "no_candidate"


def test_get_self_improvement_status_structure(sandbox_repo: Path) -> None:
    status = self_improve.get_self_improvement_status()
    assert isinstance(status, dict)
    assert "total_core_modules" in status
    assert "tested_modules_count" in status
    assert "untested_modules_count" in status
    assert "test_coverage_pct" in status
    assert status["total_core_modules"] >= 1

