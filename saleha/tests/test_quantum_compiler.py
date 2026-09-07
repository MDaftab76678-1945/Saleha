"""
Unit tests for the single-qubit circuit simulator.

This module had no tests at all, which is how a silent no-op survived in it:
unsupported gates were skipped while the summary line still listed them, so
`simulate_circuit(["H"])` and `simulate_circuit(["H","Z","S","T","CNOT","Y"])`
returned identical distributions with no indication that five gates had done
nothing.
"""

from __future__ import annotations

import cmath
import math
import unittest

from saleha.core.quantum_compiler import (
    QuantumCompiler, QuantumStateVector, MULTI_QUBIT_GATES,
)


class GateCorrectnessTests(unittest.TestCase):
    """The linear algebra, checked against known quantum identities."""

    def setUp(self):
        self.q = QuantumCompiler()

    def _probs(self, gates):
        d = self.q.simulate_circuit(gates).probability_distribution
        return d["|0>"], d["|1>"]

    def test_x_flips_zero_to_one(self):
        self.assertEqual(self._probs(["X"]), (0.0, 1.0))

    def test_hadamard_creates_equal_superposition(self):
        self.assertEqual(self._probs(["H"]), (0.5, 0.5))

    def test_hadamard_is_its_own_inverse(self):
        self.assertEqual(self._probs(["H", "H"]), (1.0, 0.0))

    def test_hzh_equals_x(self):
        """A standard identity: H Z H = X."""
        self.assertEqual(self._probs(["H", "Z", "H"]), self._probs(["X"]))

    def test_hxh_equals_z(self):
        """H X H = Z, so applied to |0> it leaves the qubit in |0>."""
        self.assertEqual(self._probs(["H", "X", "H"]), (1.0, 0.0))

    def test_t_twice_equals_s(self):
        """T is a pi/4 phase, S is pi/2, so T*T = S."""
        a = self.q.simulate_circuit(["H", "T", "T"]).final_state
        b = self.q.simulate_circuit(["H", "S"]).final_state
        self.assertAlmostEqual(abs(a.beta - b.beta), 0.0, places=9)

    def test_z_changes_phase_not_probability(self):
        """Z is a phase flip: it must not alter measurement probabilities."""
        self.assertEqual(self._probs(["H", "Z"]), self._probs(["H"]))
        after = self.q.simulate_circuit(["H", "Z"]).final_state
        plain = self.q.simulate_circuit(["H"]).final_state
        self.assertNotAlmostEqual(abs(after.beta - plain.beta), 0.0, places=6)

    def test_y_gate_is_applied(self):
        """Y = [[0, -i], [i, 0]] maps |0> to i|1>."""
        st = self.q.simulate_circuit(["Y"]).final_state
        self.assertAlmostEqual(abs(st.beta), 1.0, places=9)
        self.assertAlmostEqual(abs(st.alpha), 0.0, places=9)

    def test_identity_gate_changes_nothing(self):
        self.assertEqual(self._probs(["I"]), (1.0, 0.0))

    def test_state_stays_normalised(self):
        for gates in (["H"], ["H", "T"], ["H", "S", "Y"], ["X", "H", "Z", "T"]):
            st = self.q.simulate_circuit(gates).final_state
            total = abs(st.alpha) ** 2 + abs(st.beta) ** 2
            self.assertAlmostEqual(total, 1.0, places=9, msg=str(gates))

    def test_entropy_is_zero_for_a_definite_state_and_one_for_superposition(self):
        self.assertEqual(self.q.simulate_circuit(["X"]).quantum_entropy, 0.0)
        self.assertEqual(self.q.simulate_circuit(["H"]).quantum_entropy, 1.0)


class UnsupportedGateTests(unittest.TestCase):
    """The defect: gates that were skipped without saying so."""

    def setUp(self):
        self.q = QuantumCompiler()

    def test_two_qubit_gates_are_rejected_not_ignored(self):
        res = self.q.simulate_circuit(["H", "CNOT"])
        self.assertFalse(res.all_gates_applied)
        self.assertEqual(res.gates_applied, ["H"])
        self.assertTrue(any("CNOT" in r for r in res.rejected_gates))
        self.assertIn("2+ qubits", res.rejected_gates[0])

    def test_every_named_multi_qubit_gate_is_rejected(self):
        for gate in MULTI_QUBIT_GATES:
            res = self.q.simulate_circuit([gate])
            self.assertEqual(res.gates_applied, [], gate)
            self.assertTrue(res.rejected_gates, gate)

    def test_unknown_gate_is_rejected(self):
        res = self.q.simulate_circuit(["FLOOP"])
        self.assertTrue(any("unknown" in r for r in res.rejected_gates))

    def test_summary_reports_what_ran_not_what_was_asked(self):
        """
        The old summary read "6 gates: H->Z->S->T->CNOT->Y" while five of them
        had been skipped.
        """
        res = self.q.simulate_circuit(["H", "Z", "S", "T", "CNOT", "Y"])
        self.assertIn("5 of 6 gates applied", res.summary)
        self.assertIn("NOT applied", res.summary)

    def test_previously_identical_circuits_now_differ(self):
        """
        `["H"]` and `["H","Z","S","T","CNOT","Y"]` returned the same state
        because everything after H was dropped. The extra gates are real now.
        """
        a = self.q.simulate_circuit(["H"]).final_state
        b = self.q.simulate_circuit(["H", "Z", "S", "T", "Y"]).final_state
        self.assertNotAlmostEqual(abs(a.beta - b.beta), 0.0, places=6)

    def test_all_gates_applied_flag(self):
        self.assertTrue(self.q.simulate_circuit(["H", "X"]).all_gates_applied)
        self.assertFalse(self.q.simulate_circuit(["H", "SWAP"]).all_gates_applied)


class StateShapeTests(unittest.TestCase):

    def test_dimensions_field_is_gone(self):
        """
        Every state carried `dimensions = 11`, referenced by nothing, implying
        an 11-dimensional tensor space. There is one qubit.
        """
        st = QuantumStateVector(1.0 + 0j, 0j)
        self.assertFalse(hasattr(st, "dimensions"))

    def test_amplitudes_may_be_complex(self):
        st = QuantumCompiler().simulate_circuit(["H", "T"]).final_state
        self.assertIsInstance(st.beta, complex)
        self.assertNotAlmostEqual(st.beta.imag, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
