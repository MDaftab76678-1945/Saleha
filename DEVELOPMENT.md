# DEVELOPMENT.md — Machine Setup & Contributor Guide

> **Project:** saleha-0.1 (Local-First Autonomous Multi-Agent AI Coding Assistant)  
> **Audience:** Contributors, Maintainers, CI/CD Pipeline Drivers  
> **Source of Truth:** Aligned with `AGENTS.md` and `pyproject.toml`

This guide explains how to configure a pristine, working local development environment for Saleha on Windows.

---

## 1. Prerequisites & System Constraints

- **Operating System:** Windows 10 or 11 (64-bit).
- **Python Version:** Python >= 3.12 (Default: Python 3.14).
- **Node.js & Package Manager:** Node.js >= 20.0, `pnpm` >= 9.0.
- **Local LLM Engine:** Ollama running locally at `http://127.0.0.1:11434`.

---

## 2. Python Virtual Environment Setup

The repository maintains two virtual environments. Use them strictly as intended:

| Environment Path | Python Version | Purpose |
| --- | --- | --- |
| `.\.venv\` | **Python >= 3.12** | **Primary Development.** All everyday coding, test runs, and CLI operations MUST run here. |
| `.\.venv_train\` | Python 3.11 | **Legacy Offline Training.** Strictly reserved for offline torch/PEFT scripts. Never run unit tests here. |

### Activation & Package Installation

```powershell
# 1. Activate the primary development environment
.\.venv\Scripts\Activate.ps1

# 2. Set console encoding (mandatory for Windows cp1252 consoles)
$env:PYTHONIOENCODING = "utf-8"

# 3. Install core dependencies with development and formal logic extras
pip install -e ".[dev,formal]"
```

*Note: The `[formal]` extra installs `z3-solver`, which is required for SMT contract verifier tests.*

---

## 3. TypeScript Monorepo Setup

Saleha includes an 8-package TypeScript monorepo under `packages/`:

```powershell
# Install TypeScript monorepo dependencies
pnpm install

# Run typecheck across all 8 packages (must exit 0 with 8/8 successful)
npx turbo run typecheck
```

---

## 4. Verification Workflow

Before submitting or staging any change:

```powershell
# 1. Run surgical module test
python -m pytest saleha/tests/test_math_logic.py -v

# 2. Run full test suite (~1661 tests)
python -m pytest saleha/tests/ -q

# 3. Check code style and diagnostics
python -m ruff check saleha/

# 4. Verify cyclomatic complexity
radon cc saleha/core/ -s
```
