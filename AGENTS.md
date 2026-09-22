# AGENTS.md -- the one shared contract for every agent in this repo

Claude Code, Gemini / Antigravity, Cursor and Saleha's own agents all follow
this file. `CLAUDE.md` imports it; `GEMINI.md` and `.agents/rules/` point at
it. A shared rule lives **only here** -- if another file disagrees, this file
wins and the other file is the bug.

**Saleha**: local-first multi-agent AI coding assistant in Python. Runs against local models
via Ollama -- no cloud, no API keys. Ships a CLI, a TUI, and a REST/SSE server.

## The one thing to understand

**This project's history is a history of components that claimed work they had
not done** -- fabricated test counts, hardcoded "PASSED", orchestrators reporting
confident results without ever calling a model. The ongoing work is finding and
fixing those, one at a time.

**A fabricated pass is worse than a wrong answer.** A wrong answer gets caught by
the next person to look. A fake green is designed not to be. When a step cannot
run, it must say so -- never return a reassuring default.

- **Old tests assert the fabricated behaviour** and pass forever while the
  feature is broken. When fixing a fabrication, check whether the existing test
  is pinning the bug in place, and replace it.
- **The giveaway is self-verification**: a component that generates the thing it
  then checks itself against cannot fail. When anything reports a measurement,
  ask first where the ground truth came from.

### Shapes that have shipped here before -- never repeat them

| Shape | Seen in | What it looked like |
| --- | --- | --- |
| Success without execution | `saleha/orchestrator.py` | `success=True` without running the code |
| Hardcoded verdicts | `/autopr`, `omni_arena_engine.py`, `agent_council.py` | "5/5 PASSED", fixed 97% / 93.3 scores |
| Rubber-stamp checks | `constitutional_guard.py`, `threat_modeler.py` | COMPLIANT for a disk wipe; threats on an empty dir |
| Vacuous metrics | static tools | 100% for an empty set instead of 0 / "empty" |
| Self-graded pass | `alignment/verifiable_rewards.py` | candidate `sys.exit(0)` skipped its tests and scored as passed |
| Suppress-and-call-it-repaired | `self_correction.py`, `workflow/self_healing_node.py` | crash wrapped in `except: return None`, or a missing key filled with `None`, reported as HEALED |
| Consensus theater | `swarm/octopus_swarm_expansion.py` | a "BFT vote" on a hardcoded snippet |
| Success without the side effect | `platform/lora_adapter_hot_swapper.py`, `db/migration_safety_verifier.py` | "switched" after only writing a Modelfile; "reversible" because `down()` ran |
| Test pinning | many | tests asserting the fake value (`assert score == 93.3`) |

## Commands

```bash
# Tests. PYTHONIOENCODING is required -- this console is cp1252.
PYTHONIOENCODING=utf-8 python -m pytest saleha/tests/ -q

# Commit gate (also runs automatically on commit). Never bypass it.
python .agents/scripts/preflight_lint.py

# TypeScript workspace -- every workspace must pass
npx turbo run typecheck
```

Never quote a pass/fail count from memory or from a doc. Run the suite.

## Code rules

1. **English only** in code, comments, docstrings and log strings. The user
   writes in Hindi; the code does not. Exception: non-English strings that are
   *data the feature needs* (detection patterns, keyword lists, test fixtures)
   stay -- removing those has broken real features twice.
2. **Leave zero editor diagnostics behind.** Do not dismiss one as
   "pre-existing". If a diagnostic is genuinely wrong, say why.
3. **No decorative emoji anywhere.** They raise `UnicodeEncodeError` on this
   machine's cp1252 console. This is a live crash, not a style preference.
4. **Initialise a variable before the branches that assign it.**
5. **Read the whole surrounding area before editing**, not just the line you are
   fixing. The same bug usually has siblings in the same file.
6. **Think before writing, not after.** Name the inputs that can reach the code
   -- empty, null, duplicate, malformed, "the step did not run" -- and decide what
   each should do *before* writing it. Tests confirm; they are not how the edge
   cases get discovered.
7. **Windows first.** `pathlib.Path` for paths; no POSIX-only modules
   (`resource`, `fcntl`) or signals without a guard.

## What you may do without asking

- **"Check karo" means check**: read whole files, run read-only probes and the
  tests to prove each finding, report, stop. No edits, no commits.
- **Edit only when asked to fix or build. Commit only when asked to commit.**
  Never push unless asked.
- Stage exact paths only -- never `git add .`, `git add -A` or `git commit -a`.
- Never run destructive git (`reset --hard`, `checkout .`, `clean`,
  `branch -D`) or discard uncommitted work without an explicit ask.

## Environment

- **Python: use `.venv` (3.14).** `.venv_train` is 3.11, below the
  `requires-python = ">=3.12"` floor -- training scripts only, never the suite.
- `PYTHONIOENCODING=utf-8` on every test run (cp1252 console).
- `OLLAMA_HOST` is set scheme-less (`0.0.0.0:11434`). urllib cannot open that,
  and `0.0.0.0` is a bind address, not a client address. Normalise both.
- `pip install -e ".[dev]"` alone is not enough: Z3 lives in `[formal]`.
- Local models: run `ollama list` for what is installed now. `qwen2.5-coder:3b`
  and `qwen3:8b` are the working pair; 3B/8B context is small, so never feed
  whole multi-file dumps into one prompt.
- `saleha-asi:latest` does not exist. It scored 0/5 and was deleted
  (commit `a464b68`). Do not assume it is there.

## Working alongside other agents

- Claude and Gemini work in the same main worktree. **Unexpected edits in the
  working tree are often the other agent's** -- check `git status` and
  `COORDINATION.md` (gitignored) before claiming or reverting anything.
- Do not edit a file another agent is mid-way through. Record results and
  measured numbers in `COORDINATION.md` when you finish.
- Record every audit pass, with evidence, in `NOTEBOOK_IMPORT.md`.

## Where things are

| Path | What |
| --- | --- |
| `saleha/core/` | Engines: flat modules plus category subpackages (see `saleha/STRUCTURE.md`) |
| `saleha/cli/commands/` | CLI command implementations |
| `saleha/agents/` | Agent personas |
| `saleha/tests/` | The suite |
| `.agents/scripts/preflight_lint.py` | The commit gate |
| `NOTEBOOK_IMPORT.md` | Audit ledger -- one section per pass, with evidence |
| `ORCHESTRATOR.md` | Architecture; section 8 indexes unaudited files |
| `COORDINATION.md` | Multi-agent notes (gitignored) |

## What the user is building toward

Not instructions -- direction. Keep it in view when choosing an approach.

- **The octopus.** Many independent agents, one coordinating mind.
- **Self-building.** The system should improve its own design, write its own
  functions, build its own tools.
- **Small beating large.** Local-first is a constraint to win inside, not a
  limitation to apologise for.
- **Do not play it safe.** When asked for options, include the ambitious one.

The honesty work serves this: a system that fabricates its own results cannot
improve itself, because it cannot tell what actually worked.

## Working with this user

- **Reply in Hindi/Hinglish, in one line, in simple words.** Answer first. No
  headers, bullet lists or tables unless asked; detail goes in commit messages.
- **Never say a file is "done" or "clear."** Say what was examined and what was
  found. A green test count is not proof -- the tests may be asserting the bug.
- **Prove claims by running them.** Show the before/after of a real probe.
- **When told to choose, choose.** Do not hand the decision back.
- **Complete means complete.** One pass done properly beats five partial ones.
- **Be terse and cheap.** Minimal subagents, no over-testing, no narration.

## Keeping these files honest

Every session loads this file in full, so its length is a cost paid on every
task. `CLAUDE.md` was 2761 lines once, its own rules got ignored, and nine of
its claims went stale.

- **Target: under 200 lines.**
- **No counts** -- module totals, test totals, command totals, pass numbers.
  They go stale silently. Write the command that produces the number instead.
- **No line-number references** into this or any file. They rot on the next edit.
- **No code snippets.** Point at a file instead; copies go out of date.
- Before adding a line, ask: *would removing this cause a real mistake?* If not,
  it belongs in a skill, a path-scoped rule, or nowhere.
