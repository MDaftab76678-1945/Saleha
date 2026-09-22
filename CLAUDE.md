# Saleha

Local-first multi-agent AI coding assistant in Python. Runs against local models
via Ollama — no cloud, no API keys. Ships a CLI, a TUI, and a REST/SSE server.

## The one thing to understand

**This project's history is a history of components that claimed work they had
not done** — fabricated test counts, hardcoded "PASSED", orchestrators reporting
confident results without ever calling a model. The ongoing work is finding and
fixing those, one at a time.

**A fabricated pass is worse than a wrong answer.** A wrong answer gets caught by
the next person to look. A fake green is designed not to be. When a step cannot
run, it must say so — never return a reassuring default.

Two consequences that keep biting:

- **Old tests assert the fabricated behaviour** and pass forever while the
  feature is broken. When fixing a fabrication, check whether the existing test
  is pinning the bug in place, and replace it.
- **The giveaway is self-verification**: a component that generates the thing it
  then checks itself against cannot fail. When anything reports a measurement,
  ask first where the ground truth came from.

## Commands

```bash
# Tests. PYTHONIOENCODING is required — this console is cp1252.
PYTHONIOENCODING=utf-8 python -m pytest saleha/tests/ -q

# Pre-commit quality gate (also runs automatically on commit)
python .agents/scripts/preflight_lint.py

# TypeScript workspace — must stay green
npx turbo run typecheck
```

Never quote a pass/fail count from memory or from a doc. Run the suite.

## Code rules

1. **English only** in code, comments, docstrings and log strings. The user
   writes to you in Hindi; the code does not. Exception: non-English strings
   that are *data the feature needs* (detection patterns, keyword lists, test
   fixtures) stay — removing those has broken real features twice.
2. **Leave zero editor diagnostics behind.** Do not dismiss one as
   "pre-existing". If a diagnostic is genuinely wrong, say why.
3. **No decorative emoji anywhere.** They raise `UnicodeEncodeError` on this
   machine's cp1252 console. This is a live crash, not a style preference.
4. **Initialise a variable before the branches that assign it.**
5. **Read the whole surrounding area before editing**, not just the line you are
   fixing. The same bug usually has siblings in the same file.
6. **Think before writing, not after.** Name the inputs that can reach the code
   — empty, null, duplicate, malformed, "the step did not run" — and decide what
   each should do *before* writing it. Tests confirm; they are not how the edge
   cases get discovered.

## Environment

- **Python: use `.venv` (3.14.7).** `.venv_train` is 3.11 and below the
  `requires-python = ">=3.12"` floor — never run the suite there.
- `PYTHONIOENCODING=utf-8` on every test run (cp1252 console).
- `OLLAMA_HOST` is set scheme-less (`0.0.0.0:11434`). urllib cannot open that,
  and `0.0.0.0` is a bind address, not a client address. Normalise both.
- `pip install -e ".[dev]"` alone is not enough: Z3 lives in `[formal]`.
- `saleha-asi:latest` does not exist. It scored 0/5 and was deleted
  (commit `a464b68`). Do not assume it is there.
- The user runs other agents (Gemini/Antigravity) in parallel. Unexpected edits
  in the working tree are often theirs — check before claiming or reverting.

## Where things are

| Path | What |
| --- | --- |
| `saleha/core/` | Engines, partly organised into category subpackages |
| `saleha/cli/commands/` | CLI command implementations |
| `saleha/agents/` | Agent personas |
| `saleha/tests/` | The suite |
| `.agents/scripts/preflight_lint.py` | The commit gate |
| `NOTEBOOK_IMPORT.md` | Audit ledger — one section per pass, with evidence |
| `ORCHESTRATOR.md` | Architecture; section 8 indexes unaudited files |
| `COORDINATION.md` | Multi-agent notes (gitignored) |

Past audit passes live in the `audit-history` skill, not here — ask for it when
you need the history of a specific file or fix.

## What the user is building toward

Not instructions — direction. Keep it in view when choosing an approach.

- **The octopus.** Many independent agents, one coordinating mind.
- **Self-building.** The system should improve its own design, write its own
  functions, build its own tools.
- **Small beating large.** Local-first is a constraint to win inside, not a
  limitation to apologise for.
- **Do not play it safe.** When asked for options, include the ambitious one.

The honesty work serves this: a system that fabricates its own results cannot
improve itself, because it cannot tell what actually worked.

## Working with this user

- **Reply in Hindi/Hinglish**, short, answer first. No long preamble.
- **"Check karo" means check.** Report the findings and stop. Do not fix and
  commit unless asked.
- **Never say a file is "done" or "clear."** Say what was examined and what was
  found. A green test count is not proof — the tests may be asserting the bug.
- **Prove claims by running them.** Show the before/after of a real probe.
- **When told to choose, choose.** Do not hand the decision back.
- **Complete means complete.** One pass done properly beats five partial ones.
- **Be terse.** Minimal subagents, no over-testing, no narration.

## Keeping this file honest

This file is loaded in full at the start of every session, so its length is a
cost paid on every task. It was 2761 lines once, and the result was that its own
rules got ignored and nine of its own claims went stale.

- **Target: under 200 lines.**
- **No counts** — module totals, test totals, command totals, pass numbers.
  They go stale silently. Write the command that produces the number instead.
- **No line-number references** into this or any file. They rot on the next edit.
- **No code snippets.** Point at `file.py:123` instead; copies go out of date.
- Before adding a line, ask: *would removing this cause a real mistake?* If not,
  it belongs in a skill, a path-scoped rule under `.claude/rules/`, or nowhere.
