# Autonomous Multi-Agent Engineering System (v5.0 Core + 33 Production Specs)

## Architecture Overview
This package unifies the complete **33 Agent Production Specifications** with the active **v5.0 Self-Healing Execution Engine**:

* `01_agent_specs/` : Contains all 33 production markdown role definitions (Architecture, Security, Hardware, Firmware, QA, DevOps, etc.) with YAML frontmatter and strict schemas.
* `02_v5_engine/` :
  - `local_llm_driver.py` : Driver connecting to local Ollama (`:11434`) or vLLM (`:8000`) with native JSON-mode enforcement.
  - `ast_security_verifier.py` : Static Abstract Syntax Tree (AST) auditor preventing banned imports and enforcing assertions.
  - `sandbox_jail.py` : POSIX resource-isolated process jail (128MB RAM ceiling, CPU timeouts, anti-fork bomb).
  - `v5_production_core.py` : Evaluator-Optimizer loop that automatically generates, audits, sandboxes, and self-heals code with persistent SQLite memory.

## Quickstart Guide

### 1. Start Local LLM (Optional - Has Deterministic Fallback)
```bash
ollama run qwen2.5-coder:7b
# or: ollama run qwen3.5:9b
```

### 2. Run Autonomous Engine
```bash
cd 02_v5_engine
python3 v5_production_core.py
```
