# Where things actually are in `saleha/`

This repo grew by accretion, so some names collide across directories. This
file exists so you don't have to rediscover that every time. It describes
what's real as of this commit -- verify before trusting it, don't assume it
stays accurate forever.

## Top-level layout

| Path | What it is |
|---|---|
| `saleha/core/` | The real implementation: 197 flat `.py` modules plus 9 category subpackages (46 more modules -- see below). This is what almost everything actually imports from. |
| `saleha/agents/` | Agent persona classes (ArchitectAgent, CoderAgent, etc.) that wrap `saleha/core/` modules with a role/prompt. |
| `saleha/cli/` | The Click CLI (`commands/` package) and the interactive REPL (`repl.py`, `chat_session.py`). |
| `saleha/server/` | The stdlib HTTP server (`web_server.py`) serving `/api/*` and the bundled web Studio. |
| `saleha/tools/` | **Not** where the agent's function-calling tools live (see below) -- the real ToolForge registry (`ast_inspector.py`, `release_manager.py`, `base.py`'s `tool_registry`), used by `tool_forge.py`/`agentic_loop.py`. |
| `saleha/harness/` | A *different* thing from `saleha/core/harness/` (see collisions below): SWE-bench harness helpers (`benchmarks.py`, `swe_bench_harness.py`, `reporter.py`). |
| `saleha/sandbox/` | Standalone sandboxing/AST-security scripts, separate from `saleha/core/harness/sandbox_runner.py` and `saleha/core/hardened_sandbox.py`. |
| `saleha/skills/` | Markdown persona/skill definitions (`agent_*.md`), unrelated to `souls/` at the repo root. |
| `saleha/specs/` | Reference specs and one-off generator scripts; not imported by the running app. |
| `saleha/experimental/` | Exactly what it says -- `aionx/`, `jarvis/`, not wired into the CLI or server. |
| `saleha/ci/` | A CI helper bot (`bot.py`), not GitHub Actions config (that's `.github/workflows/`). |
| `.agents/skills/` | Agent-skill packages for external tools (e.g. `self-improve-engine`) -- unrelated to `saleha/skills/`. |

## Where the agent's actual tools are

The LLM-facing function-calling tools (`web_fetch`, etc.) are registered in
**`saleha/core/tool_calling.py`**'s `ToolRegistry` / `global_tool_registry` --
**not** in `saleha/tools/`. `saleha/tools/` is the ToolForge registry (see above).

## The `saleha/core/<category>/` subpackages -- migration completed (pass 139)

`saleha/core/` contains nine subdirectories --
`cognitive/ graph/ harness/ loop/ platform/ rag/ swarm/ telemetry/ verification/`
-- each holding the *real* implementation files for its 4-6 named modules
(46 total). This used to be a curated index with the flat files still holding
the real code (both paths existed side by side); pass 139 completed the
migration the earlier note on this page said was deferred: the 46 modules now
live only under their category folder, and the corresponding flat
`saleha/core/<name>.py` file no longer exists. Every import site across the
whole repo (~450 real references) was rewritten to the new dotted path.

**Which modules moved where:**

| Category | Modules |
|---|---|
| `cognitive/` | `causal_world_model`, `neuro_symbolic_engine`, `padic_ultrametric`, `persona_debate`, `soul_engine` |
| `graph/` | `codebase_indexer`, `dependency_graph`, `graph_memory`, `hypergraph_indexer`, `multi_repo_graph` |
| `harness/` | `approval_gate`, `benchmark_harness`, `code_executor`, `sandbox_runner`, `swebench_runner`, `test_runner` |
| `loop/` | `agentic_loop`, `deliberation_engine`, `recursive_solver`, `tot_orchestrator` |
| `platform/` | `git_native`, `lsp_engine`, `mcp_hub`, `model_provider`, `self_healer`, `smart_router` |
| `rag/` | `repo_context_packer`, `semantic_search`, `tree_context_ranker`, `vector_store` |
| `swarm/` | `agent_message_bus`, `agent_worker_pool`, `swarm_checkpoint_store`, `swarm_consensus`, `swarm_pipeline_engine`, `team_orchestrator` |
| `telemetry/` | `audit_log`, `metrics`, `session_tracer`, `token_analytics` |
| `verification/` | `apex_97_validator`, `formal_smt_verifier`, `quality_guard`, `safety_guard`, `security_scanner`, `ttc_solver` |

All other `saleha/core/*.py` files (197 of them) remain flat -- they were
never assigned to a category by any prior pass, and inventing new categories
for them was a separate, larger design decision not attempted here.

**A real trap the migration exposed, fixed in `saleha/core/__init__.py` and
each affected category `__init__.py`:** several category packages
re-export a singleton under the *same name* as its own submodule (e.g.
`saleha/core/harness/__init__.py` does
`from saleha.core.harness.approval_gate import ApprovalGate, approval_gate`),
which rebinds `saleha.core.harness.approval_gate` from the module to the
instance. `from saleha.core.harness.approval_gate import X` (the pattern
every production call site uses) is unaffected -- Python resolves the
submodule during that statement before the package's own later rebinding
takes effect. Only `import pkg.sub as alias` / bare `pkg.sub` attribute
access hits this; a couple of test helpers using that pattern were fixed to
go through `sys.modules["saleha.core.<category>.<module>"]` instead, which
always reaches the real module. If you write new code and want the module
object itself (not the singleton) from one of these packages, use
`sys.modules` or `importlib.import_module`, not a bare attribute path.

**`saleha/core/__init__.py`'s PEP-562 compatibility layer** (`_MOD_MAP`,
`_MOD_TO_SUBPACKAGE`) still lets `from saleha.core import <ClassName>` and
`from saleha.core import <module_name>` work for every migrated symbol/module,
resolving through the new category path transparently. This exists for
backward compatibility with code/tests written against the old flat layout
that never got updated to the category-qualified `from saleha.core.<category>.
<module> import X` form.

**Two circular imports were latent in the flat layout and only surfaced once
eager subpackage `__init__.py` files were involved** (`saleha/core/platform/
self_healer.py` importing `BaseAgent` at module level, and `saleha/core/
harness/benchmark_harness.py` / `swebench_runner.py` importing
`SalehaOrchestrator` at module level) -- both were always a layering
violation (`saleha/core/` importing from `saleha/agents/`/`saleha/orchestrator.py`,
which import back into `saleha/core/`), just never triggered before because
the flat modules had no eagerly-importing parent package. Fixed by making
those three imports lazy (function-local), matching how their own real
callers already used them.

## Naming collisions worth remembering

- `saleha/harness/` (SWE-bench helpers) vs. `saleha/core/harness/` (the real
  approval-gate/sandbox/test-runner implementation, see above) -- different
  things.
- `saleha/tools/` (the real ToolForge registry) vs. `saleha/core/tool_calling.py`
  (the LLM tool-calling dispatcher that uses it) -- different things, not
  competing.
- Root `tools/` (one standalone script, `code_quality_auditor.py`, invoked as
  `python -m tools.code_quality_auditor`) vs. `saleha/tools/` -- unrelated,
  name collision only.
- `saleha/skills/` (persona markdown) vs. `souls/` at the repo root (the real
  SoulSpec persona system, see `saleha/core/cognitive/soul_engine.py`) vs.
  `.agents/skills/` (packaged automation skills) -- three different things,
  see `ORCHESTRATOR.md` section 8.4a for the full reconciliation.
