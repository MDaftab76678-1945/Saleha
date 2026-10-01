"""
Real-bug bench: bugs that maintainers of real projects fixed in 2026, with the
tests they added -- not injected mutations.

For each upstream fix commit C, the repo is rebuilt as it was just before C
(its parent), plus only the TEST files C changed. Those tests fail there --
checked, or the bug is skipped -- and `saleha fix` must make them pass without
touching them. It counts only on a PROVEN receipt. The upstream source fix is
never shown to the agent: the repo has a single commit, no history.

Most of these commits are from August-September 2026, so a model trained
before then has not seen the fix.

    python bench/real_bugs.py --work DIR [--model qwen2.5-coder:3b]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

BUGS = [
    # project, repo url, fix commit, tests path (for pytest)
    ("more-itertools", "https://github.com/more-itertools/more-itertools.git", "def2dab", "tests"),
    ("more-itertools", "https://github.com/more-itertools/more-itertools.git", "6b1907d", "tests"),
    ("more-itertools", "https://github.com/more-itertools/more-itertools.git", "d032cab", "tests"),
    ("more-itertools", "https://github.com/more-itertools/more-itertools.git", "f51a53b", "tests"),
    ("more-itertools", "https://github.com/more-itertools/more-itertools.git", "958990e", "tests"),
    ("boltons", "https://github.com/mahmoud/boltons.git", "c1c25da", "tests"),
    ("boltons", "https://github.com/mahmoud/boltons.git", "ec1ff9f", "tests"),
    ("boltons", "https://github.com/mahmoud/boltons.git", "d12d86a", "tests"),
    ("boltons", "https://github.com/mahmoud/boltons.git", "a1ea103", "tests"),
    ("toolz", "https://github.com/pytoolz/toolz.git", "d2eba03", "toolz/tests"),
    ("toolz", "https://github.com/pytoolz/toolz.git", "5a7e078", "toolz/tests"),
]


@dataclass
class Result:
    bug: str
    subject: str
    verdict: str
    seconds: float
    reason: str
    tests_changed: List[str]
    source_files_upstream: List[str]
    changed_by_saleha: List[str]
    pin: str = ""


def _git(cwd: str, *args: str, check: bool = True) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()[-300:]}")
    return p.stdout


def _rm(path: Path) -> None:
    def force(func, p, _exc):          # git object files are read-only on Windows
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if path.exists():
        shutil.rmtree(path, onexc=force)


def _is_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return "/tests/" in f"/{rel}" or name.startswith("test_") or name.endswith("_test.py")


def prepare(work: Path, project: str, url: str, commit: str) -> Tuple[Optional[Path], str, List[str], List[str]]:
    """(bug repo, subject, test files taken from the fix, upstream source files) or (None, why, ...)."""
    src = work / "src" / project
    if not src.exists():
        subprocess.run(["git", "clone", "-q", url, str(src)], check=True, timeout=900)
    full = _git(str(src), "rev-parse", commit).strip()
    subject = _git(str(src), "log", "-1", "--format=%s", full).strip()
    changed = [p for p in _git(str(src), "diff", "--name-only", f"{full}^", full).splitlines() if p.strip()]
    tests = [p for p in changed if p.endswith(".py") and _is_test(p)]
    sources = [p for p in changed if p.endswith(".py") and not _is_test(p)]
    if not tests or not sources:
        return None, f"{subject}: needs both a test and a source change", tests, sources
    dest = work / "bugs" / f"{project}-{commit}"
    _rm(dest)
    dest.mkdir(parents=True)
    # The tree as it was before the fix, then the fix's tests on top.
    archive = subprocess.run(["git", "archive", "--format=tar", f"{full}^"], cwd=src, capture_output=True,
                             timeout=600, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True, timeout=600)
    for rel in tests:
        content = subprocess.run(["git", "show", f"{full}:{rel}"], cwd=src, capture_output=True,
                                 timeout=120).stdout
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_bytes(content)
    for args in (["init", "-q"], ["config", "user.email", "bench@example.com"], ["config", "user.name", "bench"],
                 ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-q", "-m", "snapshot"]):
        _git(str(dest), *args)
    return dest, subject, tests, sources


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--work", required=True)
    ap.add_argument("--model", default="qwen2.5-coder:3b")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--prepare-only", action="store_true", help="build the bug repos and check they fail")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    (work / "src").mkdir(parents=True, exist_ok=True)
    tag = a.model.replace(":", "_")
    results_file = work / f"real-results-{tag}.jsonl"
    done = set()
    if results_file.exists():
        done = {json.loads(ln)["bug"] for ln in results_file.read_text(encoding="utf-8").splitlines() if ln}
    for project, url, commit, tests_path in BUGS:
        bug = f"{project}-{commit}"
        if bug in done:
            continue
        repo, subject, tests, sources = prepare(work, project, url, commit)
        if repo is None:
            print(f"{bug}: SKIP ({subject})", flush=True)
            continue
        argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", tests_path]
        p = subprocess.run(argv, cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=900, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if p.returncode != 1:
            print(f"{bug}: SKIP (the fix's tests do not fail before it: exit {p.returncode})", flush=True)
            continue
        if a.prepare_only:
            print(f"{bug}: ready -- {subject} (tests {', '.join(tests)}; upstream fixed {', '.join(sources)})",
                  flush=True)
            continue
        test_cmd = " ".join(f'"{x}"' if " " in x else x for x in argv)
        cmd = [sys.executable, "-c", "from saleha.cli.commands import cli; cli()", "fix", "--dir", str(repo),
               "--json", "-m", a.model, "--timeout", str(a.timeout), test_cmd]
        t0 = time.time()
        out = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=a.timeout + 900).stdout
        line = next((ln for ln in reversed(out.splitlines()) if ln.startswith("{")), "{}")
        res = json.loads(line)
        r = Result(bug, subject, res.get("verdict", "HARNESS_ERROR"), round(time.time() - t0, 1),
                   str(res.get("reason", ""))[:300], tests, sources, res.get("changed_files") or [],
                   str((res.get("pin") or {}).get("verdict", "")))
        with results_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(r)) + "\n")
        print(f"{bug}: {r.verdict} ({r.seconds:.0f}s) -- {subject}", flush=True)
    rows = [json.loads(ln) for ln in results_file.read_text(encoding="utf-8").splitlines() if ln] \
        if results_file.exists() else []
    fixed = sum(1 for r in rows if r["verdict"] == "FIXED")
    print(f"\n{fixed} of {len(rows)} real bugs fixed and proven ({a.model})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
