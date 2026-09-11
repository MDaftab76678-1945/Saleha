"""Unit tests for saleha.core.inference_router_bridge.RustInferenceRouterBridge.
Had no test coverage before this file (found during a test-coverage sweep of
saleha/core/).

The compiled Rust extension is not built on this machine (see the module's
docstring for the pyo3/Python-3.14 incompatibility found and recorded during
that sweep), so these tests target the honest not-available path: every
method must raise RustInferenceRouterUnavailable with build instructions
rather than return a fabricated routing decision.
"""

import unittest

from saleha.core.inference_router_bridge import (
    RustInferenceRouterBridge,
    RustInferenceRouterUnavailable,
    build_instructions,
    _EXT_AVAILABLE,
)


class BuildInstructionsTests(unittest.TestCase):
    def test_build_instructions_mentions_maturin(self) -> None:
        self.assertIn("maturin", build_instructions())


@unittest.skipIf(_EXT_AVAILABLE, "this test targets the not-built code path")
class NotAvailableTests(unittest.TestCase):
    def test_is_available_reports_false_not_assumed_true(self) -> None:
        bridge = RustInferenceRouterBridge()
        self.assertFalse(bridge.is_available())

    def test_import_error_is_reported(self) -> None:
        bridge = RustInferenceRouterBridge()
        self.assertIsNotNone(bridge.import_error())

    def test_route_raises_rather_than_returning_a_fabricated_decision(self) -> None:
        bridge = RustInferenceRouterBridge()
        with self.assertRaises(RustInferenceRouterUnavailable):
            bridge.route(
                task_id="t1", prompt="hello", complexity_score=0.5,
                privacy_required=False, max_budget_usd=0.10,
            )

    def test_register_node_raises_rather_than_silently_no_op(self) -> None:
        bridge = RustInferenceRouterBridge()
        with self.assertRaises(RustInferenceRouterUnavailable):
            bridge.register_node("peer1", 0.5, 100.0, 0.001, False)

    def test_get_node_count_raises_rather_than_returning_zero(self) -> None:
        """Returning 0 here would be indistinguishable from a real, empty
        router -- raising is what keeps 'unavailable' and 'available but
        empty' from being confused."""
        bridge = RustInferenceRouterBridge()
        with self.assertRaises(RustInferenceRouterUnavailable):
            bridge.get_node_count()


if __name__ == "__main__":
    unittest.main()
