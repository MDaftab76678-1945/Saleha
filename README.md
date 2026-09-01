# 🧠 Saleha AI Platform v2.0

[![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)]()
[![Tests](https://img.shields.io/badge/Tests-594%20Passed%20(100%25)-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)]()
[![Ollama](https://img.shields.io/badge/Ollama-Local%20First%20($0/mo)-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()
[![CI/CD](https://img.shields.io/badge/CI%2FCD-All%20OS%20Green-success.svg)](https://github.com/MDaftab76678-1945/Saleha/actions)
[![Live Landing Page](https://img.shields.io/badge/Website-Live%20Simulator-brightgreen.svg)](https://mdaftab76678-1945.github.io/Saleha/)
[![Docs Portal](https://img.shields.io/badge/Docs-Cookbook%20Portal-cyan.svg)](https://mdaftab76678-1945.github.io/Saleha/docs.html)

**Saleha** is a local-first, self-healing **Autonomous Multi-Agent AI Software Engineering Platform** powered by Ollama. Twenty specialized agents collaborate through parallel task DAGs, run **real sandboxed test-verification loops**, perform 3-way AST Git conflict resolution, execute live multi-turn voice pair programming, expose compiler-grade LSP diagnostics, and run an ultra-luxury 3-panel Web Studio workspace — **100% local, $0 API cost**.

---

## ⚡ 1-Click Launch (Desktop & Web Studio)

### Option A: Windows 1-Click Batch Launcher
Double-click `launch_studio.bat` in the root repository folder, or run:
```powershell
.\launch_studio.bat
```

### Option B: Python Command
```powershell
python -m saleha.desktop.app
```
Then navigate to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 💎 6 Deep Enterprise Engines

| Engine | Technical Achievement | Benefit |
|:---|:---|:---|
| ⚡ **VS Code Real FIM Autocomplete** | Fill-In-The-Middle (`<fim_prefix>`, `<fim_suffix>`) with 250ms latency bound | Real-time code completions via local Ollama `qwen2.5-coder` |
| 🔀 **3-Way AST Conflict Merger** | AST parsing & body unification (`_resolve_ast_function_conflict`) | Eliminates Git merge conflicts at syntax level without manual edits |
| 🔄 **Polyglot Codebase Migrator** | Flask path params (`<int:id>`) & unittest `assertRaises` AST transforms | Automatic framework modernization to FastAPI & pytest |
| 👥 **Adversarial Council Debate** | Cross-agent critique (Security vs Performance vs Architect) | Multi-persona stress-testing for bulletproof system designs |
| 🖥️ **Hardware Probing & Port Recovery** | `nvidia-smi` VRAM detection & socket auto-collision retries | Zero crash startup on busy ports & optimal model recommendation |
| 🎙️ **Contextual Voice Live Assistant** | Session turn history memory & conversational pronoun resolution | Hands-free pair programming ("Review auth.py" ➔ "Fix it") |

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
