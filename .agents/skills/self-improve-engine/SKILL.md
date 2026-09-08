---
name: self-improve-engine
description: >-
  Autonomous self-improvement engine that scans untested modules in saleha/core/,
  generates real pytest tests using local coder LLMs (Ollama), validates in tempdir,
  commits passing tests to the isolated auto/self-improve branch, and maintains an audit log.
---

# Saleha Self-Improvement Engine

## Overview

The `self-improve-engine` skill automates the testing and continuous improvement cycle for the Saleha core codebase. On each cycle, it identifies one untested module in `saleha/core/`, generates a targeted `pytest` test suite using local coder LLMs (such as `deepseek-coder:6.7b` or `qwen2.5-coder`), validates the test in an isolated temporary directory, and commits only genuinely passing tests to the dedicated `auto/self-improve` branch.

Every action and outcome is recorded to `~/.saleha/self_improve_log.jsonl` for inspectability.

## Safety Rails

These constraints are non-negotiable and baked into the execution:

1. **Never Edits Existing Source**: Only ever creates and commits a new test file under `saleha/tests/test_<module>.py`.
2. **Dedicated Branch**: Commits only to the local `auto/self-improve` branch. Never touches the working branch or main branch history.
3. **No Remote Push**: Commits remain strictly local; human operators decide when to publish or merge.
4. **Isolated Pre-Validation**: Tests are executed via `pytest` in a temporary directory first. Failing tests are discarded immediately and logged—nothing broken is ever committed.

## Dependencies

- Python 3.10+
- `pytest`
- Ollama with a tagged coder model installed (e.g. `deepseek-coder:6.7b`, `qwen2.5-coder:1.5b`)
- Git repository with `saleha/core/` and `saleha/tests/`

## Quick Start

Inspect coverage and find the next candidate module:

```bash
python .agents/skills/self-improve-engine/scripts/run_self_improve.py status --output scratch/status.json
```

Run a single self-improvement cycle:

```bash
python .agents/skills/self-improve-engine/scripts/run_self_improve.py cycle --output scratch/cycle_result.json
```

## Utility Scripts

The skill provides `.agents/skills/self-improve-engine/scripts/run_self_improve.py` with the following subcommands:

### 1. `status`

Summarizes total core modules, tested count on working branch, tests accumulated on `auto/self-improve`, and next untested candidate.

```bash
python .agents/skills/self-improve-engine/scripts/run_self_improve.py status --output <path_to_json> [--log-limit N]
```

### 2. `cycle`

Executes one single cycle.

```bash
python .agents/skills/self-improve-engine/scripts/run_self_improve.py cycle --output <path_to_json>
```

### 3. `batch`

Executes multiple cycles sequentially, automatically skipping modules that encounter repeated model generation failures.

```bash
python .agents/skills/self-improve-engine/scripts/run_self_improve.py batch --cycles 5 --output <path_to_json>
```

### 4. `logs`

Inspects `~/.saleha/self_improve_log.jsonl` with optional filtering by status (`committed`, `test_failed`, `generation_failed`, `no_candidate`).

```bash
python .agents/skills/self-improve-engine/scripts/run_self_improve.py logs --limit 20 --status committed --output <path_to_json>
```

## Model Selection & Rate Limiting

- Local Ollama models do not incur external API costs or HTTP rate limits.
- **Model Tags**: Always ensure tagged model names (e.g., `deepseek-coder:6.7b`, not bare `deepseek-coder`) to avoid Ollama 404s.
- **Hardware & Timeout**: Cold-starting larger models (e.g. 6.7B+) under load can hit the 60s request timeout. Fast small models (`qwen2.5-coder:1.5b` or `qwen2.5-coder:3b`) are preferred for quick test scaffolding.

## Common Mistakes

1. **Running git checkout -B**: Never use `-B` when switching to `auto/self-improve` as it resets the branch to `HEAD` and erases prior accumulated test commits.
2. **Missing tags on local models**: Ollama requires the `:tag` suffix when querying `/api/generate`.
3. **Modifying source code**: Tests should only exercise the existing public API of modules, never rewrite the core source file to match a flawed test.
