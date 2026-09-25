"""
Brute-force oracle checking (ALGO-style) for small models.

Pass 161 measured that on hard tasks, agreement between qwen2.5-coder:3b
solutions is weak evidence: they share mistakes, and the 3-candidate swarm
claimed 2 false successes out of 12 held-out tasks. Model-written tests
share the same blind spots.

Different evidence: ask the model for the *simplest* correct version --
brute force, no cleverness -- which small models get right far more often
than the optimised one, plus a generator of small random inputs. A candidate
is supported only if it matches the oracle on every generated input.
Agreement between two *different algorithms* is much harder to get by
sharing a bug than agreement between three samples of the same one.

Limits, stated: the oracle and generator are model-written too. The check
refuses to vouch when the oracle itself fails on most inputs (degenerate
generator), and it does not handle stateful classes or tasks with several
valid answers -- `applicable()` says so rather than guessing.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional

from saleha.core.safety_patterns import check_dangerous

MIN_VALID_FRACTION = 0.5  # oracle must return normally on at least half the inputs


@dataclass
class OracleVerdict:
    supported: bool
    checked: int = 0
    oracle_ok: int = 0
    mismatch: str = ""
    reason: str = ""


def entry_point(prompt: str) -> Optional[str]:
    """The function name a task asks for (`name(`), or None for class tasks."""
    if re.search(r"Python class `", prompt):
        return None
    m = re.search(r"`([A-Za-z_]\w*)\(", prompt)
    return m.group(1) if m else None


def applicable(prompt: str) -> bool:
    return entry_point(prompt) is not None


ORACLE_PROMPT = (
    "Write the simplest possible CORRECT Python implementation for the task below. "
    "Ignore efficiency completely: brute force, exhaustive search, recursion without "
    "memoisation are all fine and preferred. Clarity and correctness only. "
    "Use the exact function name and signature from the task. Return only the code.\n\nTask: {task}"
)

GENERATOR_PROMPT = (
    "Write a Python function `gen(rng)` for the task below. `rng` is a random.Random. "
    "Return a tuple with the positional arguments for ONE call of `{entry}`, built from "
    "SMALL random VALID inputs (collections of at most 8 items, strings of at most 8 "
    "characters, small integers) that respect every constraint the task states. Include "
    "edge cases such as empty inputs sometimes, when the task allows them. "
    "Return only the code.\n\nTask: {task}"
)

_CHILD = r'''
import copy, json, random, types
def _load(src, name):
    m = types.ModuleType(name)
    exec(compile(src, name + ".py", "exec"), m.__dict__)
    return m
def _call(fn, args):
    try:
        return ("ok", fn(*copy.deepcopy(args)))
    except Exception as e:
        return ("error", type(e).__name__)
cand = getattr(_load(__CAND__, "candidate"), __ENTRY__)
orac = getattr(_load(__ORACLE__, "oracle"), __ENTRY__)
gen = _load(__GEN__, "gen").gen
checked = oracle_ok = gen_failed = 0
mismatch = ""
for seed in range(__N__):
    try:
        args = gen(random.Random(seed))
    except Exception:
        gen_failed += 1  # a bad draw from the generator is skipped, not fatal
        continue
    if not isinstance(args, tuple):
        args = (args,)
    want = _call(orac, args)
    got = _call(cand, args)
    checked += 1
    oracle_ok += want[0] == "ok"
    if want != got:
        mismatch = "args=%r oracle=%r candidate=%r" % (args, want, got)
        mismatch = mismatch[:300]
        break
print(__MARKER__ + json.dumps({"checked": checked, "oracle_ok": oracle_ok, "mismatch": mismatch,
                               "gen_failed": gen_failed}))
'''


def differential_check(candidate: str, oracle: str, generator: str, entry: str,
                       n: int = 200, timeout: int = 30) -> OracleVerdict:
    """Run candidate and oracle on `n` generated inputs in a separate process and compare."""
    for label, src in (("candidate", candidate), ("oracle", oracle), ("generator", generator)):
        if not src or not src.strip():
            return OracleVerdict(False, reason=f"no {label} code")
        danger = check_dangerous(src)
        if danger:
            return OracleVerdict(False, reason=f"{label} refused by safety screen: {danger.description}")

    marker = f"ORACLE_RESULT_{secrets.token_hex(8)}:"
    script = (_CHILD.replace("__CAND__", repr(candidate)).replace("__ORACLE__", repr(oracle))
              .replace("__GEN__", repr(generator)).replace("__ENTRY__", repr(entry))
              .replace("__N__", str(n)).replace("__MARKER__", repr(marker)))
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = os.path.join(tmp, "oracle_check.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(script)
        try:
            proc = subprocess.run([sys.executable, "-I", "-B", path], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout, cwd=tmp)
        except subprocess.TimeoutExpired:
            return OracleVerdict(False, reason=f"timed out after {timeout}s")

    line = next((ln for ln in reversed(proc.stdout.splitlines()) if ln.startswith(marker)), None)
    if line is None:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
        return OracleVerdict(False, reason=f"check did not complete: {tail[0][:200]}")
    data = json.loads(line[len(marker):])
    verdict = OracleVerdict(False, checked=data["checked"], oracle_ok=data["oracle_ok"],
                            mismatch=data["mismatch"])
    if verdict.checked < MIN_VALID_FRACTION * n:
        verdict.reason = (f"generator failed on {data.get('gen_failed', 0)}/{n} draws; "
                          f"too few inputs to vouch for anything")
    elif verdict.mismatch:
        verdict.reason = "differs from the brute-force oracle"
    elif verdict.oracle_ok < MIN_VALID_FRACTION * verdict.checked:
        verdict.reason = (f"oracle raised on {verdict.checked - verdict.oracle_ok}/{verdict.checked} "
                          f"inputs; the generator is not producing valid inputs")
    else:
        verdict.supported = True
    return verdict
