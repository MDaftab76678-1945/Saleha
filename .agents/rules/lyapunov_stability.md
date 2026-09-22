---
trigger: always_on
description: Detects attractor states, limit-cycle thrashing, and enforces dynamic phase resets.
---

# Lyapunov Stability & Limit-Cycle Prevention Contract

This rule governs loop stability, preventing agents from entering infinite retry loops, oscillation between mutually contradictory edits, or local minima traps.

## 1. Thrashing & Limit-Cycle Signatures

An agent loop is considered "trapped in an attractor state" if any of the following occur:
1. **Oscillatory Edits:** An edit reverts a change made in iteration $N-1$ or $N-2$.
2. **Zero-Variance Error Tracing:** The same compiler error or test failure message is produced for 2 consecutive iterations despite code changes.
3. **AST Edit Distance Degradation:** The Levenshtein distance between code iterations drops to near zero without satisfying the test assertions.

## 2. Dynamic Phase-Reset Protocol

When an attractor state is detected:
- **Do not simply re-prompt:** Re-issuing the same instruction to a deterministic model yields the same failure.
- **Trigger Phase Reset:**
  1. Discard the current scratch diff and restore to the last physically verified git commit.
  2. Increase sampling temperature slightly (e.g. from 0.0 to 0.4) or switch the underlying coder prompt to a decomposition strategy.
  3. Decompose the failing function into two smaller sub-functions.
- **Maximum Loop Bound:** No single micro-refactoring loop may exceed 4 iterations without triggering an explicit strategy re-planning step.
