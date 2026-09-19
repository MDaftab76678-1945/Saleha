"""
Tests for Saleha Core MathLogicEngine (saleha/core/math_logic.py).

Verifies bilingual complexity estimation, keyword scoring, file extension
weights, word-count penalties, threshold-based recommendations, suggested
architectural stages, and automated DAG decomposition.
"""

from __future__ import annotations

import unittest

from saleha.core.math_logic import (
    CRITICAL_COMPLEXITY,
    MAX_SAFE_COMPLEXITY,
    ComplexityResult,
    MathLogicEngine,
)


class MathLogicEngineEdgeCasesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MathLogicEngine()

    def test_empty_string_returns_zero_complexity(self) -> None:
        res = self.engine.estimate_complexity("")
        self.assertEqual(res.complexity_score, 0.0)
        self.assertEqual(res.estimated_files, 1)
        self.assertEqual(res.recommendation, "EXECUTE")
        self.assertTrue(res.is_safe_to_run)

    def test_whitespace_string_returns_zero_complexity(self) -> None:
        res = self.engine.estimate_complexity("    \n\t  ")
        self.assertEqual(res.complexity_score, 0.0)
        self.assertEqual(res.recommendation, "EXECUTE")
        self.assertTrue(res.is_safe_to_run)


class ComplexityThresholdsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MathLogicEngine()

    def test_low_complexity_direct_execute(self) -> None:
        # A simple task with single file creation keyword
        res = self.engine.estimate_complexity("create a single script hello.py")
        self.assertLess(res.complexity_score, MAX_SAFE_COMPLEXITY)
        self.assertEqual(res.recommendation, "EXECUTE")
        self.assertTrue(res.is_safe_to_run)

    def test_medium_complexity_triggers_break_down(self) -> None:
        # Task with medium complexity weight (all tests = 5.0)
        res = self.engine.estimate_complexity("run all tests for the modules")
        self.assertGreaterEqual(res.complexity_score, MAX_SAFE_COMPLEXITY)
        self.assertLess(res.complexity_score, CRITICAL_COMPLEXITY)
        self.assertEqual(res.recommendation, "BREAK_DOWN")
        self.assertTrue(res.is_safe_to_run)

    def test_critical_complexity_requires_approval(self) -> None:
        # Entire codebase refactoring triggers high weight (8.0 + 7.0 = 15.0)
        res = self.engine.estimate_complexity("refactor the entire project across all files")
        self.assertGreaterEqual(res.complexity_score, CRITICAL_COMPLEXITY)
        self.assertEqual(res.recommendation, "REQUIRES_APPROVAL")
        self.assertFalse(res.is_safe_to_run)


class FileExtensionAndWordCountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MathLogicEngine()

    def test_file_extensions_increment_files_and_score(self) -> None:
        # .py (1.0), .rs (2.0), .md (0.2)
        res = self.engine.estimate_complexity("check test.py, engine.rs, and readme.md")
        self.assertEqual(res.estimated_files, 4)  # default 1 + 3 extensions
        expected_ext_weight = 1.0 + 2.0 + 0.2
        # Base keyword 'check' also adds 2.0
        self.assertAlmostEqual(res.complexity_score, expected_ext_weight + 2.0, places=2)

    def test_word_count_penalty_over_50_words(self) -> None:
        short_prompt = "build a single function"
        long_prompt = "build a single function " + "word " * 55
        res_short = self.engine.estimate_complexity(short_prompt)
        res_long = self.engine.estimate_complexity(long_prompt)
        # Should differ by the 2.0 word-count penalty
        self.assertAlmostEqual(res_long.complexity_score - res_short.complexity_score, 2.0, places=2)


class BilingualKeywordsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MathLogicEngine()

    def test_hindi_medium_large_triggers_break_down(self) -> None:
        # "पूरे प्रोजेक्ट" matches weight 8.0 -> triggers BREAK_DOWN (5.0 <= score < 9.0)
        res = self.engine.estimate_complexity("पूरे प्रोजेक्ट को refactor करो")
        self.assertEqual(res.complexity_score, 8.0)
        self.assertEqual(res.recommendation, "BREAK_DOWN")
        self.assertTrue(res.is_safe_to_run)

    def test_hindi_critical_scope_triggers_requires_approval(self) -> None:
        # Combines multiple scope patterns: entire project (8.0) + all files (3.0) + tests (2.0) = 13.0
        prompt = "पूरे प्रोजेक्ट को refactor करो, सभी फाइलों में सुधार करो और नए tests लिखो।"
        res = self.engine.estimate_complexity(prompt)
        self.assertGreaterEqual(res.complexity_score, CRITICAL_COMPLEXITY)
        self.assertEqual(res.recommendation, "REQUIRES_APPROVAL")
        self.assertFalse(res.is_safe_to_run)

    def test_hindi_simple_task_execute(self) -> None:
        res = self.engine.estimate_complexity("बनाओ एक simple script")
        # Matches 'create a single file/script' = 2.0
        self.assertEqual(res.recommendation, "EXECUTE")
        self.assertTrue(res.is_safe_to_run)


class ArchitectureAndDAGDecompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MathLogicEngine()

    def test_microservice_pattern_complexity_and_stages(self) -> None:
        res = self.engine.estimate_complexity("Build a distributed microservice cluster node")
        self.assertGreaterEqual(res.complexity_score, 4.5)
        self.assertIn("distributed_architecture", res.suggested_stages)

    def test_full_stack_pattern_complexity_and_stages(self) -> None:
        res = self.engine.estimate_complexity("Design a full stack app with frontend and backend")
        self.assertGreaterEqual(res.complexity_score, 6.0)
        self.assertIn("full_stack", res.suggested_stages)

    def test_database_migration_pattern_complexity_and_stages(self) -> None:
        res = self.engine.estimate_complexity("Execute database migration for schema")
        self.assertGreaterEqual(res.complexity_score, 4.0)
        self.assertIn("database_migration", res.suggested_stages)

    def test_decompose_to_dag_full_stack(self) -> None:
        dag = self.engine.decompose_to_dag("Build a full stack dashboard with frontend and backend")
        self.assertIn("task_spec", dag.nodes)
        self.assertIn("task_arch", dag.nodes)
        self.assertIn("task_backend", dag.nodes)
        self.assertIn("task_frontend", dag.nodes)
        self.assertIn("task_security", dag.nodes)
        self.assertIn("task_qa", dag.nodes)

        batches = dag.get_topological_batches()
        self.assertGreaterEqual(len(batches), 4)
        # Verify that task_backend and task_frontend run in parallel stage
        batch_ids = [{n.id for n in b} for b in batches]
        self.assertTrue(any({"task_backend", "task_frontend"}.issubset(b) for b in batch_ids))

    def test_decompose_to_dag_database_migration(self) -> None:
        dag = self.engine.decompose_to_dag("Run database migration for authentication")
        self.assertIn("task_db", dag.nodes)
        batches = dag.get_topological_batches()
        self.assertGreaterEqual(len(batches), 3)


if __name__ == "__main__":
    unittest.main()

