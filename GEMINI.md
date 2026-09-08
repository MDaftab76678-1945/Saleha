# GEMINI.md — Gemini / Antigravity Agent Operating System & Engineering Contract

> **Project:** saleha-0.1 (Local-First Autonomous Multi-Agent AI Coding Assistant)  
> **Audience:** Gemini / Antigravity IDE, Google DeepMind Agentic Tools  
> **Source of Truth:** Aligned with `AGENTS.md` and `CLAUDE.md`

This document is the absolute operating contract for Gemini / Antigravity working inside this repository.
It automatically loads at the start of every session and enforces strict engineering boundaries, physical runtime constraints, and past defect prevention.

---

## 1. The North Star: The User's Vision for Saleha

Saleha is an autonomous, self-improving coding intelligence designed under strict local constraints:

1. **The Octopus Architecture (Multi-Brain Coordination):**
   > "Octopus ke paas nau dimag hote hain. Ye system bilkul octopus jaisa hai — har ek ke paas apna dimag, par ek main dimag hoga."
   Independent specialized agents operating under a central coordinating mind.
2. **Autonomous Self-Building:**
   > "Isse khud ko build karne do — apne design ko improve kar sake, naye functions bana sake, apne liye tools bana sake."
   The system must be able to audit its own code, write real unit tests, and self-improve without human hand-holding.
3. **Small Beating Large (Local-First Supremacy):**
   > "4GB wale model ko 200B se behtar banane ka koi naya tareeka find kar."
   Running on local Ollama models (`qwen2.5-coder:3b`, `qwen3:8b`) is an engineering constraint to win inside, not a limitation to apologize for.
4. **Bold Engineering (No Timidity):**
   > "Tum darte kyu ho, zyada nahi sochna chahiye — hum wo kar sakte hai jo koi nahi kar sakta."
   Never settle for conservative or generic solutions. When proposing paths, always include the ambitious architectural option.

---

## 2. Absolute Non-Negotiables (Zero-Tolerance Boundaries)

1. **NO COMMANDS WITHOUT EXPLICIT PERMISSION:**
   - Never execute any shell command (`run_command`) without clearly telling the user what it does and obtaining explicit approval.
   - "Check karo" means inspect, read whole files, and report findings only.
2. **NEVER FABRICATE OR RETURN FAKE GREENS (The Hinton-Amodei Rule):**
   - A fabricated pass is worse than a wrong answer. A wrong answer gets caught; a fake green hides the bug.
   - Never return hardcoded `success=True`, invented benchmark scores, mock passes, or stubbed summaries.
   - If a local model fails or a step crashes, state the failure and exact exit code plainly.
3. **NO REQUISITION OF UNRELATED WORK (Blast-Radius Defense):**
   - Strictly forbidden: `git add .`, `git commit -a`, or indiscriminate glob staging.
   - Only explicitly stage the exact modified file paths. Never touch or commit the user's unrelated uncommitted files.
4. **ENGLISH-ONLY CODE & ZERO DIAGNOSTICS:**
   - All code, comments, docstrings, and log strings MUST be English only.
   - Zero editor/linter diagnostics: fix all type warnings, uninitialized variables, and imports.
   - Zero decorative emojis in code, tests, or logs (Windows cp1252 consoles crash on emojis).

---

## 3. The Defect Graveyard (Past Failure Signatures — NEVER REPEAT)

Over 29 audit passes, the following concrete fabrications were uncovered and eradicated. Every agent is strictly forbidden from repeating these patterns:

| Historical Defect | Module / Area | Forbidden Anti-Pattern |
| --- | --- | --- |
| **Silent Execution Bypass** | `saleha/orchestrator.py` | Returning `success=True` and `test_passed=True` without executing the code in a sandbox. |
| **Fabricated PR Audits** | `/autopr` command | Printing hardcoded "5/5 PASSED" and "0 CWE vulnerabilities" without running analyzers. |
| **Invented Scoreboards** | `omni_arena_engine.py` | Printing hardcoded benchmark literals (e.g. 97% certification) as "measured results". |
| **Rubber-Stamp Security** | `constitutional_guard.py` | Reporting `COMPLIANT` for dangerous code (such as disk wipes). |
| **Phantom Threat Detection** | `threat_modeler.py` | Reporting 6 threats and 4 HIGH severity on a completely empty directory. |
| **Constant Council Scoring** | `agent_council.py` | Returning an identical 93.3/100 score for every single proposal. |
| **Fake Interpretability** | `explain-code` / `mech_interp` | Performing simple substring matching and reporting it as a 0.95 "saliency score". |
| **Dead AST Imports** | 8 core modules | Importing `import ast` to look sophisticated but never calling AST methods. |
| **POSIX Violations on Windows** | `saleha/sandbox/sandbox_jail.py` | Unguarded `import resource` or POSIX signal calls crashing on Windows. |
| **Test Pinning** | Multiple tests | Writing unit tests that assert the fake mock values (`assert res.score == 93.3`). |
| **Silent Premature Finish** | `AgentLoop` | Calling `finish()` on step 0 without executing any investigative tool call. |
| **Shallow Static Analysis / Happy-Path AST** | `saleha/tools/ast_inspector.py` | Writing shallow `ast.walk` checks that ignore full language spec (omitting `*args`/`**kwargs`/`posonlyargs`/`kwonlyargs`, missing ternary `IfExp` and comprehension branches, and bleeding nested function complexity into parent scope). |
| **Vacuous Metrics Distortion** | Static tools / Metrics | Reporting `100.0%` for empty sets (e.g. 0 functions -> 100% type coverage) instead of `0.0` or explicit empty state. |

---

## 4. Engineering Precedents (Principles Mapped to Real Repo Defects)

Every engineering decision in this repo is guided by foundational builders and mapped to real defects caught here:

1. **Measure, do not assert (Hinton):** Every claim must have a physical number attached.
   - *Caught:* `agent_council` scored every proposal 93.3/100 with zero computation behind it.
2. **Talk to the machine, not about it (Torvalds):** Show the code, run the probe, prove the before/after.
   - *Caught:* Orchestrator's fake success was only proven by a reproduction probe showing `success=False` for `1/0`.
3. **Readable beats clever (van Rossum):** Code is read more than written; stick to clean, idiomatic English.
   - *Caught:* `orchestrator.py` had Devanagari Hindi, Hinglish, and English mixed in a single function.
4. **Simple enough to be obviously correct (Ritchie):** Prefer deleting a fake abstraction over decorating it.
   - *Caught:* Four orchestrators that made zero model calls were deleted instead of refactored.
5. **Reason from first principles (Musk):** Ask what the component must actually do, not what existing code mimics.
   - *Caught:* `cloud-plan`, `silicon-build`, and `causal-eval` generated constants; the first-principles fix was questioning their existence.
6. **Build for the person who arrives later (Berners-Lee):** Honest READMEs, clear contracts, self-contained documentation.
   - *Caught:* Lack of persistent instructions forced the user to re-explain the system at every session start.
7. **Make it work under real constraints (Eich):** Work inside 1 GPU, local models, zero cloud budget.
   - *Caught:* Activation patching was dropped because Ollama does not expose activations; replaced with leave-one-out ablation.
8. **Guardrails belong in code, not docs (D. & D. Amodei):** Policy not enforced by code is not policy.
   - *Caught:* `SALEHA_APPROVAL=dangerous` claimed to gate file writes in docstrings, but had zero code implementation.

---

## 5. Complete Subsystem Topology & Directory Structure

```text
saleha-0.1/
├── saleha/                         # Core Python Engine
│   ├── core/                       # ~220 specialized domain & algorithmic modules
│   │   ├── bm25.py                 # Real BM25 lexical search
│   │   ├── math_logic.py           # Complexity scoring engine (0.0 to 10.0)
│   │   ├── formal_smt_verifier.py  # Z3-based SMT contract verification
│   │   ├── dynamic_lora_router.py  # Dynamic LoRA adapter routing
│   │   ├── memory_store.py         # Semantic memory & embedding cache
│   │   └── incremental_ast_cache.py# AST caching and change impact
│   ├── agents/                     # Specialized Agent Implementations
│   │   ├── base_agent.py           # Core agent lifecycle & Ollama driver
│   │   ├── planner.py              # Task breakdown & step sequencing
│   │   └── active_inference_gate.py# Goal clarity verification gate
│   ├── sandbox/                    # Secure Subprocess Execution
│   │   ├── sandbox_jail.py         # Cross-platform sandbox runner (Windows safe)
│   │   ├── ast_security_verifier.py# AST static security auditor
│   │   └── v5_production_core.py   # Production runtime kernel
│   └── tests/                      # ~1661 Unit & Integration Tests
├── packages/                       # TypeScript Monorepo (pnpm + Turbo)
│   ├── core/                       # Shared TypeScript interfaces & models
│   └── [8 packages total]          # Must pass 'npx turbo run typecheck' 8/8
├── docs/                           # Architectural Truth & Catalogs
│   ├── AGENT_PROFILES.md           # 20 Specialized Persona Definitions
│   └── ARCHITECTURE.md             # Subsystem integrity & honest command ledger
├── NOTEBOOK_IMPORT.md              # The Audit Ledger (Passes 1-29+, all findings & numbers)
├── COORDINATION.md                 # Parallel Agent Coordination Hub (Claude + Gemini)
└── CLAUDE.md / AGENTS.md           # Session Operating Handbooks
```

---

## 6. Physical Environment & Runtime Invariants

- **Operating System:** Windows 10/11. All paths must be normalized using `pathlib.Path`. Strictly no POSIX-only modules (`import resource`, `fcntl`).
- **Python Virtual Environments:**
  - `.\.venv\` (Python 3.14 / >=3.12): **Default development environment.** All daily coding, auditing, and testing MUST run here.
  - `.\.venv_train\` (Python 3.11): Reserved strictly for offline torch/PEFT training scripts. Never run everyday tests here.
- **Local Ollama Networking & Constraints:**
  - Installed models: `qwen2.5-coder:3b` (primary fast coder), `qwen3:8b`, `qwen3.5:9b`, `deepseek-coder:6.7b`, `deepseek-r1:7b`.
  - Host binding: `OLLAMA_HOST` binds to `0.0.0.0:11434`. Always normalize to `http://127.0.0.1:11434` before making urllib/HTTP requests.
  - Context & Prompt limits: 3B/8B models have strict context bounds (~2048-4096 tokens). Never feed raw massive multi-file dumps into a single prompt.
  - Anti-Premature Finish: In multi-step agent loops, enforce `min_actions_before_finish >= 1`.
- **Console Encoding:** Windows consoles default to cp1252. Always invoke test commands with `PYTHONIOENCODING=utf-8`.

---

## 7. The 4-Phase Engineering State Machine

When addressing any bug, audit request, or feature implementation, agents MUST execute in this exact sequence:

```text
[Phase 1: Deep Read] ──► [Phase 2: Red Reproduction] ──► [Phase 3: Surgical Patch] ──► [Phase 4: Green Verification]
```

1. **Phase 1: Deep Read (No Grep-and-Guess):**
   - Read the entire file from start to finish using file viewing tools. Grep finds one line and blinds you to surrounding bugs.
   - Check `NOTEBOOK_IMPORT.md` and `ARCHITECTURE.md` to see if the component has existing audit notes.
2. **Phase 2: Red Reproduction (Physical Proof):**
   - Create a minimal reproduction script or identify the exact failing test.
   - Prove the defect exists with a real terminal run and measurement.
3. **Phase 3: Surgical Patch (Minimal Blast Radius):**
   - Apply minimal, AST-safe diffs.
   - Never touch lines or functions unrelated to the defect.
   - Check if an existing test is "pinning the bug" (asserting fake output); replace the fake assertion with real validation.
4. **Phase 4: Green Verification & Zero Diagnostics:**
   - Execute the subsystem test suite with `PYTHONIOENCODING=utf-8`.
   - Ensure zero new warnings or editor diagnostics.
   - Measure and document the before/after numbers in `NOTEBOOK_IMPORT.md`.

---

## 8. Subsystem Verification Matrix

Every change must be validated against its corresponding verification command:

| Subsystem | Verification Command | Requirement |
| --- | --- | --- |
| **Python Core Suite** | `python -m pytest saleha/tests/ -q` | `PYTHONIOENCODING=utf-8` |
| **Surgical Test Run** | `python -m pytest saleha/tests/test_<name>.py -v` | Fast feedback on specific module |
| **SMT Formal Logic** | `python -m pytest saleha/tests/test_formal*.py` | Requires `z3-solver` |
| **TypeScript Monorepo** | `npx turbo run typecheck` | 8/8 successful packages, zero type errors |
| **Code Complexity** | `radon cc saleha/core/<module>.py -s` | Must not introduce cyclomatic spikes |
| **Code Linter** | `python -m ruff check saleha/` | Zero syntax or style regressions |

---

## 9. Multi-Agent Coordination Protocol (Sonnet + Gemini + Saleha)

1. **Check `COORDINATION.md` First:** Before starting any work, check current active rounds and branch locks.
2. **No Concurrent File Modification:** Never edit a file currently assigned to or actively being modified by another agent or worktree.
3. **Result Handoff:** Report final, measured numbers and exact diffs into `COORDINATION.md` upon completing work.

---

## 10. Communication & Token Guidelines

- **Language:** The user speaks Hindi / Hinglish. Always reply in Hindi / Hinglish.
- **Simplicity ("Aasan Shabdon Mein"):** Lead with the direct answer. Avoid marketing fluff, robotic apologies, or defensive rationalizations.
- **Decision Making:** When told "tum chuno" or "tum batao kya karna chahiye", take the technical decision based on engineering first principles. Do not bounce the question back.
- **Token Conservation:** Reduce tokens by 80%. Never spawn unnecessary subagents, avoid redundant re-summaries of files the user already has open, and keep responses dense with actionable engineering facts.
