"""Unit tests for saleha.core.inference_router_bridge.RustInferenceRouterBridge.

Two code paths, and exactly one of them is live on any given machine:

* The extension is NOT built -- every method must raise
  RustInferenceRouterUnavailable with build instructions rather than return a
  fabricated routing decision.
* The extension IS built -- the call must genuinely cross into Rust and the
  decision must depend on the input.

Both classes are guarded on `_EXT_AVAILABLE`, so on either machine one class
runs and the other skips. That guard is deliberate, but it has a failure mode
worth naming: when the extension was unbuildable (pyo3 0.20.3 rejected Python
3.14), only the not-available class existed, so this file ran five tests that
could never exercise a single line of routing logic. Tests that cannot fail
are the defect this repository keeps finding; the available-path class below
is what stops this file from being one.
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


@unittest.skipUnless(_EXT_AVAILABLE, "compiled inference_router extension not built")
class AvailableTests(unittest.TestCase):
    """Real calls across the Python/Rust boundary."""

    def setUp(self) -> None:
        self.bridge = RustInferenceRouterBridge()

    def _route(self, **kw) -> dict:
        base = dict(
            task_id="t", prompt="do a thing", complexity_score=0.5,
            privacy_required=False, max_budget_usd=0.10,
        )
        base.update(kw)
        return self.bridge.route(**base)

    def test_is_available_and_no_import_error(self) -> None:
        self.assertTrue(self.bridge.is_available())
        self.assertIsNone(self.bridge.import_error())

    def test_decision_carries_every_documented_key(self) -> None:
        decision = self._route()
        for key in ("target", "node_id", "estimated_latency_ms", "estimated_cost_usd"):
            self.assertIn(key, decision)

    def test_low_and_high_complexity_route_to_different_tiers(self) -> None:
        """The whole point of a router: the answer must depend on the input."""
        cheap = self._route(complexity_score=0.1)
        costly = self._route(complexity_score=0.95)
        self.assertNotEqual(cheap["target"], costly["target"])
        self.assertLess(cheap["estimated_cost_usd"], costly["estimated_cost_usd"])

    def test_empty_registry_falls_back_rather_than_inventing_a_peer(self) -> None:
        """With no FHE-capable node registered, a privacy-required request
        falls back to the premium API. `node_id` names that provider, which is
        legitimate -- what must never happen is a peer id for a node nobody
        registered."""
        decision = self._route(privacy_required=True)
        self.assertEqual(self.bridge.get_node_count(), 0)
        self.assertEqual(decision["target"], "GPT-4-Turbo")
        self.assertEqual(decision["node_id"], "openai")

    def test_registering_an_fhe_node_changes_the_private_route(self) -> None:
        before = self._route(privacy_required=True)
        self.bridge.register_node("fhe-1", 0.2, 300.0, 0.0001, True)
        after = self._route(privacy_required=True)
        self.assertNotEqual(before["target"], after["target"])
        self.assertEqual(after["node_id"], "fhe-1")

    def test_node_count_reflects_real_registrations(self) -> None:
        self.assertEqual(self.bridge.get_node_count(), 0)
        self.bridge.register_node("n1", 0.1, 100.0, 0.0001, False)
        self.bridge.register_node("n2", 0.2, 200.0, 0.0001, False)
        self.assertEqual(self.bridge.get_node_count(), 2)

    def test_cost_scales_with_prompt_length(self) -> None:
        """`cost_per_token * 100.0` was hardcoded while the real prompt sat
        unused in `_prompt`, so every request was quoted the same price
        whatever its size. The estimate is crude (4 chars per token) but it
        must at least respond to the input it is handed."""
        self.bridge.register_node("gpu-1", 0.1, 200.0, 0.001, False)
        short = self._route(complexity_score=0.6, prompt="hi")
        long = self._route(complexity_score=0.6, prompt="x" * 4000)
        self.assertEqual(short["target"], "Decentralized-GPU")
        self.assertEqual(long["target"], "Decentralized-GPU")
        self.assertGreater(long["estimated_cost_usd"], short["estimated_cost_usd"])

    def test_missing_key_raises_keyerror_naming_it(self) -> None:
        """Every lookup used to `.unwrap()`, which aborts the interpreter
        rather than raising -- a caller omitting a field killed the process."""
        router = self.bridge._router
        self.assertIsNotNone(router)
        assert router is not None  # narrows Optional for the type checker
        with self.assertRaises(KeyError) as ctx:
            router.route_request({"task_id": "only-this-one"})
        self.assertIn("prompt", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
