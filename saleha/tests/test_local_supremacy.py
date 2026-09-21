"""Unit tests for LocalSupremacyEngine (Small Beating Large)."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from saleha.core.harness.code_executor import CodeExecutor, ExecutionResult
from saleha.core.fast_inference import FastInference, InferenceResult
from saleha.core.local_supremacy import (
    LocalSupremacyEngine,
    CandidateEvaluation,
    SupremacyResult,
)


class LocalSupremacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.executor = CodeExecutor(timeout=10)
        self.engine = LocalSupremacyEngine(
            model="mock",
            num_trajectories=4,
            max_refinements=2,
            executor=self.executor,
        )

    def test_local_supremacy_stratified_diversity(self) -> None:
        """Verifies that engine produces K distinct strategies and stratified temperatures."""
        candidates = self.engine._generate_candidate_batch("Double the input integer", 4)
        self.assertEqual(len(candidates), 4)

        strategies = [c[1] for c in candidates]
        temperatures = [c[2] for c in candidates]

        self.assertIn("direct_idiomatic", strategies)
        self.assertIn("defensive_guarded", strategies)
        self.assertIn("modular_decomposed", strategies)
        self.assertIn("algorithmic_optimized", strategies)

        self.assertEqual(temperatures, [0.2, 0.4, 0.6, 0.8])

    def test_local_supremacy_fast_pass(self) -> None:
        """When candidate 1 passes tests immediately, wins fast without needing reflexion."""
        test_suite = "assert solve(5) == 5\nassert solve('abc') == 'abc'\n"
        result: SupremacyResult = self.engine.solve(
            problem="Return the input unchanged",
            test_suite=test_suite,
        )

        self.assertTrue(result.passed)
        self.assertTrue(result.single_shot_passed)
        self.assertEqual(result.winner_id, "TRAJ-01")
        self.assertEqual(result.total_repairs, 0)
        self.assertEqual(result.amplification_factor, 1.0)
        self.assertIn("solve", result.winner_code)

    def test_local_supremacy_reflexion_repair_success(self) -> None:
        """When initial candidate fails sandbox tests, reflexion repairs it and verifies."""
        test_suite = "assert solve(2) == 4\nassert solve(10) == 20\n"

        # Candidate generator where initial candidates return buggy code (x + 1),
        # but reflexion repair returns correct code (x * 2)
        failing_candidates = [
            ("TRAJ-01", "direct_idiomatic", 0.2, "def solve(x):\n    return x + 1\n"),
            ("TRAJ-02", "defensive_guarded", 0.4, "def solve(x):\n    return x + 2\n"),
        ]

        with patch.object(self.engine, "_generate_candidate_batch", return_value=failing_candidates):
            # Mock repair generation returning the correct solution
            mock_repair_result = InferenceResult(
                content="```python\ndef solve(x):\n    return x * 2\n```",
                success=True,
            )
            mock_inference = MagicMock(spec=FastInference)
            mock_inference.run.return_value = mock_repair_result
            self.engine.inference = mock_inference

            result: SupremacyResult = self.engine.solve(
                problem="Double the input number",
                test_suite=test_suite,
            )

            self.assertTrue(result.passed)
            self.assertFalse(result.single_shot_passed)
            self.assertEqual(result.amplification_factor, float("inf"))
            self.assertGreaterEqual(result.total_repairs, 1)
            self.assertIn("solve(x)", result.winner_code)
            self.assertIn("x * 2", result.winner_code)

    def test_local_supremacy_honest_failure_reporting(self) -> None:
        """When sandbox tests fail and repairs fail, honestly reports passed=False with exit code."""
        test_suite = "assert False, 'Always failing assertion'\n"
        result: SupremacyResult = self.engine.solve(
            problem="Always failing problem",
            test_suite=test_suite,
        )

        self.assertFalse(result.passed)
        self.assertFalse(result.single_shot_passed)
        self.assertEqual(result.amplification_factor, 0.0)
        self.assertGreater(len(result.candidates), 0)
        # Sandbox execution must have failed with non-zero exit code
        failing_eval = result.candidates[0]
        self.assertNotEqual(failing_eval.exit_code, 0)
        self.assertIn("AssertionError", failing_eval.stderr or failing_eval.stdout or failing_eval.error_summary)

    def test_local_supremacy_security_disqualification(self) -> None:
        """Candidate with dangerous dynamic execution (eval) is disqualified by AST filter."""
        eval_res = self.engine.evaluate_candidate(
            candidate_id="TRAJ-INSECURE",
            strategy_name="dangerous",
            temperature=0.2,
            code="def solve(x):\n    return eval(x)\n",
            test_suite="assert True",
        )

        self.assertFalse(eval_res.security_clean)
        self.assertFalse(eval_res.tests_passed)
        self.assertIn("Dangerous dynamic code execution", eval_res.error_summary)
        self.assertEqual(eval_res.score, 0.0)


if __name__ == "__main__":
    unittest.main()
