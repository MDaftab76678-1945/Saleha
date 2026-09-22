---
trigger: always_on
description: Prevents premature termination of agent loops on step 0 and mandates physical verification evidence.
---

# Anti-Premature Finish & Loop Invariant Contract

This rule enforces non-trivial agent execution invariants across all autonomous loops in Saleha.

## 1. Zero-Step Termination Prohibition

- An agent loop MUST NOT invoke `finish()` or report completion at step 0 without executing at least one physical exploratory or analytical action (`min_actions_before_finish >= 1`).
- Returning immediate speculative conclusions without consulting the filesystem, AST, or test runner is strictly forbidden.

## 2. Physical Evidence Mandate

- No task claiming a fix, refactoring, or implementation is complete until supported by physical evidence:
  1. A successful AST validation or compilation step.
  2. A verified exit code `0` from the relevant test command.
- The phrase "the code should now work" or "looks correct" without an executed verification command is an invalid termination signature.

## 3. Loop Termination Invariants

Before exiting any iterative loop (ReAct, CEGIS, or Self-Healing), the agent must physically assert:
- `residual_delta == 0`: All reported compiler diagnostics, type errors, or failing assertions have been addressed.
- `untracked_side_effects == 0`: No unrelated files were touched or modified.
- `regression_count == 0`: Existing adjacent tests continue to pass.
