---
name: mutation-engine
description: Mutation testing engine that injects AST mutants (operator swaps, inverted conditions) to physically verify test suite rigor and eliminate fake greens.
---

# Mutation Testing Engine

## Overview

The `mutation-engine` enforces the Hinton-Amodei rule ("A fabricated pass is worse than a wrong answer") through **Mutation Testing**. A test suite that passes 100% of the time is untrustworthy if it cannot detect intentional flaws.

This skill synthesizes mutated variations of target Python files. Implemented mutations, in `ASTMutator` (`run_mutation_test.py`):
- Arithmetic inversion (`+` to `-`, `-` to `+`)
- Comparison flipping (`>` to `<=`, `<` to `>=`, `==` to `!=`)

(`*`/`/` and boundary-value mutations are not implemented.)

It executes the test suite against each mutant. If a mutant causes the test suite to **fail**, the mutant is **killed** (good). If the test suite continues to pass despite the mutant, the mutant has **survived** (test suite defect).

## Safety & Invariants

1. **Mutation Kill Threshold:** A test suite must achieve a **Mutation Score >= 80%** to be accepted as a genuine green.
2. **Original File Restored:** Each mutant is written directly to `target_path` on disk (not a copy), the test command is run against it, and the original file is restored from a `.py.bak` backup in a `finally` block afterward -- the file is genuinely modified during the run, not left untouched, but is always restored before the script exits.

## Usage

Run mutation analysis against a target module:

```bash
python .agents/skills/mutation-engine/scripts/run_mutation_test.py --target saleha/core/math_logic.py --test-cmd "python -m pytest saleha/tests/test_math_logic.py -q"
```
