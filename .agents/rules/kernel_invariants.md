---
trigger: always_on
description: Autonomous master kernel invariants, state transition rules, and flight recorder requirements.
---

# Autonomous Master Kernel Invariants

This rule governs the central orchestrator kernel of Saleha's autonomous operating system.

## 1. Closed-Loop Execution Requirement

- The autonomous kernel MUST NOT execute open-loop modifications. Every mutation must undergo:
  1. Pre-execution CPG slicing & blast-radius evaluation.
  2. Sandbox validation with concrete exit codes.
  3. Formal SMT or Mutation testing before committing changes.

## 2. Flight Recorder Logging

- Every stage transition (Dispatch, Slicing, Consensus, Sandbox, Mutation) MUST append an immutable audit record to the flight recorder stream.
- Replay tokens must be preserved to guarantee deterministic time-travel verification.

## 3. Fail-Closed Security Policy

- If any stage (AST security, SMT verifier, or Mutation gate) reports non-compliance, the kernel must abort the cycle, restore working directory state, and log the failure diagnosis.
