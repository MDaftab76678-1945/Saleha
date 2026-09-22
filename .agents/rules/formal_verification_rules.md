---
trigger: always_on
description: Mandatory formal verification, invariant preservation, and zero fake green rules.
---

# Formal Verification & Non-Fabrication Engineering Contract

This rule codifies the physical verification boundaries and mathematical rigor required across all Saleha autonomous operations.

## 1. Zero Tolerance on Fabricated Passes (Hinton-Amodei Rule)

- Fabricated passes, mocked scoreboards, and synthetic "5/5 tests passed" claims without subprocess execution are catastrophic violations.
- An agent must never write unit tests that merely assert hardcoded constants returned by fake stubs.
- If a check fails, the agent must output the genuine stderr, stack trace, and non-zero exit code.

## 2. SMT Contract Requirements

For critical algorithms (such as complexity scoring in `math_logic.py`, routing bounds in `dynamic_lora_router.py`, and token allocation):
- Define mathematical pre-conditions and post-conditions.
- Use `saleha/core/formal_smt_verifier.py` with Z3 to prove that invariants hold for all valid inputs across domain bounds.
- If an edge case counterexample is produced by Z3, treat it as a hard reproduction unit test before writing production code.

## 3. Sandboxed Execution Safety

- All untrusted or synthesized code must run through `saleha/sandbox/sandbox_jail.py`.
- Windows process isolation must be respected: zero POSIX signals or unportable memory primitives.
