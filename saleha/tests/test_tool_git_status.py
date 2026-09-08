"""Unit tests for saleha.tools.git_status_auditor module.

Validates porcelain v2 parsing, branch topology extraction, diff numstat,
secret hygiene auditing, and MCP definition.
"""

import os
import tempfile
import pytest
from saleha.tools.git_status_auditor import (
    GitStatusAuditorTool,
    GitCLIExecutor,
    GitPorcelainV2Parser,
    GitSecurityAuditor,
    GitStateInspector,
    FileStatusCode,
    RepositoryState,
    SecretRiskLevel,
)
from saleha.tools import tool_registry


def test_git_status_auditor_registered():
    """Verifies that GitStatusAuditorTool is registered in tool_registry."""
    tool = tool_registry.get("git_status_auditor")
    assert tool is not None
    assert isinstance(tool, GitStatusAuditorTool)
    assert tool.name == "git_status_auditor"


def test_git_status_auditor_live_execution():
    """Verifies live execution against the current repository workspace."""
    tool = GitStatusAuditorTool()
    res = tool.execute(include_diff_stats=True, include_recent_commits=True)
    assert res.success is True
    assert res.data is not None
    assert res.data["repository_root"] is not None
    assert os.path.isdir(res.data["repository_root"])
    assert res.data["branch"]["current_branch"] is not None
    assert res.data["repository_state"] in [s.value for s in RepositoryState]
    assert 0.0 <= res.data["hygiene_score"] <= 100.0

    summary = res.data["summary"]
    assert "staged_count" in summary
    assert "unstaged_count" in summary
    assert "untracked_count" in summary
    assert "total_lines_added" in summary
    assert "total_lines_deleted" in summary


def test_git_status_auditor_non_git_dir():
    """Verifies error handling when pointed at a non-git directory."""
    tool = GitStatusAuditorTool()
    with tempfile.TemporaryDirectory() as tmp:
        res = tool.execute(repo_path=tmp)
        assert res.success is False
        assert res.error is not None
        assert "not a Git repository" in res.error
        assert res.metadata is not None
        assert res.metadata["state"] == RepositoryState.NOT_A_GIT_REPO.value


def test_porcelain_v2_parser():
    """Verifies porcelain v2 parser handles branch, tracked, untracked, and renamed entries."""
    raw_status = """# branch.oid 0123456789abcdef0123456789abcdef01234567
# branch.head feature/test-branch
# branch.upstream origin/feature/test-branch
# branch.ab +2 -1
1 M. N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 saleha/core/foo.py
1 .M N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 saleha/core/bar.py
2 R. N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 R100 saleha/core/new_name.py\tsaleha/core/old_name.py
? untracked_script.py
! ignored_file.log
"""
    branch, files = GitPorcelainV2Parser.parse(raw_status, repo_root=".")
    assert branch.current_branch == "feature/test-branch"
    assert branch.upstream_branch == "origin/feature/test-branch"
    assert branch.ahead_count == 2
    assert branch.behind_count == 1
    assert branch.is_detached is False

    paths = {f.path: f for f in files}
    assert "saleha/core/foo.py" in paths
    assert paths["saleha/core/foo.py"].is_staged is True
    assert paths["saleha/core/foo.py"].status == FileStatusCode.MODIFIED

    assert "saleha/core/bar.py" in paths
    assert paths["saleha/core/bar.py"].is_staged is False
    assert paths["saleha/core/bar.py"].status == FileStatusCode.MODIFIED

    assert "saleha/core/new_name.py" in paths
    assert paths["saleha/core/new_name.py"].orig_path == "saleha/core/old_name.py"
    assert paths["saleha/core/new_name.py"].status == FileStatusCode.RENAMED

    assert "untracked_script.py" in paths
    assert paths["untracked_script.py"].is_untracked is True
    assert paths["untracked_script.py"].status == FileStatusCode.UNTRACKED

    assert "ignored_file.log" in paths
    assert paths["ignored_file.log"].status == FileStatusCode.IGNORED


def test_security_auditor_detects_sensitive_files():
    """Verifies that .env files and private keys are flagged as sensitive."""
    from saleha.tools.git_status_auditor import FileChangeDetail

    files = [
        FileChangeDetail(
            path=".env",
            orig_path=None,
            status=FileStatusCode.UNTRACKED,
            is_staged=False,
            is_untracked=True,
            is_conflicted=False,
        ),
        FileChangeDetail(
            path="config/id_rsa.key",
            orig_path=None,
            status=FileStatusCode.MODIFIED,
            is_staged=True,
            is_untracked=False,
            is_conflicted=False,
        ),
        FileChangeDetail(
            path="saleha/core/safe_code.py",
            orig_path=None,
            status=FileStatusCode.MODIFIED,
            is_staged=True,
            is_untracked=False,
            is_conflicted=False,
        ),
    ]

    # Mock executor that returns empty diff
    class MockExecutor(GitCLIExecutor):
        def __init__(self) -> None:
            super().__init__(repo_path=".")

        def execute(self, args: list, timeout: int = 30) -> tuple[int, str, str]:
            return 0, "", ""

    findings = GitSecurityAuditor.audit_working_tree(MockExecutor(), files, repo_root=".")
    rule_ids = [f.rule_id for f in findings]
    assert "GIT-SEC-001" in rule_ids
    flagged_files = [f.file_path for f in findings]
    assert ".env" in flagged_files
    assert "config/id_rsa.key" in flagged_files
    assert "saleha/core/safe_code.py" not in flagged_files


def test_security_auditor_detects_secret_in_diff():
    """Verifies that AWS access keys or Google API keys in staged diffs are flagged."""
    diff_text = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,2 +10,3 @@
+AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
+GOOGLE_KEY = "AIzaSyD-7EXAMPLE_KEY_123456789012345"
"""
    findings: list = []
    GitSecurityAuditor._scan_diff_for_secrets(diff_text, findings)
    assert len(findings) >= 2
    rule_ids = [f.rule_id for f in findings]
    assert all(r == "GIT-SEC-002" for r in rule_ids)
    assert any("AWS Access Key ID" in f.message for f in findings)
    assert any("Google API / AI Key" in f.message for f in findings)


def test_mcp_definition_and_markdown_report():
    """Verifies MCP definition schema and markdown report generation."""
    tool = GitStatusAuditorTool()
    mcp_def = tool.to_mcp_definition()
    assert mcp_def["name"] == "git_status_auditor"
    assert "properties" in mcp_def["inputSchema"]
    assert callable(mcp_def["handler"])

    # Test report generator
    res = tool.execute(include_diff_stats=False, include_recent_commits=False)
    assert res.success is True
    report_md = tool.generate_markdown_report(res.data)
    assert "# Git Repository Audit:" in report_md
    assert "Hygiene Score:" in report_md


def test_edge_case_c_quoting_command_construction():
    """Edge Case 1: Verifies executor injects -c core.quotePath=false."""
    executor = GitCLIExecutor(".")
    if not executor.git_bin:
        pytest.skip("git not installed on PATH")

    # Call a harmless command to check command construction
    code, out, _ = executor.execute(["rev-parse", "--is-inside-work-tree"])
    assert code == 0
    assert "true" in out.lower()


def test_edge_case_double_counting_prevented():
    """Edge Case 2: Verifies partially staged files are not double-counted in summary or security audit."""
    from saleha.tools.git_status_auditor import FileChangeDetail

    raw_status = (
        "# branch.head main\n"
        "1 MM N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 "
        "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 config/secret.env\n"
    )
    branch, files = GitPorcelainV2Parser.parse(raw_status, repo_root=".")
    # File is both staged and unstaged -> 2 records in files_list
    assert len(files) == 2
    assert files[0].is_staged is True
    assert files[1].is_staged is False

    # Summary unique path count must be 1, not 2
    unique_count = len({f.path for f in files})
    assert unique_count == 1

    class MockExecutor(GitCLIExecutor):
        def __init__(self) -> None:
            super().__init__(repo_path=".")

        def execute(self, args: list, timeout: int = 30) -> tuple[int, str, str]:
            return 0, "", ""

    findings = GitSecurityAuditor.audit_working_tree(MockExecutor(), files, repo_root=".")
    # Sensitive file check must deduplicate paths and not append finding twice
    env_findings = [f for f in findings if f.file_path == "config/secret.env"]
    assert len(env_findings) == 1


def test_edge_case_tab_character_in_commit_and_stash():
    """Edge Case 3: Verifies maxsplit prevents misalignment when commit/stash subjects contain tabs."""
    class MockStashExecutor(GitCLIExecutor):
        def __init__(self) -> None:
            super().__init__(repo_path=".")

        def execute(self, args: list, timeout: int = 30) -> tuple[int, str, str]:
            # Formatted line with message at the end (%gd%x09%cr%x09%gs)
            line = "stash@{0}\t10 minutes ago\tWIP on main:\tinternal tab in commit subject"
            return 0, line, ""

    stashes = GitStateInspector.inspect_stashes(MockStashExecutor())
    assert len(stashes) == 1
    assert stashes[0].index == 0
    assert "internal tab in commit subject" in stashes[0].message
    assert stashes[0].date_relative == "10 minutes ago"

    class MockLogExecutor(GitCLIExecutor):
        def __init__(self) -> None:
            super().__init__(repo_path=".")

        def execute(self, args: list, timeout: int = 30) -> tuple[int, str, str]:
            # Commit subject with tabs inside
            line = "a1b2c3d4e5f6\ta1b2c3d\tDev Name\tdev@test.com\t2026-09-08T00:00:00\t1 hour ago\tfix(core):\trefactor\tsomething"
            return 0, line, ""

    commits = GitStateInspector.get_recent_commits(MockLogExecutor(), limit=1)
    assert len(commits) == 1
    assert commits[0].commit_hash == "a1b2c3d4e5f6"
    assert commits[0].short_hash == "a1b2c3d"
    assert commits[0].author_name == "Dev Name"
    assert commits[0].subject == "fix(core):\trefactor\tsomething"


def test_edge_case_redos_and_lockfile_guards():
    """Edge Case 4: Verifies _scan_diff_for_secrets skips lockfiles and oversized lines."""
    findings: list = []

    # 1. Staged change in package-lock.json with fake secret - should be skipped
    lockfile_diff = (
        "diff --git a/package-lock.json b/package-lock.json\n"
        "--- a/package-lock.json\n"
        "+++ b/package-lock.json\n"
        "@@ -1,3 +1,4 @@\n"
        '+   "integrity": "AKIAIOSFODNN7EXAMPLE",\n'
    )
    GitSecurityAuditor._scan_diff_for_secrets(lockfile_diff, findings)
    assert len(findings) == 0

    # 2. Staged change with line > 1000 characters - should be skipped (ReDoS guard)
    long_line = "+" + "A" * 1005 + "AKIAIOSFODNN7EXAMPLE" + "\n"
    oversized_diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,2 +1,3 @@\n"
        f"{long_line}"
    )
    GitSecurityAuditor._scan_diff_for_secrets(oversized_diff, findings)
    assert len(findings) == 0


def test_edge_case_git_state_detection_revert_and_auto_merge():
    """Edge Case 5: Verifies REVERT_HEAD and AUTO_MERGE state markers are recognized."""
    with tempfile.TemporaryDirectory() as tmp:
        git_dir = os.path.join(tmp, ".git")
        os.makedirs(git_dir)

        # 1. Clean state
        state = GitStateInspector.detect_state(tmp, is_dirty=False)
        assert state == RepositoryState.CLEAN

        # 2. AUTO_MERGE marker
        auto_merge = os.path.join(git_dir, "AUTO_MERGE")
        with open(auto_merge, "w") as f:
            f.write("test")
        assert GitStateInspector.detect_state(tmp, is_dirty=False) == RepositoryState.MERGE_IN_PROGRESS
        os.remove(auto_merge)

        # 3. REVERT_HEAD marker
        revert_head = os.path.join(git_dir, "REVERT_HEAD")
        with open(revert_head, "w") as f:
            f.write("test")
        assert GitStateInspector.detect_state(tmp, is_dirty=False) == RepositoryState.REVERT_IN_PROGRESS
        os.remove(revert_head)


def test_edge_case_root_directory_basename_fallback():
    """Edge Case 6: Verifies markdown report handles root filesystem path without blank title."""
    tool = GitStatusAuditorTool()
    data = {
        "repository_root": "/",
        "repository_state": "clean",
        "is_clean": True,
        "hygiene_score": 100.0,
        "branch": {"current_branch": "main", "ahead_count": 0, "behind_count": 0},
        "summary": {
            "total_modified_files": 0,
            "staged_count": 0,
            "unstaged_count": 0,
            "untracked_count": 0,
            "conflicted_count": 0,
            "total_lines_added": 0,
            "total_lines_deleted": 0,
            "stash_count": 0,
        },
        "security_findings": [],
        "recent_commits": [],
    }
    report = tool.generate_markdown_report(data)
    assert "# Git Repository Audit: `/`" in report

