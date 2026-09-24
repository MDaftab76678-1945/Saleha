"""Tests for the Laya hybrid step in SmartRouter.classify_task_tier.

Hybrid rule under test: the keyword classifier's answer is the default;
Laya is consulted only to upgrade a task to "reasoning" when it says so.
Any other Laya answer -- or no usable Laya at all -- must leave the
keyword answer untouched, and a Laya failure must fall back to it with a
recorded reason rather than propagate or silently pass.
"""
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from saleha.core.platform.smart_router import SmartRouter


class _FakeLayaAgent:
    """Stands in for a real laya.load(...) agent in tests."""

    def __init__(self, choice: str) -> None:
        self.choice = choice
        self.calls = 0

    def predict(self, task: str, questions: Dict[str, Any]) -> Dict[str, Any]:
        self.calls += 1
        return {"answers": {"tier": {"choice": self.choice}}}


class _RaisingLayaAgent:
    """Simulates a Laya agent whose predict() call fails."""

    def predict(self, task: str, questions: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("simulated laya predict failure")


def _router(tmp: str, laya_agent: Any = None) -> SmartRouter:
    return SmartRouter(history_file=str(Path(tmp) / "router.json"), laya_agent=laya_agent)


class LayaHybridUpgradeTests(unittest.TestCase):
    def test_laya_reasoning_upgrades_a_keyword_standard_task(self) -> None:
        """A task the keyword logic alone calls 'standard' must become
        'reasoning' when the injected Laya agent answers 'reasoning'."""
        task = "build user login endpoint with password hash"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            keyword_only = _router(tmp).classify_task_tier(task)
            self.assertEqual(keyword_only["tier"], "standard")

            hybrid = _router(tmp, laya_agent=_FakeLayaAgent("reasoning")).classify_task_tier(task)

        self.assertEqual(hybrid["tier"], "reasoning")
        self.assertEqual(hybrid["decided_by"], "laya+keyword")
        self.assertNotIn("laya_note", hybrid)


class LayaHybridNoChangeTests(unittest.TestCase):
    def test_laya_fast_does_not_change_the_keyword_answer(self) -> None:
        task = "build user login endpoint with password hash"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            keyword_only = _router(tmp).classify_task_tier(task)
            hybrid = _router(tmp, laya_agent=_FakeLayaAgent("fast")).classify_task_tier(task)

        self.assertEqual(hybrid["tier"], keyword_only["tier"])
        self.assertEqual(hybrid["decided_by"], "laya+keyword")

    def test_laya_standard_does_not_change_the_keyword_answer(self) -> None:
        task = "build user login endpoint with password hash"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            keyword_only = _router(tmp).classify_task_tier(task)
            hybrid = _router(tmp, laya_agent=_FakeLayaAgent("standard")).classify_task_tier(task)

        self.assertEqual(hybrid["tier"], keyword_only["tier"])
        self.assertEqual(hybrid["decided_by"], "laya+keyword")

    def test_laya_reasoning_on_an_already_reasoning_task_is_a_no_op_label(self) -> None:
        """Keyword already says reasoning; Laya agreeing must not error or
        double-count -- it just gets attributed to the hybrid path."""
        task = "design distributed microservice architecture with security audit"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            hybrid = _router(tmp, laya_agent=_FakeLayaAgent("reasoning")).classify_task_tier(task)

        self.assertEqual(hybrid["tier"], "reasoning")
        self.assertEqual(hybrid["decided_by"], "laya+keyword")


class LayaFailureFallsBackTests(unittest.TestCase):
    def test_a_raising_agent_falls_back_to_the_keyword_answer_with_a_note(self) -> None:
        task = "build user login endpoint with password hash"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            keyword_only = _router(tmp).classify_task_tier(task)
            hybrid = _router(tmp, laya_agent=_RaisingLayaAgent()).classify_task_tier(task)

        self.assertEqual(hybrid["tier"], keyword_only["tier"])
        self.assertEqual(hybrid["decided_by"], "keyword")
        self.assertIn("laya_note", hybrid)
        self.assertIn("predict raised", hybrid["laya_note"])


class LayaNotLoadedUnderTestModeTests(unittest.TestCase):
    def test_test_mode_with_no_injected_agent_never_loads_laya(self) -> None:
        """SALEHA_TEST_MODE=1 (set repo-wide by conftest) with no injected
        agent must never attempt to import/load the real Laya model."""
        self.assertEqual(os.environ.get("SALEHA_TEST_MODE"), "1")

        with (
            patch(
                "saleha.core.platform.smart_router._get_laya_agent",
                side_effect=AssertionError("Laya must not be loaded under SALEHA_TEST_MODE=1"),
            ),
            tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp,
        ):
            result = _router(tmp).classify_task_tier("build user login endpoint")

        self.assertEqual(result["decided_by"], "keyword")
        self.assertNotIn("laya_note", result)


if __name__ == "__main__":
    unittest.main()
