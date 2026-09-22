---
name: codebase-world-model
description: JEPA-style latent predictive world model that mentally simulates code change impacts and test failures without disk compilation.
---

# Codebase Latent World Model

## Overview

The `codebase-world-model` implements Yann LeCun's **Joint Embedding Predictive Architecture (JEPA)** for software engineering. Instead of relying exclusively on slow physical compile-test cycles, the agent maintains an internal predictive mental model:
$$\text{State}_{t+1} = \text{WorldModel}(\text{State}_t, \text{Action})$$

Before mutating code on disk, the agent queries the mental simulator:
- Predicts expected compiler syntax and type diagnostics
- Predicts which downstream test suites are at risk of failing
- Prunes counter-productive refactorings in latent space

## What this actually is

`LatentPredictor.simulate_modification()` is a real, deterministic AST diff:
it parses the proposed code, diffs function signatures against the current
file, substring-searches the test suite for references to removed/changed
symbols, and computes a risk score from those counts. There is no learned
model, embedding, or neural prediction -- "JEPA" here names the AST-diff
approach's role (predict impact before touching disk), not a trained
predictive network.

## Safety & Invariants

1. **Latent Simulation:** Evaluates hypothesis diffs in RAM without touching working directory files.
2. **No calibration loop exists.** Nothing in this script records predictions
   or compares them against later real test outcomes -- there is no feedback
   or calibration mechanism. Predictions are a one-shot static estimate only.

## Usage

Simulate the latent impact of a proposed change:

```bash
python .agents/skills/codebase-world-model/scripts/latent_world_model.py --target saleha/core/math_logic.py --code "x = x + 1"
```
