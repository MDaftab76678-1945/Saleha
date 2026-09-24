"""
Saleha Core: Proof Receipt -- is this code change actually proven?

Any change (written by an AI agent or a person) gets a receipt that answers,
by running things rather than reading claims:

  1. Do the project's tests pass WITH the change?
  2. Do those same tests FAIL on the code as it was before the change?
     If they pass either way, they do not guard the change: a green suite
     proves nothing about it. (Measured in this repo: agents shipped patches
     the tests never exercised, under a green tick.)
  3. Were the tests weakened -- asserts deleted, tests removed, skips added?
  4. The head test run is recorded in the WorkLedger, anchored in the Rust
     intent kernel outside the repo, so the receipt can be re-checked later
     and cannot be quietly edited.

Verdicts, kept distinct on purpose:
  PROVEN        tests pass now, fail without the change, no weakening
  UNPROVEN      tests pass, but they would pass without the change too,
                or the tests were weakened
  FAILING       tests fail with the change
  NOT_CHECKED   nothing could be run (no git, no test command, no change)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROVEN = "PROVEN"
UNPROVEN = "UNPROVEN"
FAILING = "FAILING"
NOT_CHECKED = "NOT_CHECKED"

_ASSERT_RE = re.compile(r"^\s*(assert\b|self\.assert\w*\(|expect\(|assert_\w+\()")
_SKIP_RE = re.compile(r"(@pytest\.mark\.(skip|xfail)|pytest\.skip\(|@unittest\.skip|\.skip\(|xit\(|it\.skip)")
_TEST_DEF_RE = re.compile(r"^\s*(async\s+)?def\s+(test_\w+)|^\s*(it|test)\(\s*['\"]")


@dataclass
class TestRun:
    ran: bool
    passed: bool
    exit_code: Optional[int]
    tail: str
    seconds: float


@dataclass
class Receipt:
    verdict: str
    reason: str
    base: str
    changed_files: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    test_files: List[str] = field(default_factory=list)
    test_command: List[str] = field(default_factory=list)
    head_run: Optional[TestRun] = None
    base_run: Optional[TestRun] = None
    weakening: List[str] = field(default_factory=list)
    # Race/deadlock patterns in the changed Python files. Warnings only: a
    # race rarely fails a test run, so tests cannot be the judge here, and a
    # pattern match is not a proof either -- it never changes the verdict.
    concurrency: List[str] = field(default_factory=list)
    ledger_entry: str = ""
    anchor: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _git(root: str, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, check=check)


def _changed_files(root: str, base: str) -> List[str]:
    """Tracked files changed since `base` plus untracked, non-ignored files."""
    tracked = _git(root, "diff", "--name-only", base).stdout.splitlines()
    untracked = _git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
    return sorted({p.strip() for p in tracked + untracked if p.strip()})


def _is_test_path(rel: str) -> bool:
    from saleha.core.loop.agentic_loop import _is_test_path as is_test
    return is_test(rel)


def _discover_tests(root: str) -> Tuple[Optional[List[str]], str]:
    from saleha.core.loop.agentic_loop import discover_test_command
    return discover_test_command(root)


def _run_tests(argv: List[str], cwd: str, timeout: float) -> TestRun:
    env = {**os.environ, "PYTHONPATH": cwd, "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8"}
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return TestRun(True, False, None, f"timed out after {timeout:.0f}s",
                       round(time.time() - t0, 1))
    except OSError as exc:
        return TestRun(False, False, None, f"could not run: {exc}", 0.0)
    tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-6:])
    return TestRun(True, p.returncode == 0, p.returncode, tail[-800:], round(time.time() - t0, 1))


def _base_text(root: str, base: str, rel: str) -> Optional[str]:
    r = _git(root, "show", f"{base}:{rel}")
    return r.stdout if r.returncode == 0 else None


def _test_names(lines: List[str]) -> set:
    names = set()
    for ln in lines:
        match = _TEST_DEF_RE.match(ln)
        if match:
            names.add(match.group(0).strip())
    return names


def _weakening(root: str, base: str, test_files: List[str]) -> List[str]:
    """Signs the tests were made easier to pass, per changed test file."""
    findings: List[str] = []
    for rel in test_files:
        old = _base_text(root, base, rel) or ""
        try:
            new = Path(root, rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            new = ""
        old_lines, new_lines = old.splitlines(), new.splitlines()
        lost_asserts = (sum(1 for ln in old_lines if _ASSERT_RE.match(ln))
                        - sum(1 for ln in new_lines if _ASSERT_RE.match(ln)))
        if lost_asserts > 0:
            findings.append(f"{rel}: {lost_asserts} assert(s) removed")
        new_skips = (sum(1 for ln in new_lines if _SKIP_RE.search(ln))
                     - sum(1 for ln in old_lines if _SKIP_RE.search(ln)))
        if new_skips > 0:
            findings.append(f"{rel}: {new_skips} skip/xfail marker(s) added")
        gone = sorted(_test_names(old_lines) - _test_names(new_lines))
        if gone:
            findings.append(f"{rel}: {len(gone)} test(s) removed ({', '.join(gone[:3])})")
    return findings


def _run_at_base(root: str, base: str, changed: List[str], argv: List[str],
                 timeout: float) -> TestRun:
    """The NEW tests against the OLD source, in a throwaway git worktree.

    Test files (changed or new) are copied over from the working tree; source
    files stay as they were at `base`. The user's working tree is never
    touched.
    """
    tmp = tempfile.mkdtemp(prefix="saleha-receipt-")
    work = os.path.join(tmp, "base")
    try:
        add = _git(root, "worktree", "add", "--detach", work, base)
        if add.returncode != 0:
            return TestRun(False, False, None, f"git worktree failed: {add.stderr.strip()[-300:]}", 0.0)
        for rel in changed:
            if not _is_test_path(rel):
                continue
            src = Path(root, rel)
            dst = Path(work, rel)
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
            elif dst.exists():
                dst.unlink()
        return _run_tests(argv, work, timeout)
    finally:
        _git(root, "worktree", "remove", "--force", work)
        shutil.rmtree(tmp, ignore_errors=True)


def make_receipt(root_dir: str = ".", base: str = "HEAD", test_command: Optional[List[str]] = None,
                 timeout: float = 900.0, ledger_path: Optional[str] = None,
                 anchor_path: Optional[str] = None) -> Receipt:
    root = os.path.abspath(root_dir)
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return Receipt(NOT_CHECKED, "not a git repository", base)
    root = os.path.abspath(top.stdout.strip())
    if _git(root, "rev-parse", "--verify", f"{base}^{{commit}}").returncode != 0:
        return Receipt(NOT_CHECKED, f"base {base!r} is not a commit", base)

    changed = _changed_files(root, base)
    receipt = Receipt(NOT_CHECKED, "", base, changed_files=changed,
                      source_files=[p for p in changed if not _is_test_path(p)],
                      test_files=[p for p in changed if _is_test_path(p)])
    if not changed:
        receipt.reason = f"no changes since {base}: nothing to prove"
        return receipt

    argv, why = (test_command, "given with --test-cmd") if test_command else _discover_tests(root)
    if not argv:
        receipt.reason = f"no test command: {why}"
        return receipt
    receipt.test_command = list(argv)
    receipt.weakening = _weakening(root, base, receipt.test_files)
    from saleha.core.verification.concurrency_checker import check_paths
    py_sources = [os.path.join(root, p) for p in receipt.source_files
                  if p.endswith(".py") and os.path.isfile(os.path.join(root, p))]
    conc = check_paths(py_sources)
    receipt.concurrency = [f"{os.path.relpath(f.path, root)}:{f.line} {f.rule} {f.message}"
                           for f in conc.findings]
    receipt.concurrency += [f"{os.path.relpath(p, root)}: not analyzed ({why})"
                            for p, why in conc.skipped.items()]

    # Head run, recorded in the anchored ledger as it happens.
    from saleha.core.intent_kernel import default_anchor_path
    from saleha.core.work_ledger import WorkLedger
    ledger = WorkLedger(ledger_path or os.path.join(root, ".saleha", "work.jsonl"), root_dir=root,
                        anchor_path=anchor_path or default_anchor_path())
    t0 = time.time()
    entry, passed = ledger.record_tests("saleha-receipt", f"receipt vs {base}", list(argv),
                                        timeout=timeout)
    receipt.head_run = TestRun(True, passed, None, str(entry.claim.get("observed", ""))[-800:],
                               round(time.time() - t0, 1))
    receipt.ledger_entry = entry.hash
    receipt.anchor = ledger.anchor_note or f"anchored in {ledger.anchor_path}"

    if not passed:
        receipt.verdict, receipt.reason = FAILING, "tests fail with this change"
        return receipt
    if not receipt.source_files:
        receipt.verdict = UNPROVEN
        receipt.reason = "only test files changed: there is no source change to prove"
        return receipt

    receipt.base_run = _run_at_base(root, base, changed, list(argv), timeout)
    if not receipt.base_run.ran:
        receipt.verdict = NOT_CHECKED
        receipt.reason = f"could not run tests without the change: {receipt.base_run.tail}"
    elif receipt.base_run.passed:
        receipt.verdict = UNPROVEN
        receipt.reason = ("tests pass with AND without the change -- they do not guard it")
    elif receipt.weakening:
        receipt.verdict = UNPROVEN
        receipt.reason = "tests guard the change, but they were weakened: " + "; ".join(receipt.weakening)
    else:
        receipt.verdict = PROVEN
        receipt.reason = "tests pass with the change and fail without it; no weakening found"
    return receipt


def render_markdown(r: Receipt) -> str:
    def run_line(label: str, run: Optional[TestRun]) -> str:
        if run is None:
            return f"- {label}: not run"
        if not run.ran:
            return f"- {label}: could not run ({run.tail})"
        return f"- {label}: {'PASS' if run.passed else 'FAIL'} ({run.seconds}s)"

    lines = [
        f"# Proof receipt: {r.verdict}",
        "",
        r.reason,
        "",
        f"- Compared against: `{r.base}`",
        f"- Changed files: {len(r.changed_files)} "
        f"({len(r.source_files)} source, {len(r.test_files)} test)",
        f"- Test command: `{' '.join(r.test_command)}`" if r.test_command else "- Test command: none",
        run_line("Tests with the change", r.head_run),
        run_line("Same tests without the change", r.base_run),
        f"- Test weakening: {'; '.join(r.weakening) if r.weakening else 'none found'}",
        f"- Concurrency warnings: {'; '.join(r.concurrency) if r.concurrency else 'none found'}",
        f"- Ledger entry: `{r.ledger_entry[:16]}`" if r.ledger_entry else "- Ledger entry: none",
        f"- Anchor: {r.anchor or 'none'}",
        "",
        "What this does not prove: that the tests cover every behaviour that matters, "
        "or that untested code paths are correct.",
    ]
    return "\n".join(lines) + "\n"


def save(r: Receipt, root_dir: str) -> str:
    out = Path(root_dir, ".saleha", "receipts")
    out.mkdir(parents=True, exist_ok=True)
    stem = time.strftime("%Y%m%d-%H%M%S", time.localtime(r.created_at))
    (out / f"{stem}.json").write_text(json.dumps(r.to_dict(), indent=1), encoding="utf-8")
    md = out / f"{stem}.md"
    md.write_text(render_markdown(r), encoding="utf-8")
    return str(md)
