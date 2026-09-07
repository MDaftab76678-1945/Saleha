# AGENTSKILLS.md — Real Capability Matrix & Tool Registry

> **Project:** saleha-0.1 (Local-First Autonomous Multi-Agent AI Coding Assistant)  
> **Audience:** Saleha Core Orchestrators, 20 Domain Personas, Antigravity IDE, Claude Code  
> **Source of Truth:** Aligned with `docs/AGENT_PROFILES.md` and `saleha/skills/`

This document defines the real, executable capability matrix, tool permissions, and context budgets
for Saleha's 20 domain personas and autonomous workflow skills.

---

## 1. System Tooling Registry

All agent capabilities are grounded strictly in real executable modules within `saleha/`:

| Tool Identifier | Implementation File | Primary Capability | Execution Mode |
| --- | --- | --- | --- |
| `sandbox_jail` | `saleha/sandbox/sandbox_jail.py` | Subprocess execution with Windows timeout | Isolated Subprocess |
| `ast_verifier` | `saleha/sandbox/ast_security_verifier.py` | Static AST audit of imports & syscalls | Deterministic Python AST |
| `math_engine` | `saleha/core/math_logic.py` | Complexity estimation (0.0 to 10.0) | Regex & Weighted Scoring |
| `smt_verifier` | `saleha/core/formal_smt_verifier.py` | Mathematical & logical constraint proofs | Z3 Theorem Solver |
| `bm25_search` | `saleha/core/bm25.py` | Lexical indexing and relevant code retrieval | Lexical Inverted Index |
| `ast_cache` | `saleha/core/incremental_ast_cache.py` | Cache AST parses to detect change impact | AST Dependency Graph |

---

## 2. Domain Personas Capability Matrix

Saleha adopts specialized personas defined in `docs/AGENT_PROFILES.md`. Each role operates under strict boundary gates:

| Profile ID | Role Name | Allowed Tools | Boundary Restrictions | Token Budget |
| --- | --- | --- | --- | --- |
| `agent_sde` | Core Distributed SDE | `sandbox_jail`, `math_engine`, `ast_cache` | Cannot bypass AST security verifier | 2048 tokens |
| `agent_security_engineer` | App & Cloud Security | `ast_verifier`, `sandbox_jail`, `bm25_search` | Cannot commit changes directly to main | 4096 tokens |
| `agent_test_automation_engineer` | Test Automation | `sandbox_jail`, `ast_cache`, `math_engine` | Restricted strictly to `saleha/tests/` | 2048 tokens |
| `agent_software_designer` | LLD Architect | `bm25_search`, `math_engine`, `smt_verifier` | Read-only analysis; no code synthesis | 4096 tokens |
| `agent_programmer` | Core Code Synthesizer | `sandbox_jail`, `math_engine` | Must follow surgical diff contracts | 2048 tokens |
| `agent_cloud_architect` | Cloud Solutions Architect | `bm25_search`, `ast_verifier` | Cannot generate synthetic cloud mocks | 4096 tokens |
| `agent_performance_tester` | Performance Engineer | `sandbox_jail`, `math_engine` | Must measure physical execution times | 2048 tokens |
| `agent_compliance_officer` | Compliance & Privacy | `ast_verifier`, `bm25_search` | Read-only audit; zero disk writes | 4096 tokens |

---

## 3. Invokable Workflow Skills

In addition to static personas, Saleha executes autonomous workflow skills located in `.agents/skills/`:

### Self-Improvement Engine (`self-improve-engine`)

- **Implementation:** `.agents/skills/self-improve-engine/SKILL.md`
- **Workflow:**
  1. Scans untested modules in `saleha/core/` using AST inspection.
  2. Generates real unit tests using the local coder model (`qwen2.5-coder:3b`).
  3. Executes test candidates in an isolated temporary directory (`tempfile.TemporaryDirectory`).
  4. Commits passing tests strictly to the isolated `auto/self-improve` branch.
  5. Never touches the user's active branch or unrelated files.

---

## 4. Local Model Budgeting & Context Bounds

To prevent hallucinations on consumer-grade local hardware:

- **Fast Tier (`qwen2.5-coder:3b`):** Max prompt context 2048 tokens. Used for surgical unit test generation, regex extraction, and single-function patches.
- **Reasoning Tier (`qwen3:8b` / `deepseek-r1:7b`):** Max prompt context 4096 tokens. Used for multi-step planning, security reviews, and SMT verification tasks.
- **BM25 Pruning:** Any prompt referencing multiple files must prune irrelevant functions using `saleha/core/bm25.py` before model submission.

---

## 5. Autonomous Evolution & Self-Building Architecture

Saleha agents are architected to self-improve without human hand-holding while respecting absolute safety invariants:

### 5.1 Dynamic Tool Synthesis Lifecycle

When an agent identifies a missing capability (e.g., a custom dependency checker or log parser):

1. **Specification:** Agent specifies typed input and output contracts.
2. **AST Static Verification:** The synthesized tool code is inspected by `ast_security_verifier.py` to ensure zero unsafe syscalls or network leaks.
3. **Sandbox Unit Testing:** The agent writes positive and negative test cases. The tool must execute in `sandbox_jail.py` and pass with exit code 0.
4. **Dynamic Registration:** The verified tool is registered in the orchestrator's dispatcher and becomes available for runtime execution.
5. **Runtime Fallback:** If the tool fails at runtime, the orchestrator gracefully degrades to standard execution without crashing the active session.

### 5.2 Reusable Function Synthesis

- Agents abstract frequently repeated algorithmic logic into clean, modular Python functions within `saleha/core/`.
- Every synthesized function requires full type annotations and automated unit tests.

### 5.3 Autonomous Regression Shields

- Every bug fix executed by an agent must be paired with a new permanent test in `saleha/tests/test_*.py`.
- The test must fail before the fix (Red) and pass after the fix (Green), locking the fix against future regressions.

### 5.4 Reflexion Memory & Error Playbooks

- When an execution path fails or encounters an edge case, the orchestrator records a structured lesson in `saleha/core/memory_store.py`.
- Future sessions targeting similar tasks automatically inject these lessons to eliminate repetitive mistakes.

### 5.5 Self-Design & Complexity Refactoring

- Agents periodically audit repository complexity using `saleha/core/math_logic.py` and `radon`.
- Functions exceeding cyclomatic complexity 10.0 are automatically staged for AST-safe modularization into smaller, testable sub-functions.
