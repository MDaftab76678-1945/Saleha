---
name: active-inference-loop
description: Karl Friston's Free Energy / Active Inference loop that iteratively minimizes prediction error between desired code state and physical environment feedback.
---

# Active Inference Loop

## Overview

The `active-inference-loop` implements the Free Energy Principle for agentic code synthesis. Instead of open-loop generation or naive retries, it treats compiler messages, AST validations, and test execution outcomes as **sensory observations**. It continuously computes the delta between the expected state (prior) and physical observation (evidence) and selects actions that maximally reduce variational free energy (prediction error).

## Safety & Invariants

1. **Physical Sensory Feedback:** Every step must execute an AST inspection or sandbox test to obtain physical evidence.
2. **Convergence Bound:** If prediction error does not decrease over 3 consecutive cycles, trigger a strategy reset.
3. **No Fabricated Greens:** Exit only when verified evidence matches the expected specification with exit code 0.

## Usage

Run an active inference cycle on a target task:

```bash
python .agents/skills/active-inference-loop/scripts/run_inference_loop.py --target saleha/core/math_logic.py --goal "Preserve score range [0.0, 10.0]"
```
