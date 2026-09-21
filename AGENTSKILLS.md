# AGENTSKILLS.md — Real Capability Matrix & Tool Registry

> **Project:** saleha-0.1 (Local-First Autonomous Multi-Agent AI Coding Assistant)  
> **Audience:** Saleha Core Orchestrators, 30 Domain Personas, Antigravity IDE, Claude Code  
> **Source of Truth:** Aligned with `docs/AGENT_PROFILES.md` and `saleha/skills/`

This document defines the real, executable capability matrix, tool permissions, and context budgets
for Saleha's 30 domain personas and autonomous workflow skills.

---

## 1. Capability Module Index (not a callable tool registry)

The modules below implement the capabilities the personas in section 2
depend on. **These are Python modules, not tool identifiers** — the short
names in the first column are descriptive labels for this table only, and
a persona cannot invoke them. The real, enforceable identifiers are the
`allowed_tools` values in section 2, which `agent_profile_loader.py`
parses from each profile's frontmatter.

> **Corrected 2026-09-21 (pass 137):** this table was headed "System
> Tooling Registry" with a "Tool Identifier" column, reading as if
> `sandbox_jail`, `math_engine`, `ast_cache` and the rest were callable
> by an agent. None of the six strings appears anywhere in the codebase
> as an identifier (verified by grep across `saleha/`); `math_engine` and
> `ast_cache` exist only as ordinary local variable and parameter names
> inside `planner.py` and `change_impact.py`. Section 2's note already
> warned that these were "not the real tool identifiers"; this heading
> now says so too rather than contradicting it.

| Label (this table only) | Implementation File | Primary Capability | Execution Mode |
| --- | --- | --- | --- |
| sandbox jail | `saleha/sandbox/sandbox_jail.py` | Subprocess execution with Windows timeout | Isolated Subprocess |
| AST verifier | `saleha/sandbox/ast_security_verifier.py` | Static AST audit of imports & syscalls | Deterministic Python AST |
| math engine | `saleha/core/math_logic.py` | Complexity estimation (0.0 to 10.0) | Regex & Weighted Scoring |
| SMT verifier | `saleha/core/formal_smt_verifier.py` | Mathematical & logical constraint proofs | Z3 Theorem Solver |
| BM25 search | `saleha/core/bm25.py` | Lexical indexing and relevant code retrieval | Lexical Inverted Index |
| AST cache | `saleha/core/incremental_ast_cache.py` | Cache AST parses to detect change impact | AST Dependency Graph |

---

## 2. Domain Personas Capability Matrix

Saleha adopts specialized personas defined in `docs/AGENT_PROFILES.md`. Each role operates under strict boundary gates:

`allowed_tools` below is read verbatim from each profile's YAML frontmatter
in `saleha/skills/agent_*.md`. `agent_profile_loader.py` parses it and
injects it into the system prompt as an `[AUTHORIZED TOOLS]` line — these
are the real tool identifiers the loader uses, not the module names in
section 1. A persona with no `write_file` is read-only by virtue of the
tools it was granted, which is the only boundary the code actually
enforces.

| Profile ID | Role Name | Allowed Tools (verbatim from frontmatter) |
| --- | --- | --- |
| `agent_sde` | Core Distributed SDE | `read_file`, `write_file`, `run_code`, `search_repo`, `list_dir` |
| `agent_security_engineer` | App & Cloud Security | `read_file`, `search_repo`, `run_code` |
| `agent_test_automation_engineer` | Test Automation | `read_file`, `search_repo`, `run_code` |
| `agent_software_designer` | LLD Architect | `read_file`, `search_repo`, `write_file` |
| `agent_programmer` | Core Code Synthesizer | `read_file`, `write_file`, `run_code`, `search_repo` |
| `agent_cloud_architect` | Cloud Solutions Architect | `read_file`, `search_repo`, `web_fetch` |
| `agent_performance_tester` | Performance Engineer | `read_file`, `search_repo`, `run_code` |
| `agent_compliance_officer` | Compliance & Privacy | `read_file`, `search_repo` |

> **Removed 2026-09-20 (pass 84):** this table previously carried a
> "Token Budget" column (2048 / 4096 per persona) and a "Boundary
> Restrictions" column with prose rules like "Cannot commit changes
> directly to main". Neither was real: no profile declares a token budget
> in its frontmatter, nothing in `agent_profile_loader.py` or anywhere
> else reads or enforces one, and the prose boundaries were not
> represented in code either. The `allowed_tools` list is the boundary
> mechanism that genuinely exists. See section 4 for the context limits
> that *are* real (they are per-model, not per-persona).

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

Context windows below are the registered values in
`saleha/core/context_budget.py`, which `ContextBudgetGuard` uses to size
prompts. Do not quote numbers that are not in that registry.

- **Fast Tier (`qwen2.5-coder:3b`):** 32768-token context. Used for surgical unit test generation, regex extraction, and single-function patches.
- **Reasoning Tier (`qwen3:8b`: 40960, `qwen3.5:9b`: 40960, `deepseek-r1:7b`: 32768):** Used for multi-step planning, security reviews, and SMT verification tasks. Note these are *reasoning* models — Ollama bills their chain of thought against the same `num_predict` budget as the answer, so a small output budget can return an empty reply (pass 63); `budget_for_model()` in `model_provider.py` accounts for this.
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
