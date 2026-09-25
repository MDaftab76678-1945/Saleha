"""SemVer bumps and changelog entries computed from real commits.

The next version is derived only from the conventional-commit history since
the commit that last changed ``version`` in pyproject.toml:

- ``type!:`` or a ``BREAKING CHANGE:`` footer -> major
- ``feat`` -> minor
- ``fix`` / ``perf`` -> patch
- anything else -> no release

No commits, or no git history, means "nothing to release" -- never a
made-up entry. ``apply_bump`` writes the working tree only; committing and
tagging stay a human decision.
"""

from __future__ import annotations

import datetime as _dt
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]

_PYPROJECT_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE)
_INIT_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)(")', re.MULTILINE)
_CONVENTIONAL_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<subject>.+)$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

_SECTIONS = [("feat", "Features"), ("fix", "Fixes"), ("perf", "Performance"),
             ("refactor", "Refactoring"), ("docs", "Documentation"), ("test", "Tests")]


def write_preserving_eol(path: Path, text: str) -> None:
    """Write `text` (LF) using the line ending the file already has.

    This checkout uses core.autocrlf, so most files are CRLF on disk; writing
    them back as LF would make every line look changed.
    """
    text = text.replace("\r\n", "\n")
    crlf = path.is_file() and b"\r\n" in path.read_bytes()
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def read_project_version(root: Path = REPO_ROOT) -> Optional[str]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    m = _PYPROJECT_RE.search(path.read_text(encoding="utf-8"))
    return m.group(2) if m else None


def version_declarations(root: Path = REPO_ROOT) -> Dict[str, Optional[str]]:
    """Every place the Python package declares its version."""
    found: Dict[str, Optional[str]] = {"pyproject.toml": read_project_version(root)}
    init = root / "saleha" / "__init__.py"
    if init.is_file():
        m = _INIT_RE.search(init.read_text(encoding="utf-8"))
        found["saleha/__init__.py"] = m.group(2) if m else None
    return found


@dataclass
class Commit:
    sha: str
    type: str
    subject: str
    breaking: bool


@dataclass
class BumpPlan:
    current: Optional[str]
    next: Optional[str]
    level: str  # "major" | "minor" | "patch" | "none"
    since: Optional[str]
    commits: List[Commit] = field(default_factory=list)
    reason: str = ""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60)


def parse_commit(sha: str, subject: str, body: str) -> Commit:
    m = _CONVENTIONAL_RE.match(subject.strip())
    breaking = "BREAKING CHANGE:" in body or "BREAKING-CHANGE:" in body
    if not m:
        return Commit(sha, "other", subject.strip(), breaking)
    return Commit(sha, m.group("type"), m.group("subject").strip(), breaking or bool(m.group("bang")))


def bump(version: str, level: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return version


def level_for(commits: List[Commit]) -> str:
    if any(c.breaking for c in commits):
        return "major"
    if any(c.type == "feat" for c in commits):
        return "minor"
    if any(c.type in ("fix", "perf") for c in commits):
        return "patch"
    return "none"


def plan_bump(root: Path = REPO_ROOT) -> BumpPlan:
    current = read_project_version(root)
    if current is None or not _SEMVER_RE.match(current):
        return BumpPlan(current, None, "none", None, reason="pyproject.toml has no X.Y.Z version")
    since = _git(root, "log", "-n1", "--format=%H", "-G", r"^version\s*=", "--", "pyproject.toml")
    if since.returncode != 0:
        return BumpPlan(current, None, "none", None,
                        reason=f"git log failed: {since.stderr.strip()[:200]}")
    since_sha = since.stdout.strip() or None
    rev = f"{since_sha}..HEAD" if since_sha else "HEAD"
    log = _git(root, "log", rev, "--format=%H%x1f%s%x1f%b%x1e")
    if log.returncode != 0:
        return BumpPlan(current, None, "none", since_sha,
                        reason=f"git log failed: {log.stderr.strip()[:200]}")
    commits = []
    for record in log.stdout.split("\x1e"):
        parts = record.strip("\n").split("\x1f")
        if len(parts) >= 2 and parts[0].strip():
            commits.append(parse_commit(parts[0].strip(), parts[1], parts[2] if len(parts) > 2 else ""))
    if not commits:
        return BumpPlan(current, None, "none", since_sha, reason="no commits since the last version change")
    level = level_for(commits)
    if level == "none":
        return BumpPlan(current, None, "none", since_sha, commits,
                        reason="no feat/fix/perf/breaking commits since the last version change")
    return BumpPlan(current, bump(current, level), level, since_sha, commits,
                    reason=f"{len(commits)} commit(s) since {since_sha[:8] if since_sha else 'the first commit'}")


def render_changelog_section(plan: BumpPlan, today: Optional[str] = None) -> str:
    today = today or _dt.date.today().isoformat()
    lines = [f"## [{plan.next}] - {today}", ""]
    breaking = [c for c in plan.commits if c.breaking]
    if breaking:
        lines += ["### Breaking changes", ""] + [f"- {c.subject} ({c.sha[:8]})" for c in breaking] + [""]
    for ctype, title in _SECTIONS:
        entries = [c for c in plan.commits if c.type == ctype and not c.breaking]
        if entries:
            lines += [f"### {title}", ""] + [f"- {c.subject} ({c.sha[:8]})" for c in entries] + [""]
    other = [c for c in plan.commits if c.type not in dict(_SECTIONS) and not c.breaking]
    if other:
        lines += ["### Other", ""] + [f"- {c.subject} ({c.sha[:8]})" for c in other] + [""]
    return "\n".join(lines)


def apply_bump(plan: BumpPlan, root: Path = REPO_ROOT, today: Optional[str] = None) -> List[str]:
    """Write the new version and changelog entry. Returns the files written."""
    if not plan.next or not plan.current:
        raise ValueError(f"nothing to apply: {plan.reason}")
    written: List[str] = []
    for rel, regex in (("pyproject.toml", _PYPROJECT_RE), ("saleha/__init__.py", _INIT_RE)):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        m = regex.search(text)
        if m is None:
            raise ValueError(f"{rel}: no version declaration to update")
        if m.group(2) != plan.current:
            raise ValueError(f"{rel} declares {m.group(2)}, expected {plan.current}; fix GOV-VERSION first")
        write_preserving_eol(path, regex.sub(lambda mm: mm.group(1) + plan.next + mm.group(3), text, count=1))
        written.append(rel)

    changelog = root / "CHANGELOG.md"
    section = render_changelog_section(plan, today)
    text = changelog.read_text(encoding="utf-8").replace("\r\n", "\n") if changelog.is_file() else "# Changelog\n\n"
    first = re.search(r"^## ", text, re.MULTILINE)
    new_text = (text[:first.start()] + section + "\n" + text[first.start():]) if first \
        else text.rstrip("\n") + "\n\n" + section
    write_preserving_eol(changelog, new_text)
    written.append("CHANGELOG.md")
    return written
