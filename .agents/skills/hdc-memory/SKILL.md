---
name: hdc-memory
description: Kanerva Hyperdimensional Computing (HDC) Vector Symbolic Architecture for O(1) associative bug-solution recall without token bloat.
---

# Hyperdimensional Computing (HDC) Memory

## Overview

The `hdc-memory` skill implements Pentti Kanerva's **Hyperdimensional Computing (HDC)** and Plate's Holographic Reduced Representations (HRR). Instead of dumping historical conversation transcripts or raw code logs into LLM prompt contexts, it represents program states, defect signatures, and successful fixes as **10,000-dimensional bipolar hypervectors** ($\{-1, +1\}^{10000}$).

### What is actually implemented

`hyperdimensional_memory.py` implements two of the three HDC operations:

1. **Encoding:** a bug-description string is deterministically hashed
   (SHA-256-seeded) into a $\{-1, +1\}^{10000}$ bipolar hypervector.
2. **Associative Recall:** cosine similarity against all stored vectors finds
   the closest matching historical pattern.

**Binding ($\otimes$) and Bundling ($\oplus$) are not implemented** -- there is
no role/filler composition and no superposition of multiple associations into
one vector. Each stored pattern is one independent hypervector; recall is a
linear scan over stored vectors, not O(1).

## Safety & Invariants

1. **Zero Context Pollution:** Solution patterns are stored as mathematical hypervectors in RAM, consuming 0 LLM context tokens.
2. **Deterministic Orthogonality:** High dimensionality guarantees that unrelated code patterns remain quasi-orthogonal (cosine similarity $\approx 0$).

## Usage

Index a resolved bug pattern and query associative memory:

```bash
python .agents/skills/hdc-memory/scripts/hyperdimensional_memory.py --store --bug "ZeroDivisionError in math_logic.py" --fix "add guard: if denom == 0: return 0.0"
```
