"""
Fix bench: does `saleha fix` fix bugs in real open-source code, and prove it?

Single-line bugs are injected into the source of real projects (pinned
commits) by mutation: operator swaps, comparison flips, off-by-one integer
constants, boolean swaps. A bug is kept only when the project's own test
suite fails with it. Each kept bug becomes a fresh git repo whose only
commit is the buggy code (no history to peek at), and `saleha fix` runs on it
with a local model. A bug counts as fixed only on the proof receipt's
verdict: the tests pass with the fix, fail without it in a clean checkout,
and were not weakened.

What this measures: single-line injected bugs that the tests locate. It is
not SWE-bench: real bugs span files and need understanding an operator swap
does not. The model-free repair search tries the same kinds of one-token
edit these bugs are made of, so its fixes here are expected and say little
about real bugs: the report counts them apart, `--no-search` measures the
model alone, and bench/real_bugs.py measures the search on real bugs.

    python bench/fix_bench.py --work DIR [--per-project 6] [--model qwen2.5-coder:3b] [--no-search]
    python bench/fix_bench.py --work DIR --report-only
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECTS = [
    # name, git url, pinned commit, source dirs/files, tests path
    ("more-itertools", "https://github.com/more-itertools/more-itertools.git", "1ea82a7",
     ["more_itertools"], "tests"),
    ("toolz", "https://github.com/pytoolz/toolz.git", "451af60", ["toolz"], "toolz/tests"),
    ("boltons", "https://github.com/mahmoud/boltons.git", "4e5faa3", ["boltons"], "tests"),
    ("inflection", "https://github.com/jpvanhal/inflection.git", "88eefaa", ["inflection"],
     "test_inflection.py"),
]
BINOP_SWAP = {ast.Add: ("+", "-"), ast.Sub: ("-", "+")}
CMP_SWAP = {ast.Lt: ("<", "<="), ast.LtE: ("<=", "<"), ast.Gt: (">", ">="), ast.GtE: (">=", ">"),
            ast.Eq: ("==", "!="), ast.NotEq: ("!=", "==")}


@dataclass
class Bug:
    id: str
    project: str
    file: str
    line: int
    kind: str
    before: str      # the original line
    after: str       # the buggy line


@dataclass
class Outcome:
    bug: str
    verdict: str
    seconds: float
    agent_steps: int
    reason: str
    exact_revert: Optional[bool]    # the fixed line equals the original line
    model: str = ""                 # the model whose fix was kept (escalation)
    suspects: Optional[List[str]] = None   # fault localization, file:line
    bug_ranked: Optional[int] = None       # 1-based rank of the bug line among suspects


def _run(argv: List[str], cwd: str, timeout: float) -> Tuple[Optional[int], str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    return p.returncode, p.stdout + p.stderr


def test_argv(tests: str) -> List[str]:
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", tests]


def fetch(work: Path) -> Dict[str, Path]:
    out = {}
    for name, url, commit, _src, _tests in PROJECTS:
        dest = work / "src" / name
        if not dest.exists():
            subprocess.run(["git", "clone", "-q", url, str(dest)], check=True, timeout=600)
        # --hard: a run killed mid-validation must not leave a mutation behind.
        subprocess.run(["git", "-C", str(dest), "reset", "-q", "--hard", commit], check=True, timeout=120)
        out[name] = dest
    return out


def _segment_swap(line: bytes, start: int, end: int, old: str, new: str) -> Optional[bytes]:
    seg = line[start:end]
    token = f" {old} ".encode()
    if seg.count(token) != 1:
        return None
    return line[:start] + seg.replace(token, f" {new} ".encode()) + line[end:]


def candidates(path: Path) -> List[Tuple[int, str, bytes]]:
    """(line number, kind, mutated line bytes) for every single-line mutation site."""
    src = path.read_bytes()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    lines = src.split(b"\n")
    found = []
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) is None or node.lineno != getattr(node, "end_lineno", None):
            continue
        line = lines[node.lineno - 1]
        new = None
        kind = ""
        if isinstance(node, ast.BinOp) and type(node.op) in BINOP_SWAP:
            old, rep = BINOP_SWAP[type(node.op)]
            new = _segment_swap(line, node.left.end_col_offset, node.right.col_offset, old, rep)
            kind = f"'{old}' -> '{rep}'"
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in CMP_SWAP:
            old, rep = CMP_SWAP[type(node.ops[0])]
            new = _segment_swap(line, node.left.end_col_offset, node.comparators[0].col_offset, old, rep)
            kind = f"'{old}' -> '{rep}'"
        elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
            old, rep = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
            new = _segment_swap(line, node.values[0].end_col_offset, node.values[1].col_offset, old, rep)
            kind = f"'{old}' -> '{rep}'"
        elif (isinstance(node, ast.Constant) and type(node.value) is int and 0 <= node.value <= 2
              and node.end_col_offset - node.col_offset == 1):
            new = line[:node.col_offset] + str(node.value + 1).encode() + line[node.end_col_offset:]
            kind = f"{node.value} -> {node.value + 1}"
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, bool):
            v = node.value
            new = line[:v.col_offset] + str(not v.value).encode() + line[v.end_col_offset:]
            kind = f"return {v.value} -> {not v.value}"
        if new is not None and new != line:
            found.append((node.lineno, kind, new))
    return found


def make_bugs(srcs: Dict[str, Path], per_project: int, seed: int, max_tries: int = 80) -> List[Bug]:
    rng = random.Random(seed)
    bugs: List[Bug] = []
    for name, _url, _commit, src_paths, tests in PROJECTS:
        root = srcs[name]
        files = []
        for sp in src_paths:
            p = root / sp
            files += sorted(p.rglob("*.py")) if p.is_dir() else [p]
        files = [f for f in files if "test" not in f.relative_to(root).as_posix().lower()]
        pool = [(f, c) for f in files for c in candidates(f)]
        rng.shuffle(pool)
        kept = 0
        for f, (lineno, kind, new_line) in pool[:max_tries]:
            if kept >= per_project:
                break
            original = f.read_bytes()
            lines = original.split(b"\n")
            mutated = b"\n".join(lines[:lineno - 1] + [new_line] + lines[lineno:])
            try:
                ast.parse(mutated)
            except SyntaxError:
                continue
            f.write_bytes(mutated)
            try:
                code, _out = _run(test_argv(tests), str(root), 120)
            finally:
                f.write_bytes(original)
            if code != 1:          # 0: tests miss it; None: hang; 2+: collection/usage error
                continue
            kept += 1
            bugs.append(Bug(f"{name}-{kept}", name, f.relative_to(root).as_posix(), lineno, kind,
                            lines[lineno - 1].decode("utf-8", "replace").rstrip("\r"),
                            new_line.decode("utf-8", "replace").rstrip("\r")))
    return bugs


def _force_remove(func, path, _exc) -> None:
    """rmtree helper: git marks its object files read-only, which Windows will not delete."""
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def materialize(bug: Bug, srcs: Dict[str, Path], work: Path) -> Path:
    dest = work / "bugs" / bug.id
    if dest.exists():
        shutil.rmtree(dest, onexc=_force_remove)
    shutil.copytree(srcs[bug.project], dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    f = dest / bug.file
    lines = f.read_bytes().split(b"\n")
    lines[bug.line - 1] = bug.after.encode() + (b"\r" if lines[bug.line - 1].endswith(b"\r") else b"")
    f.write_bytes(b"\n".join(lines))
    for args in (["init", "-q"], ["config", "user.email", "bench@example.com"],
                 ["config", "user.name", "bench"], ["config", "core.autocrlf", "false"],
                 ["add", "-A"], ["commit", "-q", "-m", "buggy snapshot"]):
        subprocess.run(["git", *args], cwd=dest, check=True, capture_output=True, timeout=120)
    return dest


def run_fix(bug: Bug, repo: Path, tests: str, model: str, timeout: int,
            escalate: Optional[str] = None, search: bool = True) -> Outcome:
    test_cmd = " ".join(f'"{a}"' if " " in a else a for a in test_argv(tests))
    cmd = [sys.executable, "-c", "from saleha.cli.commands import cli; cli()", "fix",
           "--dir", str(repo), "--json", "-m", model, "--max-steps", "15",
           "--timeout", str(timeout), "--no-memory", test_cmd]
    if escalate:
        cmd[-1:-1] = ["--escalate", escalate]
    if not search:
        cmd[-1:-1] = ["--no-search"]
    t0 = time.time()
    code, out = _run(cmd, str(repo), timeout + 600)
    seconds = round(time.time() - t0, 1)
    last = next((ln for ln in reversed(out.splitlines()) if ln.startswith("{")), "")
    try:
        res = json.loads(last)
    except json.JSONDecodeError:
        return Outcome(bug.id, "HARNESS_ERROR", seconds, 0, out[-300:], None)
    exact = None
    if res.get("verdict") in ("FIXED", "FIXED_UNPROVEN"):
        fixed = (repo / bug.file).read_bytes().split(b"\n")[bug.line - 1].decode("utf-8", "replace")
        exact = fixed.rstrip("\r").strip() == bug.before.strip()
    suspects = res.get("suspects") or []
    target = f"{bug.file}:{bug.line}"
    ranked = suspects.index(target) + 1 if target in suspects else None
    return Outcome(bug.id, res.get("verdict", "?"), seconds, res.get("agent_steps", 0),
                   res.get("reason", "")[:300], exact, res.get("model", ""), suspects, ranked)


def report(bugs: List[Bug], outcomes: List[Outcome], model: str) -> str:
    by_id = {b.id: b for b in bugs}
    n = len(outcomes)
    fixed = [o for o in outcomes if o.verdict == "FIXED"]
    lines = [f"# Saleha fix bench -- {model}", "",
             f"{len(fixed)} of {n} injected bugs fixed and proven "
             f"({100 * len(fixed) / n:.0f}%)." if n else "No bugs run.", ""]
    counts: Dict[str, int] = {}
    for o in outcomes:
        counts[o.verdict] = counts.get(o.verdict, 0) + 1
    lines += [f"- {k}: {v}" for k, v in sorted(counts.items())]
    if fixed:
        by_model: Dict[str, int] = {}
        for o in fixed:
            by_model[o.model or "?"] = by_model.get(o.model or "?", 0) + 1
        lines += [f"- median time per proven fix: {statistics.median(o.seconds for o in fixed):.0f}s",
                  f"- proven fixes that restored the exact original line: "
                  f"{sum(1 for o in fixed if o.exact_revert)} of {len(fixed)}",
                  "- proven fixes by model: " + ", ".join(f"{m}: {n}" for m, n in sorted(by_model.items()))]
        searched = sum(1 for o in fixed if o.model.startswith("search"))
        if searched:
            lines += [f"- {searched} of the {len(fixed)} came from the model-free search, which tries the same "
                      "kinds of one-token edit these bugs were injected with: expected here, and no measure "
                      "of real bugs (see bench/real_bugs.py)"]
    top1 = sum(1 for o in outcomes if o.bug_ranked == 1)
    top5 = sum(1 for o in outcomes if o.bug_ranked)
    lines += [f"- fault localization put the bug line first in {top1} of {n} bugs, "
              f"in the top 5 in {top5}"]
    lines += ["", "| bug | file:line | mutation | verdict | model | bug rank | time |",
              "|---|---|---|---|---|---|---|"]
    for o in outcomes:
        b = by_id[o.bug]
        lines.append(f"| {b.id} | {b.file}:{b.line} | {b.kind} | {o.verdict} | {o.model} | "
                     f"{o.bug_ranked or '-'} | {o.seconds:.0f}s |")
    lines += ["", "Projects (pinned): " + ", ".join(f"{p[0]}@{p[2]}" for p in PROJECTS),
              "", "Bugs are single-line mutations kept only when the project's own tests fail "
              "with them. A fix counts only when the proof receipt says PROVEN."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--work", required=True, help="working directory for clones, bugs and results")
    ap.add_argument("--per-project", type=int, default=6)
    ap.add_argument("--model", default="qwen2.5-coder:3b")
    ap.add_argument("--escalate", default=None, help="second, bigger model tried when the first fails")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per saleha fix run")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--no-search", action="store_true", help="the model alone, without the model-free search")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    config = a.model + (f"+{a.escalate}" if a.escalate else "") + ("+no-search" if a.no_search else "")
    tag = config.replace(":", "_").replace("+", "__")
    bugs_file, results_file = work / "bugs.json", work / f"results-{tag}.jsonl"
    srcs = fetch(work)
    if bugs_file.exists():
        bugs = [Bug(**b) for b in json.loads(bugs_file.read_text(encoding="utf-8"))]
    else:
        bugs = make_bugs(srcs, a.per_project, a.seed)
        bugs_file.write_text(json.dumps([asdict(b) for b in bugs], indent=1), encoding="utf-8")
        print(f"{len(bugs)} bugs kept", flush=True)
    done = {}
    if results_file.exists():
        for ln in results_file.read_text(encoding="utf-8").splitlines():
            o = Outcome(**json.loads(ln))
            done[o.bug] = o
    tests_of = {p[0]: p[4] for p in PROJECTS}
    if not a.report_only:
        for bug in bugs:
            if bug.id in done:
                continue
            repo = materialize(bug, srcs, work)
            o = run_fix(bug, repo, tests_of[bug.project], a.model, a.timeout, a.escalate, not a.no_search)
            done[bug.id] = o
            with results_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(o)) + "\n")
            print(f"{bug.id}: {o.verdict} ({o.seconds:.0f}s)", flush=True)
    outcomes = [done[b.id] for b in bugs if b.id in done]
    md = report(bugs, outcomes, config)
    (work / f"REPORT-{tag}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
