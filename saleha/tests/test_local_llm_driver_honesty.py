"""LocalLLMDriver / SelfHealingEngine must not invent a model's answer.

With no daemon running, the driver used to return a fixed 'network packet
parser' response; SelfHealingEngine sandboxed it, reported PASSED and cached
it under the user's real task. Embeddings fell back to 16 numbers derived from
SHA-256. Both are now explicit failures.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import tempfile
import unittest
from typing import Any, Dict

from saleha.sandbox.local_llm_driver import LLMUnavailableError, LocalLLMDriver
from saleha.sandbox.sandbox_jail import HardenedSandbox

DEAD = dict(ollama_url="http://127.0.0.1:9", vllm_url="http://127.0.0.1:9/v1")

GOOD_CODE = (
    "def double(x: int) -> int:\n"
    "    assert isinstance(x, int), 'x must be int'\n"
    "    return x * 2\n\n"
    "assert double(2) == 4\n"
    "print('SELF_TEST_PASSED')\n"
)


class _StubLLM:
    def __init__(self, response: Any) -> None:
        self.response = response

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class DriverTests(unittest.TestCase):
    def test_generate_raises_when_no_backend_answers(self) -> None:
        driver = LocalLLMDriver(**DEAD)
        with self.assertRaises(LLMUnavailableError) as ctx:
            asyncio.run(driver.generate_structured("anything"))
        self.assertIn("ollama", str(ctx.exception))
        self.assertIn("vllm", str(ctx.exception))

    def test_embedding_is_never_a_hash(self) -> None:
        driver = LocalLLMDriver(**DEAD)
        with self.assertRaises(LLMUnavailableError):
            asyncio.run(driver.get_embedding("hello"))


@unittest.skipUnless(HardenedSandbox.is_available(), "POSIX jail not available here")
class HealingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        from saleha.sandbox.v5_production_core import SelfHealingEngine

        self._old_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.chdir(self._tmp.name)
        self.engine = SelfHealingEngine()

    def tearDown(self) -> None:
        self.engine.db.conn.close()
        os.chdir(self._old_cwd)
        self._tmp.cleanup()

    def _run(self, task: str) -> Dict[str, Any]:
        return asyncio.run(self.engine.execute_task_with_healing(task, max_retries=2))

    def _cached_keys(self) -> list:
        conn = sqlite3.connect(os.path.join(self._tmp.name, "swarm_memory.sqlite3"))
        try:
            return [r[0] for r in conn.execute("select task_hash from error_memory")]
        finally:
            conn.close()

    def test_model_unavailable_is_not_passed_and_not_cached(self) -> None:
        self.engine.llm = _StubLLM(LLMUnavailableError("daemon down"))
        result = self._run("Write a thread-safe rate limiter")
        self.assertEqual(result["status"], "MODEL_UNAVAILABLE")
        self.assertIn("daemon down", result["error"])
        self.assertNotIn("code", result)
        self.assertEqual(self._cached_keys(), [])

    def test_empty_code_is_not_a_pass(self) -> None:
        self.engine.llm = _StubLLM({"code": "  ", "explanation": "nothing"})
        result = self._run("Write anything")
        self.assertEqual(result["status"], "FAILED_BUDGET_EXHAUSTED")
        self.assertEqual(result["last_error"], "Model returned no code")

    def test_verified_solution_is_cached_under_a_stable_key(self) -> None:
        self.engine.llm = _StubLLM({"code": GOOD_CODE})
        task = "Write double(x)"
        result = self._run(task)
        self.assertEqual(result["status"], "PASSED", result)
        # sha256, not hash(): str hashes differ between processes, so the old
        # key could never be found again by the next run.
        self.assertEqual(self._cached_keys(), [hashlib.sha256(task.encode("utf-8")).hexdigest()])
        self.engine.llm = _StubLLM(LLMUnavailableError("down"))
        again = self._run(task)
        self.assertEqual(again["status"], "RESOLVED_FROM_MEMORY")


if __name__ == "__main__":
    unittest.main()
