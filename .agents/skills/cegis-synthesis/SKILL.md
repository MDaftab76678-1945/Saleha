---
name: cegis-synthesis
description: Counterexample-Guided Inductive Synthesis (CEGIS) engine that verifies code candidates against formal mathematical specifications using Z3 SMT solving.
---

# Counterexample-Guided Inductive Synthesis (CEGIS)

## Overview

## What this actually is

`cegis_engine.py` implements only the **verifier** step of CEGIS: given a
precondition and postcondition over a single numeric variable, it uses Z3 to
either prove the postcondition holds (`unsat` on the negation) or produce a
concrete counterexample (`sat`). There is no synthesizer (no candidate
implementations are generated) and no counterexample-accumulation loop --
each invocation is a single one-shot check, not an iterative CEGIS loop. The
"CEGIS" name describes the intended full architecture this component is one
piece of, not what this script alone does.

## Safety & Invariants

1. **Deterministic Guarantees:** Verification relies on first-order logic and SMT constraints, not stochastic heuristics.
2. **No Mocked Passes:** A candidate is only accepted (`verified: True`) if Z3 reports `unsat` (no counterexample exists) across the domain space.

## Usage

Run a formal verification check:

```bash
python .agents/skills/cegis-synthesis/scripts/cegis_engine.py --pre "x >= 0" --post "x + 1 > x" --var x
```
