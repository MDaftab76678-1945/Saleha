"""Unit tests for Model Manager & Local Inference Profiler."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from saleha.core.model_manager import ModelManager, BenchmarkResult
from saleha.agents.base_agent import AgentResponse


class ModelManagerTests(unittest.TestCase):

    def setUp(self):
        self.manager = ModelManager()

    def test_benchmark_model_metrics(self):
        with patch("saleha.agents.base_agent.BaseAgent.think") as mock_think:
            mock_think.return_value = AgentResponse(
                success=True,
                content="def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        yield a\n        a, b = b, a + b\n"
            )
            bench = self.manager.benchmark_model("qwen2.5-coder:1.5b")
            self.assertTrue(bench.success)
            self.assertGreater(bench.tokens_generated, 0)
            self.assertGreater(bench.tokens_per_sec, 0)


if __name__ == "__main__":
    unittest.main()
