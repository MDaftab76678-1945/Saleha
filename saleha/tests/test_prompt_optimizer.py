"""Unit tests for Auto-Curriculum & Prompt Self-Optimizer."""

import unittest
import tempfile
import os
from saleha.core.prompt_optimizer import PromptOptimizer, PromptOptimizationRecord


class TestPromptOptimizer(unittest.TestCase):
    """Test suite for PromptOptimizer self-refinement and directive synthesis."""

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        self.optimizer = PromptOptimizer(store_path=self.tmp_file)

    def tearDown(self):
        if os.path.exists(self.tmp_file):
            try:
                os.unlink(self.tmp_file)
            except OSError:
                pass

    def test_optimize_prompt_adds_safety_directives(self):
        record = self.optimizer.optimize_prompt(
            role_name="CoderAgent",
            current_prompt="You are a senior coder.",
            recent_errors=["IndexError in array bounds", "ZeroDivisionError in payment calc"],
        )
        self.assertIsInstance(record, PromptOptimizationRecord)
        self.assertEqual(record.role_name, "CoderAgent")
        self.assertTrue(len(record.added_directives) >= 2)
        self.assertIn("Auto-Optimized Guideline", record.optimized_prompt)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Regression: `saleha optimize-prompts` passed a hardcoded failure list --
# literally ['IndexError in test suite'] -- with a hardcoded base prompt, so it
# "self-optimized" against an error that had never occurred, while 145 real
# failures sat unused in TaskHistory. Same shape as the godel-utility defect.
#
# Second bug found doing this: an error with no rule in DIRECTIVE_MAP fell
# through to a generic directive, so a RecursionError silently produced
# "ensure complete test coverage" and looked like it had been learned from.
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

from saleha.core.prompt_optimizer import PromptOptimizer, recent_real_errors


def _opt(tmp_path):
    return PromptOptimizer(store_path=str(tmp_path / "opt.json"))


def test_unmatched_errors_are_reported_not_hidden(tmp_path):
    rec = _opt(tmp_path).optimize_prompt(
        "CoderAgent", "Base.",
        ["RecursionError: maximum recursion depth exceeded"])
    assert rec.errors_seen == 1
    assert rec.unmatched_errors == ["RecursionError: maximum recursion depth exceeded"]
    assert rec.learned_from_all is False


def test_matched_error_is_learned_from(tmp_path):
    rec = _opt(tmp_path).optimize_prompt(
        "CoderAgent", "Base.", ["IndexError: list index out of range"])
    assert rec.unmatched_errors == []
    assert rec.learned_from_all is True
    assert any("index boundaries" in d for d in rec.added_directives)


def test_mixed_errors_split_correctly(tmp_path):
    rec = _opt(tmp_path).optimize_prompt(
        "CoderAgent", "Base.",
        ["TypeError: bad operand", "RecursionError: too deep"])
    assert rec.errors_seen == 2
    assert len(rec.unmatched_errors) == 1
    assert rec.learned_from_all is False


def test_no_errors_means_nothing_was_learned(tmp_path):
    rec = _opt(tmp_path).optimize_prompt("CoderAgent", "Base.", [])
    assert rec.errors_seen == 0
    assert rec.learned_from_all is False   # zero errors is not "learned all"


def test_different_errors_give_different_prompts(tmp_path):
    o = _opt(tmp_path)
    a = o.optimize_prompt("A", "Base.", ["IndexError: x"])
    b = o.optimize_prompt("B", "Base.", ["TypeError: y"])
    assert a.optimized_prompt != b.optimized_prompt


def test_recent_real_errors_reads_history():
    fake = MagicMock()
    fake.all.return_value = [
        MagicMock(success=True, error=""),
        MagicMock(success=False, error="IndexError: list index out of range"),
        MagicMock(success=False, error="TypeError: bad operand"),
    ]
    with patch("saleha.core.task_history.TaskHistory", return_value=fake):
        errs = recent_real_errors()
    assert "IndexError: list index out of range" in errs
    assert len(errs) == 2                      # the successful run is excluded


def test_recent_real_errors_is_most_recent_first():
    fake = MagicMock()
    fake.all.return_value = [
        MagicMock(success=False, error="older"),
        MagicMock(success=False, error="newer"),
    ]
    with patch("saleha.core.task_history.TaskHistory", return_value=fake):
        assert recent_real_errors()[0] == "newer"


def test_recent_real_errors_deduplicates():
    fake = MagicMock()
    fake.all.return_value = [MagicMock(success=False, error="same")] * 5
    with patch("saleha.core.task_history.TaskHistory", return_value=fake):
        assert recent_real_errors() == ["same"]


def test_recent_real_errors_skips_blank_messages():
    fake = MagicMock()
    fake.all.return_value = [
        MagicMock(success=False, error="   "),
        MagicMock(success=False, error="real failure"),
    ]
    with patch("saleha.core.task_history.TaskHistory", return_value=fake):
        assert recent_real_errors() == ["real failure"]


def test_recent_real_errors_honours_limit():
    fake = MagicMock()
    fake.all.return_value = [
        MagicMock(success=False, error=f"err {i}") for i in range(50)
    ]
    with patch("saleha.core.task_history.TaskHistory", return_value=fake):
        assert len(recent_real_errors(limit=3)) == 3


def test_unreadable_history_returns_empty_not_a_fake_error():
    """An empty list must be reported as 'nothing to learn from', never
    replaced with an invented example -- that was the original bug."""
    fake = MagicMock()
    fake.all.side_effect = OSError("history unreadable")
    with patch("saleha.core.task_history.TaskHistory", return_value=fake):
        assert recent_real_errors() == []
