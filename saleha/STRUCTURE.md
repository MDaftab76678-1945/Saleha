# Where things actually are in `saleha/`

This repo grew by accretion, so some names collide across directories. This
file exists so you don't have to rediscover that every time. It describes
what's real as of this commit -- verify before trusting it, don't assume it
stays accurate forever.

## Top-level layout

| Path | What it is |
|---|---|
| `saleha/core/` | The real implementation: 216 flat `.py` modules. This is what almost everything actually imports from. |
| `saleha/agents/` | Agent persona classes (ArchitectAgent, CoderAgent, etc.) that wrap `saleha/core/` modules with a role/prompt. |
| `saleha/cli/` | The Click CLI (`commands.py`) and the interactive REPL (`repl.py`, `chat_session.py`). |
| `saleha/server/` | The stdlib HTTP server (`web_server.py`) serving `/api/*` and the bundled web Studio. |
| `saleha/tools/` | **Not** where the agent's function-calling tools live (see below) -- one file, `release_manager.py`, used by the CLI's release command. |
| `saleha/harness/` | A *different* thing from `saleha/core/harness/` (see collisions below): SWE-bench harness helpers (`benchmarks.py`, `swe_bench_harness.py`, `reporter.py`). |
| `saleha/sandbox/` | Standalone sandboxing/AST-security scripts, separate from `saleha/core/sandbox_runner.py` and `saleha/core/hardened_sandbox.py`. |
| `saleha/skills/` | Markdown persona/skill definitions (`agent_*.md`), unrelated to `souls/` at the repo root. |
| `saleha/specs/` | Reference specs and one-off generator scripts; not imported by the running app. |
| `saleha/experimental/` | Exactly what it says -- `aionx/`, `jarvis/`, not wired into the CLI or server. |
| `saleha/ci/` | A CI helper bot (`bot.py`), not GitHub Actions config (that's `.github/workflows/`). |
| `.agents/skills/` | Agent-skill packages for external tools (e.g. `self-improve-engine`) -- unrelated to `saleha/skills/`. |

## Where the agent's actual tools are

The LLM-facing function-calling tools (`web_fetch`, etc.) are registered in
**`saleha/core/tool_calling.py`**'s `ToolRegistry` / `global_tool_registry` --
**not** in `saleha/tools/`. `saleha/tools/` is a small, differently-scoped
package (currently just the release manager).

## The `saleha/core/<category>/` subpackages

`saleha/core/` also contains nine subdirectories --
`cognitive/ graph/ harness/ loop/ platform/ rag/ swarm/ telemetry/ verification/`
-- that group the 216 flat modules into themed categories and each add one or
two higher-level classes that compose several of those modules (e.g.
`swarm/__init__.py` re-exports `team_orchestrator.py` and friends, and adds
nothing you can't already import directly).

**These are a curated index, not a second copy of the implementation.**
The real code still lives in the flat `saleha/core/*.py` files; the
subpackage `__init__.py` just imports from them. Almost the entire codebase
(cli/, server/, agents/) imports the flat paths directly
(`from saleha.core.team_orchestrator import ...`), not the categorized ones.
Only `saleha/tests/test_2026_disciplines_suite.py` currently imports through
the categorized paths. Moving the real files into these folders was never
finished -- that's why both paths exist side by side. If you want one
canonical import path, that migration (moving 216 files + rewriting every
import site) is a large, separate, high-risk task -- not done here because
it would touch every test currently passing.

## Naming collisions worth remembering

- `saleha/harness/` (SWE-bench helpers) vs. `saleha/core/harness/` (category
  index for sandboxing/testing modules) -- different things.
- `saleha/tools/` (release manager) vs. `saleha/core/tool_calling.py` (the
  actual LLM tool registry) -- different things.
- `saleha/skills/` (persona markdown) vs. `souls/` at the repo root (the real
  SoulSpec persona system, see `saleha/core/soul_engine.py`) vs.
  `.agents/skills/` (packaged automation skills) -- three different things.
