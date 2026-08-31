# 🧠 Saleha AI Framework

[![Tests](https://img.shields.io/badge/Tests-400%20Passed%20(100%25)-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)]()
[![Ollama](https://img.shields.io/badge/Ollama-Local%20First-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()

**Saleha** is a local-first, self-healing **Autonomous Multi-Agent AI Engineering Platform** powered by Ollama. Twenty specialized agents collaborate through parallel task DAGs, run **real sandboxed test-verification loops**, perform AST-based SAST security audits, expose compiler-grade LSP diagnostics, ship cloud deployments, and run with a ReAct-style autonomous agent loop with surgical Aider-style diffing — **100% local, $0 API cost**.

---

## ⚡ Why Saleha

| Capability | Detail |
|---|---|
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
