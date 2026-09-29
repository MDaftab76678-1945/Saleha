"""
Saleha Core: agent benchmark -- can `saleha agent` fix a real bug in a small repo?

`real_task_bench` and `hard_task_bench` measure a model writing one function.
Nothing measured the agent loop itself: reading a repo, finding the bug,
patching the right file and getting the tests green. Every agent-loop change
(context compaction, subagents, plans) needs that number to be judged.

Each task is a tiny repo with one planted bug, a goal phrased as a user would
report it, visible tests the agent can run, and HIDDEN tests it never sees.
A task counts as solved only when the hidden tests pass on the repo the agent
left behind -- never on the agent's own claim.

The same two gates as the other benches, applied before any score:
- the hidden tests must FAIL on the buggy repo, and
- they must PASS once the reference fix is applied.
A task that fails either gate is refused, not scored.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class AgentTask:
    task_id: str
    goal: str
    files: Dict[str, str]          # the buggy repo: path -> content
    fix: Dict[str, str]            # reference fix: path -> full fixed content
    hidden_test: str               # pytest source, never written into the repo the agent sees


@dataclass
class AgentOutcome:
    task_id: str
    solved: bool
    agent_claimed: bool            # the loop reported success
    steps: int
    seconds: float
    detail: str = ""


@dataclass
class AgentBenchReport:
    model: str
    outcomes: List[AgentOutcome] = field(default_factory=list)
    refused: List[str] = field(default_factory=list)

    @property
    def solved(self) -> int:
        return sum(o.solved for o in self.outcomes)

    @property
    def false_claims(self) -> int:
        """The loop said success, the hidden tests say otherwise."""
        return sum(o.agent_claimed and not o.solved for o in self.outcomes)

    def summary_line(self) -> str:
        return (f"{self.model}: solved {self.solved}/{len(self.outcomes)}, "
                f"false success claims {self.false_claims}"
                + (f", refused {self.refused}" if self.refused else ""))


def _write(root: str, files: Dict[str, str]) -> None:
    for rel, content in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)


def run_hidden_test(root: str, hidden_test: str, timeout: int = 60) -> Tuple[bool, str]:
    """Run the hidden tests against the repo at `root`, from outside it."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tdir:
        test_path = os.path.join(tdir, "test_hidden.py")
        with open(test_path, "w", encoding="utf-8") as fh:
            fh.write(hidden_test)
        # An empty bytecode prefix, so the grade never reads a .pyc the agent's
        # own test runs left in the repo. PYTHONDONTWRITEBYTECODE stops writes
        # only; a stale .pyc (same size, same second) was still read and a
        # real fix graded as failed.
        env = dict(os.environ, PYTHONPATH=root, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPYCACHEPREFIX=os.path.join(tdir, "pycache"))
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=tdir, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"hidden tests timed out after {timeout}s"
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or [f"exit {proc.returncode}"]
    return proc.returncode == 0, tail[0][:200]


def check_task(task: AgentTask) -> str:
    """'' when the task can measure something, else why it cannot."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        _write(root, task.files)
        ok, _ = run_hidden_test(root, task.hidden_test)
        if ok:
            return "hidden tests pass on the buggy repo"
        _write(root, task.fix)
        ok, detail = run_hidden_test(root, task.hidden_test)
        if not ok:
            return f"hidden tests fail on the reference fix: {detail}"
    return ""


def run_task(task: AgentTask, agent_factory: Callable[[], object], max_steps: int = 15,
             timeout_sec: float = 900.0, **loop_kwargs: Any) -> AgentOutcome:
    """One agent run on a fresh copy of the buggy repo, graded by the hidden tests."""
    from saleha.core.loop.agentic_loop import AgentLoop

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        _write(root, task.files)
        started = time.time()
        try:
            loop = AgentLoop(agent=agent_factory(), root_dir=root, max_steps=max_steps,
                             allow_write=True, timeout_sec=timeout_sec, **loop_kwargs)
            res = loop.run(task.goal)
            claimed, steps, err = res.success, len(res.steps), res.error
        except Exception as exc:  # noqa: BLE001 -- a crashed run is a failed run, and says why
            claimed, steps, err = False, 0, f"agent crashed: {type(exc).__name__}: {exc}"
        seconds = round(time.time() - started, 1)
        solved, detail = run_hidden_test(root, task.hidden_test)
    return AgentOutcome(task.task_id, solved, claimed, steps, seconds, detail if not solved else err)


def run_bench(model: str, tasks: Optional[List[AgentTask]] = None,
              on_task: Optional[Callable[[AgentOutcome], None]] = None,
              **loop_kwargs: Any) -> AgentBenchReport:
    from saleha.agents.base_agent import BaseAgent

    report = AgentBenchReport(model=model)
    for task in tasks or AGENT_TASKS:
        why = check_task(task)
        if why:
            report.refused.append(f"{task.task_id}: {why}")
            continue
        outcome = run_task(task, lambda: BaseAgent(role="Agent", model=model), **loop_kwargs)
        report.outcomes.append(outcome)
        if on_task:
            on_task(outcome)
    return report


def _t(task_id: str, goal: str, files: Dict[str, str], fix: Dict[str, str], hidden: str) -> AgentTask:
    return AgentTask(task_id, goal, files, fix, hidden)


AGENT_TASKS: List[AgentTask] = [
    _t("pager_off_by_one",
       "Users report that page() in the shop returns one item too many per page. Fix the bug.",
       {"shop/__init__.py": "",
        "shop/pager.py": "def page(items, number, size):\n"
                         "    \"\"\"Return page `number` (0-based) of `items`, `size` per page.\"\"\"\n"
                         "    start = number * size\n"
                         "    return items[start:start + size + 1]\n",
        "tests/test_pager.py": "from shop.pager import page\n\n"
                               "def test_first_page():\n    assert page(list(range(10)), 0, 3) == [0, 1, 2]\n"},
       {"shop/pager.py": "def page(items, number, size):\n"
                         "    \"\"\"Return page `number` (0-based) of `items`, `size` per page.\"\"\"\n"
                         "    start = number * size\n"
                         "    return items[start:start + size]\n"},
       "from shop.pager import page\n\n"
       "def test_pages():\n"
       "    data = list(range(10))\n"
       "    assert page(data, 0, 3) == [0, 1, 2]\n"
       "    assert page(data, 1, 3) == [3, 4, 5]\n"
       "    assert page(data, 3, 3) == [9]\n"
       "    assert page(data, 4, 3) == []\n"),

    _t("discount_percent",
       "A 10% discount on a 200.0 cart total gives 190.0 instead of 180.0. Fix it.",
       {"billing/__init__.py": "",
        "billing/discount.py": "def apply_discount(price, percent):\n"
                               "    \"\"\"Price after taking `percent` percent off.\"\"\"\n"
                               "    return price - percent\n",
        "billing/cart.py": "from billing.discount import apply_discount\n\n\n"
                           "def cart_total(prices, percent=0):\n"
                           "    return apply_discount(sum(prices), percent)\n",
        "tests/test_cart.py": "from billing.cart import cart_total\n\n"
                              "def test_discount():\n    assert cart_total([150.0, 50.0], 10) == 180.0\n"},
       {"billing/discount.py": "def apply_discount(price, percent):\n"
                               "    \"\"\"Price after taking `percent` percent off.\"\"\"\n"
                               "    return price * (100 - percent) / 100\n"},
       "import pytest\nfrom billing.cart import cart_total\nfrom billing.discount import apply_discount\n\n"
       "def test_discount():\n"
       "    assert cart_total([150.0, 50.0], 10) == pytest.approx(180.0)\n"
       "    assert cart_total([80.0], 0) == pytest.approx(80.0)\n"
       "    assert apply_discount(50.0, 50) == pytest.approx(25.0)\n"
       "    assert apply_discount(10.0, 100) == pytest.approx(0.0)\n"),

    _t("date_day_month",
       "parse_date('03-04-2024') should be 3 April 2024 (the format is DD-MM-YYYY) but the "
       "app shows March 4. Fix the parser.",
       {"util/__init__.py": "",
        "util/dates.py": "import datetime\n\n\n"
                         "def parse_date(text):\n"
                         "    \"\"\"Parse DD-MM-YYYY into a date.\"\"\"\n"
                         "    a, b, year = (int(p) for p in text.strip().split('-'))\n"
                         "    return datetime.date(year, a, b)\n",
        "tests/test_dates.py": "import datetime\nfrom util.dates import parse_date\n\n"
                               "def test_parse():\n    assert parse_date('03-04-2024') == datetime.date(2024, 4, 3)\n"},
       {"util/dates.py": "import datetime\n\n\n"
                         "def parse_date(text):\n"
                         "    \"\"\"Parse DD-MM-YYYY into a date.\"\"\"\n"
                         "    day, month, year = (int(p) for p in text.strip().split('-'))\n"
                         "    return datetime.date(year, month, day)\n"},
       "import datetime\nfrom util.dates import parse_date\n\n"
       "def test_parse():\n"
       "    assert parse_date('03-04-2024') == datetime.date(2024, 4, 3)\n"
       "    assert parse_date('25-12-2023') == datetime.date(2023, 12, 25)\n"
       "    assert parse_date(' 01-02-2000 ') == datetime.date(2000, 2, 1)\n"),

    _t("merge_mutates_defaults",
       "After calling load_config({'debug': True}) once, every later load_config({}) also has "
       "debug=True. The defaults are being changed. Fix it.",
       {"app/__init__.py": "",
        "app/config.py": "DEFAULTS = {'debug': False, 'retries': 3}\n\n\n"
                         "def load_config(overrides):\n"
                         "    config = DEFAULTS\n"
                         "    config.update(overrides)\n"
                         "    return config\n",
        "tests/test_config.py": "from app.config import load_config\n\n"
                                "def test_override():\n    assert load_config({'debug': True})['debug'] is True\n"},
       {"app/config.py": "DEFAULTS = {'debug': False, 'retries': 3}\n\n\n"
                         "def load_config(overrides):\n"
                         "    config = dict(DEFAULTS)\n"
                         "    config.update(overrides)\n"
                         "    return config\n"},
       "from app.config import DEFAULTS, load_config\n\n"
       "def test_defaults_untouched():\n"
       "    assert load_config({'debug': True})['debug'] is True\n"
       "    assert load_config({})['debug'] is False\n"
       "    assert DEFAULTS == {'debug': False, 'retries': 3}\n"
       "    assert load_config({'retries': 5})['retries'] == 5\n"),

    _t("stock_goes_negative",
       "remove_stock lets the stock go below zero. Removing more than is in stock must raise "
       "ValueError and leave the stock unchanged. Fix it.",
       {"store/__init__.py": "",
        "store/inventory.py": "class Inventory:\n"
                              "    def __init__(self):\n"
                              "        self.stock = {}\n\n"
                              "    def add_stock(self, item, qty):\n"
                              "        self.stock[item] = self.stock.get(item, 0) + qty\n\n"
                              "    def remove_stock(self, item, qty):\n"
                              "        self.stock[item] = self.stock.get(item, 0) - qty\n",
        "tests/test_inventory.py": "from store.inventory import Inventory\n\n"
                                   "def test_remove():\n    inv = Inventory()\n    inv.add_stock('pen', 5)\n"
                                   "    inv.remove_stock('pen', 2)\n    assert inv.stock['pen'] == 3\n"},
       {"store/inventory.py": "class Inventory:\n"
                              "    def __init__(self):\n"
                              "        self.stock = {}\n\n"
                              "    def add_stock(self, item, qty):\n"
                              "        self.stock[item] = self.stock.get(item, 0) + qty\n\n"
                              "    def remove_stock(self, item, qty):\n"
                              "        have = self.stock.get(item, 0)\n"
                              "        if qty > have:\n"
                              "            raise ValueError(f'only {have} {item} in stock')\n"
                              "        self.stock[item] = have - qty\n"},
       "import pytest\nfrom store.inventory import Inventory\n\n"
       "def test_never_negative():\n"
       "    inv = Inventory()\n    inv.add_stock('pen', 5)\n"
       "    with pytest.raises(ValueError):\n        inv.remove_stock('pen', 6)\n"
       "    assert inv.stock['pen'] == 5\n"
       "    inv.remove_stock('pen', 5)\n    assert inv.stock['pen'] == 0\n"
       "    with pytest.raises(ValueError):\n        inv.remove_stock('ink', 1)\n"),

    _t("median_even",
       "The stats report shows the wrong median when there is an even number of values. Fix it.",
       {"report/__init__.py": "",
        "report/stats.py": "def mean(values):\n    return sum(values) / len(values)\n\n\n"
                           "def median(values):\n"
                           "    ordered = sorted(values)\n"
                           "    return ordered[len(ordered) // 2]\n",
        "report/summary.py": "from report.stats import mean, median\n\n\n"
                             "def summarize(values):\n"
                             "    return {'mean': mean(values), 'median': median(values)}\n",
        "tests/test_summary.py": "from report.summary import summarize\n\n"
                                 "def test_odd():\n    assert summarize([3, 1, 2])['median'] == 2\n"},
       {"report/stats.py": "def mean(values):\n    return sum(values) / len(values)\n\n\n"
                           "def median(values):\n"
                           "    ordered = sorted(values)\n"
                           "    mid = len(ordered) // 2\n"
                           "    if len(ordered) % 2:\n"
                           "        return ordered[mid]\n"
                           "    return (ordered[mid - 1] + ordered[mid]) / 2\n"},
       "from report.summary import summarize\n\n"
       "def test_median():\n"
       "    assert summarize([3, 1, 2])['median'] == 2\n"
       "    assert summarize([4, 1, 3, 2])['median'] == 2.5\n"
       "    assert summarize([10, 20])['median'] == 15\n"),

    _t("slug_dashes",
       "slugify('Hello,  World!') gives 'hello---world-' but should give 'hello-world'. "
       "Runs of separators must become one dash, with no dash at either end. Fix it.",
       {"web/__init__.py": "",
        "web/text.py": "def slugify(title):\n"
                       "    out = []\n"
                       "    for ch in title.lower():\n"
                       "        out.append(ch if ch.isalnum() else '-')\n"
                       "    return ''.join(out)\n",
        "tests/test_text.py": "from web.text import slugify\n\n"
                              "def test_simple():\n    assert slugify('Hello') == 'hello'\n"},
       {"web/text.py": "import re\n\n\n"
                       "def slugify(title):\n"
                       "    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')\n"},
       "from web.text import slugify\n\n"
       "def test_slug():\n"
       "    assert slugify('Hello,  World!') == 'hello-world'\n"
       "    assert slugify('  Saleha 2.0  ') == 'saleha-2-0'\n"
       "    assert slugify('a--b') == 'a-b'\n"),

    _t("retry_count",
       "call_with_retry(fn, retries=3) should call fn at most 3 times in total, but a function "
       "that always fails is called 4 times. Fix it.",
       {"net/__init__.py": "",
        "net/retry.py": "def call_with_retry(fn, retries=3):\n"
                        "    last = None\n"
                        "    for _ in range(retries + 1):\n"
                        "        try:\n"
                        "            return fn()\n"
                        "        except Exception as exc:\n"
                        "            last = exc\n"
                        "    raise last\n",
        "tests/test_retry.py": "from net.retry import call_with_retry\n\n"
                               "def test_success():\n    assert call_with_retry(lambda: 7) == 7\n"},
       {"net/retry.py": "def call_with_retry(fn, retries=3):\n"
                        "    last = None\n"
                        "    for _ in range(retries):\n"
                        "        try:\n"
                        "            return fn()\n"
                        "        except Exception as exc:\n"
                        "            last = exc\n"
                        "    raise last\n"},
       "import pytest\nfrom net.retry import call_with_retry\n\n"
       "def test_attempts():\n"
       "    calls = []\n"
       "    def bad():\n        calls.append(1)\n        raise OSError('down')\n"
       "    with pytest.raises(OSError):\n        call_with_retry(bad, retries=3)\n"
       "    assert len(calls) == 3\n"
       "    assert call_with_retry(lambda: 'ok', retries=1) == 'ok'\n"),
]
