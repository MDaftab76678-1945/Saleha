# PRODUCT_BRIEF.md — Saleha

## 1. What it is

- **Product name:** Saleha AI
- **One-line description:** A local-first, multi-agent AI coding assistant (CLI + TUI + web server) that runs against local Ollama models, with companion Next.js and Tauri clients that talk to it over HTTP.
- **Primary interface today:** the Python CLI and TUI (`saleha run`, `saleha tui`, etc.), backed by a REST/SSE web server that both `apps/web` and `apps/desktop` consume.

This brief describes the product as it exists in the codebase, not a target state. Forward-looking ideas live in [ROADMAP.md](ROADMAP.md).

---

## 2. Market & audience

- **Target users:** developers who want an AI coding assistant that runs on their own hardware against local models (privacy-sensitive users, cost-sensitive hobbyists, teams that can't send code to a third-party API) as well as anyone wanting an open, inspectable agent framework to extend.
- **Comparable tools:** Aider, Cursor, Cline, and other open or semi-open AI coding assistants — most competitors in this space are cloud-API-first; Saleha's differentiation is being local-model-first by default while still supporting cloud providers as an option.
- **Realistic differentiators today:**
  1. **Local-first model routing** — works against Ollama out of the box, avoiding per-token cloud costs when running on local hardware capable of hosting a coding model.
  2. **Breadth of tooling in one codebase** — codebase indexing/patching, sandboxed execution, a static security scanner, RAG/memory, and a persona ("souls") system are all implemented and testable in the same package, rather than requiring separate plugins.
  3. **A real (if young) multi-surface story** — a CLI/TUI, a REST/SSE server, a Next.js web client, and a Tauri desktop client that all share the same Python backend.
  4. **Souls persona system** — versioned, schema-validated persona packages (`souls/*/soul.json`) that let a team give agents a consistent voice, temperature/tool profile, and set of stylistic constraints — a genuinely useful and unusual feature among comparable tools.
  5. **Zero-leak local secret vault** — `saleha/core/vault.py` stores API keys and other secrets in a locally encrypted store (PBKDF2-HMAC-SHA256), so credentials used by the agent never need to leave the machine.

We do not currently have a distributed/Byzantine-fault-tolerant swarm, formally verified code generation, or a hyperbolic-manifold reasoning system as shipped, working differentiators — see [ARCHITECTURE.md](ARCHITECTURE.md) for what the "swarm"/"consensus"/"formal verification" modules actually do versus their naming.

---

## 3. Product scope

| Component | Path | Stack | Status |
| :--- | :--- | :--- | :--- |
| **Python core (CLI, agents, server)** | `saleha/` | Python 3.10–3.14 | Primary product; ~220 core modules, 100+ CLI subcommands, 955 collected tests. |
| **Web app** | `apps/web` | Next.js (App Router) | Working; calls the Python backend over HTTP for code execution and agent/swarm requests. |
| **Desktop app** | `apps/desktop` | Tauri v2 + React | Recently wired to the same Python backend via a bundled sidecar process; less mature than the CLI/web app. |
| **Landing page** | `apps/landing` | Astro | Marketing site for the project. |
| **UI kit / DB / API / Auth packages** | `packages/*` | React/Tailwind, Prisma, tRPC | Support the web app's own concerns (shared components, any account data, typed API routes); not part of the Python agent's own state. |
| **Souls persona packages** | `souls/*` | JSON + Markdown | Real, working prompt/persona layer used by the Python core. |
| **Rust crates (zkVM/blockchain research)** | `rust/` | Rust/Cargo | Experimental, standalone; not integrated with the agent runtime. |
| **Solidity contracts** | `contracts/` | Solidity/Hardhat | Experimental, standalone; not integrated with the agent runtime. |

---

## 4. Monetization

No monetization is implemented in the codebase today (no billing, licensing, or tiering logic found in `saleha/` or the web app). If a business model is adopted, document it here once it exists — the previous three-tier SaaS/enterprise pricing plan described here was aspirational and has been removed pending an actual implementation.

---

## 5. Quality bar (what we actually check for)

Rather than an unverifiable checklist, here's what the codebase actually enforces or measures:

1. **Tests:** `python -m pytest saleha/tests/` — 955 collected tests across ~200 files; run locally for current pass/fail status.
2. **Static security scanning:** `saleha sast` runs AST-based checks (unsafe `shell=True`, bare `except`, hardcoded secrets, string-built SQL) via `saleha/core/security_scanner.py`.
3. **Sandboxed execution:** generated/untrusted code runs through `sandbox_runner.py` (subprocess, resource-limited) or `docker_sandbox.py` (containerized), not directly on the host.
4. **Human approval gate:** `approval_gate.py`/`execution_policy.py` can require confirmation before risky operations.
5. **Audit trail:** `audit_log.py` + `merkle_provenance.py` keep a hash-chained log of actions, verifiable with `saleha merkle-audit`.

Claims like "WCAG 2.1 AA across all UI primitives," "sub-100μs execution," or "zero OWASP vulnerabilities" are not backed by any test, lint rule, or benchmark in this repository and have been removed. If accessibility/perf/security budgets are adopted, they should be tied to an actual CI check before being stated here again.
