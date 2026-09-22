---
name: causal-debugger
description: Pearl's Causal Interventional Debugger using do-calculus to isolate root causes of failing tests rather than correlational symptoms.
---

# Pearl's Causal Interventional Debugger

## Overview

The `causal-debugger` skill implements Judea Pearl's **$do$-calculus** for software defect diagnosis. Standard debuggers observe correlations (which lines ran before an exception occurred), which leads to speculative edits.

This engine performs **counterfactual interventions**:
1. Identifies candidate state variables preceding an assertion failure.
2. Injects simulated interventions $do(X = v)$ into the evaluation environment.
3. Calculates the **Average Causal Effect (ACE)** of each variable on the assertion outcome:
   $$ACE = P(\text{AssertionPass} \mid do(X=v)) - P(\text{AssertionPass} \mid do(X=v_{\text{failing}}))$$

The variable with the highest causal effect is identified as the true root cause.

## Safety & Invariants

1. **Pure Counterfactual Analysis:** Interventions run inside an isolated simulation space without modifying disk files.
2. **Definitive Root-Cause Isolation:** Differentiates between symptom lines (where the crash happened) and causal lines (where bad state was born).

## Usage

Run causal intervention diagnosis:

```bash
python .agents/skills/causal-debugger/scripts/causal_intervention.py --expr "x + y > 10" --state '{"x": 2, "y": 3}'
```
