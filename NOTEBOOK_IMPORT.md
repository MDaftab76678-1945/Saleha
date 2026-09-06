# Notebook → saleha-0.1 import

Pulled the useful, not-yet-integrated code out of `Notebook/` into the repo.
`Notebook/` itself is untouched (gitignored research vault).

## Added

| Landed at | From | Lines | What it is |
| --- | --- | --- | --- |
| `rust/intent-kernel/` | `Notebook/intent-kernel/` | ~4,500 | **Rust agentic core.** intent → plan compiler → capability registry → executor (snapshot/rollback) → hash-chained proof ledger → Ollama LLM client → reflexion/negotiation. Working; ships runtime state in `.ik/`. This is the Rust performance layer saleha's Python side never had. See `docs/v0.3-technical-spec.md`. |
| `rust/meridian-core/` | `Notebook/meridian-core/` | ~2,700 | Rust agent framework — agent runtime, swarm (`swam.rs` 696 ln), LLM bindings, MCP client. Half-built: `swam.rs`, `client.rs`, `bindings.rs` are real; `memory/*`, `workflow/*`, several `llm/*` are empty stubs. |
| `rust/fragments/` | loose `.rs` in Notebook root | ~900 | `runtime.rs` (lock-free ring buffer / IPC), `server.rs`, `sync.rs`, `swarm_demo.rs`. Unattached snippets — mine for the IPC / hot-path patterns. |
| `saleha/sandbox/` | `Notebook/v5_production_system_with_33_specs/02_v5_engine/` | ~420 | `sandbox_jail.py` (POSIX process jail, 128MB cap, anti-fork-bomb), `ast_security_verifier.py` (AST auditor, banned imports), `local_llm_driver.py` (Ollama/vLLM + JSON mode), `v5_production_core.py` (evaluator-optimizer self-heal loop + SQLite). **Real sandbox** — `saleha/core/` only has sandbox theater. |
| `saleha/specs/agent_specs/` | v5 `01_agent_specs/` | 34 files | Agent role definitions (YAML frontmatter): ai_engineer, cloud_architect, firmware_engineer, ml_engineer, qa_engineer, sre, security_engineer, … Reference for `saleha/agents/`. |
| `saleha/experimental/aionx/extensions_v10.py` | `Notebook/aionx-v10-backend_1/` | ~800 | Claude-API agent extensions: self-consistency voting, Critic-A/B/Judge debate, multi-lang codegen, GitHub PR gen, cron missions, plugin system, WS token streaming, cost routing. Uses `anthropic` SDK (cloud, not local). |
| `saleha/server/dashboard_reference.jsx` | `Notebook/saleha_dashboard.jsx` | ~460 | React dashboard — reference for `saleha/server/web_server.py`'s UI. |
| `docs/notes/hyperbolic_geometry.txt` | `Notebook/geometry.txt` | ~600 | Hyperbolic / Poincaré math notes — background for `saleha/core/hyperbolic_engine.py`. |
| `docs/notes/mhd_engine_reference.cpp` | Notebook root | ~350 | C++ magnetohydrodynamics solver (Dedner GLM). Out of scope for the coding agent — parked. |
| `docs/notes/*.txt` | `Architecture Vision.txt`, `MUKTI Sovereign AI Summary.txt`, `Mukti Agents SDK Implementation.txt` | — | Design notes / ASCII architecture diagrams. Reference only. |
| `saleha/specs/project_zip_generator.py`, `saleha/specs/README.md` | v5 root | — | v5 skeleton generator + its README. |

## NOT copied (deliberately)

- `Notebook/**/target/`, `*.exe`, `*.pdb`, `*.rlib`, `*.rmeta` — Rust build artifacts (`cargo build` regenerates).
- The 40 PDF decks + 24 chat exports — these are the *source* of the vision; already distilled into `saleha/core/`. Stay in `Notebook/`.
- `v5_production_system/files.zip`, `LM Studio vs Ollama.docx` — archives/notes.

## Second pass — from `nexus-universe/` (the re-assembled chat-export code)

`nexus-universe/` was built by pattern-matching every code block out of the same
chat exports. Most of it duplicates the already-cleaned `saleha/core/` — that was
**skipped**. Only the genuinely-new, not-in-saleha-0.1 areas were pulled:

| Landed at | From | Files | What it is |
| --- | --- | --- | --- |
| `contracts/` | `nexus-universe/contracts/` | 37 | **On-chain economy layer** — Solidity (Bridge, AgentReputation, EscrowMarketplace, CompoundStaking, VAATracker) + CosmWasm Rust (mukti-dao, mkt-token, mkt-bridge, fee-abstraction). saleha-0.1 had zero chain code. |
| `rust/crates/` | `agentstack/crates/` + `crates/` | 90 | **Sovereign / L1 / crypto Rust crates** — zkml_prover, fhe_machine, verkle_tree, pqc_identity, tee_core/enclave_runtime, snn_core, agent-consensus (pbft/hotstuff/bls_threshold), nexus-safety (constitutional_drift, memory_interp_probe), nexus-core dispatch, secure-node. |
| `rust/nexus-l1/` `rust/nexus-l1-core/` `rust/nexus_core/` | same | 13 | L1 chain node — blockchain, consensus (povc), state, api. |
| `rust/nexus-zkvm/` `rust/zkvm-guest/` `rust/nexus-executor/` | same | 5 | zkVM host/guest + executor. |
| `rust/cpp-native/` | `agentstack/cpp/` + `cpp/` | 22 | C++ — pbft.cpp, federated_learning.cpp, gnn/emergence_detector, snn_engine, lockfree_ring_buffer, arena_allocator, ebpf_agent. |
| `rust/specs-tla/` | `misc-title/tla/` | 5 | **TLA+ formal specs** — NexusAgenticV7, HotStuffExtension, HardwareAsync (+ .cfg). |
| `saleha/experimental/jarvis/` | `nexus-universe/jarvis/` | 16 | **Voice / perception arm skeleton** — whisper STT, duplex audio, speculative decoder, paged KV cache, world model, self-awareness, common-sense engines. |
| `docs/manifestos/` | `agent_manifestos/` | 4 | `soul.md`, `harness.md`, `threat_model.md`, `agentskills.md` — agent identity/philosophy. |
| `docs/notes/model-lab/` | `nexus-universe/model-lab/` | 7 | `trust_kernel.py`, `prooftsilicon_trust.py` + HTMX dashboard templates. |
| `deploy/k8s/` | `nexus-universe/k8s/` | 96 | argo, argocd, rollout, chaos, multi-region, slo, velero, monitoring manifests. |
| `deploy/infra/` | `nexus-universe/infra/` | 48 | terraform (modules), ansible (roles), k8s, protos. |
| `deploy/monitoring/` `deploy/ci-workflows-ref/` | same | 21 | grafana dashboards, prometheus; 17 GitHub Actions workflows (reference). |

**Skipped from `nexus-universe/`** (deliberately, per "jo pehle se hai vo nhi"):

- `mukti/` `saleha/` `nexus-omni/` `nexus-agentic/` `nexus-advanced/` Python — ~1,000 pattern-matched .py files that duplicate the clean `saleha/core/` (205 modules) the user already built.
- `apps/` `packages/` `scripts/` `tests/` `docs/` — saleha-0.1 has real ones.
- `_loose/` (2,193) `_extracted/` (6,544) `misc-*/` — raw dump / fragments. Kept in `nexus-universe/` as an archive; delete when confident.

`nexus-universe/` can now be treated as a disposable staging repo.

## Loose ends to fix

- `rust/intent-kernel/cargo.toml` → rename to `Cargo.toml` (Rust is case-sensitive here).
- `rust/meridian-core/src/memory/mod.rs.rs` → `mod.rs` (double extension).
- `rust/meridian-core/` has empty stub files — fill or delete before `cargo build`.
- `saleha/specs/agent_specs/ai_engineer - Copy.md` → dedupe.
- `rust/` has no workspace `Cargo.toml` tying the two crates together — add one if you want a single `cargo build`.

## Third pass — ideas, not code (2026-09-07)

The first two passes pulled **code** out of `Notebook/`. This pass mined the
40 PDFs and 24 chat exports that were skipped as "already distilled" — and
one of them was not.

`chat-Nexus Branding Strategy.txt:850` contains the user's own explicit
"real gold vs trash" split. Item 2 of the keep-list:

> **Active Inference (Free Energy Principle):** अगर यूजर का प्रॉम्प्ट अस्पष्ट
> (vague) है, तो Saleha अंदाजे से गलत कोड नहीं लिखेगी। वह अपनी "अनिश्चितता"
> को मापेगी और **आपसे एक स्मार्ट सवाल पूछेगी**।

That was never built. Verified before building it:

```
PlannerAgent.create_plan("fix it")
  -> success=True, recommendation=EXECUTE, complexity 0.0
  -> steps: ['"main ise pragati karunga."']
```

No file, no repo, no bug named — and the planner reported success and moved
to execution. The planner branched on *complexity* (how big) and never on
*specificity* (how clear); "fix it" is trivially small and completely
unactionable, so complexity scoring could never catch it.

**Landed:** `saleha/core/active_inference.py` + the gate wired into
`PlannerAgent.create_plan()` and surfaced by `SalehaOrchestrator`.

Deliberately **not** implemented as perplexity: a real perplexity score needs
logprobs, which the Ollama `/api/generate` path does not return. Faking a
number and calling it entropy would be the same defect this repo keeps
finding. It measures checkable properties of the goal text instead, and says
so in its own docstring.

### Also from this pass, deliberately rejected

| Idea | Source | Why not |
| --- | --- | --- |
| Artificial Endocrine System (dopamine/cortisol modulating temperature) | `chat-Recursive Problem Solving.txt:880` | Mood theater. Mapping "stress" to `top_p` is a made-up number wearing a biology costume; there is no signal behind it. |
| Ouroboros 7-layer containment (DNA transcoder, NV-diamond quantum seal, hardware zeroize pin) | `chat-Heterogeneous AGI Containment Architecture.txt:321` | Silicon/wetware, not software. Also on the user's own trash-list. |
| Hyperdimensional / holographic memory (10,000-D superposition) | same | Real technique, but `saleha/core/` already has a working vector store; this would be a rewrite with no measured win. |
| Type-state task transitions (`Task<Pending>` → `Task<Verified>`) | same, line 340 | **Already built** — `saleha/core/task_evidence.py` `_ALLOWED_TRANSITIONS` makes CREATED→ACCEPTED structurally impossible. |

The user's own trash-list in that same chat (crypto/tokenomics, zkML, FHE,
algorithmic trading) was respected — nothing from those areas was pulled.

## Fourth pass — the file nobody had opened (2026-09-07)

`Notebook/madad-ke-liye-sawaal.json` (5.3 MB) is not a design document. It is
a **complete transcript of a previous agent session on this exact repo**
(`directory: C:\Users\alama\saleha-0.1`, 752 messages, 701K input tokens,
285 bash / 235 edit / 56 write calls). It was never listed in the passes above.

Its value is the audit it contains, not code to import. Every finding was
re-checked against the repo as it stands today:

| Finding from that session | Status now | How verified |
| --- | --- | --- |
| Web Studio: `Access-Control-Allow-Origin: *` + zero auth → `/api/exec` RCE | **fixed** | `web_server.py` now token-authenticated (`X-Saleha-Token`, `SALEHA_STUDIO_TOKEN`); wildcard CORS is deliberate and documented as safe *because* of the token |
| Fake sandbox: regex blocklist, `__import__("os").system()` bypasses it | **fixed** | now AST-based. Re-ran the exact bypass: `import os`, `__import__("os")`, and `importlib.import_module("os")` are all blocked; benign code still runs |
| Reviewer fail-open (`approved=True` on LLM error) | **fixed** | `reviewer.py` is fail-closed with a comment naming the old behaviour |
| PyYAML imported but undeclared → fresh install crash | **fixed** | declared in `pyproject.toml` |
| `memory_store.py`: four methods defined twice | **fixed** | no duplicate defs remain |
| `voice_assistant.py:52` AttributeError on `res.error_log` | **fixed** | symbol gone |
| 3× HIGH `SEC101` unsafe `eval()` in `vscode-extension/extension.js` | **fixed** | extension moved to `editors/vscode/`; no `eval(`/`new Function(` anywhere in repo JS |
| Memory store O(N) reindex on every mutation | **fixed** | `vector_store.py` uses a `_dirty` flag, reindexing once per search |
| Dead code purge (`studio/`, `web/`, `utils/`) | **fixed** | all three directories gone |

Nothing from that session needs re-doing. Recording it here so the next pass
does not re-audit ground that is already covered — and so the 5.3 MB file is
not mistaken for an unmined design doc.

### Measured while checking: the DAG engine is real, its default graph is not parallel

`saleha/core/dag_engine.py` genuinely implements parallel batch execution
(`get_topological_batches()` + `ThreadPoolExecutor`), and dependency outputs
really are threaded into downstream prompts. Ran it end-to-end:

```
nodes: 5
  batch 0: ['task_prd']
  batch 1: ['task_arch']
  batch 2: ['task_core_impl']
  batch 3: ['task_sec_audit', 'task_qa_tests']
elapsed 123s  completed=5/5 failed=0
```

**Only the last batch has more than one node.** Four of five stages run
alone, so `execute_parallel()` is doing almost nothing parallel on the
default graph. This is *not* a bug: the declared dependencies are honest —
architecture really does need the PRD first. The engine is ready for wide
graphs; `build_default_dag_for_goal()` just does not produce one. Worth
knowing before anyone cites "parallel DAG execution" as a speed feature.

### Rejected from the large chat exports

`chat-Understanding Each Point.txt` (1 MB, densest source of concrete
techniques) recommends **speculative decoding** for a 2-3x speedup. Skipped,
and the same file says why (line 8904): it needs a draft model resident
alongside the target model, and one GPU here cannot hold 8B + 1B without
crashing. The file's own conclusion was to defer it until the project moves
to server hardware. Prefix caching and constrained decoding from the same
source are already in the repo (`PromptCache`, and `response_format` JSON
schemas used by `action_menu.py` and `recursive_solver.py`).

## Fifth pass — the 13 JSON exports (2026-09-07)

Six of the 13 `chat-export-*.json` files have titles with no matching `.txt`,
so they were never distilled. Checked all six:

| Title | Verdict |
| --- | --- |
| Self-Evolving Prompt Optimization (×3) | A prompt **template**, not an implementation. Its "Module 4 – Result Evaluator" asks a model to judge its own output — the exact trust failure this repo keeps finding. The execution-based selection in `parallel_solver.py` is the stronger version of the same idea. |
| SiliconCopilot Benchmark Failure | HACK@DAC RTL/hardware security benchmarking. Out of scope for a coding agent. |
| Local AI Monitoring Solution | Market positioning (vs Datadog / W&B / Prometheus), no implementation. |
| branch·Agent Task Workflow | Branch of an already-distilled chat. |

`AgentEvolutionEngine` (`chat-Agent Task Workflow.txt:16473`) — genetic
algorithm evolving agent prompts and sampling parameters — looked like the
richest find of the pass. The GA machinery is real (tournament/roulette
selection, elitism, crossover, mutation, hall of fame), but the fitness
function is not:

```python
# Random performance factor (simulates actual execution)
score += random.uniform(0.1, 0.5)
```

with the comment *"In production, this would call the actual agent"*. The
evolution optimises against a random number generator. Not imported; the
scoring half is the whole point and it does not exist.

### Fixed while checking: `saleha optimize-prompts` learned from a fake error

Same defect as `godel-utility` (see `4518da8`), in a different command:

```python
rec = prompt_optimizer.optimize_prompt(
    role, 'You are a senior AI software engineer.',
    ['IndexError in test suite'])          # <- never happened
```

A hardcoded failure and a hardcoded base prompt, while **145 real failures**
sat unused in `TaskHistory`. The optimizer engine itself is honest — different
errors really do produce different, relevant directives — so only the caller
needed fixing.

Second bug found doing it: an error with no rule in `DIRECTIVE_MAP` (only 6
types are covered) fell through to a generic directive, so a `RecursionError`
silently produced *"ensure complete test assertion coverage"* and looked like
it had been learned from. Unmatched errors are now counted and reported.

Measured after the fix, on this repo's real history:

```
Learned from 10 real failure(s) in task history.
8 failure(s) had no matching rule and were NOT learned from:
  - Planning failed: All providers in fallback chain failed: 404 ...
  - Max healing attempts reached
  ...
```

That 8/10 miss rate is now visible instead of hidden behind a confident
directive. It is the honest state: `DIRECTIVE_MAP` covers Python exception
types, and most real failures here are orchestration failures.
