"""
Measure what Saleha actually solves. No literals, no leaderboard, no ranks.

## Why this exists

`NOTEBOOK_IMPORT.md` records twenty-eight passes of removing fabricated
benchmark numbers from this repository: "97.2% SWE-bench, Rank #1, CERTIFIED",
"All 12 unit tests passed in 0.42s", "GLOBAL_FRONTIER_LEADER". Every one was a
literal someone typed. Not one thing here had ever been measured.

`saleha/harness/swe_bench_harness.py` does call a model, but its three tasks
carry `test_patch="def test_x(): assert True"` -- a test that passes for any
output, including no output. So it cannot fail, which makes its number
meaningless too.

This script is the opposite of all of that. Each task below has:

  * a real prompt,
  * a real test that fails on wrong code -- verified before the run,
  * execution in a subprocess with a timeout.

The pass rate it prints is the number of tasks whose generated code actually
ran and passed its assertions. Nothing is inferred, and a failure is reported
as a failure with its error text.

## What the number does and does not mean

It measures this machine's default local model on twelve small, self-contained
programming problems. It is not SWE-bench, it is not a leaderboard position,
and twelve tasks is a small sample -- a run is worth reporting as "8/12 with
these four failures", never as a percentage standing on its own.

Usage:
    python scripts/measure_real_pass_rate.py
    python scripts/measure_real_pass_rate.py --model qwen3:8b
    python scripts/measure_real_pass_rate.py --verify-tests-only
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@dataclass
class Task:
    task_id: str
    prompt: str
    # Appended to the generated code and executed. Must raise on wrong output.
    test: str
    # A deliberately wrong implementation. The test must fail against it --
    # checked before the run, so a test that cannot fail never counts.
    wrong_impl: str


TASKS: List[Task] = [
    Task(
        "two_sum",
        "Write a Python function `two_sum(nums, target)` that returns the "
        "indices of the two numbers in `nums` that add up to `target`, as a "
        "list of two ints. Assume exactly one solution exists. Return only "
        "the function.",
        "r = two_sum([2,7,11,15], 9)\n"
        "assert sorted(r) == [0,1], r\n"
        "r = two_sum([3,2,4], 6)\n"
        "assert sorted(r) == [1,2], r\n",
        "def two_sum(nums, target):\n    return [0, 0]\n",
    ),
    Task(
        "reverse_words",
        "Write a Python function `reverse_words(s)` that reverses the order "
        "of words in a string, collapsing runs of whitespace to one space and "
        "stripping leading/trailing space. Return only the function.",
        "assert reverse_words('  the sky   is blue  ') == 'blue is sky the'\n"
        "assert reverse_words('hello') == 'hello'\n",
        "def reverse_words(s):\n    return s[::-1]\n",
    ),
    Task(
        "binary_search",
        "Write a Python function `binary_search(arr, target)` that returns "
        "the index of `target` in the sorted list `arr`, or -1 if absent. "
        "Return only the function.",
        "assert binary_search([1,3,5,7,9], 7) == 3\n"
        "assert binary_search([1,3,5,7,9], 1) == 0\n"
        "assert binary_search([1,3,5,7,9], 9) == 4\n"
        "assert binary_search([1,3,5,7,9], 4) == -1\n"
        "assert binary_search([], 1) == -1\n",
        "def binary_search(arr, target):\n"
        "    lo, hi = 0, len(arr) - 1\n"
        "    while lo < hi:\n"          # off-by-one: misses the boundary
        "        mid = (lo + hi) // 2\n"
        "        if arr[mid] == target: return mid\n"
        "        if arr[mid] < target: lo = mid + 1\n"
        "        else: hi = mid - 1\n"
        "    return -1\n",
    ),
    Task(
        "group_anagrams",
        "Write a Python function `group_anagrams(words)` that groups a list "
        "of strings into lists of anagrams. Return a list of lists. Return "
        "only the function.",
        "r = group_anagrams(['eat','tea','tan','ate','nat','bat'])\n"
        "norm = sorted(sorted(g) for g in r)\n"
        "assert norm == [['ate','eat','tea'],['bat'],['nat','tan']], r\n",
        "def group_anagrams(words):\n    return [words]\n",
    ),
    Task(
        "merge_intervals",
        "Write a Python function `merge_intervals(intervals)` that merges "
        "overlapping intervals given as a list of [start, end] pairs and "
        "returns the merged list sorted by start. Return only the function.",
        "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == "
        "[[1,6],[8,10],[15,18]]\n"
        "assert merge_intervals([[1,4],[4,5]]) == [[1,5]]\n"
        "assert merge_intervals([]) == []\n",
        "def merge_intervals(intervals):\n    return intervals\n",
    ),
    Task(
        "lru_cache",
        "Write a Python class `LRUCache` with `__init__(self, capacity)`, "
        "`get(self, key)` returning -1 if absent, and `put(self, key, value)` "
        "evicting the least recently used entry when over capacity. Return "
        "only the class.",
        "c = LRUCache(2)\n"
        "c.put(1,1); c.put(2,2)\n"
        "assert c.get(1) == 1\n"
        "c.put(3,3)\n"
        "assert c.get(2) == -1\n"
        "assert c.get(3) == 3\n",
        "class LRUCache:\n"
        "    def __init__(self, capacity): self.d = {}\n"
        "    def get(self, key): return self.d.get(key, -1)\n"
        "    def put(self, key, value): self.d[key] = value\n",
    ),
    Task(
        "valid_parentheses",
        "Write a Python function `is_valid(s)` returning True if a string of "
        "'()[]{}' is correctly bracketed. Return only the function.",
        "assert is_valid('()[]{}') is True\n"
        "assert is_valid('(]') is False\n"
        "assert is_valid('([)]') is False\n"
        "assert is_valid('') is True\n",
        "def is_valid(s):\n    return len(s) % 2 == 0\n",
    ),
    Task(
        "flatten_dict",
        "Write a Python function `flatten(d, sep='.')` that flattens a nested "
        "dictionary into one level, joining keys with `sep`. Return only the "
        "function.",
        "assert flatten({'a': {'b': {'c': 1}}, 'd': 2}) == {'a.b.c': 1, 'd': 2}\n"
        "assert flatten({'x': 1}) == {'x': 1}\n",
        "def flatten(d, sep='.'):\n    return d\n",
    ),
    Task(
        "roman_to_int",
        "Write a Python function `roman_to_int(s)` converting a Roman numeral "
        "string to an int. Handle subtractive pairs like IV and IX. Return "
        "only the function.",
        "assert roman_to_int('III') == 3\n"
        "assert roman_to_int('LVIII') == 58\n"
        "assert roman_to_int('MCMXCIV') == 1994\n",
        "def roman_to_int(s):\n"
        "    v = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n"
        "    return sum(v[c] for c in s)\n",   # ignores subtractive pairs
    ),
    Task(
        "safe_divide",
        "Write a Python function `safe_divide(a, b)` returning a / b as a "
        "float, or None if b is zero. It must not raise. Return only the "
        "function.",
        "assert safe_divide(10, 2) == 5.0\n"
        "assert safe_divide(1, 0) is None\n"
        "assert safe_divide(-9, 3) == -3.0\n",
        "def safe_divide(a, b):\n    return a / b\n",
    ),
    Task(
        "longest_common_prefix",
        "Write a Python function `longest_common_prefix(strs)` returning the "
        "longest common prefix of a list of strings, or '' if there is none. "
        "Return only the function.",
        "assert longest_common_prefix(['flower','flow','flight']) == 'fl'\n"
        "assert longest_common_prefix(['dog','racecar','car']) == ''\n"
        "assert longest_common_prefix([]) == ''\n",
        "def longest_common_prefix(strs):\n"
        "    return strs[0] if strs else ''\n",
    ),
    Task(
        "fibonacci",
        "Write a Python function `fib(n)` returning the nth Fibonacci number, "
        "with fib(0)=0 and fib(1)=1. Return only the function.",
        "assert fib(0) == 0\n"
        "assert fib(1) == 1\n"
        "assert fib(10) == 55\n"
        "assert fib(20) == 6765\n",
        "def fib(n):\n    return n\n",
    ),
]


@dataclass
class TaskResult:
    task_id: str
    passed: bool
    duration_sec: float
    error: str = ""
    code: str = ""


@dataclass
class RunReport:
    model: str
    results: List[TaskResult] = field(default_factory=list)
    total_sec: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def total(self) -> int:
        return len(self.results)


def ollama_host() -> str:
    """
    Normalise OLLAMA_HOST. On this machine it is set scheme-less to
    `0.0.0.0:11434`; urllib cannot open that, and 0.0.0.0 is a bind address,
    not a client address.
    """
    raw = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").strip()
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.replace("0.0.0.0", "127.0.0.1")
    return f"http://{raw}"


def generate(prompt: str, model: str, timeout: int = 180) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "seed": 7},
    }).encode()
    req = urllib.request.Request(
        f"{ollama_host()}/api/generate", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()).get("response", "")


def extract_code(text: str) -> str:
    """
    Take the fenced block if there is one, else the whole reply, then keep
    only the definitions.

    Models routinely append their own demo calls and self-written test
    harnesses. The first version of this script executed all of it, and that
    measured the wrong thing. `reverse_words` was recorded as a FAIL on a run
    where the function was correct:

        def reverse_words(s):
            words = s.split(); words.reverse()
            return ' '.join(words)               # correct

        def check_solution():
            test_cases = [..., ("  ", " ")]      # the model's own test, and
            ...                                  # it is wrong: the answer
        check_solution()                         # for "  " is "", not " "

    The model's bad test raised, the file exited non-zero, and the task went
    down as a failure. That is a defect in this harness, not in the model --
    exactly the kind of number this repo has spent twenty-eight passes
    removing, arrived at from the other direction.

    So: parse, keep imports / functions / classes / module constants, drop
    top-level calls and `if __name__` blocks. Code that does not parse is
    returned untouched -- a syntax error is a real failure and stays one.
    """
    # Reasoning models (qwen3, deepseek-r1) emit a <think> block before the
    # answer. Left in, it is a syntax error, and the task fails for a reason
    # that has nothing to do with the code -- the same harness-not-model
    # mistake as the demo-call bug above.
    if "</think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    elif "<think>" in text:
        # Opened and never closed -- the model ran out of budget mid-thought.
        # Keep only what follows a fence, if any; otherwise there is no answer.
        after = re.split(r"<think>", text, maxsplit=1)[1]
        fenced = re.findall(r"```(?:python)?\s*\n(.*?)```", after, re.DOTALL)
        text = max(fenced, key=len) if fenced else ""

    fences = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    code = max(fences, key=len).strip() if fences else text.strip()

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    kept: List[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Import, ast.ImportFrom,
                             ast.Assign, ast.AnnAssign)):
            kept.append(node)
        # Everything else -- bare calls, prints, `if __name__ == "__main__"`,
        # the model's own asserts -- is demo code, not the answer.

    if not kept:
        return code
    return ast.unparse(ast.Module(body=kept, type_ignores=[]))


def run_in_subprocess(code: str, test: str, timeout: int = 15) -> tuple[bool, str]:
    """Execute code + test in a separate process. Never in this one."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "candidate.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code + "\n\n" + test)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", path],
                capture_output=True, text=True, timeout=timeout,
                cwd=tmp, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return False, f"timed out after {timeout}s"
        if proc.returncode == 0:
            return True, ""
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, (err[-1] if err else f"exit {proc.returncode}")[:200]


def verify_tests_can_fail() -> List[str]:
    """
    Every test must fail against a deliberately wrong implementation.

    This is the check the existing harness in saleha/harness/ does not do: its
    tasks carry `assert True`, which passes for any output, so its pass rate
    could never have been anything but 100%.
    """
    broken = []
    for task in TASKS:
        ok, _ = run_in_subprocess(task.wrong_impl, task.test)
        if ok:
            broken.append(task.task_id)
    return broken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2.5-coder:3b")
    parser.add_argument("--verify-tests-only", action="store_true",
                        help="only check that each test fails on wrong code")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args()

    print(f"Verifying {len(TASKS)} tests can actually fail...")
    broken = verify_tests_can_fail()
    if broken:
        print(f"  REFUSING TO RUN: these tests pass against deliberately "
              f"wrong code: {broken}")
        print("  A test that cannot fail cannot measure anything.")
        return 2
    print(f"  all {len(TASKS)} tests fail on wrong code, as they must.\n")

    if args.verify_tests_only:
        return 0

    report = RunReport(model=args.model)
    run_start = time.time()

    for i, task in enumerate(TASKS, 1):
        print(f"[{i:2d}/{len(TASKS)}] {task.task_id:24s} ", end="", flush=True)
        started = time.time()
        try:
            reply = generate(task.prompt, args.model)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            elapsed = round(time.time() - started, 1)
            report.results.append(TaskResult(
                task.task_id, False, elapsed, f"model call failed: {exc}"))
            print(f"MODEL ERROR  ({elapsed}s)  {exc}")
            continue

        code = extract_code(reply)
        ok, err = run_in_subprocess(code, task.test)
        elapsed = round(time.time() - started, 1)
        report.results.append(TaskResult(task.task_id, ok, elapsed, err, code))
        print(f"{'PASS' if ok else 'FAIL'}  ({elapsed}s)"
              + (f"  {err}" if err else ""))

    report.total_sec = round(time.time() - run_start, 1)

    print()
    print("=" * 62)
    print(f"  {report.passed}/{report.total} tasks passed"
          f"   model {report.model}   {report.total_sec}s")
    print("=" * 62)
    failures = [r for r in report.results if not r.passed]
    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  {r.task_id:24s} {r.error}")
    print("\nThis is twelve small self-contained problems on one local model. "
          "\nIt is not SWE-bench and not a leaderboard position. Report it as "
          f"\n\"{report.passed}/{report.total} with these failures\", never as "
          "a percentage on its own.")

    if args.as_json:
        print(json.dumps({
            "model": report.model,
            "passed": report.passed,
            "total": report.total,
            "duration_sec": report.total_sec,
            "results": [{"task": r.task_id, "passed": r.passed,
                         "duration_sec": r.duration_sec, "error": r.error}
                        for r in report.results],
        }, indent=2))

    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    sys.exit(main())
