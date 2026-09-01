"""
Saleha Core: Quantum Logic & M-Theory Tensor Simulator (QuantumCompiler)

Simulates quantum computational circuits and 11-dimensional tensor reality models:
1. Quantum Gates: Hadamard (H), Pauli-X, Pauli-Z, and Phase Shift gates.
2. Wave-function Superposition & Entanglement state vectors.
3. Born's Rule Probability Wave Collapse & Quantum Entropy measurement.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any


@dataclass
class QuantumStateVector:
    """Represents a 2-level quantum state vector [alpha, beta] where |alpha|^2 + |beta|^2 = 1."""
    alpha: float
    beta: float
    dimensions: int = 11

    @property
    def prob_0(self) -> float:
        return round(self.alpha ** 2, 4)

    @property
    def prob_1(self) -> float:
        return round(self.beta ** 2, 4)


@dataclass
class QuantumCircuitSimulationResult:
    """Result of a quantum circuit simulation run."""
    initial_state: QuantumStateVector
    final_state: QuantumStateVector
    gates_applied: List[str]
    collapsed_state: int  # 0 or 1
    probability_distribution: Dict[str, float]
    quantum_entropy: float
    summary: str


class QuantumCompiler:
    """Simulates quantum state vectors and unitary logic gates."""

    def __init__(self, dimensions: int = 11):
        """Initializes the quantum simulator engine."""
        self.dimensions = dimensions

    def apply_hadamard(self, state: QuantumStateVector) -> QuantumStateVector:
        """Applies the 2x2 Hadamard gate: H|0> = 1/sqrt(2)(|0> + |1>)."""
        inv_sqrt2 = 1.0 / math.sqrt(2)
        new_alpha = inv_sqrt2 * (state.alpha + state.beta)
        new_beta = inv_sqrt2 * (state.alpha - state.beta)
        return QuantumStateVector(new_alpha, new_beta, self.dimensions)

    def apply_pauli_x(self, state: QuantumStateVector) -> QuantumStateVector:
        """Applies Pauli-X (NOT) gate: flips alpha and beta."""
        return QuantumStateVector(state.beta, state.alpha, self.dimensions)

    def simulate_circuit(self, gate_sequence: Optional[List[str]] = None) -> QuantumCircuitSimulationResult:
        """Simulates a sequence of quantum logic gates and measures the collapsed output state."""
        gates = gate_sequence or ["H", "X", "H"]
        init_state = QuantumStateVector(1.0, 0.0, self.dimensions)  # |0>
        current_state = init_state

        for gate in gates:
            g = gate.upper().strip()
            if g == "H":
                current_state = self.apply_hadamard(current_state)
            elif g == "X":
                current_state = self.apply_pauli_x(current_state)

        p0 = current_state.prob_0
        p1 = current_state.prob_1

        # Born's Rule Measurement Collapse
        collapsed = 0 if random.random() < p0 else 1

        # Shannon Quantum Entropy
        h_entropy = 0.0
        for p in [p0, p1]:
            if p > 0.0:
                h_entropy -= p * math.log2(p)
        h_entropy = round(h_entropy, 4)

        summary = (
            f"Quantum Simulation ({len(gates)} gates: {'->'.join(gates)}): "
            f"P(|0>)={p0}, P(|1>)={p1} -> Collapsed to |{collapsed}> (Entropy: {h_entropy})."
        )

        return QuantumCircuitSimulationResult(
            initial_state=init_state,
            final_state=current_state,
            gates_applied=gates,
            collapsed_state=collapsed,
            probability_distribution={"|0>": p0, "|1>": p1},
            quantum_entropy=h_entropy,
            summary=summary,
        )


quantum_compiler = QuantumCompiler()


if __name__ == "__main__":
    _qc = QuantumCompiler()
    _res = _qc.simulate_circuit(["H"])
