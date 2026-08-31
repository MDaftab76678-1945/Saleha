# 🧠 Saleha AI Framework

[![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)]()
[![Tests](https://img.shields.io/badge/Tests-574%20Passed%20(100%25)-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)]()
[![Ollama](https://img.shields.io/badge/Ollama-Local%20First-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()
[![CI/CD](https://img.shields.io/badge/CI%2FCD-All%20OS%20Green-success.svg)]()

**Saleha** is a local-first, self-healing **Autonomous Multi-Agent AI Engineering Platform** powered by Ollama. Twenty specialized agents collaborate through parallel task DAGs, run **real sandboxed test-verification loops**, perform AST-based SAST security audits, expose compiler-grade LSP diagnostics, ship cloud deployments, and run with a ReAct-style autonomous agent loop with surgical Aider-style diffing — **100% local, $0 API cost**.

---

## ⚡ Why Saleha

| Capability | Detail |
|---|---|
| 🔍 **AI-Powered Code Review Dashboard** | `saleha review-ai . --html` scans OWASP Top-10, code smells, performance bottlenecks, and generates HTML report |
| 🧠 **Per-Project Episodic Agent Memory** | `saleha memory-project --recall "<query>"` persists decisions, fixes, and architecture choices across sessions |
| 🚀 **Local LoRA Fine-Tuning Pipeline** | `saleha tune --model qwen2.5-coder:1.5b` auto-collects dataset and fine-tunes local models for $0 |
| ✂️ **Surgical Diff Preview & Blast Radius** | `saleha diff-preview old.py new.py` shows AST blast radius, hunk breakdown, and 1-10 risk scoring |
| 🏆 **Public SWE-bench Leaderboard** | `saleha benchmark-public` evaluates local models on SWE-bench tasks and compares vs Devin (13.86%) |
| 👀 **Real-Time Watch-AI Suggester** | `saleha watch-ai .` monitors file saves and emits instant inline syntax, security, and fix suggestions |
| 🤖 **Multi-OS GitHub Actions CI/CD** | `.github/workflows/ci.yml` runs full 547+ test suite across Ubuntu, Windows, macOS on Python 3.10 - 3.14 |
| 📚 **Searchable HTML Documentation** | `saleha docs --build` synthesizes responsive static HTML documentation portal (`docs/site/index.html`) |
| ⏱️ **Performance & Memory Profiler** | `saleha profile "<snippet>"` measures execution latency, peak RAM memory allocations, and GC overhead |
| 🔐 **Ephemeral Secret & Env Sync** | `saleha env list` securely bridges decrypted Vault secrets to subprocess memory without disk leakage |
| 🌐 **Interactive Local Web Dashboard** | `saleha web --port 3000` serves live browser telemetry, agent swarms, memory search, and token metrics |
| 🪄 **Interactive Project Onboarding** | `saleha init` auto-detects stack, configures `.saleharules`, and indexes baseline AST dependency graphs |
| 🪝 **Git Pre-Commit Security Guard** | `saleha hook install` prevents commits containing broken AST syntax or leaked `.env`/API tokens |
| 📥 **Model Manager & Speed Profiler** | `saleha pull recommended --benchmark` downloads models and benchmarks local inference speed (tokens/sec) |
| ⚡ **In-Chat REPL Slash Suite** | `/fix`, `/search`, `/debt`, `/threat`, `/budget`, `/hud` commands directly accessible inside `saleha chat` |
| 💥 **Autonomous Chaos Engineering** | `saleha chaos --iterations 10` injects synthetic network delays, connection drops, and null payloads to probe resilience |
| 🎭 **Synthetic Mock API Server** | `saleha mock --port 8080` launches zero-config in-memory mock JSON servers from codebase models |
| 🛡️ **STRIDE Threat Modeling Engine** | `saleha threat` auto-audits auth boundaries and entrypoints to synthesize standard Microsoft STRIDE matrices |
| 📉 **Technical Debt & Complexity Analyzer** | `saleha debt --threshold 10` computes Cyclomatic & Cognitive Complexity and flags God Objects / spaghetti loops |
| 🔌 **Native VS Code Extension Package** | `editors/vscode` connects VS Code directly to `saleha lsp --stdio` for inline shortcuts & diagnostics |
| 🖥️ **Distributed GPU Swarm Server** | `saleha server --port 8000` coordinates multi-developer async task queues over shared local GPU pools |
| 🎙️ **Full-Duplex Voice Assistant** | `saleha voice "<command>"` provides hands-free speech input, ReAct agent execution, and TTS audio synthesis |
| 📝 **Automated SemVer Changelog** | `saleha changelog --write` parses conventional commits and generates GitHub release markdown notes |
| 🌐 **Autonomous Visual Browser Tester** | `saleha test --browser` executes headless DOM flows (click, fill, screenshot, text assertions) for E2E web verification |
| 🔌 **Standard JSON-RPC LSP Daemon** | `saleha lsp --stdio` connects to VS Code, Cursor, Neovim for live diagnostics, definition jumps, and autocompletion |
| 🏢 **Multi-Repository Swarm Indexer** | `saleha multi-repo scan` maps cross-repo microservice dependencies and calculates global blast-radius |
| 🗺️ **Live Interactive Graph Visualizer** | `saleha graph --output docs/graph.html` generates interactive D3.js force-directed SVG network topologies |
| 🔄 **Multi-File Atomic Refactoring** | `saleha refactor rename <old> <new>` performs synchronized symbol renaming with transactional rollback protection |
| 🧠 **Continuous Skill Synthesis** | `saleha learn "<task>"` auto-distills successful fixes into permanent reusable skill files (`.saleha/skills/*.md`) |
| 💰 **Token Economics & Cost Analytics** | `saleha budget` tracks prompt/completion/reasoning tokens, generation speeds, and dollar savings vs Claude 3.5 & GPT-4o |
| ⚔️ **Architecture Debate & ADR Engine** | `saleha debate "<topic>"` runs 3-agent dialectic debates (Advocate vs Skeptic vs Judge) to generate ADR markdown docs |
| 🌐 **Polyglot AST & CST Parser** | Native AST extraction for Python, JavaScript, TypeScript, Go, Rust, and Java |
| 🩹 **Autonomous Self-Healing Loop** | `saleha fix "<cmd>"` parses failing test/compiler stacktraces, localizes fault, patches surgically, and verifies with auto-commit |
| 🔎 **Hybrid Semantic Code Search** | `saleha search "<query>" --semantic` combines subword BM25 ranking and TF-IDF vector embeddings for <10ms symbol retrieval |
| 👥 **Multi-Model Ensemble Reviewer** | `saleha review <path> --ensemble` cross-validates code via Security Auditor + Performance Architect + QA Reliability agents |
| 📊 **Live Interactive Terminal HUD** | `saleha hud` renders 4-quadrant real-time TUI telemetry (Ollama health, RAM/VRAM, AST symbols, hotkeys) |
| 🧠 **DeepSeek-R1 CoT Reasoning** | Extracts and streams `<think>...</think>` internal model reasoning tokens without JSON corruption |
| ✂️ **Surgical Aider-Style Diffing** | `<<<<<<< SEARCH ... ======= ... >>>>>>>` block diffs with 3-tier fuzzy indentation-tolerant search (90% token reduction) |
| 🌲 **Git Worktree Isolation** | Swarm agents run in parallel ephemeral Git worktree branches (`saleha/task-...`) keeping the main workspace pristine |
| 👁️ **Live Repo Watcher** | `saleha watch` monitors IDE saves in background (<20ms) and emits live downstream blast-radius alerts |
| 🔍 **Compiler-Grade LSP Engine** | `saleha lsp` extracts compiler diagnostics, type mismatches, mutable default arguments, and bare exceptions |
| 🚢 **Autonomous Cloud Deployer** | `saleha ship --apply` synthesizes hardened multi-stage Dockerfiles, docker-compose, and GitHub Actions CI pipelines |
| 🏆 **SWE-bench / HumanEval Suite** | `saleha bench` measures Pass@1 resolution rate and latency on standardized repository coding problems |
| 🗄️ **Database Query Optimizer** | `saleha db audit` detects silent N+1 query loops and missing foreign key indexes with migration generators |
| 🔒 **Enforced Sandboxing** | Generated code runs via Docker (`--network none`, CPU/mem caps) or hardened polyglot subprocess blocklist (Python, JS, TS, Go, Java, Rust) |
| 🤖 **Autonomous Agent Loop (ReAct)** | `saleha agent "goal"` — model thinks, calls tools (`read_file`, `find_symbols`, `get_file_outline`, `patch_file`, `run_code`), iterates until done |
| ⚡ **Speculative Fast Tier Router** | Sub-5ms task tier classifier cascading simple tasks to instant 1.5B/4B models and complex tasks to 8B/30B reasoning models |
| 🩺 **System Doctor & Auto-Repair** | `saleha doctor --fix` audits Python, Git, Ollama models, Sandboxes, and Vault with auto-repair and JSON output |
| 🌐 **MCP Dual Engine** | JSON-RPC 2.0 stdio server/client exposing swarm/DAG/SAST/sandbox/memory tools |

---

## 🚀 Quickstart

### 1. Prerequisites
Install [Ollama](https://ollama.ai/) and pull a coding model:
```powershell
ollama pull qwen2.5-coder:1.5b   # fast tier
# optional flagship:
ollama pull qwen2.5-coder:7b
```

### 2. Install Saleha
```powershell
git clone https://github.com/MDaftab76678-1945/Saleha.git
cd Saleha
py -m pip install -r requirements.txt
py -m pip install -e .
saleha --version
```

### 3. First Run
```powershell
saleha doctor                                                   # diagnose environment
saleha run "Build a token bucket rate limiter" --tests          # real unittest healing
saleha agent "find functions without docstrings" --dir ./src    # autonomous exploration
saleha watch .                                                  # live blast-radius watcher
```

---

## 🛠️ Command Reference

### Core Autonomous Pipelines
| Command | What it does |
|---|---|
| `saleha run "GOAL"` | Full self-healing pipeline: Plan → Code → Test → Review → Execute |
| `saleha agent "GOAL" --dir .` | Autonomous ReAct loop with tools (`--write` opt-in) |
| `saleha watch [DIR]` | Live background AST re-indexer & real-time blast-radius alerts |
| `saleha lsp [DIR]` | Compiler-grade static type & syntax diagnostics |
| `saleha ship [DIR] --apply` | Autonomous multi-stage Dockerfile, compose, and GitHub CI synthesizer |
| `saleha bench` | Automated SWE-bench & HumanEval software engineering benchmark evaluation |
| `saleha db audit [DIR]` | Detect N+1 query bottlenecks and synthesize index migrations |
| `saleha team "GOAL"` | 5-agent swarm: PM → Designer → SDE → Security Gate → QA (+`--debate`) |
| `saleha dag "GOAL" --parallel` | Dependency-DAG execution on thread pool |
| `saleha edit "GOAL" --dir ./repo --apply` | Multi-file edits: dry-run diffs → atomic apply |

### Introspection & Health
```powershell
saleha doctor --fix            # diagnose & auto-repair models/directories
saleha metrics                 # success-rate, avg attempts, per-model stats
saleha memory stats            # semantic solution cache stats
saleha agents                  # 20 dynamically-loaded agent personas
```

### Security & CI
```powershell
saleha sast ./src              # AST SAST scan (SQLi, eval, secrets, shell=True)
saleha ci review .             # autonomous PR review bot (CI-friendly exit codes)
saleha vault set db_pass x     # encrypted secret store
```

### Interactive & Web
```powershell
saleha chat                    # streaming pair-programming REPL (/outline, /symbols, /undo, ...)
saleha studio                  # Web Studio + REST API (token-authenticated)
saleha sidecar                 # floating desktop AI companion daemon
```

---

## 🧪 Test Suite

```powershell
pytest saleha/tests
```
```text
============================ 400 passed in 36.97s =============================
```
100% offline, fully mocked LLM fallbacks, deterministic execution.

## 📄 License
MIT
