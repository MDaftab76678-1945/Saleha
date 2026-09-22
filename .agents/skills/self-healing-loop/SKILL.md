---
name: self-healing-loop
description: Stack-trace diagnosis and surgical patch loop that autonomously isolates failing lines, generates targeted AST diffs, and validates in sandbox.
---

# Self-Healing Execution Loop

## Overview

The `self-healing-loop` skill provides automated diagnosis and repair for test and runtime failures. When a crash or assertion failure occurs, it parses the standard Python traceback, extracts the exact file and line number, analyzes the failing expression, and generates a minimal surgical patch.

## Safety & Invariants

1. **Minimal Blast Radius:** Edits only the targeted failing function or expression. Never modifies unrelated files or global configurations.
2. **Physical Verification:** Each proposed patch is verified via sandbox test execution. If the patch fails or introduces a new error, it is discarded immediately.
3. **Attractor State Defense:** Discontinues patching after 3 unsuccessful attempts and triggers phase reset instead of thrashing.

## Usage

Diagnose and heal a failing test command:

```bash
python .agents/skills/self-healing-loop/scripts/self_heal_engine.py --test-cmd "python -m pytest saleha/tests/test_math_logic.py"
```
