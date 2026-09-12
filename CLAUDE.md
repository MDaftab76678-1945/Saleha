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
5. **Before touching a file, read the whole surrounding area — not just the
   line you are fixing.** A one-line patch to `polyglot_executor.py`'s
   `subprocess.run()` call (pass 36: missing `encoding="utf-8"`, silently
   falling back to this machine's cp1252 default and risking a swallowed
   decode crash on non-ASCII subprocess output) is only safe once you have
   also checked every other `subprocess.run`/`text=True` call in the file for
   the same gap, and checked whether the test that would have caught it
   actually asserts on the failure reason (`res.error`) or just a bare
   boolean (`res.success`) — a bare-boolean assert is a test that cannot tell
   you why it failed, which is how this one first reached CI as an
   unexplained red job on two different Windows/Python versions before the
   real cause was found.
6. **A CI failure without a fix in hand is not the same as a proven fix.**
   Don't report a bug as fixed until it has been reproduced locally (or the
   report explicitly says it could not be, and why) and the fix has been
   re-run against that reproduction. Guessing at a plausible cause and
   shipping it as "fixed" — without ever seeing it fail the same way
   locally — is exactly the kind of confident-but-unverified claim this
   whole file exists to stop making.

---

## Where the project state is written down

| File | What it holds |
| --- | --- |
| `NOTEBOOK_IMPORT.md` | The audit ledger. Every pass, what was found, what was measured. **Append a new section per pass.** |
| `ARCHITECTURE.md` | What each subsystem really does; which CLI commands are real vs template. Update entries when they change — a stale "this is broken" note costs as much trust as a stale "this works". |
| `COORDINATION.md` | Multi-session coordination notes (gitignored, local only). |
| `README.md` | User-facing, honest description of working features. |
| `ROADMAP.md` | Things that do not exist yet. Speculative claims belong here, not in README. |
| `ORCHESTRATOR.md` | The central coordinating-mind architecture (Octopus model, 6-stage execution graph, memory/consensus/rollback contracts). **Section 8 is a full repository file index** — every file/directory that exists in the repo but is not named anywhere else in this file, organized by area, flagged unaudited. Read section 8 before assuming a file is either in scope or already covered by a prior pass; `saleha/experimental/jarvis/` and `deploy/` are flagged there as the two highest-priority open questions. |

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
`model != "mock"`). Full multi-stage writeup in `NOTEBOOK_IMPORT.md`,
"Thirtieth pass".

**Design UI synthesis commands — fixed (pass 32).** Both were pass-30
template findings; the fix was to make them input-driven, not to delete
them (no production caller for either, but the instruction was to fix).

- **`design-model`** — `neural_designer.py` was always real (parameter
  count, FP16 size, FLOPs/token, VRAM all computed from the spec; generated
  PyTorch source uses the real dims). The CLI took only `name`, so every
  other field defaulted. Now takes `--d-model`, `--layers`, `--heads`,
  `--vocab`, `--seq-len`, `--show-code`. Probe: `--d-model 256 --layers 4` →
  20.5M params / 39 MB; `--d-model 4096 --layers 32` → 8.85B params / 16.9 GB.
- **`design-vision`** — was a genuine template: hardcoded component list,
  one palette, literal CSS, `total_tokens_generated = 420`, no model call
  despite extending `BaseAgent`. Rewritten: six layout families (auth,
  dashboard, pricing, article, settings, landing) chosen by keyword match,
  each with its own components and palette; JSX/CSS from a real
  `self.think()` call parsed for `jsx`/`css` fenced blocks. If the model is
  unavailable, a layout-specific template is returned and labelled
  `used_model=False`, tokens `0` — the CLI/REPL print which path ran.
  Docstring corrected: no image parsing. Probe: four different prompts →
  four different layout types, components and palettes.

**`swe_repo_fixer.py` and `extreme_contrastive_trainer.py` — deleted, not
fixed** (commit `f9814b6`, 2026-09-07). Both confirmed pure templates (see
git history for the probes); no production caller for either, so the fix was
removal rather than a rebuild. `apex_97_validator.py`'s hardcoded per-domain
scores were fixed in the same commit (it had a caller).

**`docs_generator.py`, `swarm_self_play_arena.py`, `code_executor.py`** —
the unused `import ast` in each was removed in pass 32. `swarm_self_play_arena.py`
went further in pass 33 (its `fight_battle` was a hardcoded template with
`6/6` "attacks neutralized" — now calls `CoderAgent.generate_code()` and the
real `ASTSecurityScanner`).

**`quality_guard.py` — all three design issues fixed** (commits `2d5915a`,
`ade661b`, follow-ups `d0e237b`/`121c55b`). `SOV-001` removed entirely
(naming a model you call is not a defect). `raw_score` added, uncapped,
alongside the clamped `quality_score`, so 25 and 400 untyped functions are
distinguishable for ranking. `check_workspace` now returns `files_found`,
`files_analyzed`, `truncated`, and `scan_is_complete` instead of a silent
partial scan. Also: `ScopeVisitor` had no `visit_Lambda`, so any lambda
parameter scored a false CRITICAL `UNDEF-001` — fixed. 20 tests in
`test_quality_guard.py`.

Detail: `NOTEBOOK_IMPORT.md`, "Thirty-second pass."

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
- `docs_generator.py`, `swarm_self_play_arena.py`, `code_executor.py` — the
  unused `import ast` in each was removed in pass 32 (plus other dead
  imports).

**The two REPL turn handlers are fixed (pass 33).**
`chat_session.py:_generate_turn_response` now builds a
`BaseAgent(model="auto")` and calls `think()` with the recent conversation
turns, printing an honest "No answer generated" (with the provider error)
on failure instead of the old hardcoded "I have analyzed your
requirement..." reply. `swarm_self_play_arena.py:fight_battle` now calls
`CoderAgent.generate_code()` for a real candidate and runs the real
`ASTSecurityScanner` over it; `red_attacks = 6 / neutralized = 6` and
`hard_negative_mined=True` (both unconditional) are gone, and
`StochasticWeightAverager` (which had a `+1.8` magic "ensemble boost" and
an `adapter_weights_mock` despite claiming to fuse adapter checkpoints) is
now `RewardAggregator` — a plain top-K mean of the round rewards, with a
docstring that says it trains nothing. Old tests that pinned the
fabrication (`6 == 6`, `reward >= 0.8`) replaced. Detail:
`NOTEBOOK_IMPORT.md`, "Thirty-third pass."

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

**Lockfiles — resolved (commit `2d5915a`).** `package-lock.json` was
deleted; only `pnpm-lock.yaml` remains. `package.json` declares
`"packageManager": "pnpm@9.15.0"`, `.npmrc` carries the pnpm-only
`link-workspace-packages=true` (with a comment explaining the `@saleha/*`
workspace-range resolution), and `.gitignore` now lists `package-lock.json`
and `yarn.lock` so they cannot come back silently. The two
`package-lock.json` under `.claude/worktrees/` are other agents' isolated
worktrees, not this repo.

**`templates/` — now used by `saleha new` (pass 34).** The three scaffolds
(`python_fastapi`, `nodejs_express`, `go_service`) each got
`{{PROJECT_NAME}}` / `{{PROJECT_SLUG}}` placeholders and are copied by
`saleha/core/project_scaffolder.py` into a new project directory with the
name substituted -- deterministic file copy, no model call, byte-identical
for the same inputs. After copying, the stack's own build/test is run
(`pytest` for fastapi via the template's `test_main.py`, `tsc --noEmit` for
express, `go build` for go); a toolchain that is absent is reported
`verify_ran=False` ("skipped"), never a pass. With go, node/npm, and `fastapi`+`httpx` installed on this box, all three
stacks report `Verification passed` on a real run. A missing toolchain is
`verify_ran=False` / "skipped", never a fake pass. This is the honest fast
path for the health/root boilerplate that never changes; `saleha build`
remains the LLM path for bespoke multi-file projects. CLI: `saleha new
<stack> <name>` in `saleha/cli/commands/scaffold.py`. The express template
gained a `tsconfig.json` (needed for `tsc --noEmit` to have something to
check).

**`forge-tool` / `ToolForge` — fixed (pass 37).** Validation staged the
generated tool in a temp dir on `PYTHONPATH`, so a model-written test
using a top-level import (`from word_counter import ...`) passed
validation and then would have failed collection once the file moved to
its real home `saleha/tools/<name>.py`. Now validated at that real path,
with the test prompt requiring the real import
(`from saleha.tools.<name> import ...`). Added two deterministic repair
steps (no extra model call): `_heal_tool_source` injects
`BaseTool`/`ToolResult`/stdlib imports the model referenced but forgot,
and a failing-test pruner keeps the tests that pass instead of discarding
the whole suite over one unmet assertion. `model_provider.py`'s
`OllamaProvider` no longer collapses a slow-but-working generation and a
genuinely unreachable server into the same "server not running" message
(distinguishes `requests.exceptions.Timeout` from `ConnectionError`;
timeout is now `SALEHA_MODEL_TIMEOUT`, default 300s, was hardcoded 60).
`word_counter` is the first tool the fixed pipeline produced end-to-end.
Detail: `NOTEBOOK_IMPORT.md`, "Thirty-seventh pass."

**`saleha stream` — fixed (pass 38).** A test-coverage sweep of
`saleha/core/` found 7 of 239 modules with no test importing them.
`streaming_ui.py` was not just untested -- it crashed on every real
invocation (`AttributeError`: no `ModelProvider` subclass ever defined
`stream_generate`), which is exactly why no test existed: any real test
would have hit the same crash. Fixed by adding real `stream_generate()`
across the provider hierarchy (`OllamaProvider` does genuine
`stream: true` NDJSON streaming, verified against a live Ollama
instance: 115 real incremental chunks for a multi-line generation).
Fixing it also exposed a bug in the quality gate itself:
`quality_guard.py`'s module-level scope walker silently skipped every
`except ... as name:` handler (`ast.ExceptHandler` is not an
`ast.stmt`), falsely flagging a pre-existing, correct exception binding
in `inference_router_bridge.py` as CRITICAL -- fixed, same shape of gap
as the earlier `visit_Lambda` issue. Two other untested modules
(`mukti_chain_bridge.py`, `inference_router_bridge.py`) were probed
directly and confirmed to fail honestly rather than fabricate; the
latter's docstring claimed a build "verified in this environment" that
no longer holds against this project's actual `.venv` (Python 3.14.7
vs. pyo3's 3.12 ceiling) -- docstring corrected rather than left stale.
Detail: `NOTEBOOK_IMPORT.md`, "Thirty-eighth pass."

**Formal verification -- widened, and a false negative fixed (pass
39).** `formal_verifier.py`/`formal_smt_verifier.py` were already
honestly labelled (an earlier pass, not this one): the Lean 4 output
is marked `lean_verified=False` / "UNVERIFIED SCAFFOLD", and the SMT
verifier genuinely calls Z3 for division-by-zero safety. Real Lean
verification needs `elan`/`lake`/Mathlib (several GB, not installed
here) -- disproportionate for one sitting, so the chosen direction was
to widen the one real proof this project already has instead. Added a
second genuine Z3 obligation: `seq[i]` is proven in-bounds when `i` is
guarded by `assert`/early-exit statements implying
`0 <= i < len(seq)`. Reused the existing guard-detection machinery,
extended for chained comparisons and `len(name)` terms. Hand-testing
the new code surfaced a real bug in the *existing* division checker:
a comparison with the guarded variable on the right (`5 < b`, i.e.
`b > 5`) was translated by swapping operands without flipping the
operator, silently becoming `b < 5` -- a real, provable safety fact
(`5 < b` rules out zero) was reported `not_proven`. Confirmed with
`git stash`: `not_proven` before the fix, `proven_safe` after. Full
suite: 1809 passed, 7 skipped (was 1800). Detail:
`NOTEBOOK_IMPORT.md`, "Thirty-ninth pass."

**Retrieval-augmented tool generation -- measured, then wired in (pass
40).** Direction: this project's local models will not out-generate a
cloud-scale assistant on raw capability, so the honest angle is
closing part of that gap for $0 -- not claiming parity. Measured
before building: generating the same kind of tool with
`qwen2.5-coder:3b`, bare prompt vs. prompt + an existing tool file as
a "match this convention" example (two tasks, two trials). The bare
prompt consistently omitted the `name`/`description`/`parameters`
class attributes entirely (undiscoverable by the registry even after
`_heal_tool_source` patches the missing `ToolResult` import) and
forgot to import `ToolResult` while constructing one. The
example-augmented prompt got all three attributes and the correct
import every time. Wired into
`ToolForge._find_reference_tool_source()` /`generate_tool_code()`:
appends the shortest existing tool in `saleha/tools/` as an example
when one exists; falls through unchanged on a clean install with zero
prior tools. Verified end-to-end against a live Ollama instance.
Full suite: 1812 passed, 7 skipped (was 1809). Detail:
`NOTEBOOK_IMPORT.md`, "Fortieth pass."

**Remaining test-coverage gaps from pass 38 closed (pass 41).** All 6
modules pass 38 left honest-but-untested now have tests:
`audit_log`, `inference_router_bridge`, `mukti_chain_bridge`,
`path_utils`, `project_builder`, `stats_tracker`. Re-reading
`project_builder.py` in full before writing tests against it (this
file's own audit rule) found two rule violations that had survived
every prior pass: Hindi text in its docstring/prompts/log messages,
and decorative emoji in log output -- confirmed the emoji rule's own
stated failure mode directly (`re.findall` over the file's emoji then
printing them crashed with `UnicodeEncodeError` on this machine's
cp1252 console, the exact bug the rule exists to prevent). Fixed both
in `project_builder.py` and its one live CLI caller (`saleha project`
in `cli/commands/git_release.py`); left ~20 unrelated emoji elsewhere
in that same file alone (other commands, out of scope). Full suite:
1856 passed, 8 skipped (was 1812 passed, 7 skipped). Detail:
`NOTEBOOK_IMPORT.md`, "Forty-first pass."

**Desktop app -- read in full, actually built, two real defects fixed
(pass 42).** `src-tauri/src/main.rs`'s sidecar lifecycle management
was already solid (free-port picking, full process-tree kill, a
`start_lock` mutex specifically guarding against React StrictMode's
double-mount spawning two Python servers, capped respawn backoff) --
0 changes needed there beyond one `cargo check` warning. `App.tsx` had
a fabricated "Chain-of-Thought Reasoning" panel: hardcoded fake
reasoning steps and a literal, unconditional "PBFT Quorum: 16/19
agents reached 98.1% consensus" string, never from the backend. Fixed
to render the real per-stage data `/api/v2/swarm/execute` already
returns (`agent_role`, `status`, `duration_ms`, `output_summary`),
hidden until a run actually has stages. Separately, running the real
build (not just reading config) found it could not complete at all:
PyInstaller was never declared as a dependency anywhere in
`pyproject.toml` (fixed: new `[desktop]` extra), and once that was
fixed the build recursed infinitely -- `package.json`'s `build` ran
`tauri build`, which read `tauri.conf.json`'s
`beforeBuildCommand: "pnpm build"` and called `pnpm build` again,
looping until Windows rejected the command line after ~70 passes.
Fixed by splitting the two files' responsibilities so neither calls
the other back. Verified end-to-end: a full release build now
completes in 2m35s and produces a real 14.8MB `saleha-desktop.exe`.
Not verified: actually launching the built app (needs a human at the
machine). Detail: `NOTEBOOK_IMPORT.md`, "Forty-second pass."

**Branch state:** PR #2 (passes 36-42) merged into `main` 2026-09-11
(commit `da4ea18`). `main` is now current. A one-off Windows CI flake in
`test_validate_tool_and_test_success` (Python 3.12/3.13 only) cleared on
re-run without a code fix -- a diagnostic assert-message change
(commit `b4889b4`) shipped with the PR in case it recurs, so the next
occurrence prints the real `detail` string instead of a bare
`assert False is True`.

**`saleha/server/` read in full and fixed (pass 43).** Eight fabrications
found and fixed across `web_server.py` and `swarm_stream_hub.py`:
`swarm_stream_hub.py` was dead code (undeclared `fastapi` dependency,
nothing imported it) duplicating the real `/api/v2/swarm/execute` -- not
deleted, rebuilt into a genuinely wired optional real-time WebSocket push
channel (new `[realtime]` extra), which also exposed and fixed a real
cross-thread `asyncio` bug (`AgentMessageBus.publish()` can run on any
thread; the old broadcast code silently dropped every event when called
from a thread with no event loop). `/api/workflow/dag` now calls the real
`SwarmRouter.route_goal_to_dag()` instead of a fixed literal.
`/api/hardware/accel` no longer claims NPU/WebGPU detection it cannot
perform (reports `None` + a reason instead of hardcoded `True`/constants).
`/api/vault/ticker` discloses `is_live_feed: false` for its mock prices.
`/api/voice/dispatch` no longer claims "Auto-healing initiated" for an
endpoint that only classifies intent. `/api/ast/merge` now runs the real
(previously unwired) `ConflictResolver` instead of string concatenation.
`/api/db/seed` reports real failure instead of `success: True` on an
exception. `/api/git/pr/generate` runs real `ast.parse`/`ASTSecurityScanner`
checks instead of printing a fully hardcoded "0 Memory Leaks, OWASP Clean,
10-Department Swarm Consensus" report -- the same class of bug `/autopr`
had before its pass-13 fix, found a second time here. 7 tests across 5
files had pinned these fabrications directly; all fixed to assert the real
behavior, plus one new test. Committing exposed a ninth, unrelated bug:
`quality_guard.py`'s pre-commit gate flagged pre-existing, valid code
(`web_server.py:1853`, a chained generator expression) CRITICAL undefined
-- `_visit_comprehension` visited every generator's `iter` before any
target entered scope, instead of left-to-right, so a later clause
referencing an earlier clause's target (legal Python) read as undefined.
Same shape of gap as the `visit_Lambda` fix (pass 38). Fixed and covered
by two new tests. Full suite: 1859 passed, 8 skipped (was 1856). Detail:
`NOTEBOOK_IMPORT.md`, "Forty-third pass."

**A full-repo file inventory found and fixed three more issues, and
confirmed one directory doesn't belong to this project (pass 44).**
Built at the user's request: `ORCHESTRATOR.md` section 8 now indexes every
tracked file not already named in this file, organized by area, with most
entries backed by an actual read rather than a directory listing.
Three fixes landed from it:

- **`tools/code_quality_auditor.py`** hardcoded `"test_coverage_pass_rate":
  100.0` and printed `870/870 Tests Passed` unconditionally, never running a
  test. Not called anywhere (dead code), but fixed anyway rather than left
  live in the tree: now shells out to a real `pytest saleha/tests/` run
  with an honest `ran: False` path if pytest is unavailable. Verified:
  `python -m tools.code_quality_auditor` end-to-end, real result
  `1859 passed, 8 skipped, 60 subtests` in 102.73s.
- **`saleha/experimental/jarvis/`** — never mentioned anywhere before this
  pass. Three files (`self_awareness_engine.py`, `jarvis_world_model.py`,
  `general_reasoning_engine.py`) made confident "self-awareness"/"JEPA"/
  "AGI Component 3" claims with zero model calls behind them (hardcoded
  strings, dict lookups, regex keyword-matching); a fourth
  (`jarvis_unified_v11.0.py`) was not even valid, importable code. Confirmed
  unimported anywhere in `saleha/cli/`/`saleha/core/`, then deleted (same
  precedent as `swe_repo_fixer.py`). `saleha/experimental/aionx/extensions_v10.py`,
  checked for comparison, makes genuine Anthropic API calls and was left
  alone — this finding is specific to those four `jarvis/` files.
- **`deploy/`** (165 files: Terraform/K8s/Ansible/chaos/monitoring infra)
  and three Mukti-branded docs (`docs/manifestos/threat_model.md`,
  `docs/notes/mukti_agents_sdk_impl.txt`,
  `docs/notes/mukti_sovereign_summary.txt`) were confirmed to belong to a
  differently-branded, unrelated hosted product ("Mukti"/"Nexus-Omni") that
  landed in this repo via one 564-file bulk commit (`8c6c607`) of
  previously-unsaved local work. Verified before deleting: zero "saleha"
  references anywhere in `deploy/`, no CI/build config points at the path,
  no vendoring markers, and the only real "mukti" code in `saleha/` itself
  (`mukti_chain_bridge.py`/`mukti_economy.py` — a real, wired Web3-insurance
  feature) is unrelated, just a coincidental shared brand name. Deleted.

Full suite unchanged at 1859 passed, 8 skipped after all three fixes
(expected — both deletions were confirmed unreferenced first). Detail:
`NOTEBOOK_IMPORT.md`, "Forty-fourth pass." Section 8 of `ORCHESTRATOR.md`
still has open items not acted on this pass — see its "What's actually
confirmed vs. still just an inventory entry" subsection before assuming
anything else in that index is clean.

**Pass 44's remaining open items — five fixed (pass 45).**
`saleha/core/grpo_reasoning_trainer.py` was a full fabrication never
previously flagged anywhere: zero model calls (hardcoded `<think>` template,
candidate code chosen by loop index, `red_team_vulnerabilities_neutralized=24`
and `deployed_model_name` both constants), and its own test file
(`test_grpo_reasoning_trainer.py`) pinned the fabrication in place — the
same trap as every prior instance. Rewritten to do real, achievable work:
G real `CoderAgent`-generated candidates per prompt, scored by the real AST
security scanner and neuro-symbolic engine, with genuine group-relative
advantage math; no policy weight update, red-team run, or deployment is
claimed (matches `frontier_trainer.py`'s already-honest RLIF gap).
`scripts/train_swarm_self_play_arena.py` was a separate fabrication sitting
on top of the already-fixed `swarm_self_play_arena.py` module — hardcoded
battle rows and the exact `"+1.8% SWA Ensemble Boost"` string CLAUDE.md
already recorded as removed elsewhere; rewritten to render the real
per-battle results. `scripts/train_saleha_frontier_model.py` crashed on
every real invocation (`AttributeError: no attribute 'initial_loss'`) —
API drift from the pass-40 `frontier_trainer.py` rewrite that was never
propagated to this caller; rewritten against the real `TrainingRunReport`
fields, confirmed to run end-to-end without crashing. Two real bugs also
found by actually running things: `doom_workspace_engine.py`'s
`_apply_swarm_patch` produced invalid C (`divisor = 1  // comment;` —
the comment swallowed the statement's own semicolon), caught by running
`examples/run_dogfood_demo.py`, and fixed with a regex that places the
comment after the terminator; and `evaluate_real_trained_model.py` labelled
an actual regression (base model passed, LoRA failed) as "MAINTAINED",
same as a true no-change case — split into four explicit outcomes.
Full suite after pass 45: 1859 passed, 8 skipped (unchanged baseline).
Committed `9da562c`, pushed to `origin/main`.
Detail: `NOTEBOOK_IMPORT.md`, "Forty-fifth pass."

**`datasets/synthesize_*.py` lineage — cleanup claims verified, then a new
gap closed (pass 46).** Pass 44 had flagged this lineage's "already
partially remediated by an earlier, unlogged cleanup" note as unconfirmed.
Independently re-measured every specific claim in all six scripts'
"PARTIALLY BROKEN"/"BROKEN, DO NOT RUN" docstrings against the real output
files — all checked out (`saleha_sovereign_train.json` 31/31 unique rows,
`tourist_gemini_grandmaster.json` 7 rows with HLD genuinely dropped,
`saleha_omni_grandmaster_train.json`/`saleha_dsa_livecodebench_train.json`
7/7 unique each, the three purged files genuinely `[]`). Found a real,
previously-unflagged gap: the "do not re-run" warning was docstring-only —
nothing in the code stopped a re-run from silently overwriting the
hand-deduplicated files with the fabricated versions again. Confirmed live
by actually running `synthesize_sovereign_ultra_dataset.py`: it built the
full 1600-row fabricated dataset in memory before an unrelated path issue
stopped it short of writing. Fixed with a new shared
`datasets/_synth_guard.py` — `guard_output_path()` refuses to overwrite an
existing output file unless `--force` is passed — wired into all six
scripts at their write entry point. Verified: all six now exit 1 with the
target file byte-for-byte unchanged when run without `--force`, and
`--force` correctly bypasses the guard when tested directly.
Detail: `NOTEBOOK_IMPORT.md`, "Forty-sixth pass."

**`saleha/core/` bulk sweep started — seven fabrications found and fixed
in the first ten modules read (pass 47).** Prioritized by naming risk
among the ~30 core modules never named in any prior pass; three
(`doom_vault.py`, `sentinel_rs.py`, `saleha_watchdog.py`) were already
genuinely real or honestly labelled.

- **`pqc_guard.py` — the most serious finding.** Claimed CRYSTALS-Kyber/
  Dilithium (real NIST post-quantum algorithms); implemented neither —
  just SHA3-512 hashing and a SHAKE-256 XOR stream cipher. The old
  decrypt API required a `shared_secret_seed` no caller could ever
  supply, so decryption was structurally impossible, not just
  mislabelled. Its CLI caller, `saleha release`, turned out to hide a
  second fabrication in the same file: hardcoded `"696/696 PASSED (100%
  GREEN)"` with no test ever run, and four release artifacts all marked
  `"READY"`/`"SIGNED"` with no build step producing any of them — the
  same "fake green" shape as `/autopr` before its pass-13 fix. Renamed to
  `Sha3VaultGuard`, docstring states plainly what it is and isn't;
  `saleha release` now runs the real test suite (or honestly records
  `ran: False` with `--skip-tests`) and makes no artifact claims it can't
  back. `test_future_engines.py` had asserted the fabricated algorithm
  strings directly — rewritten to assert the honest ones plus a genuine
  encrypt/decrypt round-trip (impossible under the old API).
- **`native_compiler.py`** — `success=True` was unconditional; when no
  compiler was on PATH it wrote a 4-byte fake ELF/MZ header and still
  reported success with a hardcoded `compilation_time_ms=12.4`. Confirmed
  live on this machine (no clang/gcc installed): now honestly reports
  `success=False` with the real subprocess error.
- **`self_evolving_loop.py`** — `avg_quality_score` returned the literal
  `0.94` whenever any sample qualified, ignoring the real buffered
  scores. Fixed to compute the genuine mean.
- **`sheaf_consensus.py`** — `verify_mesh_consensus` derived a fixed
  symmetric pattern internally that satisfied its own consistency check
  by algebraic construction for any input — it could never detect a real
  desync. The `saleha doom sheaf` CLI command made this concrete by
  calling it with a hardcoded literal every run. Changed to take
  independently-reported triplets directly; verified it now genuinely
  distinguishes a consistent case from an inconsistent one (the old
  version could not produce `synchronized=False` for any input).
- **`saleha_wasm_runtime.py`** — "simulated execution" (the code's own
  comment already said so) returned a hardcoded fake digest string
  regardless of input. Made the two functions that map onto cheap real
  stdlib operations actually real: `rust_sha3_digest` now computes a
  genuine `hashlib.sha3_256` digest, `python_ast_validator` runs a real
  `ast.parse`. Both now genuinely vary with input.
- **`speculative_accelerator.py`** — fixed template code plus an
  artificial `time.sleep()` divided by a never-measured "45 tok/s
  baseline" to manufacture a speedup number. Kept as an explicitly
  labelled demo (real speculative decoding needs two resident models,
  which this project's one-GPU constraint rules out — see the
  Engineering Principles section) rather than deleted, since it has a
  live CLI caller. Reading it in full also surfaced an independent real
  bug matching code-quality rule 4 exactly: `generate()`'s `metrics`
  variable was only assigned inside an `except` branch, risking a bare
  `NameError` on any path that didn't hit it — fixed with proper
  initialization and an explicit error instead of a silent crash.
- **`mcts_search_engine.py`** — left functionally as-is (its scoring
  pipeline — AST validation, invariant scoring, sandboxed execution — is
  genuinely real); only the docstring and CLI text were corrected to stop
  calling fixed-template candidate selection "MCTS" and stop claiming
  guarantees no single-level scorer can make.

33/33 tests pass across the four affected test files (two new
desync-detection tests added; two rewritten to stop pinning the
pqc/native-compiler fabrications). ~20 of the ~30 priority-list modules
remain unread — next candidates: `change_impact.py`, `p2p_swarm.py`,
`hypergraph_indexer.py`, `multi_file_editor.py`, `review_reporter.py`,
`mcp_server.py`. Detail: `NOTEBOOK_IMPORT.md`, "Forty-seventh pass."

**Six next-candidate modules read — two fabrications fixed, four genuine
(pass 48).**

- **`p2p_swarm.py`** — claimed "Libp2p-inspired Peer Discovery", real
  network peers at hardcoded fake IPs (`192.168.1.11`-`14`), and
  "Consensus Aggregation over Asynchronous Gossip" — none of it real, no
  socket/network code anywhere in the file. "Crash detection" was a naive
  substring check (`"eval(" in code`) that never ran the code, and
  `consensus_achieved=True` was unconditional. Rewritten as
  `BatchedFuzzingEngine`: real batched runs of the existing
  `SPICSFuzzEngine` (the same real fuzzer `swarm_self_play_arena.py`
  already uses), honestly labelled single-process, not distributed. The
  `/api/p2p/fuzz` endpoint now returns real aggregated trial counts.
- **`mcp_server.py`** — three of four tool-call branches are genuinely
  real (call the real AST scorer, sandbox, notebook engine). The fourth
  and most prominent, `execute_swarm_dag`, returned a hardcoded
  `"Executed 27-Agent Pipeline ... Status: 100% Invariants Verified"`
  regardless of input, invoking zero agents — this is a real MCP server
  the docstring says is exposed to Cursor/VS Code/Claude Desktop, so a
  real IDE client calling this tool would get a fabricated success claim.
  The real orchestrator it would need is a long-running, model-calling
  pipeline with no bounded-time contract suitable for a synchronous MCP
  response, so rather than fabricate a result or risk blocking an IDE
  indefinitely, the tool now honestly returns `isError: True` pointing at
  the real CLI path (`saleha build`).
- Genuine, no action needed: `change_impact.py` (real AST blast-radius
  analyzer), `hypergraph_indexer.py` (real cross-file symbol indexer —
  initially looked like dead code, confirmed wired through
  `saleha/core/graph/__init__.py`, which has live CLI callers),
  `review_reporter.py` (real HTML report generator). `multi_file_editor.py`
  is also genuinely real (atomic multi-file edits with real rollback) —
  fixed a Hindi/Hinglish docstring and five Hindi-word comments to
  English per the language rule, not a fabrication finding.

31/31 tests pass across the three affected test files.
`test_frontier_suite.py` also failed the strict-mode quality gate before
this pass's changes (verified via `git stash`) — brought to 100/100
rather than worked around, same approach as pass 47.
Detail: `NOTEBOOK_IMPORT.md`, "Forty-eighth pass."

**`safety_guard.py` — entirely in Hindi, fixed to English (pass 49).**
`red_team_engine.py` and `hardened_sandbox.py` (also read this pass) were
genuinely real, no fabrication. `safety_guard.py` was entirely Devanagari
Hindi — every docstring, comment, and all four user-facing
`SAFE`/`WARN`/`BLOCK` messages — the same violation `CLAUDE.md`'s
English-only rule names `orchestrator.py` for, found in a second file.
Confirmed this was not cosmetic: `tool_calling.py`'s `shell_exec` tool
returns the Hindi message directly as a real production tool-output
string whenever a command is blocked. Rewrote all code/comments/
docstrings/messages to English; kept the Hindi regex *patterns* and
`SAFE_KEYWORDS` Hindi words themselves unchanged (language-specific
content a Hindi/Hinglish safety detector genuinely needs), with an
English translation comment next to each. Translating it line-by-line
surfaced a real pre-existing bug: the chest-pain pattern required its
intensifier word to sit immediately adjacent with nothing between, so
"सीने में बहुत तेज दर्द है" (chest pain, with "बहुत"/"very" inserted)
failed to match while the simpler phrasing did — a real miss in a
health-emergency detector, silently present since before this pass (the
file's own untested `if __name__` smoke block used this exact failing
phrasing already, claiming "this should now be caught"). Fixed by
allowing 0-2 intervening words in both the chest-pain and
difficulty-breathing patterns; verified the fix catches the intensifier
case, still catches the simple case, and does not false-positive on safe
input. Two new tests added; existing four (already Hindi-agnostic) pass
unchanged. The full suite that was pending when this entry was written
has since been run: `1863 passed, 8 skipped`.
Detail: `NOTEBOOK_IMPORT.md`, "Forty-ninth pass."

**A silent `ConnectionAbortedError` under a green suite -- fixed
(pass 50).** The pass-49 suite printed `Exception occurred during
processing of request from ('127.0.0.1', ...)` next to a green
`1863 passed`; nothing failed, so nothing had chased it. Root cause:
`web_server.py`'s `_send_json` never sent `Content-Length`, and the
header was in fact written nowhere in the server (only read, for
request bodies). With neither `Content-Length` nor `Transfer-Encoding`
on any response -- confirmed on the wire with a raw socket, for both
200 and 401 -- a client cannot know where a body ends and must read
until close, so the server aborted every connection. Connection reuse
was structurally impossible (a second request on the same socket raised
`ConnectionAbortedError`); `protocol_version` was also never set, so
the server answered HTTP/1.0. Fixed on all three bounded response paths
found by auditing every `send_response` in the file -- JSON, the HTML
index, and the **ZIP project export** (an unframed binary download is
the case most likely to truncate in a real browser) -- then enabled
HTTP/1.1, with the one unbounded response (the SSE stream) opting out
explicitly via `Connection: close` so the fix did not introduce a new
hang. Measured: 5 aborts per run before, 0 after. Two raw-socket
regression tests added, verified to fail (`3 failed, 1 passed`) against
the stashed unfixed server. Found while in the file: **`/api/team`
crashed on every call** (`result.plan` -- `TeamResult` has no such
field; probed live, `RemoteDisconnected` before vs. a real 200 after),
missed by pass 43's read of this same file; and two fabrications in the
dashboard SQL panel (an invented default row `[[1, 'Saleha DB Engine',
99.98]]` rendered when a query returned nothing, and a `catch` block
printing "Query executed: 1 row returned." with a green success toast
when the request had failed). Also: a pre-existing flaky test measured
rather than guessed at -- `/api/scan` takes 2.33-2.43s against a
hardcoded `timeout=5`, confirmed flaky on stashed old code too, raised
to a named `REQUEST_TIMEOUT = 30`.
Detail: `NOTEBOOK_IMPORT.md`, "Fiftieth pass."

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
  never tests. It was kept for `torch` (the LoRA/training path), but as of
  pass 35 its `Scripts/` has no `python.exe` any more (only the
  `accelerate`/`torch` console shims), so it is not a usable interpreter —
  recreate it if training is actually needed. `.vscode/settings.json`
  (gitignored) now points `defaultInterpreterPath` at `.venv`. The GPU
  training tests are backend-aware since pass 35: with no `torch` they
  assert the honest `success=False`, not a skip or a crash.
- `pip install -e ".[dev]"` alone does **not** give a passing test run: two SMT
  tests need `z3-solver`, which lives in the `[formal]` extra. A working test
  environment also wants `tree-sitter*` and `numpy`. `graphifyy` is now in
  the `[dev]` extra too (pass 35) -- without it 8 real-graph tests in
  `test_repo_graph.py` skip.
- Test suite: `python -m pytest saleha/tests/ -q` — 1714 passed, 7 skipped,
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

- [x] `design-vision` — **fixed pass 32.** Was a template; now infers one of
  six layout families from the prompt and calls the model for JSX/CSS,
  labelling a template fallback when the model is unreachable.
- [x] `design-model` — **fixed pass 32.** Engine was always real; CLI now
  takes `--d-model`/`--layers`/`--heads`/`--vocab` so the architecture
  actually varies.
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
