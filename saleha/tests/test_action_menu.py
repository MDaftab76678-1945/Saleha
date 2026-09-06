"""
Tests for the action-menu loop (saleha/core/action_menu.py).

The claim being tested is structural: a hallucinated path cannot be chosen
because it is never offered, and a fabricated completion cannot be claimed
because `finish` is absent from the menu until the evidence admits it.
Measured against qwen2.5-coder:3b, 5 runs each on the same task:

    write-a-call loop:  2/5 success,  2 real tool calls total
    action-menu loop:   3/5 success, 22 real tool calls, real file read 5/5
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from saleha.core.action_menu import (
    CHOICE_SCHEMA,
    ActionMenuLoop,
    MenuOption,
)
from saleha.core.task_evidence import (
    EvidenceKind,
    EvidenceLedger,
    TaskState,
)


class ChoiceAgent:
    """Replies with scripted choices, like a constrained-decoding model."""

    def __init__(self, choices):
        self.choices = list(choices)
        self.prompts = []

    def think(self, prompt, **kwargs):
        self.prompts.append(prompt)
        resp = MagicMock()
        resp.success = True
        resp.content = (str(self.choices.pop(0)) if self.choices else "summary text")
        return resp


class MenuBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "billing.py"), "w") as f:
            f.write("def charge(a):\n    return a * 2\n")
        with open(os.path.join(self.tmp, "utils.py"), "w") as f:
            f.write("def helper():\n    return 1\n")
        os.makedirs(os.path.join(self.tmp, "__pycache__"))
        with open(os.path.join(self.tmp, "__pycache__", "junk.py"), "w") as f:
            f.write("x = 1\n")
        self.loop = ActionMenuLoop(agent=ChoiceAgent([]), root_dir=self.tmp,
                                   use_constrained_decoding=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_menu_only_contains_real_files(self):
        """The core guarantee: you cannot pick a file that doesn't exist."""
        opts = self.loop.build_menu("fix the charge bug in billing")
        paths = [o.args.get("path") for o in opts if o.tool == "read_file"]
        for p in paths:
            self.assertTrue(os.path.isfile(os.path.join(self.tmp, p)),
                            f"menu offered a non-existent file: {p}")
        self.assertIn("billing.py", paths)

    def test_menu_skips_build_noise(self):
        opts = self.loop.build_menu("anything")
        paths = " ".join(o.args.get("path", "") for o in opts)
        self.assertNotIn("__pycache__", paths)

    def test_goal_relevant_file_is_offered(self):
        opts = self.loop.build_menu("fix the bug in billing.py")
        labels = " ".join(o.label for o in opts)
        self.assertIn("billing.py", labels)

    def test_menu_always_has_an_escape_option(self):
        """A menu must never be a trap when the right file isn't listed."""
        opts = self.loop.build_menu("investigate the charge calculation")
        self.assertTrue(any(o.kind == "escape" for o in opts))

    def test_finish_absent_until_evidence_exists(self):
        """Fabricated completion is unrepresentable, not merely rejected."""
        led = EvidenceLedger(goal="x", required={EvidenceKind.FILE_READ})
        loop = ActionMenuLoop(agent=ChoiceAgent([]), root_dir=self.tmp,
                              ledger=led, use_constrained_decoding=False)
        self.assertFalse(any(o.tool == "finish" for o in loop.build_menu("goal")))

        led.record(EvidenceKind.FILE_READ, "billing.py", "test")
        self.assertTrue(any(o.tool == "finish" for o in loop.build_menu("goal")))

    def test_menu_is_capped(self):
        for i in range(40):
            with open(os.path.join(self.tmp, f"mod{i}.py"), "w") as f:
                f.write("x = 1\n")
        self.assertLessEqual(len(self.loop.build_menu("goal")), 12)


class ChoiceParsingTests(unittest.TestCase):
    def test_parses_constrained_schema_reply(self):
        self.assertEqual(ActionMenuLoop._parse_choice('{"choice": 3}', 5), 3)

    def test_parses_bare_number(self):
        self.assertEqual(ActionMenuLoop._parse_choice("2", 5), 2)

    def test_parses_number_inside_prose(self):
        self.assertEqual(
            ActionMenuLoop._parse_choice("I think option 4 is best", 5), 4)

    def test_rejects_out_of_range(self):
        self.assertIsNone(ActionMenuLoop._parse_choice('{"choice": 99}', 5))

    def test_rejects_empty(self):
        self.assertIsNone(ActionMenuLoop._parse_choice("", 5))

    def test_schema_constrains_to_an_integer(self):
        self.assertEqual(CHOICE_SCHEMA["properties"]["choice"]["type"], "integer")
        self.assertIn("choice", CHOICE_SCHEMA["required"])


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "billing.py"), "w") as f:
            f.write("def charge(a):\n    return a * 2\n")

        def read_file(path=""):
            full = os.path.join(self.tmp, path)
            if not os.path.isfile(full):
                return f"no such file: {path}"
            with open(full, encoding="utf-8") as f:
                return f.read()

        def list_dir(path="."):
            return "\n".join(sorted(os.listdir(self.tmp)))

        def search_repo(query=""):
            return f"matches for {query}: billing.py"

        self.tools = {"read_file": read_file, "list_dir": list_dir,
                      "search_repo": search_repo}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _loop(self, choices, ledger=None, **kw):
        return ActionMenuLoop(agent=ChoiceAgent(choices), root_dir=self.tmp,
                              tools=self.tools, ledger=ledger,
                              use_constrained_decoding=False, **kw)

    def test_choice_runs_the_real_tool(self):
        loop = self._loop([1])
        res = loop.run("read billing.py", on_event=lambda e: None)
        self.assertEqual(res.steps[0].tool, "read_file")
        self.assertIn("def charge", res.steps[0].observation)

    def test_reaches_finish_and_accepts_ledger(self):
        led = EvidenceLedger(goal="g", required={EvidenceKind.FILE_READ})
        led.transition(TaskState.ANALYZING)
        loop = self._loop([1], ledger=led)  # read first...
        # ...then pick whatever index `finish` really occupies once the
        # evidence lets it appear, rather than assuming a fixed position.
        loop._read_files.add("billing.py")
        led.record(EvidenceKind.FILE_READ, "billing.py", "test-setup")
        finish_idx = next(i for i, o in enumerate(loop.build_menu("find the bug"), 1)
                          if o.tool == "finish")
        loop.agent.choices = [1, finish_idx]
        loop._read_files.clear()
        res = loop.run("find the bug in billing.py")
        self.assertTrue(res.success, res.error)
        self.assertTrue(led.has(EvidenceKind.FILE_READ))
        self.assertEqual(led.state, TaskState.ACCEPTED)

    def test_invalid_reply_does_not_end_the_run(self):
        """A junk reply falls back to a real action instead of dying."""
        loop = self._loop(["banana", 1])
        res = loop.run("read billing.py")
        self.assertGreaterEqual(res.invalid_choices, 1)
        self.assertTrue(res.steps)
        self.assertEqual(res.steps[0].tool, "read_file")

    def test_max_steps_fails_honestly(self):
        led = EvidenceLedger(goal="g", required={EvidenceKind.TESTS_PASSED})
        led.transition(TaskState.ANALYZING)
        loop = self._loop([1] * 10, ledger=led, max_steps=3)
        res = loop.run("do the impossible")
        self.assertFalse(res.success)
        self.assertIn("max_steps", res.error)
        self.assertEqual(led.state, TaskState.FAILED)

    def test_reading_records_real_evidence_only(self):
        led = EvidenceLedger(goal="g", required={EvidenceKind.FILE_READ})
        led.transition(TaskState.ANALYZING)
        loop = self._loop([1], ledger=led, max_steps=1)
        loop.run("read billing.py")
        reads = [e for e in led.evidence if e.kind == EvidenceKind.FILE_READ]
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0].source, "action_menu.run")

    def test_tool_calls_property_excludes_finish(self):
        led = EvidenceLedger(goal="g", required={EvidenceKind.FILE_READ})
        led.transition(TaskState.ANALYZING)
        loop = self._loop([1], ledger=led)
        loop._read_files.add("billing.py")
        led.record(EvidenceKind.FILE_READ, "billing.py", "test-setup")
        finish_idx = next(i for i, o in enumerate(loop.build_menu("read billing"), 1)
                          if o.tool == "finish")
        loop.agent.choices = [1, finish_idx]
        loop._read_files.clear()
        res = loop.run("read billing.py")
        self.assertTrue(res.success, res.error)
        self.assertNotIn("finish", res.tool_calls)

    def test_menu_option_is_a_real_dataclass(self):
        o = MenuOption(label="read x", tool="read_file", args={"path": "x"})
        self.assertEqual(str(o), "read x")
        self.assertEqual(o.kind, "explore")


if __name__ == "__main__":
    unittest.main()
