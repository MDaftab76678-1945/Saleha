"""
Saleha Core: single-qubit quantum circuit simulator.

Applies a sequence of single-qubit gates to |0>, measures under the Born rule,
and reports the Shannon entropy of the outcome distribution. The linear algebra
is real and correct.

## What the name used to claim

This was "Quantum Logic & M-Theory Tensor Simulator", advertising
"11-dimensional tensor reality models" and "entanglement state vectors".

There is **one qubit**. The state is `[alpha, beta]` -- two complex amplitudes,
here restricted to reals. There is no tensor product, so entanglement is not
representable at all: it needs at least two qubits. The `dimensions = 11` field
was carried on every state and used by nothing.

## The bug that name hid

Unsupported gates were silently skipped. Measured, before the fix:

    simulate_circuit(["H"])                        -> P0=0.5, P1=0.5
    simulate_circuit(["H","Z","S","T","CNOT","Y"]) -> P0=0.5, P1=0.5

Identical, because five of the six gates did nothing -- while the summary line
read "6 gates: H->Z->S->T->CNOT->Y", so the caller had no way to know.

Z, S, T and Y are genuine single-qubit gates and are implemented now. Gates
that need a second qubit (CNOT, CZ, SWAP, Toffoli) cannot work in a one-qubit
simulator, so they are **rejected by name** rather than ignored: the result
carries `rejected_gates` and the summary says which were not applied.

Phase gates (S, T) and Y introduce complex amplitudes, so the state is complex
now. `prob_0`/`prob_1` use |amplitude|^2 accordingly.
"""

import cmath
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

# Gates that act on one qubit. Anything outside this set either needs more
# qubits or is not a gate at all.
SUPPORTED_GATES = ("H", "X", "Y", "Z", "S", "T", "I")

# Real gates that this simulator structurally cannot run: they act on two or
# more qubits. Named explicitly so the rejection message can say why.
MULTI_QUBIT_GATES = ("CNOT", "CX", "CZ", "SWAP", "TOFFOLI", "CCX", "CSWAP")


@dataclass
class QuantumStateVector:
    """
    One qubit: [alpha, beta] with |alpha|^2 + |beta|^2 = 1.

    Amplitudes are complex, because the S, T and Y gates produce complex
    values. The `dimensions = 11` field is gone -- it was on every state,
    referenced by nothing, and implied a tensor space this simulator does not
    have.
    """
    alpha: complex
    beta: complex

    @property
    def prob_0(self) -> float:
        return round(abs(self.alpha) ** 2, 4)

    @property
    def prob_1(self) -> float:
        return round(abs(self.beta) ** 2, 4)


@dataclass
class QuantumCircuitSimulationResult:
    """Result of a quantum circuit simulation run."""
    initial_state: QuantumStateVector
    final_state: QuantumStateVector
    # Only the gates that were actually applied. Previously this echoed back
    # everything the caller passed, including gates that were silently skipped.
    gates_applied: List[str] = field(default_factory=list)
    collapsed_state: int = 0  # 0 or 1
    probability_distribution: Dict[str, float] = field(default_factory=dict)
    quantum_entropy: float = 0.0
    summary: str = ""
    # Gates that were NOT applied, each with the reason.
    rejected_gates: List[str] = field(default_factory=list)

    @property
    def all_gates_applied(self) -> bool:
        return not self.rejected_gates


class QuantumCompiler:
    """Simulates quantum state vectors and unitary logic gates."""

    def __init__(self):
        """Initializes the single-qubit simulator."""

    def apply_hadamard(self, state: QuantumStateVector) -> QuantumStateVector:
        """H = 1/sqrt(2) * [[1, 1], [1, -1]]."""
        inv_sqrt2 = 1.0 / math.sqrt(2)
        return QuantumStateVector(inv_sqrt2 * (state.alpha + state.beta),
                                  inv_sqrt2 * (state.alpha - state.beta))

    def apply_pauli_x(self, state: QuantumStateVector) -> QuantumStateVector:
        """X = [[0, 1], [1, 0]] -- the NOT gate."""
        return QuantumStateVector(state.beta, state.alpha)

    def apply_pauli_y(self, state: QuantumStateVector) -> QuantumStateVector:
        """Y = [[0, -i], [i, 0]]."""
        return QuantumStateVector(-1j * state.beta, 1j * state.alpha)

    def apply_pauli_z(self, state: QuantumStateVector) -> QuantumStateVector:
        """Z = [[1, 0], [0, -1]] -- a phase flip on |1>."""
        return QuantumStateVector(state.alpha, -state.beta)

    def apply_phase(self, state: QuantumStateVector, angle: float) -> QuantumStateVector:
        """A phase-shift gate: [[1, 0], [0, e^(i*angle)]]. S is pi/2, T is pi/4."""
        return QuantumStateVector(state.alpha, cmath.exp(1j * angle) * state.beta)

    def simulate_circuit(self, gate_sequence: Optional[List[str]] = None) -> QuantumCircuitSimulationResult:
        """Simulates a sequence of quantum logic gates and measures the collapsed output state."""
        gates = gate_sequence or ["H", "X", "H"]
        init_state = QuantumStateVector(1.0 + 0j, 0j)  # |0>
        current_state = init_state

        applied: List[str] = []
        rejected: List[str] = []

        for gate in gates:
            g = gate.upper().strip()
            if g == "H":
                current_state = self.apply_hadamard(current_state)
            elif g == "X":
                current_state = self.apply_pauli_x(current_state)
            elif g == "Y":
                current_state = self.apply_pauli_y(current_state)
            elif g == "Z":
                current_state = self.apply_pauli_z(current_state)
            elif g == "S":
                current_state = self.apply_phase(current_state, math.pi / 2)
            elif g == "T":
                current_state = self.apply_phase(current_state, math.pi / 4)
            elif g == "I":
                pass  # identity: a real gate that legitimately changes nothing
            elif g in MULTI_QUBIT_GATES:
                # Structurally impossible here, not merely unimplemented.
                rejected.append(f"{g} (needs 2+ qubits; this simulator has 1)")
                continue
            else:
                rejected.append(f"{g} (unknown gate)")
                continue
            applied.append(g)

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

        # Report what ran, not what was asked for. The old summary printed the
        # full requested sequence even when most of it had been skipped.
        applied_desc = "->".join(applied) if applied else "none"
        summary = (
            f"Single-qubit simulation ({len(applied)} of {len(gates)} gates "
            f"applied: {applied_desc}): P(|0>)={p0}, P(|1>)={p1} -> "
            f"collapsed to |{collapsed}> (entropy {h_entropy})."
        )
        if rejected:
            summary += f" NOT applied: {', '.join(rejected)}."

        return QuantumCircuitSimulationResult(
            initial_state=init_state,
            final_state=current_state,
            gates_applied=applied,
            collapsed_state=collapsed,
            probability_distribution={"|0>": p0, "|1>": p1},
            quantum_entropy=h_entropy,
            summary=summary,
            rejected_gates=rejected,
        )


quantum_compiler = QuantumCompiler()
