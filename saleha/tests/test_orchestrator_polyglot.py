"""
Unit and integration tests for Saleha Polyglot Orchestrator & Execution Dispatch.
Verifies that non-Python languages (JavaScript, TypeScript, Go, Rust) are handled cleanly
without triggering Python-specific AST syntax errors.
"""

import tempfile
import unittest
import shutil
from unittest.mock import MagicMock

from saleha.core.code_executor import CodeExecutor, ExecutionResult
from saleha.core.memory_store import MemoryStore
from saleha.agents.coder import CoderAgent, CodeResult
from saleha.agents.tester import TesterAgent
from saleha.agents.reviewer import ReviewerAgent, ReviewResult
from saleha.orchestrator import SalehaOrchestrator
import saleha.orchestrator as orchestrator_module


class PolyglotOrchestratorIntegrationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.code_executor = CodeExecutor(timeout=10)
        self.tester = TesterAgent()

    def test_code_executor_dispatches_javascript_to_polyglot(self) -> None:
        # CodeExecutor with language='javascript' must route to PolyglotExecutor
        js_code = 'console.log("polyglot-js-ok");'
        res = self.code_executor.execute(js_code, language="javascript")
        self.assertEqual(res.backend, "polyglot")

        if shutil.which("node"):
            self.assertTrue(res.success)
            self.assertIn("polyglot-js-ok", res.output)
            self.assertEqual(res.exit_code, 0)
        else:
            self.assertFalse(res.success)
            self.assertIn("not found on system PATH", res.error)

    def test_code_executor_blocks_javascript_sast_eval(self) -> None:
        # SAST security guard must block JavaScript eval
        bad_js = 'const payload = "alert(1)"; eval(payload);'
        res = self.code_executor.execute(bad_js, language="javascript")
        self.assertEqual(res.backend, "polyglot")
        self.assertTrue(res.blocked)
        self.assertIsNotNone(res.block_reason)
        self.assertIn("SEC101", res.block_reason or "")
        self.assertFalse(res.success)

    def test_tester_agent_does_not_fail_valid_javascript_as_python_syntax_error(self) -> None:
        # Modern JS arrow function and template literal
        js_code = 'const greet = (name) => { return `Hello, ${name}`; };'

        # When tested as Python, it must fail with Python SyntaxError
        py_res = self.tester.test_code(js_code, language="python")
        self.assertFalse(py_res.passed)
        self.assertEqual(py_res.error_type, "SyntaxError")

        # When tested as JavaScript, it must pass without Python SyntaxError
        js_res = self.tester.test_code(js_code, language="javascript")
        self.assertTrue(js_res.passed)
        self.assertEqual(js_res.error_type, "None")

    def test_tester_agent_catches_empty_code_in_english(self) -> None:
        res = self.tester.test_code("   ", language="typescript")
        self.assertFalse(res.passed)
        self.assertEqual(res.error_type, "EmptyCode")
        self.assertEqual(res.error_message, "Code is empty.")

    def test_coder_agent_detect_language(self) -> None:
        self.assertEqual(CoderAgent.detect_language("Write a TypeScript interface for user profile"), "typescript")
        self.assertEqual(CoderAgent.detect_language("Create a Go goroutine worker"), "go")
        self.assertEqual(CoderAgent.detect_language("Implement Rust binary search with Result"), "rust")
        self.assertEqual(CoderAgent.detect_language("Simple Fibonacci script"), "python")

    def test_coder_agent_sets_language_in_code_result(self) -> None:
        coder = CoderAgent()
        coder.think = MagicMock(return_value=MagicMock(
            success=True,
            content="```typescript\nexport const add = (a: number, b: number): number => a + b;\n```",
            model_used="qwen2.5-coder:3b",
            error_message="",
        ))
        res = coder.generate_code("Write TypeScript addition", language="typescript")
        self.assertTrue(res.success)
        self.assertEqual(res.language, "typescript")
        self.assertIn("export const add", res.code)
        self.assertNotIn("```", res.code)

    def test_reviewer_agent_uses_dynamic_language_fence(self) -> None:
        reviewer = ReviewerAgent()
        captured_prompts: list = []

        def mock_think(prompt: str, **kwargs: object) -> MagicMock:
            captured_prompts.append(prompt)
            return MagicMock(success=True, content="APPROVED", model_used="qwen2.5-coder:3b", error_message="")

        setattr(reviewer, "think", MagicMock(side_effect=mock_think))
        res = reviewer.review_code("Write a Go function", "func Add(a, b int) int { return a + b }", language="go")
        self.assertTrue(res.approved)
        self.assertTrue(any("```go" in p for p in captured_prompts))
        self.assertTrue(any("You are an experienced go code reviewer" in p for p in captured_prompts))

    def test_orchestrator_routes_language_to_verifier(self) -> None:
        # execute_task() checks the module-level memory_store BEFORE touching
        # planner/coder/reviewer/verifier at all (saleha/orchestrator.py's own
        # cache-recall branch). memory_store persists to ~/.saleha/memory.json
        # across test runs and processes, keyed on (goal, model) -- so without
        # swapping it out, a second run of this exact test (same goal string,
        # same model="mock-model") hits the real disk-persisted cache from the
        # FIRST run, returns success=True/verified=False from the cache-replay
        # path, and every mock below (including orchestrator.verifier.execute)
        # is never even called. Reproduced directly: memory_store.recall() on
        # this goal/model already had hit_count=4 before this fix.
        #
        # Same class of bug as Round 4's "memory_store cache breaks
        # multi-model benchmark comparisons" -- same fix shape: swap in a
        # throwaway, tmp-file-backed MemoryStore for the duration of the test.
        tmp_dir = tempfile.mkdtemp()
        throwaway_store = MemoryStore(storage_path=f"{tmp_dir}/test_memory.json")
        original_store = orchestrator_module.memory_store
        orchestrator_module.memory_store = throwaway_store
        try:
            orchestrator = SalehaOrchestrator(model="mock-model")

            # Mock planner, coder, and reviewer to simulate end-to-end flow without calling local Ollama
            orchestrator.planner.create_plan = MagicMock(return_value=MagicMock(
                success=True, steps=["Step 1: Write TypeScript function"], complexity_score=2.0
            ))
            orchestrator.coder.generate_code = MagicMock(return_value=CodeResult(
                success=True,
                code="export function double(n: number): number { return n * 2; }",
                language="typescript",
                model_used="mock-model",
                attempts=1,
            ))
            orchestrator.reviewer.review_code = MagicMock(return_value=ReviewResult(
                approved=True, feedback="", model_used="mock-model"
            ))

            mock_verifier_res = ExecutionResult(
                success=True, output="double(2) = 4", error="", exit_code=0, backend="polyglot"
            )
            orchestrator.verifier.execute = MagicMock(return_value=mock_verifier_res)

            res = orchestrator.execute_task("Write a TypeScript function to double numbers", use_context=False)
            self.assertTrue(res.success)
            self.assertTrue(res.verified)

            # Check that verifier was called with language="typescript"
            orchestrator.verifier.execute.assert_called_once_with(
                "export function double(n: number): number { return n * 2; }",
                language="typescript"
            )
        finally:
            orchestrator_module.memory_store = original_store
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
