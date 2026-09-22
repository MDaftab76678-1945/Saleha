---
name: darwinian-evolution
description: AlphaDev/FunSearch style self-evolution engine that benchmarks, mutates, and safely hot-reloads Saleha's internal algorithms to self-improve over time.
---

# Darwinian Self-Evolution Engine

## Overview

The `darwinian-evolution` skill empowers Saleha to autonomously optimize its own internal codebase. Following the principles of **DeepMind's FunSearch and AlphaDev**, it treats internal scripts and algorithms as evolving genotypes:
1. Evaluates baseline execution latency and memory allocation.
2. Synthesizes algorithmic mutant variations targeting bottleneck functions.
3. Benchmarks candidates in an isolated temporary sandbox.
4. If a mutant achieves physical speedup (e.g. >= 15% latency reduction) while maintaining 100% test passing, it is ratified for hot-reload.

## Safety & Invariants

1. **Strict Sandboxing:** All evolutionary trials execute in temporary directories. Broken mutants are instantly discarded.
2. **Non-Regressive Guarantee:** A mutant is never merged if even one existing unit test fails.

## Usage

Run an evolutionary optimization cycle on an internal script:

```bash
python .agents/skills/darwinian-evolution/scripts/self_mutator.py --target .agents/scripts/compact_context.py --test-cmd "python -m pytest saleha/tests/test_agent_scripts.py -k compact"
```
