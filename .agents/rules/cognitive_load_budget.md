---
trigger: always_on
description: Cognitive load budgeting and model routing constraints for 3B/8B local inference.
---

# Cognitive Load Budget & Local Model Routing Contract

This rule codifies context limits and specialized role routing to maximize the capabilities of local Ollama models (`qwen2.5-coder:3b`, `qwen3:8b`).

## 1. Physical Context Budget (2048 - 4096 Tokens)

- Local models suffer severe attention degradation beyond their trained attention span.
- Never feed full multi-file dumps into a single prompt.
- When file size exceeds 150 lines, slice the AST or extract relevant def-use chains via `cpg_slicer.py` or `compact_context.py`.
- Target prompt ceiling: Under 2000 tokens for generation, reserving remaining capacity for output tokens.

## 2. Model Routing Specialization Matrix

Tasks must be routed to the appropriate engine rather than burdening a single general model:

| Task Type | Designated Engine | Rationale |
| :--- | :--- | :--- |
| **AST Inspection & Parsing** | `python:ast` / `QualityGuard` | Deterministic, zero tokens, instant execution. |
| **Surgical Syntax Fixes (<30 lines)** | `qwen2.5-coder:3b` | Fast latency (80+ tok/s), high syntax precision. |
| **Architectural Design & Planning** | `qwen3:8b` / `deepseek-r1:7b` | Multi-step reasoning and structural coherence. |
| **Mathematical Contract Proof** | `saleha/core/formal_smt_verifier.py` (Z3) | Exact logical proofs; zero stochastic hallucinations. |
| **Semantic Recall** | `BM25` + `nomic-embed-text` | Dense semantic retrieval under 50ms. |

## 3. Epistemic Foraging Constraint

- If a model's generation indicates high uncertainty (repetitive tokens or syntax truncation), immediately step down prompt complexity and isolate the single sub-function under test.
