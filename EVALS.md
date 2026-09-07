# EVALS.md — Ground-Truth Evaluation & Benchmark Protocol

> **Project:** saleha-0.1 (Local-First Autonomous Multi-Agent AI Coding Assistant)  
> **Audience:** Core Developers, AI Benchmark Drivers, Model Fine-Tuners  
> **Source of Truth:** Aligned with `AGENTS.md` and `NOTEBOOK_IMPORT.md`

This document defines the strict, honest benchmarking standards for evaluating models and autonomous agent loops in Saleha.
Fabricated scores and unmeasured passes are strictly forbidden in this repository.

---

## 1. The Core Honesty Protocol (No Fake Greens)

1. **Every Score Must Be Measured:** Never print hand-typed literals or hardcoded percentages as benchmark results (eradicated in Pass 20 and Pass 28).
2. **Real Sandbox Execution:** A generated code candidate is only scored as PASS if it runs inside `saleha/sandbox/sandbox_jail.py` and exits code 0 with zero runtime exceptions.
3. **No Test Pinning:** Tests must never assert hardcoded mock scores (`assert score == 93.3`). Tests must assert the physical outcome of the execution.
4. **Isolate Memory Caches:** When comparing Model A and Model B, the orchestrator must swap in an ephemeral, throwaway `MemoryStore` so Model B cannot replay Model A's cached solution.

---

## 2. Evaluation Suites & Data Sources

| Benchmark Suite | Script Path | Evaluation Focus | Metric |
| --- | --- | --- | --- |
| **Speed & Throughput** | `scripts/benchmark_ollama_speed.py` | Local Ollama prompt eval & token/s | Tokens / Second |
| **Artificial Analysis** | `scripts/evaluate_artificial_analysis_benchmarks.py` | Real reasoning & syntax accuracy | Pass@1 on live tasks |
| **Multi-Agent Emergence** | `saleha/tests/test_emergence_honest.py` | Agent message bus & coordination | Real message logs |
| **SMT Contract Logic** | `saleha/tests/test_formal_smt_verifier.py` | Z3 constraint proof satisfaction | UNSAT / SAT proofs |

---

## 3. Dataset Integrity & Purge Ledger

In Pass 28, 8,100 rows of fabricated training data were audited and purged down to 59 genuine verified rows:

- **Empty Placeholders Purged:** Generator scripts that synthesized identical math constants or tautological questions were replaced with real algorithmic challenges.
- **Deduplication:** Repeated prompt variations disguised as volume were unified.
- **Backups:** Historical backups are stored locally in uncommitted, gitignored directories. Only clean, tested rows enter production training scripts (`scripts/train_saleha_targeted.py`).

---

## 4. How to Run an Honest Evaluation Run

Always invoke benchmark scripts inside the development `.venv` with UTF-8 encoding enabled:

```bash
# Ensure UTF-8 console output
$env:PYTHONIOENCODING = "utf-8"

# Run speed benchmark against local 3B model
python scripts/benchmark_ollama_speed.py --model qwen2.5-coder:3b

# Run core test suite verification
python -m pytest saleha/tests/ -q
```
