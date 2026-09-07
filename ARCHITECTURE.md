# Saleha: System Architecture

This document describes what the codebase actually contains and how the pieces fit together. Forward-looking design ideas that are not implemented yet are called out explicitly as such, or left to [ROADMAP.md](ROADMAP.md).

---

## High-level layout

```text
saleha-0.1/
├── apps/
│   ├── desktop/          # Tauri desktop shell; launches the Python backend as a sidecar
│   ├── web/              # Next.js web app; calls the Python backend over HTTP
│   └── landing/           # Astro marketing/landing site
├── packages/
│   ├── ui/               # Shared React/Tailwind components used by web + desktop
│   ├── db/               # Prisma schema (used by the web app's own data, not the Python core)
│   ├── api/               # tRPC routers for the web app's own endpoints
│   ├── auth/              # Session/auth helpers for the web app
│   └── core/              # Shared TypeScript utilities for the JS apps
├── saleha/               # Python package: the actual agent runtime
│   ├── agents/            # PlannerAgent, CoderAgent, TesterAgent, DebuggerAgent, base classes
│   ├── cli/                # Click CLI (100+ subcommands), TUI, REPL, dashboards
│   ├── core/               # ~220 modules: agentic loop, indexing, sandboxing, memory, routing, souls, etc.
│   ├── server/             # Dependency-light HTTP/SSE REST API + browser UI
│   └── tests/               # ~200 test files, 955 collected tests
├── souls/                # SoulSpec persona packages (soul.json + SOUL.md/IDENTITY.md/STYLE.md per persona)
├── rust/                 # Experimental Rust crates (zkVM/blockchain research) — separate subsystem
├── contracts/             # Solidity contracts — separate subsystem
├── pyproject.toml
└── package.json           # JS monorepo workspace root (apps/, packages/)
```

The Python package under `saleha/` is the core product: the CLI, the agent loop, and the web server. `apps/web` and `apps/desktop` are thin clients that talk to it over HTTP — they do not re-implement agent logic in TypeScript. `packages/db`, `packages/api`, and `packages/auth` back the web app's own concerns (e.g. any account/session data it stores), not the Python core's state.

`rust/` and `contracts/` are separate, self-contained experiments (a zkVM/blockchain research area and a set of Solidity contracts, respectively). As of this writing they are not wired into the agent runtime described below; treat any diagram or claim elsewhere suggesting otherwise as aspirational.

---

## Core subsystems (Python, `saleha/core/`)

### Agentic loop and orchestration

`agentic_loop.py` drives the plan → edit → test → repeat cycle used by `saleha run`/`saleha agent`. `saleha/agents/` defines role-specific agents (planner, coder, tester, debugger); `team_orchestrator.py` and `SalehaOrchestrator` coordinate multiple roles for `saleha team`/`saleha project`. `dag_engine.py` provides a task-dependency DAG for parallelizable multi-step goals (`saleha dag`).

### Codebase understanding

`codebase_indexer.py` builds an AST-based symbol index and generates/applies unified diffs (`SmartPatcher`). `fast_search.py` provides local code search. `graph_rag.py` and `graph_memory.py` implement a lightweight retrieval/graph-memory layer over indexed code and prior interactions. `dependency_graph.py` and `change_impact.py` build import/call graphs and estimate blast radius of a change.

### Execution and safety

`sandbox_runner.py` runs code in a restricted subprocess (timeouts, resource limits); `docker_sandbox.py` does the same inside a Docker container when available. `security_scanner.py` is an AST-based static analyzer flagging patterns like `shell=True`, bare `except:`, string-built SQL, and hardcoded secrets (`saleha sast`). `approval_gate.py` and `execution_policy.py` implement a human-in-the-loop gate for risky operations. `audit_log.py` and `merkle_provenance.py` keep an append-only, hash-chained log of actions (`saleha merkle-audit` verifies the hash chain — this is a straightforward Merkle/hash-chain integrity check, not a blockchain).

### Model access

`model_provider.py` and `smart_router.py` route requests to configured backends — local Ollama models by default, with optional cloud providers. `dynamic_lora_router.py` and `lora_tuner.py` are experimental hooks for routing to/training LoRA adapters; treat these as in-progress rather than production-hardened.

### Coordination modules ("swarm" naming)

Several modules use "swarm" and consensus-related terminology in their names and docstrings. Concretely:

- **`swarm_consensus.py`** — a propose/prepare/commit voting scheme among named agent roles (e.g. `ArchitectAgent`, `CoderAgent`, `SecurityAgent`, `TesterAgent`), used to gate whether a proposed patch is accepted. It runs in-process; there is no networked quorum of independent nodes, and it has not been validated against formal Byzantine fault-tolerance properties. `saleha consensus` prints its current validator/proposal state.
- **`quadratic_voting.py`** — a quadratic-cost voting/allocation mechanism for weighing competing proposals (`saleha quadratic-vote`). This is a real, working scoring algorithm.
- **`hyperbolic_engine.py`** — computes distances and attractor-basin assignments in a 16-dimensional Poincaré ball, used as a heuristic to route a task to one of ten labeled "departments" (kernel, security, reasoning, etc.). It's real, tested vector math used for routing/classification — not a claim about spatial reasoning or emergent cognition.
- **`emergence_detector.py`** — heuristics for detecting circular message patterns or inequality in agent workload (Gini-coefficient-style metrics) across logged agent interactions.

These are genuine pieces of logic worth describing plainly. Framing them as "PBFT Byzantine consensus" or "sovereign swarm intelligence" overstates what a single-process voting/scoring function does.

### Formal verification (templates, not a real prover)

`formal_verifier.py` and `formal_smt_verifier.py` generate Lean 4- and SMT/Z3-shaped text (theorem statements, "certificate" strings) from simple heuristics about a function's structure. **Neither module invokes an actual Lean or Z3 toolchain**, so nothing they produce is a checked mathematical proof. If real formal verification is added later, it belongs in [ROADMAP.md](ROADMAP.md) until it exists.

### The orchestrator family, audited 2026-09-07

All 8 orchestrator classes were read end-to-end and probed with two unrelated
goals each, to see whether the output actually depends on the request.

**Real (fixed in earlier passes):**

- `SalehaOrchestrator` (`saleha/orchestrator.py`), `TeamOrchestrator`,
  `DebateConsensusOrchestrator`, `ToTOrchestrator` — real model calls, real
  sandboxed execution. The hardcoded-score defects in these were fixed in the
  sixth pass; `team_orchestrator` additionally records swarm handoffs as of the
  eleventh.

**Templates — zero model calls, output independent of the request:**

- **`AutonomousRepoOrchestrator`** (`repo_orchestrator.py`, `/autopr`) —
  **fixed 2026-09-07.** Was the most dangerous of the group: it returned
  `tests_passed=True` unconditionally with no test ever run, invented two
  `files_modified` paths from the goal slug that did not exist on disk, and
  emitted a PR body asserting "5/5 PASSED", "0 CWE vulnerabilities" and
  "verified inside Ephemeral Container Sandbox". The chat command printed
  "Branch Created" and "100% Invariants Passed" for a branch never created. It
  now reads real `git status`, reports `tests_passed=None` unless a caller
  supplies a real run, and lists unrun checks as unrun. Branch creation is
  opt-in.
- **`CloudInfraOrchestrator`** (`cloud_infra_orchestrator.py`, `cloud-plan`) —
  **template.** Measured: "Design a multi-region Postgres cluster" and "Write a
  haiku about frogs" produce byte-identical Kubernetes manifests, Helm values,
  IAM policy and CI/CD workflow. The Terraform differs on exactly 3 lines, all
  of them the echoed goal string (a comment, the S3 state key, a tag). Cost is
  always $142.50/mo and the CIS security score always 96. `--output-dir` writes
  these to disk as `main.tf` / `iam-policy.json`.
- **`SiliconCircuitOrchestrator`** (`silicon_circuit_orchestrator.py`,
  `silicon-build`) — **template.** "4-bit ripple carry adder" and "UART
  receiver with parity check" differ by one comment line; the same fixed ALU is
  emitted for both, at a constant 184 LUTs and 450 MHz, with
  `is_synthesizable=True` unconditional. No synthesis toolchain is invoked.
- **`MultiRepoOrchestrator`** (`multirepo_orchestrator.py`, `multirepo`) —
  **template.** Every field of the returned plan is byte-identical across
  unrelated goals, including `breaking_changes_identified` and
  `migration_order`.

### More grandiosely-named commands, audited 2026-09-06

Following the same pattern as the two sections above, 8 more CLI commands with research-sounding names were read end-to-end (CLI wiring through to the real `saleha/core/` implementation) to check what they actually do:

- **`silicon-build`** (`silicon_circuit_orchestrator.py`) — **template.** Every request, regardless of the circuit described, returns the exact same fixed ALU Verilog module (only the module name is substituted), the same testbench, and hardcoded "results" (`estimated_lut_count=184`, `450.0 MHz` in one field, a disconnected `400 MHz` in another). No synthesis/simulation toolchain (Yosys/Verilator/iverilog) is ever invoked; `is_synthesizable=True` is unconditional. The generated text happens to be syntactically valid Verilog-2001 despite this — it's real HDL syntax, just not synthesized *from* the actual request.
- **`causal-eval`** (`causal_world_model.py`) — **template.** Uses Pearl-hierarchy vocabulary (`L1`/`L2`/`L3`, `do(...)`) but `simulate_l2_intervention` (the "intervention" layer) calls the identical code path as the "association" layer — no graph surgery, no confounder adjustment. The counterfactual layer skips abduction entirely (just diffs two interventional queries). The CLI only ever exercises one hardcoded intervention against a fictional hand-authored causal graph, not anything derived from the codebase being evaluated.
- **`explain-code`** (`mech_interp.py`) — **was a template; rebuilt 2026-09-07 and renamed in substance.** It previously classified lines with four `substring in line` buckets at a fixed score each, so `x = "raise the roof"` was a "defensive error guard circuit" at 0.95 confidence, and across a 305-line file the only distinct scores were the four bucket constants. It imported `ast` and `re` and called neither. It now parses the file: classification comes from the AST node type, and the report adds per-function cyclomatic complexity, annotation/docstring coverage, enclosing scope, and bare-`except` detection. Complexity is cross-checked against `radon` over all of `saleha/core/` — 472 functions, 0 mismatches. The "mechanistic interpretability" claim is dropped rather than faked: that needs model activations Ollama does not expose. `MechInterpEngine` remains an alias of `CodeStructureEngine` for existing callers.
- **`emergence-check`** (CLI wiring only; `emergence_detector.py` itself is real, see above) — **was a template in this wiring; fixed 2026-09-07.** The CLI called the real detector's `evaluate_swarm_health()` with zero data ever fed to it (nothing in the repo called the singleton's `record_message()`), so it deterministically printed "Swarm communication is idle and healthy" every time, regardless of agent activity. Two things were missing and both are now in place: `TeamOrchestrator.run_team_workflow` records its real handoffs (PM → Designer → Coder → Security → QA, plus both directions of the Verifier↔Debugger healing loop), and events persist to `~/.saleha/swarm_messages.jsonl` because the CLI runs in a different process from the workflow it asks about. An empty history now reports that there is nothing to judge (`has_data=False`) instead of calling an empty graph healthy. Verified end-to-end across processes: a stuck healing loop recorded in one process is detected and reported as an anomaly by `emergence-check` in another.
- **`quantum-sim`** (`quantum_compiler.py`) — **real, but misnamed**, in the `swarm_consensus.py` sense: a genuinely correct single-qubit simulator (real Hadamard/Pauli-X matrices, real Born-rule sampling, real Shannon entropy). But it's marketed as an "M-theory Tensor Simulator" with "11-dimensional" state and entanglement — there is exactly one qubit, no tensor product, and unsupported gates (`Z`, `S`, `T`, `CNOT`, …) silently no-op.
- **`recursive`** (`recursive_solver.py`) — **real, but misnamed; the hardcoded half was fixed 2026-09-07.** Real LLM calls (via `BaseAgent.think()`) and real sandboxed self-healing execution genuinely happen. The advertised "7-node network" is still one class making a linear sequence of ~5 method calls (not recursive, not a network) — the name still overstates the shape. But the centerpiece "multi-path reasoning" step no longer returns 3 hardcoded `ReasoningPath` objects with fixed scores: the three framings are now prompt inputs, each path is analysed against the actual goal and scores its own suitability, and a tie at the top is reported as a tie rather than silently resolved. Previously `path_b`'s hardcoded 9.0 won for every input ever submitted.
- **`cognitive`** (`cognitive_engine.py`) — **real, but misnamed.** Genuinely re-scores each real input file (not templated output), but the "4D Cognitive State & Ethics Analysis" is four independent regex/substring checks (e.g. three literal `for` lines in a row = "temporal" violation) with fixed score deltas — no AST parsing (again, `ast` imported and unused), no real ethics/bias/safety evaluation.
- **`constitutional-check`** (`constitutional_guard.py`) — **real, but misnamed.** A real, working 4-rule regex linter for dangerous patterns (`rm -rf /`, unsafe deserialization, privilege escalation, credential exfiltration) that genuinely depends on its input — but has nothing to do with Anthropic's actual Constitutional AI technique (a constitution plus LLM self-critique/revision) the name invokes; it's a much narrower sibling of the `sast` command's AST scanner, done with plain regex instead.

None of these are disqualifying on their own — same conclusion as the swarm/consensus and formal-verification sections above — but as a set they show the same naming pattern recurring across a large fraction of the CLI's more exotic commands. Treat any command name here as "at least worth reading the real implementation before repeating the claim," not as ARCHITECTURE.md having already cleared it.

### Souls (persona) system

`soul_engine.py` loads persona packages from `souls/<name>/`, each with a `soul.json` (name, archetype, cognitive params like temperature/top_p, allowed tool list) validated against a schema in `souls/schema/v1/`, plus `SOUL.md`/`IDENTITY.md`/`STYLE.md` prose files. `SoulPackage.render_system_prompt()` assembles these into a system prompt injected into an agent's context. Ten personas ship today: `architect`, `artisan`, `auditor`, `sage`, `sentinel`, `sovereign`, `speedrunner`, `sre`, `alchemist`, `minimalist`. This is a real and reasonably well-structured prompt-engineering layer for giving agents a consistent voice/constraint set — it changes what gets put in the system prompt, not the model's underlying capabilities.

### Other notable modules

`browser_agent.py`/`browser_runner.py` (headless browser DOM/console checks), `swe_bench_harness.py` (SWE-Bench-style evaluation), `mcp_engine.py`/`mcp_hub.py` (Model Context Protocol client/server support), `pr_generator.py` (PR body/diff generation), `changelog_generator.py`, `chaos_engine.py`/`load_tester.py` (basic fault-injection and load-testing helpers), `voice_engine.py`/`full_duplex_voice.py` (local STT/TTS wiring, hardware/driver-dependent). Not all ~220 modules in `saleha/core/` are equally exercised by tests or CLI commands; the test suite (`saleha/tests/`) is the most reliable signal for what's actively maintained.

---

## Interfaces

### CLI (`saleha/cli/`)

Built on Click, `saleha/cli/commands.py` (~6,500 lines) registers well over 100 subcommands, from core workflow commands (`run`, `agent`, `team`, `plan`, `scan`, `refactor`) to diagnostics (`status`, `doctor`), memory (`memory list/search/stats`), and the coordination-module commands described above. `saleha tui` launches a full-screen terminal UI (`saleha/cli/tui_app.py`, `tui_canvas.py`); `saleha repl`/`saleha chat` provide REPL-style sessions.

### Web server (`saleha/server/web_server.py`)

A dependency-light HTTP/SSE server exposing REST endpoints for the core engines above (status, agents, scan/diff/patch, sandbox exec, memory, RAG, security scan, etc.) plus a browser-based UI. Some endpoints listed in the server's own module docstring (e.g. WASM, P2P fuzzing, spatial UI generation, post-quantum crypto, native compilation) are placeholders/stubs for future work, not implemented features — see the server module docstring and treat anything not backed by a corresponding `saleha/core/` module as aspirational.

### Web app (`apps/web`)

A Next.js (App Router) application. Confirmed working integration: it calls the Python backend directly over HTTP (e.g. `fetch("http://127.0.0.1:8000/api/v2/swarm/execute")` in `src/app/page.tsx`) for code execution and agent/swarm requests.

### Desktop app (`apps/desktop`)

A Tauri v2 application. It launches the Python backend as a bundled sidecar process on startup and polls until it's ready, then talks to it over the same HTTP API used by the web app (`src/App.tsx`). This wiring was completed recently as part of ongoing integration work; expect rougher edges than the CLI or web app.

### rust/ and contracts/

`rust/` contains multiple Cargo crates (a zkVM guest, an "intent kernel," experimental cores) exploring zkVM/blockchain ideas; `contracts/` contains Solidity contracts (escrow, marketplace, a DAO, bridging). Both are self-contained experiments today, developed and tested independently of the Python agent runtime and the web/desktop clients. If/when real integration lands, it should be documented here as a fact, not assumed in advance.

---

## Testing

```bash
python -m pytest saleha/tests/ -q
```

`saleha/tests/` currently collects 955 tests across roughly 200 files, covering CLI commands, core modules, and the web server's REST surface. Some tests are environment-dependent (Docker, a running Ollama instance, browser drivers); check locally for current pass/fail status.
