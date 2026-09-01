"""
Unit and integration tests for Phase 4: Non-Euclidean Hyperbolic AI, p-Adic Isolation, Sheaf Consensus, and Jitter Histogram.
"""

import math
import pytest

from saleha.core.hyperbolic_engine import HyperbolicVector, SAMHAttractorController, HYPERBOLIC_DIM
from saleha.core.padic_ultrametric import PadicValuationNode, PadicIsolationValidator, p_adic_valuation
from saleha.core.sheaf_consensus import SheafCohomologyConsensus, SHEAF_MOD_PRIME
from saleha.core.latency_histogram import NanosecondLatencyHistogram


class TestHyperbolicEngine:
    def test_poincare_ball_boundary_enforcement(self):
        # Create a vector exceeding unit radius
        v = HyperbolicVector([2.0] * HYPERBOLIC_DIM)
        norm_sq = v.norm_squared()
        # Must be strictly inside Poincaré ball (< 1.0)
        assert norm_sq < 1.0
        assert math.sqrt(norm_sq) < 1.0

    def test_from_bytes_projection(self):
        v = HyperbolicVector.from_bytes(b"HELLO_WORLD_12")
        assert len(v.coords) == HYPERBOLIC_DIM
        assert v.norm_squared() < 1.0

    def test_mobius_gyrovector_addition(self):
        u = HyperbolicVector([0.1] * HYPERBOLIC_DIM)
        v = HyperbolicVector([0.2] * HYPERBOLIC_DIM)
        sum_uv = u.mobius_addition(v)
        assert sum_uv.norm_squared() < 1.0

    def test_hyperbolic_geodesic_distance(self):
        u = HyperbolicVector.zero()
        v = HyperbolicVector([0.2] * HYPERBOLIC_DIM)
        dist = u.hyperbolic_distance(v)
        assert dist > 0.0

    def test_samh_attractor_healing(self):
        controller = SAMHAttractorController(drift_threshold=0.5)
        # Highly drifted state
        drifted_state = HyperbolicVector([-0.8] * HYPERBOLIC_DIM)
        dist_before, is_drifting = controller.evaluate_drift(drifted_state)
        assert is_drifting is True

        healed_state, was_healed, dist_after = controller.apply_self_healing_step(drifted_state)
        assert was_healed is True
        assert dist_after < dist_before


class TestPadicUltrametric:
    def test_padic_valuation_function(self):
        assert p_adic_valuation(25, prime=5) == 2  # 5^2 divides 25
        assert p_adic_valuation(125, prime=5) == 3 # 5^3 divides 125
        assert p_adic_valuation(7, prime=5) == 0   # 5^0 divides 7
        assert p_adic_valuation(0, prime=5) == 32  # Infinity

    def test_strong_triangle_inequality(self):
        node_x = PadicValuationNode.from_raw([25, 125, 5, 0, 10, 50, 0, 0])
        node_y = PadicValuationNode.from_raw([50, 250, 10, 0, 20, 100, 0, 0])
        node_z = PadicValuationNode.from_raw([75, 375, 15, 0, 30, 150, 0, 0])

        assert PadicValuationNode.verify_strong_triangle_inequality(node_x, node_y, node_z, prime=5) is True

    def test_padic_isolation_validator(self):
        validator = PadicIsolationValidator(prime=5)
        node_a = PadicValuationNode.from_raw([25, 125, 5, 0, 10, 50, 0, 0])
        node_b = PadicValuationNode.from_raw([50, 250, 10, 0, 20, 100, 0, 0])
        node_c = PadicValuationNode.from_raw([75, 375, 15, 0, 30, 150, 0, 0])

        res = validator.validate_compartment_isolation([node_a, node_b, node_c])
        assert res["isolated"] is True
        assert res["total_checks"] == 1
        assert "0.0%" in res["semantic_bleeding_risk"]


class TestSheafConsensus:
    def setup_method(self):
        self.sheaf = SheafCohomologyConsensus()

    def test_vanishing_cech_differential(self):
        # Symmetrical state: delta^1 c = 1000 - 2000 + 1000 = 0
        ok, diff, msg = self.sheaf.verify_cech_differential(1000, 2000, 1000)
        assert ok is True
        assert diff == 0
        assert "H^1 = 0" in msg

    def test_desynchronized_cech_differential_detected(self):
        # Desynchronized state: delta^1 c = 1000 - 2500 + 1000 = -500 != 0
        ok, diff, msg = self.sheaf.verify_cech_differential(1000, 2500, 1000)
        assert ok is False
        assert diff != 0
        assert "COHOMOLOGICAL_ANOMALY" in msg

    def test_multi_node_mesh_consensus(self):
        res = self.sheaf.verify_mesh_consensus([1000, 2000, 1000, 2000, 1000])
        assert res["synchronized"] is True
        assert "H^1 = 0" in res["cohomology_group"]


class TestLatencyHistogram:
    def setup_method(self):
        self.hist = NanosecondLatencyHistogram()

    def test_percentile_calculations(self):
        # Insert 100 samples from 10ns to 1000ns
        for i in range(1, 101):
            self.hist.record(i * 10)

        rep = self.hist.get_report()
        assert rep["total_samples"] == 100
        assert rep["min_ns"] == 10
        assert rep["max_peak_jitter_ns"] == 1000
        assert 450 <= rep["p50_ns"] <= 550
        assert 850 <= rep["p90_ns"] <= 950
        assert 950 <= rep["p99_ns"] <= 1000

