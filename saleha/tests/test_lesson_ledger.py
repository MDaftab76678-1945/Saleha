"""Lessons must earn their place: hidden tests, leave-source-out, placebo control."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, FrozenSet, List

from saleha.core.memory.lesson_ledger import (
    PLACEBOS,
    Evidence,
    Lesson,
    LessonLedger,
    ProvenLesson,
    Solver,
    harvest_lessons,
    screen_lessons,
    sign_test,
    trial,
)
from saleha.core.real_task_bench import Task


def _task(name: str) -> Task:
    return Task(name, f"Write a Python function `solve_{name}()` returning 1. Return only the code.",
                f"assert solve_{name}() == 1\n", f"def solve_{name}():\n    return 0\n")


TASKS = [_task(n) for n in ("a", "b", "c", "d")]
BARE_PASS = {"a", "c"}


class FakeModel:
    """Solves tasks by rule. `rules` maps a marker found in the prompt to the
    task names it fixes (+name) or breaks (-name)."""

    def __init__(self, rules: Dict[str, List[str]], fail_on: FrozenSet[str] = frozenset()) -> None:
        self.rules = rules
        self.fail_on = fail_on

    def __call__(self, prompt: str, _model: str, **_options: Any) -> str:
        name = re.search(r"`solve_(\w+)\(\)`", prompt).group(1)  # type: ignore[union-attr]
        if any(m in prompt for m in self.fail_on) and name == "a":
            raise OSError("connection refused")
        ok = name in BARE_PASS
        for marker, effects in self.rules.items():
            if marker in prompt:
                ok = True if f"+{name}" in effects else False if f"-{name}" in effects else ok
        return f"```python\ndef solve_{name}():\n    return {1 if ok else 0}\n```"


def _screen(rules: Dict[str, List[str]], lessons: List[Lesson], **kw: Any) -> Any:
    return screen_lessons(lessons, TASKS, Solver("fake", generate=FakeModel(rules, **kw)))


class ProvenLessonTypeTests(unittest.TestCase):
    def test_cannot_be_constructed_outside_the_screen(self) -> None:
        ev = Evidence(("b",), ("b",), (), 0, "fake")
        with self.assertRaises(TypeError):
            ProvenLesson(object(), Lesson("x", "a", "w"), ev)

    def test_ledger_refuses_an_unproven_lesson(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ledger = LessonLedger(Path(tmp) / "l.json")
            with self.assertRaises(TypeError):
                ledger.add(Lesson("trust me", "a", "w"))  # type: ignore[arg-type]


class ScreenTests(unittest.TestCase):
    def test_lesson_that_fixes_another_task_and_breaks_none_is_proven(self) -> None:
        rep = _screen({"GOOD": ["+b"]}, [Lesson("GOOD advice", "a", "w")])
        self.assertEqual(len(rep.proven), 1)
        self.assertEqual(rep.proven[0].evidence.fixed, ("b",))
        self.assertEqual(rep.proven[0].evidence.broken, ())

    def test_lesson_that_breaks_a_passing_task_is_dropped(self) -> None:
        rep = _screen({"MIXED": ["+b", "-a"]}, [Lesson("MIXED advice", "c", "w")])
        self.assertEqual(rep.proven, [])
        self.assertEqual(rep.rows[0].broken, ["a"])

    def test_lesson_is_not_credited_for_the_task_it_came_from(self) -> None:
        rep = _screen({"OWN": ["+d"]}, [Lesson("OWN advice", "d", "w")])
        self.assertEqual(rep.proven, [])
        self.assertNotIn("d", rep.rows[0].compared)

    def test_placebo_that_helps_as_much_raises_the_bar(self) -> None:
        rep = _screen({"GOOD": ["+b"], PLACEBOS[0]: ["+b"]}, [Lesson("GOOD advice", "a", "w")])
        self.assertEqual(rep.proven, [])
        self.assertEqual(rep.rows[0].best_placebo_net, 1)

    def test_failed_model_call_is_neither_a_break_nor_a_proof(self) -> None:
        # The lesson fixes b, and its call on a never ran. Not a break -- but
        # not a pass either: run 1 proved a lesson this way, and the missing
        # call, re-run, broke a task.
        rep = _screen({"GOOD": ["+b"]}, [Lesson("GOOD advice", "c", "w")], fail_on=frozenset({"GOOD"}))
        row = rep.rows[0]
        self.assertNotIn("a", row.compared)
        self.assertEqual(row.broken, [])
        self.assertEqual(row.fixed, ["b"])
        self.assertEqual(row.incomplete, ["a"])
        self.assertFalse(row.proven)
        self.assertEqual(rep.proven, [])
        self.assertIn("a", rep.unavailable)


class HarvestTests(unittest.TestCase):
    def test_lesson_naming_its_own_task_is_rejected(self) -> None:
        def writer(prompt: str, _model: str, **_options: Any) -> str:
            return "In solve_b always return 1." if "`solve_b()`" in prompt else "Check the base case first."

        solver = Solver("fake", generate=FakeModel({}))
        rep = harvest_lessons(TASKS, solver, "writer", samples=0, generate=writer)
        self.assertEqual(rep.failures_seen, 2)  # b and d fail bare
        self.assertEqual([x.text for x in rep.lessons], ["Check the base case first."])
        self.assertEqual(rep.rejected[0][0], "b")
        self.assertIn("names the task", rep.rejected[0][1])


class TrialAndLedgerTests(unittest.TestCase):
    def _proven(self) -> List[ProvenLesson]:
        return _screen({"GOOD": ["+b"]}, [Lesson("GOOD advice", "a", "w")]).proven

    def test_improvement_is_claimed_only_when_significant_against_placebo(self) -> None:
        proven = self._proven()
        many = [_task(n) for n in ("a", "b", "c", "d", "e", "f", "g")]  # b, d-g fail bare
        strong = trial(proven, many, Solver("fake", generate=FakeModel(
            {"GOOD": ["+b", "+d", "+e", "+f", "+g"]})))
        self.assertTrue(strong.claim.endswith("-- improvement"), strong.claim)
        self.assertAlmostEqual(strong.p_vs_placebo or 1.0, 1 / 32)

        # Two tasks in the lessons' favour is the pass-165 real result's
        # shape: p = 0.25, reported as a direction, not an improvement.
        weak = trial(proven, TASKS, Solver("fake", generate=FakeModel({"GOOD": ["+b", "+d"]})))
        self.assertIn("direction positive, not significant", weak.claim)

        same = trial(proven, TASKS, Solver("fake", generate=FakeModel(
            {"GOOD": ["+b"], PLACEBOS[0]: ["+b"]})))
        self.assertIn("no improvement shown", same.claim)

    def test_sign_test_values(self) -> None:
        self.assertEqual(sign_test(0, 0), 1.0)
        self.assertAlmostEqual(sign_test(2, 0), 0.25)
        self.assertAlmostEqual(sign_test(5, 0), 1 / 32)
        self.assertAlmostEqual(sign_test(1, 1), 0.75)

    def test_trial_with_a_failed_call_claims_nothing(self) -> None:
        res = trial(self._proven(), TASKS, Solver("fake", generate=FakeModel(
            {"GOOD": ["+b", "+d"]}, fail_on=frozenset({"GOOD"}))))
        self.assertIn("incomplete", res.claim)
        self.assertIn("nothing claimed", res.claim)

    def test_no_proven_lessons_claims_nothing(self) -> None:
        res = trial([], TASKS, Solver("fake", generate=FakeModel({})))
        self.assertIn("nothing to claim", res.claim)
        self.assertNotIn("proven", res.arms)

    def test_ledger_round_trip_and_tampered_record(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "lessons.json"
            ledger = LessonLedger(path)
            ledger.add(self._proven()[0])
            ledger.save()
            self.assertIn("GOOD advice", LessonLedger(path).prompt_block())

            data = json.loads(path.read_text(encoding="utf-8"))
            data[0]["evidence"]["fixed"] = []
            path.write_text(json.dumps(data), encoding="utf-8")
            reloaded = LessonLedger(path)
            self.assertEqual(reloaded.entries, [])
            self.assertEqual(len(reloaded.rejected_on_load), 1)
            self.assertEqual(reloaded.prompt_block(), "")


if __name__ == "__main__":
    unittest.main()
