# Saleha — working context

This file loads automatically at the start of every session. Read it before
doing anything else. It exists so the user never has to re-explain the project.

---

## What this project is

Saleha is a local-first, multi-agent AI coding assistant in Python. It runs
against local models via Ollama. It has a CLI (100+ subcommands), a TUI, a
REST/SSE web server, and ~220 modules under `saleha/core/`.

`README.md` describes what actually works. `ARCHITECTURE.md` describes how the
pieces fit and which commands are honest. `ROADMAP.md` is for things that do
not exist yet.

---

## What the current work actually is

**This project's central problem is that it lied about itself, and the ongoing
work is fixing that — one component at a time.**

Almost every recent commit has the same shape: something claimed it did work it
had not done. Not missing features — false claims. Examples from git history:

- the work ledger claimed a guarantee it did not have
- `godel-utility` printed AUTHORIZED about a refactoring that never happened
- `optimize-prompts` learned from an error that never occurred
- four orchestrators reported confident results without calling a model
- `SALEHA_APPROVAL=dangerous` did not actually gate file writes
- the solution cache served one model's answer as another's
- `/autopr` fabricated "5/5 PASSED" and "0 CWE vulnerabilities"

This is tracked pass by pass in `NOTEBOOK_IMPORT.md` (13 passes as of
2026-09-07). Each pass: find something that claims more than it does, replace
the fake half with something measured, write down the measurement.

### The rule that matters

**A fabricated pass is worse than a wrong answer.** A wrong answer gets caught
by the next person to look. A fake green is designed not to be. When a step
cannot run, it must say so — never return a reassuring default.

### The trap that keeps repeating

**Old tests assert the fabricated behaviour.** They pass forever while the
feature is broken, because they were written against the fake. Examples found:

- `assertIn("HighThroughputService", res.consensus_code)` — the hardcoded template
- `assert result.tests_passed is True` — the hardcoded fabrication
- the emergence tests called `record_message()` themselves, so they never
  noticed that nothing in production ever called it

So when fixing one of these, **check whether the existing test is pinning the
bug in place**, and replace it.

---

## How to audit a file in this repo (this is not optional)

The user has had to repeat this. Do not make them repeat it again.

1. **Read the whole file with `Read`. Not `grep`.** A `grep` for one pattern
   finds one bug and hides the rest. `saleha/orchestrator.py` was "checked"
   three separate times with grep; the fourth time, read in full, it had six
   more bugs — including one sitting on a line that had already been scrolled
   past twice.
2. **Report the full list of findings, then stop.** Do not fix and commit
   unless asked. "Check karo" means check.
3. **Never say "done" or "clear" about a file.** Say what was examined and what
   was found. A green test count is not proof a file is clean — the tests may
   be asserting the bug.
4. **Prove claims by running them.** Every finding in `NOTEBOOK_IMPORT.md` has a
   measurement next to it. Probe the defect, show the before/after.
5. **Check git and the docs before asking the user a question.** The answer is
   often already recorded. (`saleha-asi`'s deletion was in commit `a464b68`'s
   message the whole time it was being asked about.)

---

## Code quality rules — non-negotiable

1. **Code, comments, docstrings and log strings are English.** Only English.
   `orchestrator.py` had three languages mixed into one file — Devanagari
   Hindi, romanised Hinglish, and English, sometimes in the same function.
   That is not reviewable by anyone but the person who wrote it. The user
   writes to you in Hindi; the code does not.
2. **Leave zero editor diagnostics behind.** Do not dismiss a warning as
   "pre-existing" and move on. `orchestrator.py` carried ten
   `log may be uninitialized` errors and an `unnecessary int()` warning that
   were seen and skipped over on repeated edits, until the user had to point
   at them. If a diagnostic is genuinely wrong, say why; otherwise fix it.
3. **No decorative emoji in code or log output.** They break on cp1252
   consoles (this machine's default), which is why every test run here needs
   `PYTHONIOENCODING=utf-8`. Plain text says the same thing and always renders.
4. **A variable assigned only inside branches must be initialised first.**
   That was the exact cause of the ten errors above.

---

## Where the project state is written down

| File | What it holds |
| --- | --- |
| `NOTEBOOK_IMPORT.md` | The audit ledger. Every pass, what was found, what was measured. **Append a new section per pass.** |
| `ARCHITECTURE.md` | What each subsystem really does; which CLI commands are real vs template. Update entries when they change — a stale "this is broken" note costs as much trust as a stale "this works". |
| `COORDINATION.md` | Multi-session coordination notes (gitignored, local only). |
| `README.md` | User-facing, honest description of working features. |
| `ROADMAP.md` | Things that do not exist yet. Speculative claims belong here, not in README. |

---

## Known open work (as of 2026-09-07)

Verify these are still true before acting — they may have been fixed since.

**`saleha/orchestrator.py` — all known defects fixed** (passes 13-15): the
unverified-success path, `git add .` on auto-commit, the hardcoded
`test_passed=True`, the cache's verified-vs-did-not-crash conflation, the
missing checkpoint on the blocked exit, and profile drift on resume. The file
also reports zero editor diagnostics and is English-only.

**All commands from the 2026-09-06 audit are now honest** (passes 16-18):
`cloud-plan`, `silicon-build`, `multirepo`, `causal-eval`, `quantum-sim`,
`cognitive`, `constitutional-check`, `explain-code`, `emergence-check`.

**The fabricated benchmark scoreboard is fixed** (pass 20):
`omni_arena_engine.py` labels its literals `target_scores` with
`is_measured=False`; the two `evaluate_artificial_analysis_*` scripts no longer
print invented scores for other people's models or unconditional "Mastery
Achieved" verdicts; `verify_all_live_proofs.py` was rewritten (it had also been
crashing unnoticed on fields `formal_smt_verifier` no longer has) and now runs
5/5 real checks.

**`multi_file_auto_repair.py` is fixed** (pass 21): the commit phase is
genuinely atomic (restores every file already written when a write fails),
patching is AST-based so string literals survive, guarded constants are
declined instead of rewritten into dead code, and a miss is no longer reported
as a clean scan.

**The TypeScript workspace is fixed** (pass 22): `turbo run typecheck` went
from "0 successful, 6 total, FAILED" to 8/8. Four packages ran `tsc --noEmit`
with no tsconfig anywhere; `packages/core`'s bare `tsc` build exited 0 while
compiling nothing. Versions aligned (3 dependency conflicts → 0), and
`test_monorepo_architecture.py` now fails if they drift again.

**`saleha resolve-issue` is fixed** (pass 23): it raised `NameError:
UnifiedDiffResult` on every real invocation, and behind that crash reported
"All 12 unit tests passed in 0.42s" under a "Verification Proof" heading that
`--auto-pr` would publish to a real PR.

**Python versions are aligned** (pass 24): ruff/pyright said 3.10 while
`requires-python` said 3.12 and the venv ran 3.11. `setup.py` deleted (it
duplicated `pyproject.toml` and had drifted).

**The full test suite had never once completed — fixed** (pass 30). Fixing
`swarm_pipeline_engine.py` (above) required a full-suite run to check for
side effects; it hung indefinitely. Investigation found no `conftest.py`
existed anywhere in the project, so `SALEHA_TEST_MODE` — which three modules
already checked to route around real model calls — was never actually set
for a normal `pytest saleha/tests/` run, only when someone remembered to
export it by hand. Added `saleha/tests/conftest.py` to set it session-wide,
then found and fixed three separate modules that each independently hung
the suite for 15+ minutes on an unguarded real Ollama call:
`ttc_solver.py` (the REPL's `model="mock"` never reached its module-level
singleton), `demo_cli.py`'s `dogfood_cmd` (which also turned out to
fabricate "ALL 9 ENGINEERING PILLARS VALIDATED" while checking only 6, all
hardcoded PASS — fixed alongside the hang, see NOTEBOOK_IMPORT.md), and
`BaseAgent.__init__` (the root fix, since any future module built on
`BaseAgent` would have hit the same gap). Fixing the third one broke 7 tests
that were relying on real fallback behavior the mock now short-circuited —
both breaks were genuine test-intent conflicts, not fixed by reverting;
resolved by narrowing both guards (`self.inference is None`,
`model != "mock"`). Final verified result:
`1686 passed, 14 skipped, 60 subtests passed in 80.31s` — zero failures, no
manual setup. Full multi-stage writeup in `NOTEBOOK_IMPORT.md`, "Thirtieth
pass".

**Design UI synthesis commands are templates** (pass 30 finding):
`design-vision` (CLI in `voice_vision.py` line 104–115) calls
`vision_designer.synthesize_from_wireframe()`, which **generates hardcoded
HTML/CSS/JSX regardless of input**. Probe: `"login form"` and `"dashboard
with charts"` both return identical `components = ["HeaderBar", "MetricsGrid",
"ActionCard", "StatusBadge", "FooterNav"]` and the same 6-color palette —
a login form has no metrics grid. The JSX `<h1>{clean_prompt[:50]}</h1>` copies
the first 50 chars of input; everything else (button styles, card layout, CSS
rules) is the same literal every time. No layout-type inference, no vision
model call. `design-model` (line 113–124 in `research_experimental.py`) calls
`neural_designer.design_transformer()`, which always returns the same
NeuralArchitectureSpec defaults (512 dims, 8 heads, 6 layers, 32000 vocab)
regardless of input name — two different `design-model MySmall` and
`design-model MyHuge` calls return parameters differing only in the name field
in the returned string, not in the actual architecture. Not yet fixed. No
production caller for either.

**Full 139-command triage is done** (pass 30). Roughly 100 commands are real,
19 were already covered by earlier passes, and six new fabrications were
found. One fixed:

- **`leaderboard` — fixed (pass 30).** Deleted entirely, not rewritten:
  `saleha/core/leaderboard_generator.py`, the CLI command in
  `testing_bench.py`, and `test_leaderboard_generator.py` (which asserted the
  fabricated numbers were present — pinning the bug, same trap as always).
  This project has no real SWE-Bench Lite measurement for itself, let alone
  for Devin/Claude Code/Cursor, so there was no honest version of "compare
  Saleha to named competitors" to fall back to — the command should not
  exist until real cross-tool measurement exists (that belongs in
  `ROADMAP.md`, not shipped as a live command). Note: `saleha harness
  leaderboard` is a different, unrelated command (`harness_group.py` ->
  `saleha/harness/reporter.py`) that ranks models from real stored run
  history and correctly says "No records found" when empty — left alone,
  it was never fabricating anything. Verified: `cli.commands` still
  registers 154 commands post-deletion, `pytest -k "leaderboard or
  testing_bench or cli_commands"` 20/20 pass.

- **`swarm_pipeline_engine.py:222` — fixed (pass 30).** `tests_passed = True`
  was hardcoded in the QALead stage regardless of whether a test ran; the
  overall `success` flag was also hardcoded True, ignoring both this and
  SecurityGuard's result. Now runs the generated source + test code for real
  through `CodeExecutor` (same sandboxed runner `orchestrator.py` uses) and
  sets `success = is_secure and tests_passed`. Fixing this immediately
  exposed a second, previously-invisible bug: `qa_lead.py`'s fallback test
  template built function names directly from the task string, so a goal
  containing a hyphen (`"thread-safe rate limiter"`) produced an invalid
  Python identifier (`def test_thread-sa_happy_path():`) — a SyntaxError
  that could never be caught while `tests_passed=True` meant nothing ever
  ran the code. Fixed with a `re.sub(r"\W+", "_", ...)` slug sanitizer.
  Verified: `test_swarm_pipeline_and_bus.py` 10/10,
  `test_enterprise_architecture.py` 9/9, `test_issue_resolver*.py` 23/23 —
  the only three test files that import either module.

- **`solve-issue` — fixed (pass 30).** Was two commands in the same file
  (`testing_bench.py`), both defined `@cli.command(name='solve-issue')`;
  Click kept only the second, so the first (wired to
  `saleha/core/ticket_resolver.py`) was dead code, unreachable from the CLI,
  that also hardcoded `reproduction_test_written=True` with nothing ever
  written. Deleted the dead code (the module, its test, and the first command
  definition) rather than fixing something nothing can call. The live command
  (`agents/issue_resolver.py`) had two separate fabrications: `test_code` was
  a hardcoded literal (`"def test_regression(): assert True\n"`) for every
  issue regardless of what the swarm pipeline generated — now pulls the real
  test code the QALead stage actually produced (see the
  `swarm_pipeline_engine.py` fix above); and the PR markdown unconditionally
  printed `"AST Syntax Verification: Clean (0 Syntax Errors)"` with no `ast`
  call anywhere in the class — added a real `ast.parse()` check, and all
  three verification-gate lines (AST/security/tests) now render an unchecked
  box with the actual reason when a check did not pass. Verified: 42/42
  tests across the four related test files, plus a manual CLI invocation
  confirming genuinely generated test code in the output.
- **`pr_generator.py` — fixed (pass 30).** Two badges ("Status: Verified
  (100%)", "Security: Audit Passed") were hardcoded green unconditionally;
  now read `team_res.success` and the security stage's real verdict
  (Approved/Warnings/Vulnerable, parsed the same way the pipeline's own
  security gate already parses it). An empty `execution_output` also
  silently became the literal "All unit tests passed successfully." — now
  distinguishes a genuine no-output success from a failure, surfacing the
  real `execution_error` when there is one. Verified: `test_pr_generator.py`
  4/4; a success case and a failure case (VULNERABLE security report, real
  AssertionError) confirmed to render genuinely different badges and log
  text, not just different in theory.
- **`quadratic-vote` — fixed (pass 30).** The underlying
  `QuadraticVotingEngine` was always real (correct `votes**2` cost formula,
  real tally logic) — the bug was entirely in the CLI, which took no
  arguments and replayed one hardcoded scenario every run. Now takes a real
  `TITLE` argument and repeatable `--vote agent:count` options; two
  different invocations produce genuinely different Net Votes /
  APPROVED-REJECTED output. Verified: 5/5 tests (1 existing engine test +
  4 new CLI tests), including malformed-input rejection and negative
  (opposition) votes computing correctly.
- **`merkle-audit` — fixed (pass 30).** `merkle_provenance.py`'s SHA-256
  hashing and tamper-detection were always real — the bug was that nothing
  in production ever called `record_event()`, so the ledger was always
  empty and the command's "Ledger is empty and untampered." was honest but
  useless as an audit trail. Wired `record_event()` into
  `swarm_pipeline_engine.py`: every completed stage now records one real
  leaf. Running `execute_swarm` took a fresh ledger from 0 to one leaf per
  stage, with genuine cryptographic verification (a real root hash) instead
  of the empty-ledger message. Verified with a new test asserting the leaf
  count delta equals `len(result.stages)` exactly. Follow-up: `saleha
  merkle-leaves` (new command) lists the individual leaves — `merkle-audit`
  only ever reported pass/fail on the whole chain, not what is in it.
  Remember the ledger is an in-memory singleton: a swarm run in one process
  and `merkle-leaves` in another will show empty, which the command's own
  empty-state message says explicitly.
- **`snapshot`/`rollback` — fixed (pass 31).** `time_machine.py`'s docstring
  promised "In-memory and disk persistence"; there was no disk anything (the
  `json` import was unused) and `time_machine` was a module-level singleton,
  so `saleha snapshot` and `saleha rollback` — two separate processes — never
  saw each other's state and `rollback` always printed "No snapshots
  available." Each snapshot is now written to `.saleha/snapshots/<id>.json`
  (already gitignored); `rollback`/`list_snapshots`/pruning all read the
  directory, so there is no in-process state to diverge. Corrupt JSON is
  skipped on load. Probe: a snapshot taken in one process is now rolled back
  from a second. Verified: `test_time_machine.py` 5/5 (new
  `test_snapshot_persists_across_instances` fails against the old version),
  full suite `1697 passed`. Detail: `NOTEBOOK_IMPORT.md`, "Thirty-first pass."

All six fabrication findings from the 139-command triage are now fixed.
Full detail and evidence for each: `NOTEBOOK_IMPORT.md`, "Thirtieth pass."

**Older candidates:**

- `swe_repo_fixer.py` — **deleted (commit `f9814b6`, pass 30-adjacent).**
  Was a pure template: two unrelated issues gave identical
  `root_cause_analysis`, `tests_passing=True` with nothing run, target files
  chosen by `if "auth" in desc`. The chat REPL's `/swe-fix` handler now
  points at the real `saleha resolve-issue`. `extreme_contrastive_trainer.py`
  and `apex_97_validator` deleted in the same commit for the same reason
  (constant `final_loss 0.12` regardless of input; eight hand-typed "Rank #1"
  scores).
- `docs_generator.py` (187), `swarm_self_play_arena.py`, `code_executor.py`
  (the unused import there is likely harmless — it is a real, working sandbox).

**`quality_guard.py` — three design issues fixed (commits `2d5915a`,
`ade661b`, plus follow-ups `d0e237b`/`121c55b`).** The `SOV-001` "brand leak"
rule that failed a file for naming a model it calls is removed entirely; the
score still clamps at 0.0 but keeps `raw_score` uncapped so 25 and 400
untyped functions are distinguishable for ranking; `check_workspace` now
returns explicit `files_found`/`files_analyzed`/`truncated`/`scan_is_complete`
keys instead of a silent 50-file sample. 17 tests pass.

**`saleha/sandbox/` — Windows import fixed (commit `4d248a6`).** The
unguarded POSIX-only `import resource` in `sandbox_jail.py` is now guarded;
the module imports on Windows and exposes `is_available()` /
`unavailable_reason()`, and `run_isolated()` raises `SandboxUnavailableError`
rather than executing code with none of its limits applied.
`NOTEBOOK_IMPORT.md`'s old "Real sandbox" row (line 13) predates this and is
stale — the jail is real but does not run here.

**Unrelated, still open:** the repo carries both `package-lock.json` and
`pnpm-lock.yaml`, which is what the IDE's "multiple lockfiles" warning is
about. Nobody has decided which package manager this project uses; that is the
user's call, not a defect to fix silently. `templates/` holds three scaffolds
(`nodejs_express`, `go_service`, `python_fastapi`) that **no code reads** —
worth deciding whether they should exist before maintaining them.

**Branch state:** work happens on `test-issue-101`. It is many commits ahead of
`origin/test-issue-101` and has not been pushed. `main` is behind.

---

## Environment facts worth knowing

- Models installed: `qwen2.5-coder:3b` (the default everything uses),
  `qwen3:8b`, `qwen3.5:9b`, `qwen3.5:4b`, `deepseek-coder:6.7b`,
  `deepseek-r1:7b`, `nomic-embed-text`, `gemma4:31b-cloud`.
- `saleha-asi:latest` was the project's own fine-tune. It scored **0/5** on real
  held-out tasks and was deleted in commit `a464b68` — its training data
  contained fabricated rows since purged. It no longer exists; do not assume it
  does.
- `OLLAMA_HOST` on this machine is set scheme-less (`0.0.0.0:11434`). urllib
  cannot open that, and `0.0.0.0` is a bind address, not a client address.
  Normalise both when talking to Ollama directly.
- **Python: use `.venv` (3.14.7), not `.venv_train`.** `.venv_train` is the old
  3.11.16 environment — a version `requires-python = ">=3.12"` forbids and CI
  never tests. It is kept only because it holds `torch` (4.27 GB of its 5.3 GB)
  for the LoRA/training path that ten modules import. Everyday work belongs in
  `.venv`.
- `pip install -e ".[dev]"` alone does **not** give a passing test run: two SMT
  tests need `z3-solver`, which lives in the `[formal]` extra. A working test
  environment also wants `tree-sitter*` and `numpy`.
- Test suite: `python -m pytest saleha/tests/ -q` — 1693 passed, 14 skipped,
  60 subtests, ~80-130s. Set `PYTHONIOENCODING=utf-8`; the console is cp1252 and
  emoji in output will otherwise crash the run. `saleha/tests/conftest.py`
  sets `SALEHA_TEST_MODE=1` for the whole run automatically — no manual
  export needed as of pass 30. Before that fix the suite had never once
  completed: three separate modules (`ttc_solver.py`, `demo_cli.py`,
  `base_agent.py`, see "Known open work" below) made unguarded real Ollama
  calls and could hang 15+ minutes each. If a test hangs again, it is very
  likely the same shape of bug — a module reaching a real model call it
  should have mocked under `SALEHA_TEST_MODE`.
- TypeScript: `npx turbo run typecheck` must stay at 8/8. It was 0/6 and
  failing until pass 22.
- `radon` is a dev dependency; `test_mech_interp.py` cross-checks our own
  cyclomatic complexity against it (472 functions, 0 mismatches).

---

## How the user wants you to work

These are not guesses. Each one was said repeatedly across sessions between
2026-09-03 and 2026-09-07, in the user's own words, and each was ignored at
least once. Do not make them say it again.

### "Complete" means complete — said six times

> "tumne notebook ke files ko **thik se analyze nhi kiya**" (03 Sep)
> "**ye complete nhi hai**" (03 Sep)
> "teri analysis mein kami hai, **deep dive kar**, ek bhi folder file bina miss kiye" (06 Sep)
> "**abhi bhi complete nhi hai** teri deep dive" (06 Sep)
> "**complete ka kya matlab hota hai janta hai**" (06 Sep)
> "**ek baar main kaam complete hona chahiye** — no gap missing no anymore
> problems. apne kaam ko check kar **uske baad** final done karna" (06 Sep)

One pass, done properly, beats five partial passes. Read everything before
concluding. Never declare something finished that was only partially examined.
This was violated as recently as 2026-09-07 (see the audit rule above).

### Token use — said once, still binding

> "tum bohut jada token use kar rahe ho, token ka use **80% tak kam karo** aur
> baki kaa kaam complete karo" (04 Sep)

Be terse. No unnecessary subagents. No over-testing. But note the second half —
reducing tokens does not mean leaving work unfinished.

### Explain simply — said four times

> "kya karna chahte ho **asan sabdo main** batao" (03 Sep)
> "**asan sabdo mein samjha**" (05 Sep)
> "kehna chahta hai **tarike se kyu nhi batata** hai" (06 Sep)
> "ek line mein bata **asan sabdo mein**" (07 Sep)

Short, plain Hindi/Hinglish. Lead with the answer. No long technical preamble.

### Decide — do not hand the decision back — said five times

> "tum chuno" (03 Sep) · "tum batao kya karna chahiye" (04 Sep) ·
> "tum chuno" (04 Sep) · "jaisa tumhe sahi lage" (06 Sep)
> "ab main **sab kuch teri upar chhod raha hai** ... ek idea aur plan bana jo
> tere hisab se sahi ho aur vo kar" (06 Sep)

When told to choose, choose. Do not close every message with a question that
returns the decision. Ask only when the choice is genuinely the user's — their
model, their data, their repo history.

### Persistent state, so nothing is re-explained — asked for twice before it existed

> "pura directory structure sahi karo, **fir baar baar samjhne mein problem
> nhi aayega**" (05 Sep)
> "tere pas auto reports hona chahiye ... **bina mere bataye** jab bhi naya
> session open karu automatically tujhe sab pata chal jaye" (07 Sep)

That is what this file is. Keep it current. When something significant is
found, fixed, or decided, update it — that is not overhead, it is the point.

---

## Engineering principles to work by

The user asked that this project be built with the mindset of the people who
built the foundations. Names alone change nothing — this project spent fourteen
passes deleting code that claimed authority it had not earned, and a list of
famous names would be exactly that again. So each entry below is one concrete,
testable rule, paired with the real defect in *this* repository that it would
have caught.

### Measure, do not assert — Hinton

Backpropagation was accepted because it was demonstrated, not argued. Every
claim in this codebase needs a number next to it. `NOTEBOOK_IMPORT.md` follows
this already: BM25 shipped with `short_answer 2.99 vs long_noise 1.16`, not
"BM25 works now".

*Caught:* `agent_council` scored every proposal 93.3/100 with no measurement
behind the number. `explain-code` reported a 0.95 "saliency" that was a
per-bucket constant.

### Talk to the machine, not about it — Torvalds

"Talk is cheap. Show me the code." Do not describe a fix — apply it and show
the before/after. A defect is not real until it is reproduced, and not fixed
until the reproduction flips.

*Caught:* the orchestrator's fake success was only provable by writing a probe
that returned `success=True, verifier calls: 0` for `1/0`, then showing the
same probe return `success=False, verifier calls: 1`.

### Readable beats clever — van Rossum

Code is read far more than written; there should be one obvious way to do it.
This is the direct source of the English-only rule above: `orchestrator.py` had
three languages in one function, which is unreadable to everyone but its author.

*Caught:* 87 mixed-language strings, including Hindi prompts being sent to a
code model.

### Simple enough to be obviously correct — Ritchie

Unix tools did one thing. Complexity hides bugs; small honest pieces do not.
Prefer deleting a fake abstraction over decorating it.

*Caught:* four "orchestrators" that made zero model calls. The right fix for
`repo_orchestrator` was not more scaffolding — it was to delete the fabrication
and read real `git status`.

### Solve the exact problem, fast, then verify — Korotkevich

Competitive programming discipline: correctness first, then speed, and always
against real test data. Do not optimise what has not been measured.

*Applied:* `parallel_candidates` ships with a real measurement (5 concurrent
calls 15.5s vs ~34s sequential) and is off by default, because it costs N times
the tokens.

### Reason from first principles — Musk

Ask what the thing must actually do, not what the existing code does. The best
part is no part. When a component is a template, question whether it should
exist before rebuilding it.

*Caught:* `cloud-plan`, `silicon-build`, `causal-eval` and `multirepo` all
generate constants. The first-principles question is not "how do we improve
these" but "should these commands exist at all".

### Build for the person who arrives later — Berners-Lee

The web worked because it was open and decentralised. Every artifact here must
be usable by someone with no context: honest READMEs, real error messages,
`CLAUDE.md` itself. A tool that only its author can operate has failed.

*Caught:* the project had no `CLAUDE.md` at all until 2026-09-07, so every
session began by asking the user to re-explain their own project.

### Ship, then iterate on real feedback — Zuckerberg

Working software beats a perfect plan, but only when the feedback loop is real.
Ship the honest version now; do not hold it for the grand rewrite.

*Guard:* "move fast" is not licence to fabricate. A fake pass destroys the
feedback loop entirely — you cannot iterate on a result you invented.

### Make it work at scale for real users — Pichai

Ask what happens on someone else's machine. Defaults matter more than options,
because most people never change them.

*Caught:* `auto_commit` ran `git add .`, which on a real user's machine commits
their unrelated uncommitted work. It was the default path, and every caller
took it.

### Rebuild the culture, not just the code — Nadella

Growth mindset: "I was wrong" is information, not defeat. Fix the process that
produced the bug, not only the bug.

*Applied:* when a test of mine asserted an impossible Gini > 0.70 for two
agents, the fix was to correct the test and document the `(n-1)/n` bound — the
implementation was right. When four `orchestrator.py` requests were answered by
grepping, the fix was the audit rule at the top of this file, not just one file.

### Ship the pragmatic thing under real constraints — Eich

JavaScript was written in ten days under impossible constraints and still had
to work. Real constraints here: one GPU, local models, no cloud budget. Design
inside them instead of pretending they are absent.

*Applied:* speculative decoding was deferred because one GPU cannot hold 8B +
1B. Activation-patching interpretability was dropped because Ollama does not
expose activations — replaced with leave-one-out ablation, which the
architecture *can* do.

### Safety is an engineering property, not a disclaimer — D. Amodei

A system that cannot report its own failures cannot be trusted or improved.
Interpretability and honest self-report are engineering work, not paperwork.

*This is the core thesis of the entire audit.* A fabricated pass is worse than
a wrong answer, because a wrong answer gets caught and a fake green is designed
not to be.

### Guardrails belong in the code, not the docs — Danielle Amodei

Policy that is not enforced by the system is not policy. If a dangerous action
must be gated, gate it in code and test the gate.

*Caught:* `SALEHA_APPROVAL=dangerous` did not gate `file_write` — the docstring
claimed it did. `git reset --hard` was ungated while `file_delete` was gated.
Both are in `DANGEROUS_ACTIONS` now, with tests that fail if a call site is
added without one.

### The synthesis

These agree on one thing: **an honest system that reports what it actually did
is the precondition for everything else.** The user's goal is a system that
improves itself. A system that fabricates its results cannot — it has no signal
to learn from. The audit work in this repository is not cleanup before the real
project; it *is* the foundation the self-improving system needs.

---

## The user's vision for Saleha

Not instructions — this is what they are building toward. Keep it in view.

- **The octopus.** "Octopus ke paas nau dimag hote hain. Ye system bilkul
  octopus jaisa hai — har ek ke paas apna dimag, par ek main dimag hoga."
  (03 Sep) Many independent agents, one coordinating mind.
- **Self-building.** "isse **khud ko build karne do** — apne design ko improve
  kar sake, naye functions bana sake, apne liye tools bana sake" (04 Sep)
- **Small beating large.** "4GB wale model ko 200B se behtar banane ka koi naya
  tareeka find kar" (06 Sep) Local-first is a constraint to win inside, not a
  limitation to apologise for.
- **Do not play it safe.** "tum **darte kyu** ho, zyada nahi sochna chahiye —
  hum wo kar sakte hai jo koi nahi kar sakta" (04 Sep) When asked for options,
  include the ambitious one; do not only offer the conservative path.

The honesty work in this file serves that vision — a system that fabricates its
own results cannot improve itself, because it cannot tell what actually worked.

---

## Quality pipeline: design-level checks for new commands

Every new CLI command or agent must pass a design audit before shipping:

1. **Probe inputs across the range.** Two different calls with meaningfully
   different inputs must produce meaningfully different outputs. If
   `design-model SmallNet` and `design-model MassiveNet` return architectures
   differing only in the name string (same layer counts, dims, etc.), the
   command is a template.

2. **Check for missing model calls.** If a command claims to reason, generate
   code, analyze a file, or use ML, count calls to the model in production code.
   If the count is zero and there are no comments explaining why, it is
   fabricated.

3. **Trace the data flow.** Follow input → processing → output in the code.
   If processing is hardcoded or deterministic regardless of input, say so
   explicitly in ARCHITECTURE.md or ROADMAP.md.

4. **Run, don't just read.** Import the module, call it with test data, inspect
   the return value. Never declare a feature done from a grep alone.

5. **Document in NOTEBOOK_IMPORT.md.** When a command is confirmed real or
   template, record the probe that proved it: "called with X and Y, got
   identical output" or "called 1 model invocation with input Z."

Current checklist for existing commands — **all 139 CLI commands triaged as
of pass 30** (see NOTEBOOK_IMPORT.md "Thirtieth pass" for full detail):

- [x] `design-vision` — template (hardcoded component list, no input inference)
- [x] `design-model` — template (hardcoded architecture params)
- [x] `vision` (`vision_coder.py`) — **real, not a template.** Probed:
  no vision model installed on this machine (`find_vision_model()` returned
  `None`), so `used_vision=False` for both test calls — correctly reported,
  not faked. But the two different specs ("simple login form" vs "complex
  dashboard with charts") produced **different code** (338 vs 350 chars,
  `layout_spec[:40]` actually varies the output), and the orchestrator's
  Planner/Coder stages genuinely ran (visible `[Planner] Complexity Analysis`,
  `[Coder] Generating code...` logs) before falling back to template because
  the local LLM call did not complete. `vision_backend.py`'s image path calls
  a real Ollama `/api/generate` endpoint with `images: [b64]` — no template
  there either.
- [x] Remaining ~100 commands — genuine (real AST/subprocess/git/LLM calls,
  output varies with input). 6 confirmed template/fabrication findings, none
  fixed yet — see "Next candidates" above. All findings and their evidence
  are in `NOTEBOOK_IMPORT.md`, "Thirtieth pass."

---

## Claude Code capabilities used in this repo

These are real, working tools that Saleha will be integrated with:

- **Agent tool** — spawn subagents to parallelize work (Explore, Coder,
  Researcher types). Used by `refactor-orchestrator` pass 29 to audit 40 files.
- **Artifact system** — publish HTML/React pages with live state and databases.
  Saleha's `/design-vision` should ship results here instead of plaintext.
- **Skill system** — invoke pre-built workflows (init, run, design, dataviz).
  Saleha's agents could call `/skill run` to start the project and probe
  runtime behavior in real time.
- **Code Review** — `/code-review ultra` launches multi-agent cloud review of a
  branch or PR.
- **Git/GitHub** — full `gh` CLI access, branch management, PR creation/reading.
- **Memory system** — persistent JSON files across sessions, auto-loaded at
  start. Saleha's own task history would fit here.
- **MCP servers** — Anthropic context (docs lookup), Supabase (database), etc.
  Orchestrator could query live service state via these.
- **Bash/PowerShell** — native shell; Saleha already uses this for git.
- **Web search / fetch** — browse external documentation on demand.

**Integration point:** Saleha's orchestrator could use Claude Code as a
backend — when Claude Code tasks are triggered from Saleha's CLI, their
results flow back to inform Saleha's own decision-making. This is the
"self-building" vision from line 447–448 of this file.

---

## Communication

- The user writes in Hindi/Hinglish. Reply in the same.
- Be direct. Report what was found, including what is still broken.
- Report failures plainly. If tests fail, say so with the output. If a step was
  skipped, say that. Never dress up a partial result as a finished one.
- The user also runs other agents in parallel (Gemini has been used alongside),
  coordinating through `COORDINATION.md`. Keep that file usable.
