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

    def test_hindi_medium_large_triggers_requires_approval(self) -> None:
        # "पूरे प्रोजेक्ट...refactor" now matches both the scope pattern
        # (8.0) and the refactor-everything pattern (7.0) = 15.0, matching
        # the English "refactor the entire codebase" score exactly. It
        # used to score only 8.0 here (BREAK_DOWN) while the equivalent
        # English request scored 15.0 (REQUIRES_APPROVAL) -- the same
        # scope request was treated as smaller in Hindi than in English.
        res = self.engine.estimate_complexity("पूरे प्रोजेक्ट को refactor करो")
        self.assertEqual(res.complexity_score, 15.0)
        self.assertEqual(res.recommendation, "REQUIRES_APPROVAL")
        english_equivalent = self.engine.estimate_complexity("refactor the entire codebase")
        self.assertEqual(res.complexity_score, english_equivalent.complexity_score)

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


class RomanizedHinglishComplexityTests(unittest.TestCase):
    """Hindi typed in Latin letters must score like the other two scripts.

    A Devanagari-only pattern scored romanized input 0.0, so a
    whole-codebase refactor requested as "poore project ko dobara likho"
    was read as a trivial task and never broken down.
    """

    def setUp(self) -> None:
        self.engine = MathLogicEngine()

    def test_large_scope_scores_the_same_across_all_three_scripts(self) -> None:
        english = self.engine.estimate_complexity("refactor the entire codebase")
        devanagari = self.engine.estimate_complexity(
            "पूरे प्रोजेक्ट "
            "को दोबारा लिखो"
        )
        romanized = self.engine.estimate_complexity("poore project ko dobara likho")

        self.assertEqual(english.complexity_score, devanagari.complexity_score)
        self.assertEqual(english.complexity_score, romanized.complexity_score)
        self.assertGreater(romanized.complexity_score, MAX_SAFE_COMPLEXITY)

    def test_romanized_large_scope_requests_are_not_marked_execute(self) -> None:
        for phrase in (
            "poore project ko dobara likho",
            "pura code refactor karo",
            "saare files ka test likho",
            "sabhi files padho",
        ):
            with self.subTest(phrase=phrase):
                res: ComplexityResult = self.engine.estimate_complexity(phrase)
                self.assertGreater(res.complexity_score, MAX_SAFE_COMPLEXITY)
                self.assertNotEqual(res.recommendation, "EXECUTE")

    def test_romanized_single_file_request_stays_low(self) -> None:
        # Hindi puts the verb last ("ek file banao"); this must not be
        # scored as a large-scope task.
        res: ComplexityResult = self.engine.estimate_complexity("ek file banao script ke liye")
        self.assertLessEqual(res.complexity_score, MAX_SAFE_COMPLEXITY)


if __name__ == "__main__":
    unittest.main()

