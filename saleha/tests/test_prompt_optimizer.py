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
