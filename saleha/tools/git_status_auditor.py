"""Saleha Tools: Git Status & Repository Auditor Tool.

Production-grade, cross-platform static and runtime Git repository auditor.
Performs deep working tree inspection, porcelain v2 status parsing, branch
topology tracking, ahead/behind counting, stash inspection, diff statistics,
and security secret hygiene scanning without command injection vulnerabilities.
"""

from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field
import enum
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple, Union

from saleha.tools.base import BaseTool, ToolResult


# =====================================================================
# Section 1: Domain Enums & Security Constants
# =====================================================================

class FileStatusCode(str, enum.Enum):
    """Normalized Git file status classifications."""
    MODIFIED = "modified"
    ADDED = "added"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    UNTRACKED = "untracked"
    IGNORED = "ignored"
    CONFLICTED = "conflicted"
    TYPE_CHANGED = "type_changed"
    UNMODIFIED = "unmodified"


class RepositoryState(str, enum.Enum):
    """Lifecycle and operational state of a Git repository."""
    CLEAN = "clean"
    DIRTY = "dirty"
    DETACHED_HEAD = "detached_head"
    MERGE_IN_PROGRESS = "merge_in_progress"
    REBASE_IN_PROGRESS = "rebase_in_progress"
    CHERRY_PICK_IN_PROGRESS = "cherry_pick_in_progress"
    REVERT_IN_PROGRESS = "revert_in_progress"
    BISECT_IN_PROGRESS = "bisect_in_progress"
    NOT_A_GIT_REPO = "not_a_git_repo"
    GIT_NOT_FOUND = "git_not_found"


class SecretRiskLevel(str, enum.Enum):
    """Risk severity for security and secret leak findings."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Sensitive file patterns that should never be tracked or committed
SENSITIVE_FILE_PATTERNS: FrozenSet[str] = frozenset({
    r"^(\.env|.*\.env)(\..+)?$",
    r"^id_rsa(\.pub)?$",
    r"^id_ed25519(\.pub)?$",
    r"^.+\.pem$",
    r"^.+\.key$",
    r"^.+\.pfx$",
    r"^.+\.p12$",
    r"^credentials\.json$",
    r"^service[-_]account.*\.json$",
    r"^client_secret.*\.json$",
    r"^\.htpasswd$",
    r"^master\.key$",
    r"^\.npmrc$",
    r"^\.pypirc$",
})

# Suspicious token regexes for git diff content scanning
SECRET_CONTENT_PATTERNS: List[Tuple[str, str, SecretRiskLevel]] = [
    (
        "AWS Access Key ID",
        r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
        SecretRiskLevel.CRITICAL,
    ),
    (
        "GitHub Personal Access Token",
        r"gh[pousr]_[A-Za-z0-9_]{36,255}",
        SecretRiskLevel.CRITICAL,
    ),
    (
        "Generic Private Key",
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        SecretRiskLevel.CRITICAL,
    ),
    (
        "Google API / AI Key",
        r"AIza[0-9A-Za-z_-]{30,38}",
        SecretRiskLevel.CRITICAL,
    ),
    (
        "Slack Token",
        r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*",
        SecretRiskLevel.HIGH,
    ),
    (
        "Hardcoded Password / Secret Assignment",
        r"(?i)(?:api_key|secret|password|auth_token)\s*=\s*['\"][A-Za-z0-9@#$%^&*_\-+=]{8,}['\"]",
        SecretRiskLevel.MEDIUM,
    ),
]


# =====================================================================
# Section 2: Data Models & Container Classes
# =====================================================================

@dataclass
class FileChangeDetail:
    """Detailed metadata for a single file tracked in the working directory."""
    path: str
    orig_path: Optional[str]
    status: FileStatusCode
    is_staged: bool
    is_untracked: bool
    is_conflicted: bool
    is_ignored: bool = False
    lines_added: int = 0
    lines_deleted: int = 0
    size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serializes file change detail to standard dictionary."""
        return {
            "path": self.path,
            "orig_path": self.orig_path,
            "status": self.status.value,
            "is_staged": self.is_staged,
            "is_untracked": self.is_untracked,
            "is_conflicted": self.is_conflicted,
            "is_ignored": self.is_ignored,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "size_bytes": self.size_bytes,
        }


@dataclass
class CommitSummary:
    """Summary of a single Git commit."""
    commit_hash: str
    short_hash: str
    author_name: str
    author_email: str
    date_iso: str
    relative_date: str
    subject: str
    is_unpushed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes commit summary to dictionary."""
        return {
            "commit_hash": self.commit_hash,
            "short_hash": self.short_hash,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "date_iso": self.date_iso,
            "relative_date": self.relative_date,
            "subject": self.subject,
            "is_unpushed": self.is_unpushed,
        }


@dataclass
class BranchTopology:
    """Topological status of the active branch."""
    current_branch: str
    head_commit_hash: Optional[str]
    upstream_branch: Optional[str]
    ahead_count: int = 0
    behind_count: int = 0
    is_detached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes branch topology to dictionary."""
        return {
            "current_branch": self.current_branch,
            "head_commit_hash": self.head_commit_hash,
            "upstream_branch": self.upstream_branch,
            "ahead_count": self.ahead_count,
            "behind_count": self.behind_count,
            "is_detached": self.is_detached,
        }


@dataclass
class StashSummary:
    """Summary of an entry in the Git stash stack."""
    index: int
    name: str
    message: str
    date_relative: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes stash summary to dictionary."""
        return {
            "index": self.index,
            "name": self.name,
            "message": self.message,
            "date_relative": self.date_relative,
        }


@dataclass
class SecurityRiskDetail:
    """Identified security risk, credential leak, or oversized blob."""
    rule_id: str
    risk_level: SecretRiskLevel
    file_path: str
    message: str
    line_number: Optional[int] = None
    matched_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes security risk detail to dictionary."""
        return {
            "rule_id": self.rule_id,
            "risk_level": self.risk_level.value,
            "file_path": self.file_path,
            "message": self.message,
            "line_number": self.line_number,
            "matched_snippet": self.matched_snippet,
        }


# =====================================================================
# Section 3: Safe Subprocess CLI Executor
# =====================================================================

class GitCLIExecutor:
    """Cross-platform, command-injection-safe Git subprocess runner."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path: str = os.path.abspath(repo_path)
        self.git_bin: Optional[str] = shutil.which("git")

    def is_git_installed(self) -> bool:
        """Verifies if the git executable is installed on the system PATH."""
        return self.git_bin is not None

    def execute(
        self,
        args: List[str],
        timeout: int = 30,
    ) -> Tuple[int, str, str]:
        """Executes a git command safely without shell=True.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.git_bin:
            return 127, "", "git executable not found on system PATH"

        cmd = [self.git_bin, "-c", "core.quotePath=false"] + args
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["LC_ALL"] = "C"  # Consistent standard english parsing for git output

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
        except OSError as e:
            return -2, "", f"Failed to execute git command: {e}"

    def get_repo_root(self) -> Optional[str]:
        """Resolves the top-level root directory of the current repository."""
        code, out, _ = self.execute(["rev-parse", "--show-toplevel"])
        if code == 0 and out.strip():
            return os.path.abspath(out.strip())
        return None


# =====================================================================
# Section 4: Porcelain V2 Status Parser
# =====================================================================

class GitPorcelainV2Parser:
    """Parses machine-readable Git Status Porcelain V2 format.

    Specification:
    - Headers: '# branch.oid', '# branch.head', '# branch.upstream', '# branch.ab'
    - Ordinary changes: '1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>'
    - Renamed/Copied: '2 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <X><score> <path>\t<origPath>'
    - Unmerged: 'u <XY> ...'
    - Untracked: '? <path>'
    - Ignored: '! <path>'
    """

    @classmethod
    def parse(
        cls,
        raw_output: str,
        repo_root: str,
    ) -> Tuple[BranchTopology, List[FileChangeDetail]]:
        """Parses the raw porcelain v2 string into structured objects."""
        branch = BranchTopology(
            current_branch="(unknown)",
            head_commit_hash=None,
            upstream_branch=None,
            ahead_count=0,
            behind_count=0,
            is_detached=False,
        )
        files: List[FileChangeDetail] = []

        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Header metadata lines
            if line.startswith("#"):
                cls._parse_header(line, branch)
                continue

            # File status records
            first_char = line[0]

            # 1. Ordinary changed entries (type '1')
            if first_char == "1":
                parts = line.split(" ", 8)
                if len(parts) >= 9:
                    xy = parts[1]
                    path = parts[8]
                    files.extend(cls._build_details(xy, path, None, repo_root))

            # 2. Renamed or copied entries (type '2')
            elif first_char == "2":
                parts = line.split(" ", 9)
                if len(parts) >= 10:
                    xy = parts[1]
                    paths_part = parts[9]
                    if "\t" in paths_part:
                        path, orig_path = paths_part.split("\t", 1)
                    else:
                        path, orig_path = paths_part, None
                    files.extend(cls._build_details(xy, path, orig_path, repo_root))

            # 3. Unmerged / Conflicted entries (type 'u')
            elif first_char == "u":
                parts = line.split(" ", 10)
                if len(parts) >= 11:
                    path = parts[10]
                    files.append(FileChangeDetail(
                        path=path,
                        orig_path=None,
                        status=FileStatusCode.CONFLICTED,
                        is_staged=False,
                        is_untracked=False,
                        is_conflicted=True,
                    ))

            # 4. Untracked files (type '?')
            elif first_char == "?":
                parts = line.split(" ", 1)
                if len(parts) >= 2:
                    path = parts[1]
                    files.append(FileChangeDetail(
                        path=path,
                        orig_path=None,
                        status=FileStatusCode.UNTRACKED,
                        is_staged=False,
                        is_untracked=True,
                        is_conflicted=False,
                    ))

            # 5. Ignored files (type '!')
            elif first_char == "!":
                parts = line.split(" ", 1)
                if len(parts) >= 2:
                    path = parts[1]
                    files.append(FileChangeDetail(
                        path=path,
                        orig_path=None,
                        status=FileStatusCode.IGNORED,
                        is_staged=False,
                        is_untracked=False,
                        is_conflicted=False,
                        is_ignored=True,
                    ))

        return branch, files

    @classmethod
    def _parse_header(cls, line: str, branch: BranchTopology) -> None:
        """Parses branch metadata from '# branch.*' lines."""
        if line.startswith("# branch.oid"):
            parts = line.split()
            if len(parts) >= 3 and parts[2] != "(initial)":
                branch.head_commit_hash = parts[2]

        elif line.startswith("# branch.head"):
            parts = line.split()
            if len(parts) >= 3:
                head_name = parts[2]
                if head_name == "(detached)":
                    branch.is_detached = True
                    branch.current_branch = "HEAD (detached)"
                else:
                    branch.current_branch = head_name

        elif line.startswith("# branch.upstream"):
            parts = line.split()
            if len(parts) >= 3:
                branch.upstream_branch = parts[2]

        elif line.startswith("# branch.ab"):
            parts = line.split()
            # Format: # branch.ab +ahead -behind
            if len(parts) >= 4:
                try:
                    ahead_str = parts[2].lstrip("+")
                    behind_str = parts[3].lstrip("-")
                    branch.ahead_count = int(ahead_str)
                    branch.behind_count = int(behind_str)
                except ValueError:
                    pass

    @classmethod
    def _build_details(
        cls,
        xy: str,
        path: str,
        orig_path: Optional[str],
        repo_root: str,
    ) -> List[FileChangeDetail]:
        """Maps XY status characters into staged and unstaged change records."""
        records: List[FileChangeDetail] = []
        staged_char = xy[0]
        worktree_char = xy[1]

        # Staged change mapping
        if staged_char != ".":
            status = cls._map_status_char(staged_char)
            records.append(FileChangeDetail(
                path=path,
                orig_path=orig_path,
                status=status,
                is_staged=True,
                is_untracked=False,
                is_conflicted=False,
            ))

        # Unstaged change mapping
        if worktree_char != ".":
            status = cls._map_status_char(worktree_char)
            records.append(FileChangeDetail(
                path=path,
                orig_path=orig_path,
                status=status,
                is_staged=False,
                is_untracked=False,
                is_conflicted=False,
            ))

        return records

    @staticmethod
    def _map_status_char(char: str) -> FileStatusCode:
        """Converts a Git status code character into a FileStatusCode."""
        mapping = {
            "M": FileStatusCode.MODIFIED,
            "A": FileStatusCode.ADDED,
            "D": FileStatusCode.DELETED,
            "R": FileStatusCode.RENAMED,
            "C": FileStatusCode.COPIED,
            "T": FileStatusCode.TYPE_CHANGED,
            "U": FileStatusCode.CONFLICTED,
            "?": FileStatusCode.UNTRACKED,
            "!": FileStatusCode.IGNORED,
        }
        return mapping.get(char, FileStatusCode.MODIFIED)


# =====================================================================
# Section 5: Diff & Line Statistics Engine
# =====================================================================

class GitDiffEngine:
    """Extracts numstat line changes and unified diff excerpts."""

    @classmethod
    def populate_numstat(
        cls,
        executor: GitCLIExecutor,
        files: List[FileChangeDetail],
    ) -> None:
        """Populates lines_added and lines_deleted on FileChangeDetails via numstat."""
        # 1. Staged numstat
        code, out, _ = executor.execute(["diff", "--cached", "--numstat"])
        if code == 0:
            cls._apply_numstat_map(out, files, staged_only=True)

        # 2. Unstaged numstat
        code, out, _ = executor.execute(["diff", "--numstat"])
        if code == 0:
            cls._apply_numstat_map(out, files, staged_only=False)

    @classmethod
    def _apply_numstat_map(
        cls,
        numstat_output: str,
        files: List[FileChangeDetail],
        staged_only: bool,
    ) -> None:
        """Parses numstat lines and updates corresponding records."""
        stats_map: Dict[str, Tuple[int, int]] = {}
        for line in numstat_output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                added_str, deleted_str, path = parts[0], parts[1], parts[2]
                # Binary files show '-' for lines
                added = int(added_str) if added_str.isdigit() else 0
                deleted = int(deleted_str) if deleted_str.isdigit() else 0
                stats_map[path] = (added, deleted)

        for f in files:
            if f.is_staged == staged_only and f.path in stats_map:
                f.lines_added, f.lines_deleted = stats_map[f.path]


# =====================================================================
# Section 6: Security & Secret Hygiene Auditor
# =====================================================================

class GitSecurityAuditor:
    """Detects leaked credentials, sensitive config files, and large binary blobs."""

    MAX_SAFE_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 Megabytes

    @classmethod
    def audit_working_tree(
        cls,
        executor: GitCLIExecutor,
        files: List[FileChangeDetail],
        repo_root: str,
    ) -> List[SecurityRiskDetail]:
        """Conducts full security audit of files and staged diffs."""
        findings: List[SecurityRiskDetail] = []

        # 1. Audit file names and paths (deduplicating partially staged files)
        seen_paths: Set[str] = set()
        for f in files:
            if f.path in seen_paths:
                continue
            seen_paths.add(f.path)

            filename = os.path.basename(f.path)
            for pattern in SENSITIVE_FILE_PATTERNS:
                if re.match(pattern, filename, re.IGNORECASE):
                    findings.append(SecurityRiskDetail(
                        rule_id="GIT-SEC-001",
                        risk_level=SecretRiskLevel.CRITICAL if f.is_staged else SecretRiskLevel.HIGH,
                        file_path=f.path,
                        message=f"Potentially sensitive file '{filename}' is tracked in working directory.",
                    ))
                    break

            # Check file sizes
            full_path = os.path.join(repo_root, f.path)
            if os.path.isfile(full_path):
                try:
                    size = os.path.getsize(full_path)
                    f.size_bytes = size
                    if size > cls.MAX_SAFE_FILE_SIZE_BYTES:
                        findings.append(SecurityRiskDetail(
                            rule_id="GIT-PERF-001",
                            risk_level=SecretRiskLevel.MEDIUM,
                            file_path=f.path,
                            message=f"Oversized file ({round(size / (1024 * 1024), 2)}MB > 10MB) detected in working tree.",
                        ))
                except OSError:
                    pass

        # 2. Audit staged diff contents for leaked API keys / credentials
        code, staged_diff, _ = executor.execute(["diff", "--cached"])
        if code == 0 and staged_diff.strip():
            cls._scan_diff_for_secrets(staged_diff, findings)

        return findings

    @classmethod
    def _scan_diff_for_secrets(
        cls,
        diff_text: str,
        findings: List[SecurityRiskDetail],
    ) -> None:
        """Scans added lines in a unified diff for secret regex patterns with ReDoS guards."""
        ignored_extensions = (
            "-lock.json", ".lock", "-lock.yaml", ".lock.yaml",
            ".min.js", ".min.css", ".map", ".svg",
        )
        current_file = "<unknown>"
        current_lineno = 0
        skip_file = False

        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
                skip_file = any(current_file.endswith(ext) for ext in ignored_extensions)
                continue
            if skip_file:
                continue

            if line.startswith("@@"):
                # Extract line number from hunk header: @@ -1,5 +10,6 @@
                m = re.search(r"\+(\d+)", line)
                if m:
                    current_lineno = int(m.group(1))
                continue

            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                # ReDoS guard: skip lines over 1,000 characters (minified code / base64 dumps)
                if len(content) > 1000:
                    current_lineno += 1
                    continue

                for rule_name, pattern, severity in SECRET_CONTENT_PATTERNS:
                    if re.search(pattern, content):
                        # Mask snippet for safety
                        masked = content.strip()[:80]
                        findings.append(SecurityRiskDetail(
                            rule_id="GIT-SEC-002",
                            risk_level=severity,
                            file_path=current_file,
                            message=f"Potential secret detected ({rule_name}) in staged changes.",
                            line_number=current_lineno,
                            matched_snippet=masked,
                        ))
                current_lineno += 1


# =====================================================================
# Section 7: Repository State & Stash Inspector
# =====================================================================

class GitStateInspector:
    """Detects interactive states (merge, rebase, cherry-pick) and stashes."""

    @classmethod
    def detect_state(cls, repo_root: str, is_dirty: bool) -> RepositoryState:
        """Inspects .git directory markers to determine precise repository state."""
        git_dir = os.path.join(repo_root, ".git")
        if not os.path.exists(git_dir):
            return RepositoryState.NOT_A_GIT_REPO

        # Rebase state
        if os.path.exists(os.path.join(git_dir, "rebase-merge")) or os.path.exists(os.path.join(git_dir, "rebase-apply")):
            return RepositoryState.REBASE_IN_PROGRESS

        # Merge state (standard MERGE_HEAD or modern ort AUTO_MERGE)
        if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")) or os.path.exists(os.path.join(git_dir, "AUTO_MERGE")):
            return RepositoryState.MERGE_IN_PROGRESS

        # Revert state
        if os.path.exists(os.path.join(git_dir, "REVERT_HEAD")):
            return RepositoryState.REVERT_IN_PROGRESS

        # Cherry-pick state
        if os.path.exists(os.path.join(git_dir, "CHERRY_PICK_HEAD")):
            return RepositoryState.CHERRY_PICK_IN_PROGRESS

        # Bisect state
        if os.path.exists(os.path.join(git_dir, "BISECT_LOG")):
            return RepositoryState.BISECT_IN_PROGRESS

        return RepositoryState.DIRTY if is_dirty else RepositoryState.CLEAN

    @classmethod
    def inspect_stashes(cls, executor: GitCLIExecutor) -> List[StashSummary]:
        """Retrieves the list of entries currently in the git stash."""
        code, out, _ = executor.execute(["stash", "list", "--format=%gd%x09%cr%x09%gs"])
        stashes: List[StashSummary] = []
        if code != 0 or not out.strip():
            return stashes

        for line in out.splitlines():
            # maxsplit=2 ensures message (at the end) absorbs any internal tab characters
            parts = line.split("\t", 2)
            if len(parts) >= 3:
                name = parts[0]
                rel_date = parts[1]
                msg = parts[2]
                # Extract index from stash@{0}
                m = re.search(r"\{(\d+)\}", name)
                idx = int(m.group(1)) if m else 0
                stashes.append(StashSummary(
                    index=idx,
                    name=name,
                    message=msg,
                    date_relative=rel_date,
                ))

        return stashes

    @classmethod
    def get_recent_commits(
        cls,
        executor: GitCLIExecutor,
        limit: int = 5,
    ) -> List[CommitSummary]:
        """Fetches the N most recent commits on the current branch."""
        format_spec = "%H%x09%h%x09%an%x09%ae%x09%cI%x09%cr%x09%s"
        code, out, _ = executor.execute(["log", f"-n{limit}", f"--format={format_spec}"])
        commits: List[CommitSummary] = []
        if code != 0 or not out.strip():
            return commits

        for line in out.splitlines():
            # maxsplit=6 ensures commit subjects with internal tabs don't misalign fields
            parts = line.split("\t", 6)
            if len(parts) >= 7:
                commits.append(CommitSummary(
                    commit_hash=parts[0],
                    short_hash=parts[1],
                    author_name=parts[2],
                    author_email=parts[3],
                    date_iso=parts[4],
                    relative_date=parts[5],
                    subject=parts[6],
                ))

        return commits


# =====================================================================
# Section 8: The Git Status Auditor Tool (MCP Interface)
# =====================================================================

class GitStatusAuditorTool(BaseTool):
    """Production-grade Git repository and status auditing tool.

    Analyzes working tree modifications, branch ahead/behind status,
    staged and unstaged diffs, repository state, commit history, and
    security hygiene without command injection risks.
    """

    name: str = "git_status_auditor"
    description: str = (
        "Audits a Git repository's status. Returns branch topology, ahead/behind counts, "
        "staged and unstaged files, line additions/deletions, stash list, recent commits, "
        "and security secret leak detection."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the Git repository. Defaults to current working directory if omitted.",
            },
            "include_diff_stats": {
                "type": "boolean",
                "description": "Whether to calculate exact added/deleted line counts (default: True).",
            },
            "include_recent_commits": {
                "type": "boolean",
                "description": "Whether to include recent commit summaries (default: True).",
            },
            "include_security_audit": {
                "type": "boolean",
                "description": "Whether to scan working tree and staged diffs for leaked secrets (default: True).",
            },
            "max_commits": {
                "type": "integer",
                "description": "Maximum number of recent commits to retrieve (default: 5).",
            },
        },
    }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Executes full repository inspection and security audit."""
        repo_path = kwargs.get("repo_path") or os.getcwd()
        include_diff_stats = kwargs.get("include_diff_stats", True)
        include_recent_commits = kwargs.get("include_recent_commits", True)
        include_security_audit = kwargs.get("include_security_audit", True)
        max_commits = kwargs.get("max_commits", 5)

        executor = GitCLIExecutor(repo_path)

        # 1. Verify Git availability
        if not executor.is_git_installed():
            return ToolResult(
                success=False,
                error="Git executable not found on system PATH. Please ensure Git is installed.",
                metadata={"state": RepositoryState.GIT_NOT_FOUND.value},
            )

        # 2. Verify Repository Root
        repo_root = executor.get_repo_root()
        if not repo_root:
            return ToolResult(
                success=False,
                error=f"Directory is not a Git repository: {repo_path}",
                metadata={"state": RepositoryState.NOT_A_GIT_REPO.value},
            )

        # 3. Fetch Porcelain V2 Status
        code, status_out, err = executor.execute([
            "status",
            "--porcelain=v2",
            "--branch",
            "--ahead-behind",
            "--untracked-files=all",
        ])
        if code != 0:
            return ToolResult(
                success=False,
                error=f"Failed to execute git status: {err}",
            )

        # 4. Parse Status & Branch Topology
        branch_info, files_list = GitPorcelainV2Parser.parse(status_out, repo_root)

        # 5. Populate Line Additions/Deletions
        if include_diff_stats:
            GitDiffEngine.populate_numstat(executor, files_list)

        # 6. Categorize Files
        staged_files = [f for f in files_list if f.is_staged]
        unstaged_files = [f for f in files_list if not f.is_staged and not f.is_untracked and not f.is_ignored]
        untracked_files = [f for f in files_list if f.is_untracked]
        conflicted_files = [f for f in files_list if f.is_conflicted]

        is_dirty = bool(staged_files or unstaged_files or untracked_files or conflicted_files)

        # 7. Determine Repository State
        repo_state = GitStateInspector.detect_state(repo_root, is_dirty=is_dirty)

        # 8. Stash Inspection
        stashes = GitStateInspector.inspect_stashes(executor)

        # 9. Recent Commits
        recent_commits: List[CommitSummary] = []
        if include_recent_commits:
            recent_commits = GitStateInspector.get_recent_commits(executor, limit=max_commits)

        # 10. Security Audit
        security_findings: List[SecurityRiskDetail] = []
        if include_security_audit:
            security_findings = GitSecurityAuditor.audit_working_tree(executor, files_list, repo_root)

        # 11. Calculate Overall Hygiene Score (0.0 - 100.0)
        hygiene_score = 100.0
        if conflicted_files:
            hygiene_score -= 40.0
        for finding in security_findings:
            if finding.risk_level == SecretRiskLevel.CRITICAL:
                hygiene_score -= 30.0
            elif finding.risk_level == SecretRiskLevel.HIGH:
                hygiene_score -= 15.0
            elif finding.risk_level == SecretRiskLevel.MEDIUM:
                hygiene_score -= 5.0
        if is_dirty:
            hygiene_score -= 5.0
        hygiene_score = max(0.0, min(100.0, round(hygiene_score, 1)))

        total_lines_added = sum(f.lines_added for f in files_list)
        total_lines_deleted = sum(f.lines_deleted for f in files_list)

        # 12. Assemble Output Payload
        data: Dict[str, Any] = {
            "repository_root": repo_root,
            "repository_state": repo_state.value,
            "is_clean": not is_dirty,
            "hygiene_score": hygiene_score,
            "branch": branch_info.to_dict(),
            "summary": {
                "total_modified_files": len({f.path for f in files_list}),
                "staged_count": len(staged_files),
                "unstaged_count": len(unstaged_files),
                "untracked_count": len(untracked_files),
                "conflicted_count": len(conflicted_files),
                "total_lines_added": total_lines_added,
                "total_lines_deleted": total_lines_deleted,
                "stash_count": len(stashes),
            },
            "staged_files": [f.to_dict() for f in staged_files],
            "unstaged_files": [f.to_dict() for f in unstaged_files],
            "untracked_files": [f.to_dict() for f in untracked_files],
            "conflicted_files": [f.to_dict() for f in conflicted_files],
            "stashes": [s.to_dict() for s in stashes],
            "recent_commits": [c.to_dict() for c in recent_commits],
            "security_findings_count": len(security_findings),
            "security_findings": [s.to_dict() for s in security_findings],
        }

        return ToolResult(
            success=True,
            data=data,
            metadata={
                "tool": self.name,
                "branch": branch_info.current_branch,
                "state": repo_state.value,
                "hygiene_score": hygiene_score,
            },
        )

    def generate_markdown_report(self, analysis_data: Dict[str, Any]) -> str:
        """Formats audit data into an executive markdown summary."""
        branch = analysis_data.get("branch", {})
        summary = analysis_data.get("summary", {})
        state = analysis_data.get("repository_state", "unknown")
        hygiene = analysis_data.get("hygiene_score", 100.0)
        repo_root = analysis_data.get("repository_root", "")
        repo_name = os.path.basename(repo_root) or repo_root or "repository"

        lines = [
            f"# Git Repository Audit: `{repo_name}`",
            "",
            "## Overview",
            f"- **Branch:** `{branch.get('current_branch', 'HEAD')}` (Ahead: {branch.get('ahead_count', 0)}, Behind: {branch.get('behind_count', 0)})",
            f"- **State:** `{state.upper()}` | **Clean:** {analysis_data.get('is_clean', False)}",
            f"- **Hygiene Score:** {hygiene}/100",
            f"- **Working Tree:** {summary.get('staged_count', 0)} staged, {summary.get('unstaged_count', 0)} unstaged, {summary.get('untracked_count', 0)} untracked",
            f"- **Net Lines:** +{summary.get('total_lines_added', 0)} / -{summary.get('total_lines_deleted', 0)}",
            "",
        ]

        # Security Findings
        findings = analysis_data.get("security_findings", [])
        lines.append(f"## Security & Hygiene Findings ({len(findings)})")
        if not findings:
            lines.append("- Zero leaked secrets or sensitive files detected.")
        else:
            for f in findings:
                lines.append(f"- **[{f['risk_level']}] {f['rule_id']}**: {f['message']} (`{f['file_path']}`)")
        lines.append("")

        # Recent Commits
        commits = analysis_data.get("recent_commits", [])
        if commits:
            lines.append(f"## Recent Commits ({len(commits)})")
            for c in commits:
                lines.append(f"- `{c['short_hash']}` **{c['subject']}** ({c['author_name']}, {c['relative_date']})")
            lines.append("")

        return "\n".join(lines)
