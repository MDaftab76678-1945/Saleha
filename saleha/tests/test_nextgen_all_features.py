"""
Unit & Integration Tests for Next-Gen Multi-Model Failover Router and salehatop TUI Dashboard.

The SWEBenchHarnessTests class that lived here asserted `resolved == True` for
saleha/harness/swe_bench_harness.py, whose tasks were `assert True` and never ran;
the module was deleted in pass 158 (the real one is saleha/core/swe_bench_harness.py).
"""

import unittest
from typing import Any

from saleha.cli.salehatop import SalehaTopDashboard
from saleha.core.platform.smart_router import SmartRouter


class SmartRouterFailoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = SmartRouter()

    def test_get_failover_chain_reasoning_task(self) -> None:
        task = "Architect distributed event-driven microservices with high throughput"
        chain = self.router.get_failover_chain(task)

        self.assertTrue(len(chain) >= 3)
        self.assertIn("deepseek/deepseek-chat", chain)
        self.assertIn("anthropic/claude-3-7-sonnet", chain)

    def test_get_failover_chain_fast_task(self) -> None:
        task = "Format simple python docstring helper"
        chain = self.router.get_failover_chain(task)

        self.assertTrue(len(chain) >= 2)
        self.assertIn("deepseek/deepseek-chat", chain)

    def test_execute_with_failover_success_on_first_try(self) -> Any:
        def mock_call(model: str) -> Any:
            return f"Success with {model}"

        res, model_used, elapsed = self.router.execute_with_failover("Test task", mock_call)
        self.assertIn("Success with", res)
        self.assertTrue(model_used)
        self.assertGreaterEqual(elapsed, 0.0)

    def test_execute_with_failover_recovers_after_first_failure(self) -> Any:
        attempts = []

        def failing_first_call(model: str) -> Any:
            attempts.append(model)
            if len(attempts) == 1:
                raise ConnectionError("Ollama offline")
            return f"Recovered with {model}"

        res, model_used, elapsed = self.router.execute_with_failover("Test task", failing_first_call)
        self.assertIn("Recovered with", res)
        self.assertEqual(len(attempts), 2)


class SalehaTopTuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dashboard = SalehaTopDashboard()

    def test_generate_header_and_hardware(self) -> None:
        header = self.dashboard.generate_header()
        self.assertIsNotNone(header)

        hw = self.dashboard.generate_hardware_panel()
        self.assertIsNotNone(hw)

    def test_generate_layout(self) -> None:
        layout = self.dashboard.make_layout()
        self.assertIsNotNone(layout)


if __name__ == "__main__":
    unittest.main()
