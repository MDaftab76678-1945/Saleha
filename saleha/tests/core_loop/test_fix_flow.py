"""saleha fix: a fix is kept only when its receipt proves it; otherwise the repo is left as it was."""

from __future__ import annotations

import importlib.util
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List

from saleha.core.loop import fix_flow
from saleha.tests.agents.test_agentic_loop import ScriptedAgent, _finish, _tool_call

BUGGY = "def add(a, b):\n    return a - b\n"
TEST = "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def _git(root: str, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    return p.stdout


class _NoModel:
    def think(self, *_a: Any, **_k: Any) -> Any:
        raise AssertionError("the agent must not be called")


class FixFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "calc.py").write_bytes(BUGGY.encode())
        Path(self.root, "test_calc.py").write_bytes(TEST.encode())
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "config", "core.autocrlf", "false")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "init")
        self.state = os.path.join(self.root, "..", os.path.basename(self.root) + "-state")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fix(self, responses: List[Any], candidates: int = 0) -> fix_flow.FixResult:
        return fix_flow.fix_repo(
            self.root, model="scripted", test_command=PYTEST, max_steps=8, timeout=120,
            agent_factory=lambda _m: ScriptedAgent(responses) if responses else _NoModel(),
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"), candidates=candidates,
            record=os.path.join(self.state, "dataset.jsonl"), search=False)

    def test_a_revert_leaves_no_bytecode_that_still_runs_the_reverted_edit(self) -> None:
        """git checkout restores the source but not __pycache__: a trusted .pyc of the
        taken-back edit (unchecked-hash here; a same-second same-size one in practice)
        would keep running it."""
        src = os.path.join(self.root, "calc.py")
        Path(src).write_bytes(b"def add(a, b):\n    return a + b\n")
        py_compile.compile(src, cfile=importlib.util.cache_from_source(src),
                           invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        self.assertEqual(fix_flow._revert(self.root, [(" M", "calc.py")]), [])
        self.assertEqual(Path(src).read_bytes(), BUGGY.encode())
        passed, out = fix_flow._run_tests(PYTEST, self.root, 120)
        self.assertIs(passed, False, out)          # the reverted, buggy code is what runs

    def test_a_failure_that_does_not_repeat_is_flaky_and_nothing_changes(self) -> None:
        flaky = ("import os\n\n\ndef test_sometimes():\n"
                 "    marker = os.path.join(os.path.dirname(__file__), '..', 'ran-once')\n"
                 "    first = not os.path.exists(marker)\n"
                 "    open(marker, 'w').close()\n"
                 "    assert not first\n")
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return a + b\n")
        Path(self.root, "test_calc.py").write_text(flaky, encoding="utf-8")
        _git(self.root, "commit", "-q", "-am", "flaky")
        res = self._fix([])
        Path(self.root, "..", "ran-once").unlink(missing_ok=True)
        self.assertEqual(res.verdict, fix_flow.FLAKY, res.reason)
        self.assertIn("passed on re-run 1", res.reason)
        self.assertFalse(res.ok)

    def test_a_proven_fix_is_recorded_locally_for_later_learning(self) -> None:
        import json
        res = self._fix([
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
            _finish("fixed"), _finish("fixed"),
        ])
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        rows = Path(self.state, "dataset.jsonl").read_text(encoding="utf-8").splitlines()
        rec = json.loads(rows[-1])
        self.assertEqual(rec["receipt"], "PROVEN")
        self.assertIn("+    return a + b", rec["diff"])
        self.assertEqual(rec["failing_tests"], ["test_calc.py::test_add"])

    def test_escalation_tries_the_bigger_model_on_a_clean_tree(self) -> None:
        small = ScriptedAgent([
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a * b"),
        ] + [_finish("fixed")] * 12)
        big = ScriptedAgent([
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
            _finish("fixed"), _finish("fixed"),
        ])
        res = fix_flow.fix_repo(
            self.root, model="small", escalate="big", test_command=PYTEST, max_steps=8, timeout=120,
            agent_factory=lambda m: small if m == "small" else big, candidates=0, search=False,
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"))
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertEqual(res.model, "big")
        self.assertIn("a + b", Path(self.root, "calc.py").read_text(encoding="utf-8"))

    def test_the_loop_checks_patches_against_the_failing_tests_only(self) -> None:
        from saleha.core.loop.agentic_loop import AgentLoop
        seen: List[Any] = []
        real_run = AgentLoop.run

        def spy(loop: AgentLoop, goal: str, on_event: Any = None) -> Any:
            seen.append((loop.test_command_override, dict(loop.focus_ranges), loop.require_test_read))
            return real_run(loop, goal, on_event=on_event)

        from unittest.mock import patch
        with patch.object(AgentLoop, "run", spy):
            self._fix([_tool_call("read_file", path="calc.py")] + [_finish("x")] * 8)
        override, focus, gate = seen[0]
        self.assertEqual(override, PYTEST + ["test_calc.py::test_add"])
        self.assertEqual(list(focus), ["calc.py"])
        self.assertFalse(gate)

    def test_a_drawn_candidate_patch_can_win_when_the_models_own_does_not(self) -> None:
        res = self._fix([
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a * b"),
            # drawn by the candidate search after the model's own patch failed
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
            _finish("fixed"), _finish("fixed"), _finish("fixed"),
        ], candidates=2)
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertIn("a + b", Path(self.root, "calc.py").read_text(encoding="utf-8"))

    def test_a_proven_fix_is_kept(self) -> None:
        res = self._fix([
            _tool_call("read_file", path="test_calc.py"),
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
            _finish("fixed"), _finish("fixed"), _finish("fixed"),
        ])
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        assert res.receipt is not None
        self.assertEqual(res.receipt["verdict"], "PROVEN")
        self.assertEqual(res.changed_files, ["calc.py"])
        self.assertEqual(res.failing_before, ["test_calc.py::test_add"])
        self.assertIn("a + b", Path(self.root, "calc.py").read_text(encoding="utf-8"))

    def test_an_unproven_fix_is_taken_back_out(self) -> None:
        res = self._fix([
            _tool_call("read_file", path="test_calc.py"),
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a * b"),
        ] + [_finish("fixed")] * 6)
        self.assertEqual(res.verdict, fix_flow.NOT_FIXED, res.reason)
        self.assertIn("reverted", res.reason)
        self.assertEqual(Path(self.root, "calc.py").read_bytes(), BUGGY.encode())
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")

    def test_uncommitted_work_is_never_touched(self) -> None:
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return b - a\n")
        res = self._fix([])
        self.assertEqual(res.verdict, fix_flow.CANNOT_RUN)
        self.assertIn("uncommitted", res.reason)
        self.assertEqual(Path(self.root, "calc.py").read_bytes(), b"def add(a, b):\n    return b - a\n")

    def test_a_passing_suite_calls_no_model(self) -> None:
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return a + b\n")
        _git(self.root, "commit", "-q", "-am", "good")
        res = self._fix([])
        self.assertEqual(res.verdict, fix_flow.ALREADY_PASSING, res.reason)
        self.assertTrue(res.ok)

    def test_leftover_bytecode_is_neither_dirt_nor_part_of_the_fix(self) -> None:
        # Not calc's own cache: patch_file drops the patched module's stale bytecode.
        cache = Path(self.root, "__pycache__")
        cache.mkdir()
        (cache / "other.cpython-312.pyc").write_bytes(b"junk")
        res = self._fix([
            _tool_call("read_file", path="test_calc.py"),
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
            _finish("fixed"), _finish("fixed"), _finish("fixed"),
        ])
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertEqual(res.changed_files, ["calc.py"])
        assert res.receipt is not None
        self.assertEqual(res.receipt["changed_files"], ["calc.py"])
        self.assertTrue((cache / "other.cpython-312.pyc").exists(), "caches found there stay")
        self.assertEqual(_git(self.root, "status", "--porcelain", "--untracked-files=all").split(),
                         ["M", "calc.py", "??", "__pycache__/other.cpython-312.pyc"])

    def _search_fix(self, agent: Any = None, **kw: Any) -> fix_flow.FixResult:
        return fix_flow.fix_repo(
            self.root, model="scripted", test_command=PYTEST, max_steps=8, timeout=120, candidates=0,
            agent_factory=lambda _m: agent or _NoModel(),
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"),
            record=os.path.join(self.state, "dataset.jsonl"), **kw)

    def test_a_one_edit_bug_is_fixed_and_proven_without_any_model(self) -> None:
        res = self._search_fix()          # _NoModel: calling the agent fails the test
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertEqual((res.model, res.agent_steps), (fix_flow.SEARCH, 0))
        assert res.receipt is not None and res.search is not None
        self.assertEqual(res.receipt["verdict"], "PROVEN")
        self.assertEqual(res.search["found"]["kind"], "'-' -> '+'")
        self.assertEqual(Path(self.root, "calc.py").read_bytes(), b"def add(a, b):\n    return a + b\n")

    def test_when_the_search_misses_the_model_still_gets_its_turn(self) -> None:
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return a\n")
        _git(self.root, "commit", "-q", "-am", "needs new code")
        agent = ScriptedAgent([_tool_call("read_file", path="calc.py"),
                               _tool_call("patch_file", path="calc.py", search="return a", replace="return a + b"),
                               _finish("fixed"), _finish("fixed")])
        res = self._search_fix(agent)
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertEqual(res.model, "scripted")
        assert res.search is not None
        self.assertIsNone(res.search["found"])
        self.assertGreaterEqual(res.search["tried"], 1)

    def test_no_model_stops_after_the_search_and_leaves_the_tree_clean(self) -> None:
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return a\n")
        _git(self.root, "commit", "-q", "-am", "needs new code")
        res = self._search_fix(use_model=False)       # _NoModel would fail the test if asked
        self.assertEqual(res.verdict, fix_flow.NOT_FIXED, res.reason)
        self.assertIn("no model was asked", res.reason)
        self.assertIn(fix_flow.SEARCH, res.reason)
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")

    def test_a_past_proven_fix_is_replayed_from_the_local_dataset_unless_memory_is_off(self) -> None:
        import json
        Path(self.root, "calc.py").write_bytes(b"def key(name):\n    return name.lower()\n")
        Path(self.root, "test_calc.py").write_bytes(
            "from calc import key\n\n\ndef test_german():\n    assert key('Straße') == 'strasse'\n".encode())
        _git(self.root, "commit", "-q", "-am", "lower is not enough")
        os.makedirs(self.state, exist_ok=True)
        diff = ("--- a/other.py\n+++ b/other.py\n@@ -1 +1 @@\n-    return s.lower()\n+    return s.casefold()\n")
        Path(self.state, "dataset.jsonl").write_text(json.dumps({"receipt": "PROVEN", "diff": diff}) + "\n",
                                                     encoding="utf-8")
        off = self._search_fix(use_model=False, memory=False)
        self.assertEqual(off.verdict, fix_flow.NOT_FIXED, off.reason)
        res = self._search_fix(use_model=False)
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        assert res.search is not None
        self.assertIn("learned from a past proven fix", res.search["found"]["kind"])

    def test_not_a_git_repo_cannot_be_proven(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as bare:
            res = fix_flow.fix_repo(bare, test_command=PYTEST, agent_factory=lambda _m: _NoModel())
        self.assertEqual(res.verdict, fix_flow.CANNOT_RUN)
        self.assertIn("not a git repository", res.reason)


class HardenTests(unittest.TestCase):
    """A proven but LOOSE fix gets a test that tells it from its surviving wrong version."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "price.py").write_bytes(b"def discount(total, percent):\n    return total\n")
        Path(self.root, "test_price.py").write_bytes(
            b"from price import discount\n\n\ndef test_ten():\n    assert discount(200, 10) == 180\n")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                     ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            _git(self.root, *args)
        self.state = os.path.join(self.root, "..", os.path.basename(self.root) + "-state")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_loose_fix_is_hardened_until_pinned(self) -> None:
        pin_test = ("import pytest\nfrom price import discount\n\n\ndef test_odd_total():\n"
                    "    assert discount(199, 10) == pytest.approx(179.1)\n")
        agents = [
            ScriptedAgent([_tool_call("read_file", path="price.py"),
                           _tool_call("patch_file", path="price.py", search="return total",
                                      replace="return total - total * percent / 100"),
                           _finish("fixed"), _finish("fixed")]),
            ScriptedAgent([_tool_call("write_file", path="test_saleha_pin_1.py", content=pin_test)]
                          + [_finish("written")] * 4),
        ]
        res = fix_flow.fix_repo(
            self.root, model="scripted", test_command=PYTEST, max_steps=8, timeout=120, candidates=0,
            agent_factory=lambda _m: agents.pop(0), harden_tests=True,
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"),
            record=os.path.join(self.state, "dataset.jsonl"))
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        assert res.pin is not None
        self.assertEqual(res.pin["verdict"], "PINNED", res.reason)
        self.assertIn("now caught by test_saleha_pin_1.py", res.reason)
        self.assertEqual(sorted(res.changed_files), ["price.py", "test_saleha_pin_1.py"])

    def test_without_harden_the_survivor_is_reported(self) -> None:
        res = fix_flow.fix_repo(
            self.root, model="scripted", test_command=PYTEST, max_steps=8, timeout=120, candidates=0,
            agent_factory=lambda _m: ScriptedAgent([
                _tool_call("read_file", path="price.py"),
                _tool_call("patch_file", path="price.py", search="return total",
                           replace="return total - total * percent / 100"),
                _finish("fixed"), _finish("fixed")]),
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"),
            record=os.path.join(self.state, "dataset.jsonl"))
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        assert res.pin is not None
        self.assertEqual(res.pin["verdict"], "LOOSE")
        self.assertEqual([m["kind"] for m in res.pin["survivors"]], ["'/' -> '//'"])


CART_JS = ("function applyCoupon(total, percent) {\n"
           "  if (percent < 0 || percent > 100) throw new RangeError('bad percent');\n"
           "  return total - total * percent / 10;\n"
           "}\n\nmodule.exports = { applyCoupon };\n")
CART_TEST_JS = ("const test = require('node:test');\nconst assert = require('node:assert');\n"
                "const { applyCoupon } = require('../src/cart');\n\n"
                "test('ten percent off', () => { assert.strictEqual(applyCoupon(200, 10), 180); });\n")


@unittest.skipUnless(__import__("shutil").which("node") and __import__("shutil").which("npm"),
                     "needs node and npm")
class FixJavaScriptTests(unittest.TestCase):
    """The same flow on a node --test project: discovery, failure parsing, receipt."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "src").mkdir()
        Path(self.root, "test").mkdir()
        Path(self.root, "package.json").write_text(
            '{"name": "cart", "version": "1.0.0", "scripts": {"test": "node --test"}}\n', encoding="utf-8")
        Path(self.root, "src", "cart.js").write_bytes(CART_JS.encode())
        Path(self.root, "test", "cart.test.js").write_bytes(CART_TEST_JS.encode())
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                     ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            _git(self.root, *args)
        self.state = os.path.join(self.root, "..", os.path.basename(self.root) + "-state")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_javascript_bug_is_fixed_and_proven_with_npm_test(self) -> None:
        res = fix_flow.fix_repo(
            self.root, model="scripted", max_steps=8, timeout=120, candidates=0,
            agent_factory=lambda _m: ScriptedAgent([
                _tool_call("read_file", path="src/cart.js"),
                _tool_call("patch_file", path="src/cart.js", search="percent / 10;", replace="percent / 100;"),
                _finish("fixed"), _finish("fixed"), _finish("fixed")]),
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"),
            record=os.path.join(self.state, "dataset.jsonl"))
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertIn("npm", os.path.basename(res.test_command[0]).lower())
        self.assertEqual(res.failing_before, ["ten percent off"])
        self.assertEqual(res.changed_files, ["src/cart.js"])


REPRO = "from calc import add\n\n\ndef test_add_reported():\n    assert add(2, 3) == 5\n"


class FixIssueTests(unittest.TestCase):
    """A bug report in: a reproducing test first, then a fix proven against it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "calc.py").write_bytes(
            b"def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n")
        Path(self.root, "test_calc.py").write_bytes(
            b"from calc import mul\n\n\ndef test_mul():\n    assert mul(2, 3) == 6\n")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                     ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            _git(self.root, *args)
        self.state = os.path.join(self.root, "..", os.path.basename(self.root) + "-state")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _issue(self, *phases: List[Any]) -> fix_flow.FixResult:
        agents = [ScriptedAgent(p) for p in phases]
        return fix_flow.fix_issue(
            self.root, "add(2, 3) returns -1; it should return 5", model="scripted",
            test_command=PYTEST, max_steps=8, timeout=120, repro_attempts=len(phases) - 1 or 1,
            agent_factory=lambda _m: agents.pop(0), candidates=0, search=False,
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"),
            record=os.path.join(self.state, "dataset.jsonl"))

    def test_report_to_reproducing_test_to_proven_fix(self) -> None:
        res = self._issue(
            [_tool_call("write_file", path="test_saleha_repro.py", content=REPRO), _finish("written")]
            + [_finish("written")] * 4,
            [_tool_call("read_file", path="calc.py"),
             _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
             _finish("fixed"), _finish("fixed")])
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertEqual(res.repro_tests, ["test_saleha_repro.py"])
        self.assertIn("assert add(2, 3) == 5", res.repro_source)
        self.assertEqual(sorted(res.changed_files), ["calc.py", "test_saleha_repro.py"])
        assert res.receipt is not None
        self.assertEqual(res.receipt["verdict"], "PROVEN")

    def test_a_test_that_passes_on_the_current_code_does_not_reproduce_anything(self) -> None:
        passing = "from calc import mul\n\n\ndef test_x():\n    assert mul(1, 1) == 1\n"
        res = self._issue(
            [_tool_call("write_file", path="test_saleha_repro.py", content=passing)] + [_finish("w")] * 5)
        self.assertEqual(res.verdict, fix_flow.NOT_REPRODUCED, res.reason)
        self.assertIn("PASSED on the current code", res.reason)
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")

    def test_a_reproduction_that_edits_source_is_thrown_away(self) -> None:
        res = self._issue(
            [_tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
             _tool_call("write_file", path="test_saleha_repro.py", content=REPRO)] + [_finish("w")] * 5)
        self.assertEqual(res.verdict, fix_flow.NOT_REPRODUCED, res.reason)
        self.assertIn("non-test files", res.reason)
        self.assertTrue(Path(self.root, "calc.py").read_bytes().startswith(b"def add(a, b):\n    return a - b"))
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")

    def test_a_report_without_a_model_cannot_be_reproduced(self) -> None:
        res = fix_flow.fix_issue(self.root, "add is wrong", test_command=PYTEST, use_model=False,
                                 agent_factory=lambda _m: _NoModel())
        self.assertEqual(res.verdict, fix_flow.CANNOT_RUN)
        self.assertIn("--no-model", res.reason)

    def test_issue_urls_are_fetched_and_plain_text_passes_through(self) -> None:
        from unittest.mock import patch

        class _R:
            status_code = 200

            def json(self) -> Any:
                return {"title": "add is wrong", "body": "add(2, 3) gives -1"}

        seen: List[str] = []
        with patch("requests.get", lambda url, **kw: (seen.append(url), _R())[1]):
            text, err = fix_flow.issue_text("https://github.com/acme/shop/issues/42")
        self.assertEqual((text, err), ("add is wrong\n\nadd(2, 3) gives -1", ""))
        self.assertEqual(seen, ["https://api.github.com/repos/acme/shop/issues/42"])
        self.assertEqual(fix_flow.issue_text("  add is broken  "), ("add is broken", ""))


class FocusedCommandTests(unittest.TestCase):
    def test_the_commands_test_paths_are_dropped_before_the_ids_are_added(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            Path(root, "tests").mkdir()
            argv = ["py", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-k", "tests", "tests"]
            self.assertEqual(fix_flow.focused_command(argv, ["tests/test_x.py::test_a"], root),
                             ["py", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-k", "tests",
                              "tests/test_x.py::test_a"])


class FixCommandTests(unittest.TestCase):
    def test_no_model_fixes_a_one_edit_bug_from_the_command_line(self) -> None:
        import json

        from click.testing import CliRunner

        from saleha.cli.commands import cli
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            Path(root, "calc.py").write_bytes(BUGGY.encode())
            Path(root, "test_calc.py").write_bytes(TEST.encode())
            for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                         ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
                _git(root, *args)
            cmd = f'"{sys.executable}" -m pytest -q -p no:cacheprovider'
            res = CliRunner().invoke(cli, ["fix", "--dir", root, "--json", "--no-model", cmd])
            out = json.loads(res.output.strip().splitlines()[-1])
        self.assertEqual(out["verdict"], "FIXED", out["reason"])
        self.assertEqual(out["model"], fix_flow.SEARCH)
        self.assertEqual(res.exit_code, 0, res.output)

    def test_the_cli_reports_a_repo_it_cannot_prove_in_json_and_exits_1(self) -> None:
        import json

        from click.testing import CliRunner

        from saleha.cli.commands import cli
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as bare:
            res = CliRunner().invoke(cli, ["fix", "--dir", bare, "--json"])
        self.assertEqual(res.exit_code, 1, res.output)
        out = json.loads(res.output.strip().splitlines()[-1])
        self.assertEqual(out["verdict"], "CANNOT_RUN")
        self.assertFalse(out["ok"])


def _ci_report_module(name: str = "ci_fix_report") -> Any:
    import importlib.util
    path = Path(__file__).resolve().parents[3] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CiFixReportTests(unittest.TestCase):
    """The GitHub Action's reading of `saleha fix --json`."""

    def test_unreadable_output_is_a_harness_error_not_a_pass(self) -> None:
        mod = _ci_report_module()
        res = mod.read_result(os.path.join(tempfile.gettempdir(), "no-such-saleha-fix.json"))
        self.assertEqual(res["verdict"], "HARNESS_ERROR")
        self.assertFalse(res["ok"])

    def test_outputs_and_summary_for_a_proven_fix(self) -> None:
        from unittest.mock import patch
        mod = _ci_report_module()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            src = Path(d, "fix.json")
            src.write_text("progress noise\n" + '{"verdict": "FIXED", "ok": true, "branch": "saleha/fix-1", '
                           '"reason": "proven", "receipt_markdown": "# Proof receipt: PROVEN\\n"}\n',
                           encoding="utf-8")
            out, summ = Path(d, "out"), Path(d, "summary")
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summ)}), \
                 patch("sys.argv", ["ci_fix_report.py", str(src), str(Path(d, "body.md"))]):
                mod.main()
            self.assertEqual(out.read_text(encoding="utf-8").split(),
                             ["verdict=FIXED", "branch=saleha/fix-1", "ok=true"])
            self.assertIn("Proof receipt: PROVEN", summ.read_text(encoding="utf-8"))
            self.assertIn("proved the fix", Path(d, "body.md").read_text(encoding="utf-8"))


class CiVerifyReportTests(unittest.TestCase):
    """The GitHub Action's reading of `saleha receipt --json` (mode: verify)."""

    def test_unreadable_receipt_is_a_harness_error_not_a_pass(self) -> None:
        mod = _ci_report_module("ci_verify_report")
        r = mod.read_receipt(os.path.join(tempfile.gettempdir(), "no-such-receipt.json"))
        self.assertEqual(r["verdict"], "HARNESS_ERROR")

    def test_multiline_json_and_an_unproven_verdict_explained(self) -> None:
        from unittest.mock import patch
        mod = _ci_report_module("ci_verify_report")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            src = Path(d, "r.json")
            src.write_text('{\n  "verdict": "UNPROVEN",\n  "reason": "tests pass with AND without the change",'
                           '\n  "head_run": {"ran": true, "passed": true, "seconds": 1.0}\n}\n', encoding="utf-8")
            out = Path(d, "out")
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": ""}), \
                 patch("sys.argv", ["ci_verify_report.py", str(src), str(Path(d, "c.md"))]):
                mod.main()
            self.assertEqual(out.read_text(encoding="utf-8").split(), ["verdict=UNPROVEN", "ok=false"])
            text = Path(d, "c.md").read_text(encoding="utf-8")
            self.assertIn("do not prove this change", text)
            self.assertIn("Tests with the change: PASS", text)


class FixFlowHelperTests(unittest.TestCase):
    def test_failing_tests_are_read_from_the_short_summary(self) -> None:
        out = ("..F\nFAILED tests/test_x.py::test_a - assert 1 == 2\n"
               "ERROR tests/test_y.py::test_b\n1 failed, 1 error")
        self.assertEqual(fix_flow.failing_tests(out),
                         [("tests/test_x.py::test_a", "assert 1 == 2"), ("tests/test_y.py::test_b", "")])

    def test_failures_from_other_runners(self) -> None:
        cases = {
            "\x1b[31m● math › adds two numbers\x1b[0m\n● Console\n": ["math › adds two numbers"],
            " FAIL  src/math.test.ts > math > adds\n": ["src/math.test.ts > math > adds"],
            "--- FAIL: TestAdd (0.00s)\nFAIL\n": ["TestAdd"],
            "test tests::adds ... FAILED\ntest tests::subs ... ok\n": ["tests::adds"],
            "not ok 2 - adds numbers\n": ["adds numbers"],
            "✖ ten percent off (1.0333ms)\n✖ failing tests:\n✖ ten percent off (1.0333ms)\n": ["ten percent off"],
        }
        for out, want in cases.items():
            self.assertEqual([t for t, _ in fix_flow.failing_tests(out)], want, out)

    def test_failed_subtests_count_once_per_test(self) -> None:
        out = ("SUBFAILED(slice_args=(-1, -1, 2)) tests/test_more.py::IsliceTests::test_all\n"
               "SUBFAILED(slice_args=(-1, -1, 3)) tests/test_more.py::IsliceTests::test_all\n"
               "SUBFAILED(n=2) tests/test_more.py::IsliceTests::test_slicing - AssertionError: x\n"
               "68 failed, 767 passed")
        self.assertEqual([t for t, _ in fix_flow.failing_tests(out)],
                         ["tests/test_more.py::IsliceTests::test_all",
                          "tests/test_more.py::IsliceTests::test_slicing"])

    def test_a_windows_command_with_a_quoted_path_splits_cleanly(self) -> None:
        cmd = '"C:\\Program Files\\Py\\python.exe" -m pytest -q tests'
        if os.name == "nt":
            self.assertEqual(fix_flow.split_command(cmd),
                             ["C:\\Program Files\\Py\\python.exe", "-m", "pytest", "-q", "tests"])
        self.assertEqual(fix_flow.split_command("python -m pytest -q"), ["python", "-m", "pytest", "-q"])

    def test_saleha_test_python_picks_the_interpreter_for_the_projects_tests(self) -> None:
        from unittest.mock import patch

        from saleha.core.loop.agentic_loop import discover_test_command
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            Path(d, "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
            with patch.dict(os.environ, {"SALEHA_TEST_PYTHON": "/job/python3"}):
                argv, _why = discover_test_command(d)
            plain, _ = discover_test_command(d)
        self.assertEqual(argv, ["/job/python3", "-m", "pytest", "-q"])
        assert plain is not None
        self.assertEqual(plain[0], sys.executable)

    def test_generated_paths(self) -> None:
        for p in ("__pycache__/a.pyc", "pkg/__pycache__/b.cpython-312.pyc", ".saleha/work.jsonl",
                  ".pytest_cache/v/x", "mod.pyc"):
            self.assertTrue(fix_flow.is_generated(p), p)
        for p in ("calc.py", "tests/test_calc.py", "saleha_notes.md"):
            self.assertFalse(fix_flow.is_generated(p), p)


if __name__ == "__main__":
    unittest.main()
