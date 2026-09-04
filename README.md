# Saleha

![Version](https://img.shields.io/badge/Version-2.6.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)
![Ollama](https://img.shields.io/badge/Ollama-Local%20First-orange.svg)
![License](https://img.shields.io/badge/License-MIT-purple.svg)

**Saleha** is a local-first, multi-agent AI coding assistant written in Python. It runs against local models via **Ollama** (or a cloud model provider, if you configure one), and provides a CLI, an interactive TUI, a REST/SSE web server, and a growing set of engineering-focused agents and tools: an autonomous coding loop, a codebase indexer and AST-aware patcher, a sandboxed code executor, a static security scanner, retrieval/memory stores, a headless-browser UI checker, and a "souls" persona system for steering agent behavior.

It is a large, actively evolving codebase (~220 modules under `saleha/core/`, a Click-based CLI with 100+ subcommands, and close to a thousand collected unit/integration tests). Not every module is equally mature — this README describes what is real and working today, and defers speculative or future capabilities to [ROADMAP.md](ROADMAP.md).

---

## What's actually here

- **Agentic coding loop** (`saleha/core/agentic_loop.py`, `saleha run` / `saleha agent`): plans a task, edits files, runs tests, and iterates on failures.
- **Multi-agent roles** (`saleha/agents/`): `PlannerAgent`, `CoderAgent`, `TesterAgent`, `DebuggerAgent`, orchestrated by `SalehaOrchestrator` / `TeamOrchestrator` for multi-step or multi-role tasks (`saleha team`, `saleha project`).
- **Codebase indexing & patching** (`saleha/core/codebase_indexer.py`): AST-based symbol scanning and unified-diff patch generation (`saleha scan`, `saleha refactor`).
- **Sandboxed execution** (`saleha/core/sandbox_runner.py`, `saleha/core/docker_sandbox.py`): runs generated/untrusted code in a subprocess or Docker container with resource limits (`saleha sandbox`, `saleha exec`).
- **Static security scanning** (`saleha/core/security_scanner.py`): AST-based checks for common issues (`shell=True`, bare `except`, hardcoded secrets, SQL string formatting, etc.) via `saleha sast`.
- **Retrieval & memory** (`saleha/core/memory_store.py`, `saleha/core/graph_rag.py`, `saleha/core/fast_search.py`): a persistent memory store, a lightweight RAG/graph-memory layer, and fast local code search.
- **Headless browser checks** (`saleha/core/browser_agent.py`, `saleha browser`): DOM/console inspection of a page via a headless browser driver, when one is installed.
- **Model routing** (`saleha/core/model_provider.py`, `saleha/core/smart_router.py`): routes requests across configured local (Ollama) and remote model backends.
- **Souls persona system** (`souls/*/soul.json` + `saleha/core/soul_engine.py`, `saleha/cli/soul_cli.py`): ten named personas (`architect`, `artisan`, `auditor`, `sage`, `sentinel`, `sovereign`, `speedrunner`, `sre`, `alchemist`, `minimalist`), each a JSON config (temperature/top_p, allowed tools) plus a `SOUL.md`/`IDENTITY.md`/`STYLE.md` prompt bundle, following a versioned `soul.json` schema under `souls/schema/`. `SoulEngine` discovers, loads, and renders these into an agent's system prompt. This is a real, working prompt/persona layer, not a claim about the model's actual cognition.
- **Web server** (`saleha/server/web_server.py`): a dependency-light HTTP/SSE server exposing much of the above over a REST API, with a browser-based UI.
- **Swarm-labeled coordination modules** (`saleha/core/swarm_consensus.py`, `saleha/core/quadratic_voting.py`, `saleha/core/hyperbolic_engine.py`): in-process modules that implement a multi-phase agent voting scheme, a quadratic-voting allocator, and a geometry-inspired task-routing scorer, respectively. These are genuine, testable pieces of logic — but they run as ordinary Python objects inside one process, not as a distributed, network-partition-tolerant system. See "On the swarm/consensus language" below.

### Client apps

- **`apps/web`** — a Next.js app that calls the Python backend over HTTP (`fetch("http://127.0.0.1:8000/...")`) for code execution and swarm/agent endpoints. This integration is real and working.
- **`apps/desktop`** — a Tauri app that launches the Python backend as a bundled sidecar process and talks to it over the same HTTP API. Wiring was completed recently; treat it as newer/less battle-tested than the CLI.
- **`rust/`** and **`contracts/`** — a set of experimental Rust crates (zkVM/blockchain research) and Solidity contracts. These are separate, largely standalone subsystems today, not integrated into the Python agent runtime. Work to connect them (if it happens) is tracked separately from this document.

---

## On the swarm/consensus language

Earlier versions of this document described the coordination modules as "PBFT Byzantine Fault Tolerant consensus," "Lean 4 formal proofs," and a "16-dimensional Poincaré hyperbolic swarm topology." To be precise about what exists in code today:

- `swarm_consensus.py` implements a **three-phase (propose/prepare/commit) voting protocol** among named agent roles inside a single process. The code comments call this "PBFT," and the propose/prepare/commit structure is indeed modeled on that family of protocols — but it does not run across independent machines, does not tolerate node crashes or network partitions, and has not been verified against the Byzantine fault-tolerance guarantees the name implies. Read it as "structured agent voting," not a distributed-systems consensus protocol.
- `formal_verifier.py` **generates Lean 4-shaped theorem/proof text as a template** (a `Lean4ProofResult` dataclass with a synthesized `lean4_code` string) — it does not invoke the actual Lean toolchain or produce a checked proof. `formal_smt_verifier.py` similarly emits SMT/Z3-styled certificate text without shelling out to Z3. Treat both as scaffolding/templates for a feature that isn't implemented yet, not verified formal proofs.
- `hyperbolic_engine.py` implements real vector math in a 16-dimensional Poincaré ball (distance function, attractor basins) used to score which of ten labeled "departments" a task is routed to. This is a working, deterministic heuristic — a geometric routing/scoring function — not a claim about emergent swarm cognition.

None of this is disqualifying; it's honest scaffolding that a contributor can build on. It just isn't what the previous marketing copy claimed.

---

## Quickstart

### 1. Installation

```bash
git clone https://github.com/MDaftab76678-1945/Saleha.git
cd Saleha
pip install -e .
```

### 2. Connect a local LLM (Ollama)

```bash
ollama run qwen2.5-coder:7b
```

### 3. Launch the interactive TUI

```bash
saleha tui
```

Or run a one-shot task:

```bash
saleha run "add input validation to the login handler"
```

---

## CLI command reference (selected)

The CLI (`saleha/cli/commands.py`) exposes well over 100 subcommands; run `saleha --help` for the full, current list. The table below covers the core workflow commands:

| Command | Description |
| :--- | :--- |
| `saleha run "<goal>"` | Autonomous plan → edit → test loop for a task. |
| `saleha agent "<goal>"` | Single-agent task execution with optional write access. |
| `saleha team "<goal>"` | Multi-role (planner/coder/tester/debugger) orchestration. |
| `saleha plan "<goal>"` | Produces a plan without executing it. |
| `saleha code "<task>"` | Generates code for a described task. |
| `saleha ask "<question>"` | One-shot question answering, no shell session. |
| `saleha scan <dir>` | AST-based codebase symbol indexing. |
| `saleha refactor <file> "<instruction>"` | Targeted AST-aware refactor with diff output. |
| `saleha sandbox <file>` | Runs code in an isolated subprocess/Docker sandbox. |
| `saleha exec <file>` | Executes a file directly with resource limits. |
| `saleha sast <path>` | Static security scan (Python; some Verilog/SystemVerilog support). |
| `saleha test <file>` / `saleha debug <file>` | Generates/repairs tests for a file. |
| `saleha browser <url>` | Headless-browser DOM/console inspection. |
| `saleha rag "<question>"` | Retrieval-augmented question answering over the repo. |
| `saleha swe-bench` / `saleha harness run` | Runs SWE-Bench-style evaluation harnesses. |
| `saleha consensus` | Inspects the in-process swarm voting module's validator/proposal state. |
| `saleha constitutional-check <path>` | Runs the rule-based `constitutional_guard` code audit. |
| `saleha merkle-audit` | Verifies the hash-chain integrity of the audit log. |
| `saleha voice [prompt]` | Voice input/output via local STT/TTS, where configured. |
| `saleha soul list / use <name>` | Lists and activates a persona from `souls/`. |
| `saleha serve` / `saleha sidecar` | Starts the local REST/SSE web server. |
| `saleha status` / `saleha doctor` | Environment and dependency diagnostics. |

---

## Tests

```bash
python -m pytest saleha/tests/ -q
```

The suite (`saleha/tests/`) currently collects **955 tests** across ~200 test files, covering the CLI, core modules, the web server API, and the web-server/agent integration points. A full local run (no Ollama/Docker required for most tests) produced **954 passed, 1 failed** — the one failure is a real CORS-header regression in the web server (`test_web_server.py::test_no_wildcard_cors_header_on_json_responses`, expecting no `Access-Control-Allow-Origin: *` on an authenticated JSON endpoint), not a flake. Results can vary slightly by environment; run the suite locally for current status rather than relying on a fixed badge.

---

## Roadmap

Forward-looking and exploratory work (WebAssembly sandboxing, P2P swarm networking, hardware acceleration, an eventual real Lean 4 integration, etc.) lives in [ROADMAP.md](ROADMAP.md), clearly separated from what ships today.

## License

MIT License.
