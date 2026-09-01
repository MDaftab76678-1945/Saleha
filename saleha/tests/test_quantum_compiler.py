"""Unit tests for Quantum Logic & M-Theory Tensor Simulator."""

import unittest
from saleha.core.quantum_compiler import QuantumCompiler, QuantumStateVector, QuantumCircuitSimulationResult


class TestQuantumCompiler(unittest.TestCase):
    """Test suite for QuantumCompiler state transformations and gate operations."""

    def setUp(self):
        self.compiler = QuantumCompiler(dimensions=11)

    def test_apply_hadamard_creates_superposition(self):
        init_state = QuantumStateVector(1.0, 0.0, 11)
        sup_state = self.compiler.apply_hadamard(init_state)
        self.assertAlmostEqual(sup_state.prob_0, 0.5, places=2)
        self.assertAlmostEqual(sup_state.prob_1, 0.5, places=2)

    def test_simulate_circuit_returns_valid_measurement(self):
        res = self.compiler.simulate_circuit(["H", "X", "H"])
        self.assertIsInstance(res, QuantumCircuitSimulationResult)
        self.assertIn(res.collapsed_state, [0, 1])
        self.assertGreaterEqual(res.quantum_entropy, 0.0)


if __name__ == "__main__":
    unittest.main()
