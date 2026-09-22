---
name: bft-swarm-consensus
description: Byzantine Fault Tolerant (BFT) voting gate that coordinates heterogeneous models (3B coder, 8B reasoner, Z3 SMT) to eliminate single-model hallucinations.
---

# Byzantine Fault Tolerant (BFT) Swarm Consensus

## Overview

The `bft-swarm-consensus` coordinates a heterogeneous multi-brain voting gate across local models and formal engines:
1. **Syntactic Proposer (3B Model):** High-speed (80+ tok/s) code synthesizer proposing minimal AST patches.
2. **Structural Reasoner (8B/7B Model):** Architectural consistency and edge-case critic evaluating algorithmic side effects.
3. **Formal Arbiter (Z3 SMT Solver):** Mathematical contract verifier evaluating invariant boundary proofs.

A proposed change is only ratified and written to disk if a **$2/3$ Byzantine Supermajority** is achieved, with the Formal Arbiter possessing veto power over mathematical invariants.

## Safety & Invariants

1. **Deterministic Veto:** If Z3 SMT reports a counterexample, the proposal is rejected regardless of model voting.
2. **Zero Fabrication:** Votes are computed from physical AST checks and SMT formulas; no mock unanimous consensus.

## Usage

Arbitrate consensus on a proposal:

```bash
python .agents/skills/bft-swarm-consensus/scripts/bft_consensus_gate.py --proposal "x = max(0, x)" --pre "x > -10" --post "x >= 0"
```
