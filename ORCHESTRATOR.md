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

---

## 8. Full Repository File Index

`CLAUDE.md` names five files as the record of project state (`NOTEBOOK_IMPORT.md`,
`ARCHITECTURE.md`, `COORDINATION.md`, `README.md`, `ROADMAP.md`) plus this file.
Everything below exists in the repo but was not named in `CLAUDE.md`. None of
these have been through the audit process described in `CLAUDE.md` — treat
every claim inside them as unverified until it is read in full and probed,
same rule as everything else.

### 8.1 Root-level docs not yet in the audit trail

| File | Apparent purpose |
| --- | --- |
| `AGENTS.md` | Agent roster / contract, root level (relationship to `docs/AGENT_PROFILES.md` and `saleha/skills/agent_*.md` below not yet reconciled). |
| `AGENTSKILLS.md` | Skill-system description (relationship to `saleha/skills/` and `.agents/skills/` not yet reconciled). |
| `CHANGELOG.md` | Release/change history. |
| `CODE_OF_CONDUCT.md` | Standard community doc. |
| `CONTRIBUTING.md` | Contributor guide. |
| `DEVELOPMENT.md` | Dev setup instructions — may overlap with "Environment facts" in `CLAUDE.md`; check for drift. |
| `EVALS.md` | Evaluation/benchmark methodology — check against the fabricated-benchmark history (pass 20) before trusting any number in it. |
| `GEMINI.md` | Instructions for the Gemini agent that runs alongside Claude Code per `COORDINATION.md`. |
| `PRODUCT_BRIEF.md` | Product framing/pitch doc. |
| `SECURITY.md` | Security policy/disclosure doc. |
| `SOUL.md` | Root "soul" doc — relationship to `souls/` (below) not yet reconciled. |
| `.saleharules` | Rules file, unclear consumer — grep for a reader before trusting it's live config vs. dead file. |
| `mcp_config.json` | MCP server config. |
| `Modelfile` | Ollama model definition — check which model it builds and whether it's still referenced anywhere (`saleha-asi` was deleted per `CLAUDE.md`; confirm this isn't a stale leftover). |

### 8.2 `docs/` — a second, older, partly-generated, partly-foreign doc tree (resolved)

Compared both duplicate pairs directly instead of guessing:

- **`ARCHITECTURE.md` (root) is authoritative; `docs/ARCHITECTURE.md` is
  not.** Root version: 199 lines, last touched 2026-09-11, hand-written,
  matches the actual repo layout and separates real vs. roadmap items.
  `docs/ARCHITECTURE.md`: 82 lines, 2026-09-02, self-labeled "Autonomously
  generated by Saleha AI v2.6.0 DocGeneratorAgent," carries suspicious
  round/inflated metrics (459 modules, 834 classes, 2185 functions) and
  generic mermaid diagrams — a stale auto-generated artifact from an
  earlier version of the project, not a source of truth. Treat it as
  historical, not current.
- **`docs/threat_model.md` is the only remaining threat-model doc; its
  sibling was foreign and is gone (pass 44).**
  `docs/manifestos/threat_model.md` (47 lines, "v1.0.0") was titled for the
  "Nexus-Universe + MUKTI ecosystem" — the same foreign project confirmed
  contaminating `deploy/` (8.5) — and described NATS/gRPC/DID/mTLS
  agent-to-agent auth that had nothing to do with Saleha's local
  single-user CLI. Deleted alongside `deploy/`, see 8.5 for the
  verification done before deletion. `docs/threat_model.md` (12 lines,
  2026-09-01) remains — a terse auto-generated STRIDE table, thin but at
  least on-topic; not independently verified as current this pass.
- Not yet independently diffed this pass: `docs/AGENT_PROFILES.md`,
  `docs/CLI_REFERENCE.md`, `docs/MCP_SPEC.md`, `docs/SECURITY_MODEL.md`,
  `docs/TUTORIALS.md`, `docs/manifestos/agentskills.md`,
  `docs/manifestos/harness.md`, `docs/manifestos/soul.md`.
  `docs/manifestos/soul.md` in particular is worth checking for the same
  Mukti/Nexus contamination found in its `threat_model.md` sibling before
  trusting it as a Saleha doc.
- `docs/architecture-code-review-2026-09-03.md`,
  `docs/notes/orchestrator-audit-2026-09-07.md` — prior review/audit notes;
  cross-check against `NOTEBOOK_IMPORT.md` for findings already fixed.
- `docs/notes/` — non-code research notes (`architecture_vision.txt`,
  `hyperbolic_geometry.txt`, `mukti_agents_sdk_impl.txt` — note the "mukti"
  name again, `mukti_sovereign_summary.txt`) and a small standalone
  Flask-style app (`docs/notes/model-lab/` — `trust_kernel.py`,
  `prooftsilicon_trust.py`, templates), not referenced anywhere else found
  so far. Given two of the four filenames here contain "mukti," check this
  whole subfolder for the same foreign-project contamination before
  assuming it's Saleha's own research.
- `docs/*.html` (`architecture_graph.html`, `docs.html`, `index.html`,
  `leaderboard.html`) and `docs/site/index.html` — generated/static pages;
  confirm what generates them and whether they're current.

### 8.2b `packages/`, `apps/web`, `apps/desktop`, `contracts/` — read in full, real and wired

Unlike most of section 8, these were traced end to end, not just listed.

- **`packages/`** is a genuine, cross-linked TypeScript monorepo (pnpm +
  Turborepo). `pnpm-workspace.yaml` and root `package.json` both declare
  `packages/*`/`apps/*`; `apps/web/package.json` and `apps/desktop/package.json`
  both depend on `@saleha/core` and `@saleha/ui` for real (not aspirational —
  actual imports resolve). `packages/api` (tRPC) and `packages/db` (Prisma)
  exist but have no incoming imports found from `apps/*` yet — scaffolded,
  not wired.
- **`contracts/`** is partially real: `saleha/core/mukti_chain_bridge.py`
  genuinely bridges Python to `contracts/M2MEscrow.sol` via `web3.py`, with
  a mirrored ABI at `saleha/server/web3_contracts/M2MEscrow.abi.json` and
  live endpoints in `web_server.py`. That module's own docstring documents
  the exact failure mode this project keeps finding elsewhere: the
  "hallucination insurance" feature used to be pure in-memory bookkeeping
  with **no connection at all** to the contract it claimed to use, and this
  bridge was written to make that real, raising `ChainUnavailableError`
  instead of a fabricated success. The rest of `contracts/` (bridge/, DAO,
  staking, agent-marketplace CosmWasm contracts) has no reference from
  `saleha/` found — likely unused/aspirational extensions of the same
  Web3 feature, not yet load-bearing.
- **`rust/`** is mostly self-admitted scaffolding, not a hidden feature.
  `rust/Cargo.toml`'s own comments say `meridian-core`, `nexus-l1`,
  `nexus-executor`, etc. "have no Cargo.toml yet" and need manifests before
  they can even be enabled as workspace members — only `intent-kernel` is
  currently a real, buildable crate (a `clap`-based CLI implementing intent
  parsing / plan compilation / proof-logging, conceptually parallel to
  Saleha's own agent execution model but a separate Rust reimplementation,
  not called from Python). `nexus-executor/src/main.rs` literally contains
  a block labeled `MOCKED INTERNAL CRATE INTERFACES (Replace with actual
  crate imports in monorepo)` — this is not a fabrication in the
  `CLAUDE.md` sense (nothing claims it works), just unfinished and honestly
  marked as such in the code itself.

### 8.3 `saleha/` subpackages not named in `CLAUDE.md`

`CLAUDE.md` discusses individual modules (`orchestrator.py`, `base_agent.py`,
`quality_guard.py`, etc.) but never names these package directories as such:

- `saleha/agents/` (30 files) — persona/agent implementations.
- `saleha/cli/` (46 files) — the 100+ subcommand CLI; only a handful of
  individual commands have been triage-confirmed per-file in `CLAUDE.md`.
- `saleha/core/` (249 files) — the bulk of the project. `CLAUDE.md`'s audit
  has touched a few dozen of these by name across 43 passes; the rest are
  unaudited by default, not confirmed clean.
- `saleha/server/` (6 files) — REST/SSE web server, fixed pass 43.
- `saleha/tests/` (250 files) — test suite; `conftest.py` is named in
  `CLAUDE.md`, the other 249 files are not enumerated.
- `saleha/tools/` — generated/generatable tools (`forge-tool` output lands
  here, e.g. `word_counter` from pass 37).
- `saleha/sandbox/` — `sandbox_jail.py` named in `CLAUDE.md`; siblings not
  enumerated.
- `saleha/harness/` — `saleha harness leaderboard` / `reporter.py` named in
  passing (pass 30); rest of the directory not enumerated.
- `saleha/ci/` (`bot.py`) — CI bot, not mentioned anywhere in `CLAUDE.md`.
  Unclear what triggers it or what it posts — read before trusting output.
- `saleha/desktop/` — Python-side desktop integration (distinct from
  `apps/desktop/`, the Tauri/React app fixed in pass 42).
- `saleha/experimental/` (`aionx/` and `jarvis/`) — **read in full; four
  fabricated files deleted (pass 44).** Confirmed unimported anywhere
  outside their own directories before deletion. Three of the four
  `jarvis/` files read were exactly the fabrication pattern `CLAUDE.md`
  warns about — confident "self-awareness"/"JEPA"/"AGI Component 3" claims
  backed by hardcoded strings, dict lookups, and keyword regex, zero model
  calls — and a fourth was not even valid, importable code (a usage sketch
  referencing a `JarvisBackendWorker` class that exists nowhere in the
  repo). Deleted: `self_awareness_engine.py`, `jarvis_world_model.py`,
  `general_reasoning_engine.py`, `jarvis_unified_v11.0.py`. Full detail and
  evidence: `NOTEBOOK_IMPORT.md`, "Forty-fourth pass."
  `aionx/extensions_v10.py` was the exception found in the same read — it
  makes genuine `anthropic.Anthropic().messages.create()` calls with real
  retry/backoff and real token/cost accounting, plus a real GitHub API fetch
  and legitimate AST-based static checks in `formal_verify_python`. Left
  in place: orphaned/unwired, but not fabricated. `jarvis_common_sense.py`,
  `jarvis_novel_reasoning.py`, `jarvis_transfer_learning.py`, and the
  audio/C++ files in the same `jarvis/` directory were **not** read this
  pass and are not covered by this finding either way — still open.
- `saleha/specs/` — `saleha/specs/agent_specs/*.md` (spec docs paired with
  `saleha/skills/agent_*.md` below) and `saleha/specs/v5_files/`.
- `saleha/skills/` — `agent_*.md` (persona prompts, 20+ files) and
  `doc_*.md` / `orchestrator_hardware.md` / `orchestrator_software.md`
  (referenced by name in section 1 of this file, but individually unaudited).
- `saleha/STRUCTURE.md` — a repo-structure doc living inside `saleha/`
  itself, separate from this index.

### 8.4 `souls/` vs `saleha/skills/agent_*.md` — both real, different jobs (resolved)

Traced both to their loaders — **neither is dead, and they do not compete**:

- **`souls/`** (9 personas × `{IDENTITY,SOUL,STYLE}.md` plus a flat
  `<name>.soul.md`, 52 files total: alchemist, architect, artisan, auditor,
  minimalist, sage, sentinel, sovereign, speedrunner, sre) is loaded by
  `saleha/core/soul_engine.py` (scans `souls/<name>/`, loads and validates
  `SOUL.md`/`IDENTITY.md`/`soul.json`), exposed via `saleha/cli/soul_cli.py`
  (`saleha soul use`) and `POST /api/souls/use`, and covered by
  `test_soul_engine.py`/`test_web_server.py`. This governs system-prompt
  *flavor* and sampling parameters — matches what root `SOUL.md` (section IV)
  claims of it.
- **`saleha/skills/agent_*.md`** is loaded separately by
  `saleha/core/agent_profile_loader.py` (parses YAML frontmatter + body),
  consumed by `dag_engine.py`, `deliberation_engine.py`, and `repl.py`
  (default `initial_profile="agent_sde"`). This governs *task/role* selection
  — which domain specialist handles a DAG node — not prompt styling.

Root `SOUL.md` documents only the souls/ system and never mentions
`agent_*.md`, which is incomplete but not a false claim (it doesn't say
souls/ is the only such system). No fix needed; document the distinction in
`ARCHITECTURE.md` next time that file is touched, so a future reader doesn't
re-open this question from scratch.

### 8.5 Non-Saleha trees under the same repo — `deploy/` confirmed foreign

- **`deploy/` — confirmed NOT Saleha, deleted (pass 44).** `grep -ri "saleha"
  deploy/` returned **zero hits**. The names that actually appeared
  throughout were **mukti** (`mukti-api`, `mukti-backend`,
  `ghcr.io/mukti-foundation/*`, Terraform `Project = "mukti"`), plus
  **nexus-omni**/**nexus-protocol**, **genesis-api**, and blockchain-flavored
  oddities (`agentstack/crypto-engine`, a `dark-testnet/` folder with
  `nexus-l1/validator` statefulsets) — infra for a hosted, multi-region,
  blockchain-adjacent product, structurally foreign to "local-first, runs
  against local models via Ollama." Before deleting: confirmed no CI/build
  config referenced the path, no vendoring markers existed, and the
  introducing commit (`8c6c607`, a 564-file bulk "accumulated unsaved work"
  commit) named it only in a passing catch-all, unlike `contracts/`, which
  that same commit named as intentional. Deleted along with
  `docs/manifestos/threat_model.md` and two `docs/notes/mukti_*.txt` files
  (same contamination — see 8.2). Full evidence: `NOTEBOOK_IMPORT.md`,
  "Forty-fourth pass."
- `contracts/` and `rust/` are **not** in this foreign category — see the
  new 8.2b above, both were traced and at least partially belong to Saleha.
- `packages/` — see 8.2b, confirmed real and cross-linked to `apps/web` /
  `apps/desktop`.
- `apps/landing/`, `apps/web/` — Astro landing page and Next.js app;
  `apps/web` confirmed wired to `packages/` (8.2b), `apps/landing` not
  independently checked this pass.
- `generative-art/` — `quorum-bloom-philosophy.md`, a single essay-style
  file, not checked this pass for Mukti/Nexus contamination — worth a quick
  grep before assuming it's Saleha's.
- `datasets/` — **fabrication confirmed, same pattern as the deleted
  `saleha-asi` fine-tune, partially already fixed.**
  `datasets/synthesize_sovereign_ultra_dataset.py` carries its own
  docstring admission (written by an earlier cleanup pass): three of its
  generator functions held only 10/10/3 real distinct (prompt, completion)
  pairs each, then faked volume by appending `[Batch #N]`/`[Dialogue #N]`/
  `[Instance #N]` counters to the prompt while reusing the same completion
  — a measured 47-135x duplication factor, so a claimed 1600-row dataset
  was actually 23 unique pairs. The real output file
  (`datasets/saleha_sovereign_train.json`) has since been deduplicated
  (2600 rows -> 31/23+8/7), with the fabricated pre-cleanup version
  preserved at `datasets/_pre_cleanup_backup_20260906/` and the
  counter-cloning functions left in the script with a comment warning not
  to re-run them that way. **Currently consumed in production training:**
  `saleha_dpo_pairs.jsonl` and `saleha_sft_10k*.json(l)`, wired into
  `saleha/core/frontier_trainer.py`, `saleha/core/lora_tuner.py`,
  `saleha/core/dpo_dataset_engine.py`, with real tests
  (`test_dpo_dataset_engine.py`, `test_frontier_trainer.py`) — these files
  were not flagged as still-fabricated this pass, only the sovereign/omni
  lineage. **Orphaned, not consumed by `saleha/core` or `saleha/cli`:**
  `saleha_sovereign_train.json`, `saleha_omni_*`, `saleha_asi_math_reasoning_*`,
  `saleha_dsa_*` and their `synthesize_*.py` generators — referenced only by
  sibling `scripts/train_*_gpu.py` files, not the live product.

### 8.6 Smaller top-level items, unaudited

- `.agents/rules/agents.md`, `.agents/skills/self-improve-engine/` (with
  `run_self_improve.py`) — a "self-improve" script matching the user's
  stated self-building vision (`CLAUDE.md`, "The user's vision for Saleha")
  but not yet connected to that section or audited for whether it fabricates
  results like earlier "orchestrator" components did.
- `.cursor/rules/agents.mdc` — Cursor-IDE-specific rules; check for drift
  against `CLAUDE.md`/`AGENTS.md`.
- `editors/vscode/` — a VS Code extension (`build_extension.py`,
  `extension.ts`) not mentioned anywhere in `CLAUDE.md`.
- `examples/` — `01_rate_limiter`, `02_fastapi_crud`, `03_mcp_custom_tool`,
  `live_dogfood_demo`, `plugins`, `run_dogfood_demo.py`. `demo_cli.py`'s
  `dogfood_cmd` is named in `CLAUDE.md` (pass 30) as having fabricated a
  9-pillar pass; confirm whether `run_dogfood_demo.py` here is the same
  code path or a separate one before assuming pass 30's fix covers it.
- `templates/` — `python_fastapi`, `nodejs_express`, `go_service`, all
  fixed and wired to `saleha new` per `CLAUDE.md` pass 34.
- **`tools/code_quality_auditor.py` — fixed.** 72-line standalone script:
  globs `saleha/**/*.py`, parses with `ast`, checks for `os.system(` calls
  and regex-matched hardcoded secrets — that part was always real. It also
  **hardcoded `"test_coverage_pass_rate": 100.0` and unconditionally
  printed `870/870 Tests Passed`, without ever running a test** — the exact
  "fake green" pattern `CLAUDE.md`'s opening section names as the worst
  kind of bug. Not called anywhere in the repo, so nothing in production
  was affected, but it sat ready to be trusted by a future reader. Fixed:
  now runs a real `pytest saleha/tests/` subprocess with an honest
  `ran: False` path when pytest is unavailable; the fabricated key is gone.
  Verified end-to-end: real result `1859 passed, 8 skipped, 60 subtests` in
  102.73s. Distinct from `saleha/core/quality_guard.py` (the real,
  actively-used AST checker fixed in passes 32/38) — no overlap. Detail:
  `NOTEBOOK_IMPORT.md`, "Forty-fourth pass."
- `scripts/` (44 files) — read in full this pass, not enumerated in
  `CLAUDE.md` before now:
  - **Real, working build/release/CI tooling:** `build_distribution.py`,
    `build_release.py`, `build_standalone.py`, `build_desktop_sidecar.py`,
    `package_desktop_app.py`, `package_vscode_extension.py`,
    `ci_test_runner.py`, `gen_cli_docs.py`, `run_pr_review.py`,
    `convert_hf_to_gguf_standalone.py`, `merge_lora.py`,
    `resume_training.py`, `benchmark_ollama_speed.py`.
  - **Real training pipelines** (genuine PyTorch/PEFT/QLoRA calls against
    Qwen2.5-Coder at various sizes): `train_1.5b_pro_gpu.py`,
    `train_3b_gpu.py`, `train_7b_qlora_gpu.py`, `train_full_real_gpu_model.py`,
    `train_real_qwen_lora.py`, `train_saleha_targeted.py`,
    `chat_with_real_lora.py`, `generate_with_real_lora.py`, and several
    more `train_*_gpu.py` variants. Docstrings are marketing-heavy
    ("Frontier," "Sovereign Ultra") but the code genuinely calls
    `transformers`/`peft` — not fabricated, just oversold in naming.
  - **Post-mortem scripts that document their own past fabrication and its
    fix:** `evaluate_artificial_analysis_omni_arena.py`,
    `train_apex_97_frontier.py`, `verify_all_live_proofs.py`,
    `measure_real_pass_rate.py` — each currently carries a docstring
    explaining a prior version printed hardcoded fake leaderboard rankings
    or "100% success" banners with zero real execution, matching the
    `omni_arena_engine.py` / `verify_all_live_proofs.py` fixes already in
    `NOTEBOOK_IMPORT.md` pass 20. These look already fixed, but were not
    independently re-verified this pass.
  - **Dataset generation:** `consolidate_master_dataset.py`,
    `generate_10k_frontier_dataset.py`, `generate_massive_dataset.py` (its
    own docstring documents `synthesize_variation` being disabled after
    producing 493 fake stub samples that regressed the model — a fourth
    instance of the same fabricated-data pattern found in `datasets/`, 8.5).
  - **Not yet verified this pass, same emoji-heavy style as scripts already
    caught fabricating:** `evaluate_artificial_analysis_suite.py`,
    `evaluate_real_trained_model.py`, `train_grpo_advanced_reasoning.py`,
    `train_saleha_frontier_model.py`, `train_swarm_self_play_arena.py` —
    claim elaborate multi-phase/GRPO/self-play pipelines; bodies not read
    closely enough to confirm real training vs. scripted progress output.
    Next candidates for a real audit pass.
- **`editors/vscode/` — read in full, functional, not a stub.**
  `extension.ts` registers real commands (`saleha.fix`, `.reviewAI`,
  `.diffPreview`, `.memoryProject`, `.watchAI`, `.search`, `.hud`, `.tune`)
  that shell out to the real `saleha` CLI, plus an inline-completion
  provider doing a genuine HTTP POST to a local Ollama server with a FIM
  prompt. `build_extension.py` validates `package.json` and produces a real
  `.vsix`. No fabrication found.
- `configs/lora_training_config.yaml` — read in full: a real hyperparameter
  config (Qwen2.5-Coder-1.5B, LoRA r=16/alpha=32, 4-bit NF4). It is a
  **generated, write-only artifact** — `saleha tune --export`
  (`chat_session.py` -> `ModelDistillationPipeline.generate_lora_training_yaml()`)
  writes this exact file; nothing reads it back in. Not hand-authored
  config, not a fabrication, just worth knowing it's output not input.

### 8.7 What's actually confirmed vs. still just an inventory entry

A first pass (four parallel reads) upgraded several 8.x entries from
"unread guess" to "read in full, evidence attached": 8.2 (`docs/`
duplicates), 8.2b (`packages/`/`contracts/`/`rust/`), 8.3's
`saleha/experimental/` entry, 8.4 (`souls/` vs `agent_*.md`), 8.5's
`deploy/` and `datasets/` entries, and the `scripts/`/`tools/`/`editors/`/
`configs/` block above. Everything else in section 8 (the rest of 8.1,
most of `saleha/core/`'s 249 files, `saleha/tests/`'s 250 files, `docs/`
files not explicitly diffed above, `generative-art/`, `apps/landing/`) is
still just an inventory entry — named, not read. Before relying on anything
still in that state:

1. Read the whole file (`CLAUDE.md`'s audit rule #1 — no `grep`-and-conclude).
2. If it's a doc, check it against git history and the other docs it
   duplicates or overlaps (section 8.2, 8.4) — and check it for
   Mukti/Nexus-Omni contamination the way `deploy/` and
   `docs/manifestos/threat_model.md` turned out to have (8.5, 8.2).
3. If it's code, probe it the way every `NOTEBOOK_IMPORT.md` pass does:
   call it, vary the input, show the output actually varies.
4. Once audited, move its entry out of section 8 and into the appropriate
   place in `CLAUDE.md` ("Known open work") or `NOTEBOOK_IMPORT.md`.

**Three findings from this pass are fixed, not just flagged (pass 44):**
`tools/code_quality_auditor.py`'s hardcoded "870/870 Tests Passed" now
runs a real pytest subprocess; the fabricated `saleha/experimental/jarvis/`
quartet (`self_awareness_engine.py`, `jarvis_world_model.py`,
`general_reasoning_engine.py`, `jarvis_unified_v11.0.py`) is deleted; and
`deploy/` plus the three Mukti-branded docs are deleted after confirming
(git history, grep for any real wiring, CI/build config check) they belong
to a different, unrelated project that landed in this repo via one bulk
commit. Full evidence for all three: `NOTEBOOK_IMPORT.md`, "Forty-fourth
pass." Full suite re-verified unchanged after all three fixes: 1859
passed, 8 skipped.
