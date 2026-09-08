# ORCHESTRATOR.md — Central Coordinating Mind & Multi-Agent Architecture

> **Project:** saleha-0.1 (Local-First Autonomous Multi-Agent AI Coding Assistant)  
> **Audience:** Saleha Core Orchestrators, Planner, Domain Agents, Claude Code, Gemini / Antigravity IDE  
> **Source of Truth:** Aligned with `AGENTS.md` and `saleha/orchestrator.py`

This document defines the central coordinating intelligence ("Main Dimag") of Saleha's Octopus architecture.
It governs how goals are disambiguated, broken down, delegated across 20 specialized domain agents, verified in isolation, and safely committed.

---

## 1. The Octopus Architecture (1 Central Mind, 20 Domain Brains)

Saleha is built on the biological principle of an octopus:
> *"Octopus ke paas nau dimag hote hain. Ye system bilkul octopus jaisa hai — har ek ke paas apna dimag, par ek main dimag hoga."*

- **The Central Mind (`SalehaOrchestrator`):** Manages state, memory routing, security gates, consensus, and atomic commits. It does not write arbitrary code itself; it coordinates, delegates, verifies, and judges.
- **The Specialized Worker Brains (20 Personas):** Deep specialists defined in `docs/AGENT_PROFILES.md` and `saleha/skills/agent_*.md` (e.g., `agent_sde`, `agent_security_engineer`, `agent_tester`, `agent_cloud_architect`). They execute domain-specific tasks under the supervisor's instruction.

---

## 2. The 6-Stage Execution State Graph

Every incoming user instruction flows through a deterministic, guard-railed lifecycle:

```text
User Request
     │
     ▼
[Stage 1: Clarity Gate] (active_inference_gate.py)
     │ ── If ambiguous / underspecified ──► Halt & Request User Clarification
     ▼
[Stage 2: Complexity Scoring & Planning] (math_logic.py & planner.py)
     ├── Score < 5.0  ──► Direct Execution Plan
     ├── Score < 9.0  ──► Split into 3-5 Sequential Steps
     └── Score >= 9.0 ──► Block & Require User-Approved Chunking
     │
     ▼
[Stage 3: Persona Selection & Task Dispatch] (AGENT_PROFILES.md)
     │ ── Selects best persona (e.g., security_engineer for auth, sde for algorithms)
     ▼
[Stage 4: Isolated Execution Loop] (AgentLoop in base_agent.py)
     │ ── min_actions_before_finish >= 1 (Enforces real tool investigation)
     │ ── Sandboxed Subprocess (Windows-safe subprocess jail)
     ▼
[Stage 5: Consensus & Verification Gate] (ast_security_verifier.py & formal_smt_verifier.py)
     ├── Static AST & Type Contract Checks
     ├── Live Pytest Execution in Sandbox
     └── Z3 SMT Formal Invariant Verification
     │
     ▼
[Stage 6: Atomic Commit or Snapshot Rollback]
     ├── If Green ──► Specific-file git staging & NOTEBOOK_IMPORT.md ledger update
     └── If Red   ──► Full atomic revert to pre-execution snapshot (Zero disk debris)
```

---

## 3. Memory Hierarchy & Cross-Model Isolation Contract

A central defect caught in Pass 24 was memory poisoning: Model B replayed Model A's cached solution without running inference, corrupting benchmark comparisons. The orchestrator enforces three distinct memory boundaries:

1. **Turn Scratchpad (Ephemeral Working Memory):**
   - Active only during the execution of a single user request.
   - Cleared completely upon stage completion.
2. **Semantic Memory Store (`saleha/core/memory_store.py`):**
   - Stores BM25 and vector embeddings for code retrieval and past solutions.
   - **Isolation Rule:** Every model family (`qwen2.5-coder:3b`, `qwen3:8b`, `deepseek-r1:7b`) must have an isolated namespace. Caches must never be shared across different model runs.
3. **Persistent Audit Ledger (`NOTEBOOK_IMPORT.md`):**
   - Append-only physical log.
   - Every pass, execution time, and real test count must be physically measured and appended.

---

## 4. Disagreement, Debate & Consensus Protocol

When multiple domain agents propose competing implementations, or when a critic agent challenges a proposal:

| Evaluation Dimension | Real Measurement Mechanism | Forbidden Anti-Pattern |
| --- | --- | --- |
| **Correctness** | Live execution in `saleha/sandbox/sandbox_jail.py`. Must exit code 0. | Fabricated `success=True` without sandbox run. |
| **Security** | AST traversal via `ast_security_verifier.py` inspecting syscalls and imports. | Constant `COMPLIANT` string on uninspected code. |
| **Code Simplicity** | Cyclomatic complexity via `saleha/core/math_logic.py` cross-checked with `radon`. | Arbitrary or hardcoded scores (e.g., 93.3/100). |
| **Contract Rigor** | Z3 SMT logic solving in `formal_smt_verifier.py`. | Returning mock formal passes without solver check. |

---

## 5. Blast-Radius Defense & Atomic Rollback Protocol

The orchestrator guarantees repository safety during autonomous runs:

1. **Pre-Flight Snapshot:** Before dispatching an agent to modify files, the orchestrator records the exact git hashes and file contents of the targeted paths.
2. **Strict Whitelist Staging:** The orchestrator only ever stages files that were explicitly in the approved task plan. Indiscriminate commands (`git add .`, `git commit -a`) are blocked at the engine level.
3. **Atomic Revert on Failure:** If any unit test fails in Stage 5, the orchestrator reverts all modified files to their exact pre-flight snapshot. No broken code or unverified diffs remain in the working tree.

---

## 6. Local-Model Engineering Constraints (3B/8B Runtimes)

The orchestrator operates inside physical consumer-grade hardware limits (1 local GPU, Ollama backend):

- **Strict Context Budget:** Prompts must remain under 2048-4096 tokens. Massive multi-file dumps are chunked using BM25 relevance filtering (`saleha/core/bm25.py`).
- **Structured JSON Fallback:** If a small local model generates malformed JSON or markdown prefixes, the orchestrator applies a regex JSON-extractor fallback before reporting a parsing error.
- **Anti-Premature Finish:** Enforces `min_actions_before_finish >= 1`. If an agent attempts to finish without executing at least one investigative tool, the orchestrator rejects the finish call and forces an inspection step.

---

## 7. Subsystem Coordination Matrix

| Subsystem | Primary Module | Orchestrator Handshake |
| --- | --- | --- |
| **Clarity Gate** | `saleha/agents/active_inference_gate.py` | Halts execution if user intent has high ambiguity score. |
| **Complexity Gate** | `saleha/core/math_logic.py` | Estimates complexity (0.0 to 10.0) from file types and keywords. |
| **Task Planner** | `saleha/agents/planner.py` | Generates 3-5 step plan for complex tasks. |
| **Sandbox Jail** | `saleha/sandbox/sandbox_jail.py` | Executes subprocesses with timeout and Windows path normalization. |
| **SMT Verifier** | `saleha/core/formal_smt_verifier.py` | Proves logical assertions using Z3 solver. |
| **AST Cache** | `saleha/core/incremental_ast_cache.py` | Re-indexes AST only for files modified in the active turn. |
