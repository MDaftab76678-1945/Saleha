---
name: gwt-blackboard
description: Global Workspace Theory (GWT) 9-Brain Octopus blackboard coordinator for sparse, multi-agent attention and consensus without token bloat.
---

# Global Workspace Theory (GWT) Blackboard Coordinator

## Overview

The `gwt-blackboard` implements the central coordinating mind of Saleha's **Octopus Architecture**. Instead of $N \times N$ token-heavy multi-agent chatting, specialized subconscious agents (Syntax Specialist, Type Verifier, SMT Engine, Complexity Critic) post findings as structured fact tuples to a **Sparse Shared Blackboard**.

An Attention Arbiter selects the highest-salience item (critical bug, type discrepancy, or formal violation) and broadcasts it to the Global Workspace (the Main Coordinating Brain).

## What this actually is

`octopus_blackboard.py` is a JSON-file-backed fact queue: `post_fact()` appends a
caller-supplied `(agent, topic, content, salience)` tuple, and
`arbitrate_attention()` returns the highest-salience entry. There is no
consensus mechanism, no acceptance criteria, and no verification of any kind
in this script -- salience values are supplied by the caller, not computed or
checked against anything. It is useful as a shared, salience-sorted inbox
across agents/tools; it does not itself validate or approve anything.

## Safety & Invariants

1. **Context Window Protection:** Agents only receive the salient broadcast, not the full fact history, preserving token capacity for reasoning.

## Usage

Post an observation and arbitrate attention:

```bash
python .agents/skills/gwt-blackboard/scripts/octopus_blackboard.py --post --agent "SyntaxSpecialist" --topic "undefined_var" --data "Line 24: variable 'tmp' unassigned"
```
