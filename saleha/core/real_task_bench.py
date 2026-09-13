"""Saleha Core: the honest local task benchmark.

Every task here has three parts, and the third is what makes the number mean
anything:

  * a real prompt, sent to a real model,
  * a real test that must fail on wrong code,
  * a deliberately wrong implementation, run **before** the benchmark starts.

If any test passes against its wrong implementation, the run refuses to
start. A test that cannot fail cannot measure anything -- that is precisely
how `swe_leaderboard.py` used to report 100%: it "generated" each fix by
returning `task["expected_fix"]`, the answer key, and then checked the answer
key against the test.

## Why this module exists at all

The logic here was already written and already honest, but it lived in
`scripts/measure_real_pass_rate.py`. `pyproject.toml` ships only `saleha*`,
and `scripts/` has no `__init__.py` -- so the one trustworthy measurement in
this repository was unreachable from the installed package and from every
CLI command. The fabricated harnesses were the ones wired up. Moving the
engine here makes the honest path the importable one.

## What a number from this module is, and is not

Twelve small self-contained programming problems, run against one local
model on one machine. It is **not** SWE-bench, not a leaderboard position,
and not a claim about multi-file repository work. Report it as
"9/12, with these three failures", never as a percentage standing alone.

Scored SWE-bench is not currently possible on this machine and this module
does not pretend otherwise: the `swebench` package is not installed, the
Docker daemon is not running, and HuggingFace `datasets` is absent (the
importable `datasets` name resolves to this repo's own synthesizer folder,
which is not a package). `swe_bench_runner.py` covers the real
predictions.jsonl path for when that infrastructure exists.
"""

from __future__ import annotations

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
from typing import List, Optional, Tuple

DEFAULT_MODEL = "qwen2.5-coder:3b"


@dataclass
class Task:
    task_id: str
    prompt: str
    # Appended to the generated code and executed. Must raise on wrong output.
    test: str
    # A deliberately wrong implementation. The test must fail against this --
    # checked before any run, so a test that cannot fail never counts.
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
class TaskOutcome:
    task_id: str
    passed: bool
    duration_sec: float
    error: str = ""
    code: str = ""


@dataclass
class BenchRunReport:
    model: str
    outcomes: List[TaskOutcome] = field(default_factory=list)
    total_sec: float = 0.0
    # False when the run never started (tests could not fail, or the model was
    # unreachable). A report that did not run reports no score.
    did_run: bool = True
    refused_reason: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for o in self.outcomes if o.passed)

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def pass_rate(self) -> float:
        if not self.did_run or not self.outcomes:
            return 0.0
        return round(self.passed / len(self.outcomes) * 100, 1)

    def summary_line(self) -> str:
        if not self.did_run:
            return f"Did not run: {self.refused_reason}"
        return (f"{self.passed}/{self.total} tasks passed on {self.model} "
                f"in {self.total_sec}s")


def ollama_host() -> str:
    """Normalise OLLAMA_HOST.

    On this machine it is set scheme-less to `0.0.0.0:11434`; urllib cannot
    open that, and 0.0.0.0 is a bind address, not a client address.
    """
    raw = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").strip()
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.replace("0.0.0.0", "127.0.0.1")
    return f"http://{raw}"


def generate(prompt: str, model: str, timeout: int = 180) -> str:
    """One real completion from Ollama. Raises on transport failure."""
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
    """Take the fenced block if there is one, then keep only definitions.

    Models routinely append their own demo calls and self-written tests. An
    earlier version of this harness executed all of it, and that measured the
    wrong thing: `reverse_words` was recorded FAIL on a run where the function
    was correct, because the model's own appended test asserted `("  ", " ")`
    and the right answer is `""`. Its bad assert raised, the file exited
    non-zero, and a correct answer went down as a failure -- a fabricated
    failure, the same defect as a fabricated pass, arrived at from the other
    side.

    Code that does not parse is returned untouched: a syntax error is a real
    failure and stays one.
    """
    # Reasoning models (qwen3, deepseek-r1) emit a <think> block before the
    # answer. Left in, it is a syntax error and the task fails for a reason
    # that has nothing to do with the code.
    if "</think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    elif "<think>" in text:
        # Opened and never closed -- the model ran out of budget mid-thought.
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
        # Everything else -- bare calls, prints, `if __name__`, the model's
        # own asserts -- is demo code, not the answer.

    if not kept:
        return code
    return ast.unparse(ast.Module(body=kept, type_ignores=[]))


def run_in_subprocess(code: str, test: str, timeout: int = 15) -> Tuple[bool, str]:
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


def verify_tests_can_fail(tasks: Optional[List[Task]] = None) -> List[str]:
    """Return the ids of any task whose test passes against wrong code.

    This is the gate the fabricated harnesses did not have. `swe_leaderboard`
    graded the answer key against the test; `saleha/harness/`'s tasks carry
    `test_patch="assert True"`. Both could only ever score 100%.
    """
    broken = []
    for task in (tasks or TASKS):
        ok, _ = run_in_subprocess(task.wrong_impl, task.test)
        if ok:
            broken.append(task.task_id)
    return broken


def run_benchmark(model: str = DEFAULT_MODEL,
                  tasks: Optional[List[Task]] = None,
                  limit: Optional[int] = None,
                  on_task=None) -> BenchRunReport:
    """Run every task against a real model and report what actually passed.

    Refuses to run -- rather than reporting a score -- if any test passes
    against its own deliberately wrong implementation.
    """
    task_list = list(tasks or TASKS)
    if limit:
        task_list = task_list[:limit]

    broken = verify_tests_can_fail(task_list)
    if broken:
        return BenchRunReport(
            model=model, did_run=False,
            refused_reason=(f"these tests pass against deliberately wrong "
                            f"code and so cannot measure anything: {broken}"))

    report = BenchRunReport(model=model)
    run_start = time.time()

    for task in task_list:
        started = time.time()
        try:
            reply = generate(task.prompt, model)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            elapsed = round(time.time() - started, 1)
            outcome = TaskOutcome(task.task_id, False, elapsed,
                                  f"model call failed: {exc}")
            report.outcomes.append(outcome)
            if on_task:
                on_task(outcome)
            continue

        code = extract_code(reply)
        ok, err = run_in_subprocess(code, task.test)
        elapsed = round(time.time() - started, 1)
        outcome = TaskOutcome(task.task_id, ok, elapsed, err, code)
        report.outcomes.append(outcome)
        if on_task:
            on_task(outcome)

    report.total_sec = round(time.time() - run_start, 1)
    return report


def scored_swebench_availability() -> Tuple[bool, str]:
    """Whether a genuinely scored SWE-bench run is possible here.

    Checked rather than assumed, because claiming a SWE-bench number without
    this infrastructure is exactly the fabrication this module replaces.
    """
    missing = []
    try:
        import swebench  # noqa: F401
    except ImportError:
        missing.append("the `swebench` package is not installed")

    try:
        import datasets
        if not hasattr(datasets, "load_dataset"):
            missing.append("`datasets` resolves to a non-package directory, "
                           "not HuggingFace datasets")
    except ImportError:
        missing.append("HuggingFace `datasets` is not installed")

    try:
        proc = subprocess.run(["docker", "info"], capture_output=True,
                              text=True, timeout=30)
        if proc.returncode != 0:
            missing.append("the Docker daemon is not running")
    except (OSError, subprocess.SubprocessError):
        missing.append("Docker is not available")

    if missing:
        return False, "; ".join(missing)
    return True, "swebench, datasets and Docker are all available"
