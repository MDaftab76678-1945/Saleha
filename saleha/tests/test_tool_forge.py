"""Unit tests for saleha.core.tool_forge module."""

import os
import subprocess
import tempfile
from typing import List

from saleha.core.tool_forge import (
    ToolSpecification,
    ToolForgeResult,
    ToolForge,
    BUILTIN_TOOL_CATALOG,
    _clean_code_fence,
)


def _run_git(args: List[str], cwd: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, env=env)


def test_tool_specification_dataclass() -> None:
    spec = ToolSpecification(
        name="test_tool",
        class_name="TestTool",
        description="A test tool",
        parameters={"type": "object"},
        domain="testing",
    )
    assert spec.name == "test_tool"
    assert spec.class_name == "TestTool"
    assert spec.domain == "testing"


def test_clean_code_fence() -> None:
    fenced = "```python\nclass Foo:\n    pass\n```"
    assert _clean_code_fence(fenced) == "class Foo:\n    pass"

    plain = "class Foo:\n    pass"
    assert _clean_code_fence(plain) == plain


def test_tool_forge_catalog_and_missing() -> None:
    forge = ToolForge()
    assert len(BUILTIN_TOOL_CATALOG) >= 4
    missing = forge.get_missing_catalog_tools()
    # Built-in catalog tools that are not yet created should be in missing list
    names = [s.name for s in missing]
    assert "env_inspector" in names or "text_pattern_finder" in names
    # Implemented tools should no longer be missing
    assert "ast_inspector" not in names
    assert "git_status_auditor" not in names


def test_tool_forge_result_dataclass() -> None:
    res = ToolForgeResult(
        timestamp="2026-09-08 04:30:00",
        tool_name="sample_tool",
        status="created",
        detail="Tool created successfully",
        tool_path="saleha/tools/sample_tool.py",
        test_path="saleha/tests/test_tool_sample_tool.py",
        commit_sha="1234567",
    )
    assert res.status == "created"
    assert res.tool_name == "sample_tool"
    assert res.commit_sha == "1234567"


def test_find_reference_tool_source_returns_shortest_other_tool() -> None:
    forge = ToolForge()
    tmp_dir = tempfile.mkdtemp()
    forge.tools_dir = tmp_dir
    try:
        with open(os.path.join(tmp_dir, "base.py"), "w", encoding="utf-8") as f:
            f.write("# base, must be excluded\n")
        with open(os.path.join(tmp_dir, "_private.py"), "w", encoding="utf-8") as f:
            f.write("# underscore-prefixed, must be excluded\n")
        with open(os.path.join(tmp_dir, "long_tool.py"), "w", encoding="utf-8") as f:
            f.write("# a longer existing tool\n" * 20)
        with open(os.path.join(tmp_dir, "short_tool.py"), "w", encoding="utf-8") as f:
            f.write("# short existing tool\n")

        ref = forge._find_reference_tool_source(exclude_name="new_tool")
        assert ref == "# short existing tool\n"
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_find_reference_tool_source_excludes_the_tool_being_built() -> None:
    forge = ToolForge()
    tmp_dir = tempfile.mkdtemp()
    forge.tools_dir = tmp_dir
    try:
        with open(os.path.join(tmp_dir, "existing.py"), "w", encoding="utf-8") as f:
            f.write("# existing tool\n")
        with open(os.path.join(tmp_dir, "being_built.py"), "w", encoding="utf-8") as f:
            f.write("x\n")  # shorter, but must not reference itself as its own example

        ref = forge._find_reference_tool_source(exclude_name="being_built")
        assert ref == "# existing tool\n"
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_find_reference_tool_source_returns_none_when_no_tools_exist() -> None:
    forge = ToolForge()
    tmp_dir = tempfile.mkdtemp()
    forge.tools_dir = tmp_dir
    try:
        assert forge._find_reference_tool_source(exclude_name="anything") is None
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_validate_tool_and_test_success() -> None:
    forge = ToolForge()
    valid_tool_code = """
from saleha.tools.base import BaseTool, ToolResult

class MathAddTool(BaseTool):
    name = "math_add"
    description = "Adds two numbers"
    parameters = {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"]
    }

    def execute(self, **kwargs):
        a = kwargs.get("a", 0)
        b = kwargs.get("b", 0)
        return ToolResult(success=True, data={"result": a + b})
"""

    valid_test_code = """
from saleha.tools.math_add import MathAddTool

def test_math_add_execution():
    tool = MathAddTool()
    res = tool.execute(a=2, b=3)
    assert res.success is True
    assert res.data == {"result": 5}
"""

    passed, _, _, detail = forge.validate_tool_and_test(
        tool_name="math_add",
        tool_code=valid_tool_code,
        test_code=valid_test_code,
    )
    assert passed is True, f"validate_tool_and_test failed, detail: {detail}"
    assert "passed" in detail.lower()


def test_validate_tool_and_test_failure() -> None:
    forge = ToolForge()
    broken_tool_code = """
from saleha.tools.base import BaseTool, ToolResult

class BrokenTool(BaseTool):
    name = "broken"
    description = "Broken"

    def execute(self, **kwargs):
        raise RuntimeError("Crashed on purpose")
"""

    failing_test_code = """
from saleha.tools.broken import BrokenTool

def test_broken():
    tool = BrokenTool()
    res = tool.execute()
    assert res.success is True
"""

    passed, _, _, detail = forge.validate_tool_and_test(
        tool_name="broken",
        tool_code=broken_tool_code,
        test_code=failing_test_code,
    )
    assert passed is False
    assert "failed" in detail.lower()


def _init_temp_repo() -> str:
    """Creates a real, throwaway git repo with one commit and no hooks."""
    repo_dir = tempfile.mkdtemp()
    _run_git(["init"], cwd=repo_dir)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo_dir)
    _run_git(["config", "user.name", "Test"], cwd=repo_dir)
    seed_path = os.path.join(repo_dir, "seed.txt")
    with open(seed_path, "w", encoding="utf-8") as f:
        f.write("seed\n")
    _run_git(["add", "seed.txt"], cwd=repo_dir)
    _run_git(["commit", "-m", "seed commit"], cwd=repo_dir)
    return repo_dir


def test_commit_synthesized_files_succeeds_on_clean_repo() -> None:
    """Baseline: a real git add + commit that succeeds reports status=created
    with the SHA of the commit it actually made."""
    repo_dir = _init_temp_repo()
    head_before = _run_git(["rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()

    tool_path = os.path.join(repo_dir, "my_tool.py")
    test_path = os.path.join(repo_dir, "test_my_tool.py")
    with open(tool_path, "w", encoding="utf-8") as f:
        f.write("# tool\n")
    with open(test_path, "w", encoding="utf-8") as f:
        f.write("# test\n")

    forge = ToolForge()
    sha, status, detail = forge._commit_synthesized_files(
        tool_path, test_path, "my_tool", repo_root=repo_dir
    )

    assert status == "created"
    assert sha is not None
    assert sha != head_before
    head_after = _run_git(["rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
    assert sha == head_after


def test_commit_synthesized_files_reports_failure_when_add_fails() -> None:
    """git add on a path outside the repo must fail, and the failure must be
    reported honestly -- not silently treated as status=created.

    This is the exact bug that used to exist: forge_tool() never checked the
    return code of 'git add' / 'git commit', so a failed commit still came
    back as status="created", tests_passed=True, with commit_sha silently
    left as the *prior* commit's SHA (from 'git rev-parse HEAD' succeeding
    even though nothing new was committed).
    """
    repo_dir = _init_temp_repo()
    head_before = _run_git(["rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()

    # A path outside repo_dir entirely: os.path.relpath() will produce a
    # pathspec git cannot match ("git add" -> exit 128).
    outside_dir = tempfile.mkdtemp()
    tool_path = os.path.join(outside_dir, "my_tool.py")
    test_path = os.path.join(outside_dir, "test_my_tool.py")
    with open(tool_path, "w", encoding="utf-8") as f:
        f.write("# tool\n")
    with open(test_path, "w", encoding="utf-8") as f:
        f.write("# test\n")

    forge = ToolForge()
    sha, status, detail = forge._commit_synthesized_files(
        tool_path, test_path, "my_tool", repo_root=repo_dir
    )

    assert status == "commit_failed"
    assert sha is None
    assert "git add" in detail.lower()

    # HEAD must not have moved, and no fabricated SHA is returned.
    head_after = _run_git(["rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
    assert head_after == head_before


def test_commit_synthesized_files_reports_failure_when_hook_rejects() -> None:
    """A pre-commit hook that rejects the commit (returns non-zero) must
    produce status=commit_failed with commit_sha=None -- not the SHA of the
    seed commit that 'git rev-parse HEAD' would still happily return.
    """
    repo_dir = _init_temp_repo()
    head_before = _run_git(["rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()

    # Install a pre-commit hook that always rejects, simulating this repo's
    # own preflight quality gate rejecting model-generated code.
    hooks_dir = os.path.join(repo_dir, ".git", "hooks")
    hook_path = os.path.join(hooks_dir, "pre-commit")
    with open(hook_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\necho 'rejected by quality gate' >&2\nexit 1\n")
    os.chmod(hook_path, 0o755)

    tool_path = os.path.join(repo_dir, "my_tool.py")
    test_path = os.path.join(repo_dir, "test_my_tool.py")
    with open(tool_path, "w", encoding="utf-8") as f:
        f.write("# tool\n")
    with open(test_path, "w", encoding="utf-8") as f:
        f.write("# test\n")

    forge = ToolForge()
    sha, status, detail = forge._commit_synthesized_files(
        tool_path, test_path, "my_tool", repo_root=repo_dir
    )

    assert status == "commit_failed"
    assert sha is None
    assert "commit" in detail.lower()

    head_after = _run_git(["rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
    assert head_after == head_before
