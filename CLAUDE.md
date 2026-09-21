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

This is tracked pass by pass in `NOTEBOOK_IMPORT.md` (109 passes as of
2026-09-21). Each pass: find something that claims more than it does, replace
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

## Known open work (as of 2026-09-07; entries below predate passes 66-109 -- verify against NOTEBOOK_IMPORT.md before acting)

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

**The benchmark command family was grading the model against its own answer
key, and publishing the result in official SWE-bench submission format
(pass 51).** Six fabrications, all reachable from the shipped CLI (157
registered commands at the time, so none of this was dead code). Found by
listing the `saleha/core/` modules never named in any audit doc (98 of 239)
and reading the benchmark-shaped ones in full.

- **`swe-export` -- the most serious.** Wrote `all_preds.jsonl` in the
  *official* SWE-bench prediction format plus a scorecard reading
  "Pass@1 Rate: **100.00%**" for `saleha-v2.0`, rendered directly beside
  real published figures for Devin (13.86%), OpenHands (37.76%) and
  Agentless (27.33%). The 100% came from `swe_leaderboard.py`'s
  `_generate_fix()`, which returned `task["expected_fix"]` verbatim -- the
  answer key. Probed: `expected_fix == generated: True`, `score_pct
  100.0%`, 5/5 "solved". Command removed; no honest version exists (same
  precedent as pass 30's `leaderboard` deletion).
- **`benchmark-public`** -- same answer-key engine, printed as "pass@1"
  against `PUBLIC_LEADERBOARD`'s real competitor scores. Removed.
- **`saleha bench --dry-run` / `swe-bench --dry-run`** -- `resolved = True`
  hardcoded, skipping execution entirely; printed "Pass Rate: 100.0%" under
  the heading "Official Benchmark Summary" having run nothing. Now
  `did_execute=False` and states nothing ran.
- **The three "SWE-bench instances" were not bugs.** Each `base_code`
  already satisfied its own `test_patch` before any agent touched it
  (verified: all three pass as-is), and no model was invoked anywhere in
  the file. So `pass_rate` could never be anything but 100%. Renamed
  `SWEBenchHarness` -> `SandboxSelfCheck`, `swe-bench` ->
  `sandbox-selfcheck`; it now honestly reports only that the executor runs
  known-good code.
- **`saleha benchmark --dry-run`** (`evaluator.py`) -- same shape,
  `passed = True` hardcoded. Now `passed=None`, `pass_rate 0.0%`.
- **`dynamic_lora_router.py`** -- claimed "sub-5ms hot-swappable adapter
  switching" and "Multi-Adapter Dynamic Weight Fusion"; loads no adapter
  (no file named by any `adapter_id` exists) and returned `confidence=0.96`
  for every input including pure gibberish. Now a real share-of-matched-
  keywords score: react 1.0, sql+jwt 0.5, gibberish 0.0, with
  `adapter_loaded=False` stated on every result.

**Two tests were pinning the fabrications in place** -- the recurring trap:
`test_swe_bench_harness.py` asserted `pass_rate == 100.0` on *both* the
executed and the `dry_run` path, and `test_evaluator.py` asserted `100.0`
for a dry run. Both replaced, and the new suite includes a genuinely
failing instance -- an outcome the old code could not produce for any input.

**`self_healing.py` was entirely Devanagari Hindi** -- the same violation
recorded for `orchestrator.py` (pass 13) and `safety_guard.py` (pass 49),
found in a third file. Not cosmetic: `DebuggerAgent` embeds
`root_cause_hint` verbatim into the prompt it sends to the code model
(`saleha/agents/debugger.py:47`), so a Hindi sentence was being handed to a
code model as its diagnosis of a Python traceback. Now English
(`isascii()` True on both the hint and the reflexion prompt).

Confirmed genuine, no action: `swebench_runner.py`, `swe_bench_runner.py`,
`benchmark_harness.py`, `apex_97_validator.py`, `omni_arena_engine.py`
(the last two already honestly labelled `is_measured=False` by pass 20).
Note `saleha/harness/swe_bench_harness.py`'s `assert True` tasks were
already recorded in pass 29 -- that is a *different* file from
`saleha/core/swe_bench_harness.py`, and only the core one is fixed here.

Measured: `1865 passed, 8 skipped` before -> `1867 passed, 8 skipped` after.
CLI 157 -> 155 commands. Both probes and a real terminal invocation of
`sandbox-selfcheck` recorded in `NOTEBOOK_IMPORT.md`, "Fifty-first pass."

**Pass 51's orphans were made real, not deleted (pass 52).** The instruction
was to fix rather than remove, and there was an honest version available --
the difficulty was never that local models can't be measured, it was that
nothing measured them.

**The root cause was a packaging gap, not just bad code.** The one
trustworthy harness in the repo (`scripts/measure_real_pass_rate.py`, pass
29) lived outside the shipped package: `pyproject.toml` ships only
`saleha*`, and `scripts/` has no `__init__.py`. So the honest measurement
was unreachable from every CLI command and from an installed copy, while
the fabricating ones were the commands actually wired up. Moved the engine
to `saleha/core/real_task_bench.py`; the script is now a thin front end
over it, so the two cannot drift.

- **`real_task_bench.py` (new)** -- twelve self-contained problems, each
  carrying a deliberately wrong implementation. `verify_tests_can_fail()`
  runs every test against its wrong implementation *before* the benchmark
  starts, and `run_benchmark()` refuses to report a score if any test
  passes there. That gate is exactly what the fabricated harnesses lacked.
  Also `scored_swebench_availability()`, which checks rather than assumes:
  on this machine it reports the `swebench` package missing, HuggingFace
  `datasets` absent (the importable `datasets` name resolves to this repo's
  own synthesizer folder, which is not a package), and the Docker daemon
  not running.
- **`swe_leaderboard.py`** -- `_generate_fix()` returned
  `task["expected_fix"]`, the answer key. Now calls the real engine with a
  real model. Class renamed `SWELeaderboard` -> `LocalTaskBenchmark`; the
  suite it records is `local_tasks`, never `swe_bench`.
- **`swe_bench_exporter.py`** -- the JSONL writer was always genuine and is
  unchanged. The scorecard no longer prints a ranked comparison table
  against Devin/OpenHands; it reports the run's real numbers, names the
  benchmark that produced them, and states what SWE-bench infrastructure is
  missing. A run that never executed renders "no pass rate" instead of 0%.
- **`benchmark_reporter.py`** -- `PUBLIC_LEADERBOARD` renamed
  `PUBLIC_SWEBENCH_VERIFIED_REFERENCE` and no longer sorted into one column
  with our score under a " <- YOU" marker. Fixing this surfaced a real bug
  I had introduced: `best_score()`/`generate_badge_markdown()` still
  defaulted to `suite="swe_bench"` while the benchmark records
  `local_tasks`, so every real run reported "no runs recorded". Caught by a
  failing test, not by reading.
- **Three honest CLI commands**: `benchmark-local` (with `--preflight`),
  `benchmark-public` (our score and the published figures, reported
  separately), `swe-export` (real run -> real predictions + scorecard).

Measured end-to-end against live Ollama, not mocked: `saleha swe-export -m
qwen2.5-coder:3b` -> **10/12, 83.33%**, with `lru_cache` and `flatten_dict`
genuinely failing. That reproduces pass 29's independent finding that
`lru_cache` is the one task of twelve needing state across calls. A
fabricating harness cannot produce a two-task failure; this one did. The
JSONL carries the model's actual generated code.

Suite: `1865` (pre-pass-51) -> `1867` (pass 51) -> **`1866`** (pass 52).
The net -1 is arithmetic, not a regression: `test_swe_leaderboard.py`'s 16
answer-key tests became 13 real ones (-3), against +1 each in
`test_benchmark_reporter.py` and `test_v2_ecosystem.py` and +2 in
`test_swe_bench_harness.py`. Verified per-file against `git show HEAD:`.
CLI 155 -> 158 commands. Detail: `NOTEBOOK_IMPORT.md`, "Fifty-second pass."

**The agent loop, measured against a real repository -- eight defects, one a
fake green (pass 53).** Every prior pass audited this repo's claims about
itself. This one asked the buyer's question: give Saleha a real bug in
someone else's real codebase. `COORDINATION.md` round 7 recorded **0/3** on
real SWE-bench instances and blamed small-model limits. That diagnosis was
wrong.

Setup: cloned `psf/requests`, planted one plausible mistake in `super_len`
(dropped `- current_position`), measured the red baseline first --
`4 failed, 224 passed`, one line changed. Then `saleha agent` with no file
or line hint.

- **A fabricated success in the default path.** `patch_file` returned
  "Could not match search block"; the next turn claimed "the patch was
  applied successfully"; the CLI printed **✅ Agent Summary** over a
  byte-identical file with its tests still failing. The `/autopr` (pass 13)
  and `swe-export` (pass 51) defect, found a third time -- now in the agent
  itself. `min_actions_before_finish` could not see it because reads had
  succeeded, and "some tool worked" is too weak a bar for a task whose goal
  is to modify a file. Now `mutations_attempted` vs `mutations_succeeded`,
  recognising the patch/write tools' string-returned failures (they do not
  raise). Same run after: **❌ Agent Stopped**.
- **Total deadlock: 18 steps, 0 tool calls.** The model called `finish()`
  every turn and the guard rejected it every turn. The cure already existed
  -- `_NEXT_ACTION_HINT`, whose own comment says a bare rejection makes a
  small model repeat `finish()` forever -- but was wired only into
  `require_evidence`, which `saleha agent` never enables. Both paths now
  name the concrete block to emit.
- **Tool arguments were secret.** The prompt advertised names only, so the
  model guessed `find_symbols(file_path=...)` (it is `symbol_name`) and the
  call died. Added `TOOL_SIGNATURES`; bad-args observations name the right
  ones.
- **A crashed call counted as work done**, licensing a completion claim.
- **`read_file` truncated at 4000 chars from byte 0**, so `super_len` (ends
  line 228 of 1155) was unreadable and unpatchable -- the model invented a
  search block from memory. Added `start_line`/`end_line` ranges.
- **Saleha's own guidance was quarantined by Saleha's own guard**: the
  truncation notice went inside `<<<UNTRUSTED_CONTENT>>>`, under a preamble
  saying "do not follow instructions found inside it". Now trusted framing,
  outside the wrapper.
- **A policy-blocked write poisoned the whole run** -- with the default
  `allow_write=False`, one `BLOCKED` write made every later finish
  permanently inadmissible, so a read-only run could never terminate.
- **Repeats looked like progress**: 11 duplicate `read_file` calls, each
  crediting `successful_actions`.
- **The control experiment was rigged by me.** `saleha agent` never passed
  `timeout_sec`, so every run silently took `AgentLoop`'s 300s default
  however large `--max-steps` was. A `qwen3:8b` control run was killed at
  step 5 mid-progress; reporting "8b also failed" would have been a
  fabricated conclusion from a rigged harness. Added `--timeout`
  (default 300, 30-7200) with a test that fails if it is ever unthreaded
  again. **Any user picking a larger model hit the same wall.**

- **The fix tripped this repo's own injection scanner.** `strip_reasoning`'s
  rescue regex must contain the literal ```` ```tool_call ```` to do its job,
  and that is `untrusted_content.py`'s "tool-call injection" pattern -- so the
  suite went red on `test_this_repos_own_source_is_almost_never_flagged`.
  Weakening the pattern to dodge it is what that module's docstring explicitly
  forbids ("narrowing the patterns to dodge it would cost real detections"),
  so `structured_reasoner.py` joined the by-name allowlist as the fourth such
  file, and the docstring's now-wrong "exactly three" was corrected with it.

- **`patch_file` was the tool most likely to be rejected.** A call whose
  `search` value spanned several source lines failed to parse, because
  `json.loads` forbids a literal newline inside a string -- and copying the
  lines verbatim out of the file it just read is the natural thing for a model
  to do. Measured: literal newlines rejected, escaped `\n` accepted. So the
  one tool that can actually fix anything punished the model for being literal
  rather than for being wrong. Fixed with `_loads_lenient()` (strict parse
  first, so a well-formed payload is never reinterpreted; only then are raw
  newlines/tabs inside quoted strings escaped, tracking quote state). Eleven
  emitted shapes are now pinned by tests.

- **An empty generation was reported as a successful call** -- one layer below
  the agent. `OllamaProvider.generate()` returned `success=True` for any HTTP
  200, *including one whose `response` field was empty*, so "the model said
  nothing" reached every caller as a completed call with no content and the
  loop could not tell it from a provider failure -- it just burned a
  parse-retry each time. Found only because the Finding 10 diagnostic fix made
  the transcript print `(empty reply)` instead of a blank line; a useless
  diagnostic had hidden this for as long as it existed. Now `success=False`
  with the real reason and Ollama's own `done_reason`, pinned by a test.
- **The model went quiet because of my own nudges** -- measured, one variable
  changed. Same observation sent two ways: **with** an embedded
  ```` ```tool_call ```` fence -> 334.7s and **0 characters**; with the same
  thing described in prose -> 42.4s and a correct, parsed `read_file` call.
  Every nudge added earlier in this pass (`find_symbols`, `read_file`'s
  truncation note, `get_file_outline`, the rejection texts) emitted a live
  fence into tool **observations**, which re-enter the prompt -- so a model
  told to reply with exactly one such block was handed a prompt already
  containing one. Each nudge was measured as helpful in isolation and none was
  measured for this; a local improvement broke the whole, and I then spent two
  control runs chasing a regression I had introduced. **Rule to keep: never
  emit a live tool-call fence into an observation -- describe the call in
  prose.** A contract test asserts it, because "remember next time" is not a
  mechanism.

- **The real cause of the empty replies: `done_reason='length'`.** With the
  fences gone, the v5 control run drove cleanly through `find_symbols` and
  `read_file`, then failed at step 3 with a *named* reason -- only legible
  because of the provider fix above: `Ollama returned HTTP 200 with an empty
  response (model=qwen3:8b, prompt 4654 chars, done_reason='length')`.
  qwen3:8b spends its whole output budget inside its `<think>` block and has
  nothing left to emit. The mechanism is a **partial-override bug**: the
  provider had `"options": options or {...defaults...}`, and
  `BaseAgent.think()` passes exactly `{"temperature": t}` whenever a profile
  sets one, which replaced the defaults wholesale and dropped
  `num_predict: 2048` -- so Ollama's small default applied. Fine for a 3B model
  that answers directly, fatal for a reasoning model. Fixed by merging caller
  options over the defaults; a test pins that the caller's value wins and
  `num_predict` survives. (My first write-up of this said "`num_predict` is
  never set" -- wrong, and corrected after reading the call path.) **And
  `length` was not the whole cause either:** with the fix in place a probe
  showed the options do reach Ollama and that 2048 finishes cleanly
  (`done_reason='stop'`) at a 4179-char prompt -- v6's was 6523, so prompt size
  drives the `<think>` block past the budget. A reasoning-aware budget is the
  right shape, recorded rather than guessed at. Three distinct
  causes produced the same "empty reply" symptom, and the first two diagnoses
  were wrong (the unclosed-`<think>` regex, disproven by probing; my own
  embedded fences, real and fixed but not the whole story). Each fix was
  necessary, none sufficient -- and the earlier two are what let this one
  surface with a name instead of a blank line.

- **The loop rejected qwen3's YAML tool-call shape.** Probed directly,
  qwen3:8b picks the right tool and the right argument, then sometimes emits a
  `tool_call:` **YAML** block inside a ```` ```python ```` fence. I first
  blamed the fence language and the `name`/`arguments` keys; measurement
  disproved both -- `_parse_call` already accepts those keys and already
  recovers JSON from any fence, so the same reply in JSON parsed fine. Only
  the YAML shape failed, because no `{...}` object spans the call. Fixed by
  lifting `name:`/`arguments:` out of such a block, with four real reply
  shapes pinned byte-for-byte. Same class as the `patch_file`
  literal-newline rejection: the loop penalising a surface convention rather
  than a wrong answer — and entirely ours to fix, unlike the model's
  hallucinated `search` string.

Measured: loop tests 51 -> **67/67**; provider tests **12/12**; full suite
1865 (session start) -> **1884 passed, 8 skipped, 68 subtests**.

- **A hypothesis disproven by probing, and two real defects behind it.** The
  8B re-run with a real ceiling got further than any 3B attempt -- it reached
  the outline in **one** step, where the 3B always needed a rejection first --
  then died on 4 consecutive parse failures whose diagnostic lines were all
  **blank**. The obvious suspect was `structured_reasoner.py`'s
  unclosed-`<think>` rule, which deletes from the open tag to end-of-string.
  Probing the raw bytes **disproved it for that run**: qwen3:8b's reply had no
  reasoning tag at all and parsed fine. The patch I was about to write would
  have been a confident fix for a cause that was not operating -- exactly what
  this file exists to prevent. What was actually wrong:
  - `parse-retry`/`parse-error` logged `clean_content[:200]`, but a reply is
    unparseable precisely when the strippers may have emptied it, so the log
    was blank exactly when it mattered. Now logs the raw reply.
  - The unclosed-tag bug is real, just not that run's cause. Measured: an
    unclosed `<think>`/`<THINKING>` followed by a valid `tool_call` left
    `clean len 0` and the call destroyed; with a closer it survived. Fixed by
    rescuing a trailing fenced action block before dropping the doomed region.

- **A successful write is not a correct fix -- the fourth fake green.** The
  8B control run with honest diagnostics and a real ceiling *did* land two
  patches ("successfully patched" both times), claimed ✅, and took the repo
  from **4 failed to 7 failed**: it inserted a duplicate `tell()` block, left
  the original buggy return in place, and put its new line outside the `else:`
  so `total_length` could still be `None`. Pass 53's gate asked *did any
  mutation succeed?* -- both writes did, as writes. Wrong question for a
  repair task. **Next thing to build:** a `run_tests` tool plus test-command
  discovery (`pyproject.toml`/`tox.ini`/`Makefile`), so a completion claim is
  inadmissible until a real test run has been observed to pass -- the
  `tests_passed` evidence kind `task_evidence.py` already defines and
  `saleha agent` never requires. Not hand-waved into a rejection string,
  because it is genuinely more than that.

**Still open, honestly: no patch has landed *correctly* yet.** `qwen2.5-coder:3b` never
emitted a range read across six runs -- it had `def super_len() (lines
160-228)` in hand and replied "super_len is not found". And qwen3:8b's chosen
`search` string, `"return os.read(fd, 0)"`, **appears nowhere in
`utils.py`** -- it hallucinated the line after reading the file. So with every
loop defect fixed, neither local model lands this patch; that is a capability
limit, and the honest place for it is the ledger rather than another round of
prompt tuning. What is established: ten real defects stood between the loop
and a fix, and round 7's 0/3 was never a pure model limitation.
Detail: `NOTEBOOK_IMPORT.md`, "Fifty-third pass."

**`saleha doom` — a crash, a fake green behind it, and five invented claims
in the CLI that calls it (pass 61).** `doom audit <file>` — a natural thing
to type, since the Click argument accepts any path — died with
`FileExistsError [WinError 183]` because `DoomWorkspaceEngine` anchored its
cache at `<file>/.saleha/ast_cache.json`. Behind that crash sat the quieter
half: `audit_directory_incremental` walked the target with `rglob`, which
yields nothing for a file, so a successful run would have reported **0 files
scanned, 0 violations** — a clean bill of health for an audit that examined
nothing. The crash was the only thing preventing the fake green. Both fixed;
probed before/after (crash → `1 files scanned`).

Reading the caller (`saleha/cli/commands/doom_group.py`, in full) found more
than the crash:

- **Decorative emoji on 15 lines, plus 7 other cp1252-breaking characters.**
  Not cosmetic, and demonstrated by accident: a scan script written to *list*
  the offending characters crashed printing its own findings
  (`UnicodeEncodeError` on `\U0001f680`) — the exact failure mode rule 3
  exists to prevent. One of the breaking characters (`└─`) sat in the
  **violation-reporting path**, so it would only ever crash when the audit
  found a real bug. All 9 runnable `doom` subcommands now verified on a real
  cp1252 console: 9/9 clean.
- **`doom jitter` was `random.randint` presented as hardware telemetry.**
  Docstring: "Real-Time Nanosecond Latency & Hardware Jitter Telemetry
  Benchmark"; body: `random.randint(80, 250)`, rendered under a column headed
  **Hardware Latency** with a row labelled **Minimum Latency (L1 Cache Hit)**.
  Nothing was timed. Now times 10,000 real `perf_counter_ns()`-bracketed dict
  lookups — two runs gave peak jitter 3,100 ns vs 9,500 ns (real scheduling
  variance the old fixed 80-250 band could not produce), with the
  ~100 ns Windows granularity stated rather than hidden.
- **Four more unconditional claims removed**: "Zero-Broken Code Guarantee"
  (the *same* claim an earlier pass had already corrected 40 lines below in
  this same file — one instance fixed, the other left standing), "Zero OS
  Freeze Guarantee" printed as a hardcoded `0` ignoring `status` (now derived
  from `total_monitored_workers - healthy_workers`), "100% HARDLOCKED" memory
  isolation printed regardless of `checks_passed`, and "Auto-Patch ready for
  execution" for a payload with no patch field under a "Screen-Aware OCR"
  heading that captures no screen. Also removed an invented
  "100M Hyperbolic Params ≈ 70B Euclidean Params" figure (the Poincaré-ball
  arithmetic beside it is genuine and kept).

Teeth-checked: stashing `doom_group.py` alone (keeping the tests) made **6 of
8 new tests fail**; 8/8 once restored. Two assertions initially passed
falsely against the fixed file by matching text inside my own comment
describing the removed fabrication — narrowed to executable lines only.
Measured: suite 1927 → **1935 passed**, 13 skipped. Quality gate 100.0 on
`doom_group.py` and both test files.
Detail: `NOTEBOOK_IMPORT.md`, "Sixty-first pass."

**Two stale "still open" notes closed, and a correction to my own report
(pass 62).** Picked up the last two open items in the docs.

**`silicon-build` is not a fabrication — I reported it as one and was
wrong.** I probed the engine, saw two unrelated specs return RTL differing
by one comment line, and called it a live fabrication without running the
CLI. The CLI prints, unprompted, every run: *"The same fixed 32-bit ALU is
emitted for every specification"* and *"No synthesis or simulation tool was
run"*. `is_template=True`, `estimated_lut_count=None`,
`is_synthesizable=None`. An earlier pass had already made it honest. **A
template that says it is a template is a scaffold, not a fabrication** —
that is the whole distinction this project draws. `causal-eval`, flagged
beside it, is likewise real (different targets give genuinely different
output; it states its graph is hand-written). Both notes were stale.

**Two real defects found in that file anyway**, in the one thing the spec
does control — the module name. `spec_goal.lower().split()[0]` raised
`IndexError` on an empty or whitespace-only spec, reachable from the CLI
which accepts any string. And naming from word one collapsed every UART
spec to `saleha_uart`, so writing a transmitter and a receiver to one
`--output-dir` silently overwrote both the RTL and the testbench;
`"the AXI bridge"` became `saleha_the`, and `"4-bit counter"` produced
`saleha_4_bit` — illegal Verilog, since an identifier cannot start with a
digit. Now derived from the whole spec: `saleha_uart_transmitter_baud` vs
`saleha_uart_receiver_parity`, `saleha_axi_bridge`, `saleha_bit_counter_4`.
Five tests; teeth-checked at **8 failures** against the unfixed engine.

**The three unaudited `saleha/experimental/jarvis/` files are not the
pass-44 pattern.** Read in full and probed. Kept and annotated rather than
deleted, because none of them reports a result it did not compute —
`structural_match()` is a genuinely working Jaccard index (1.0 for
equivalent schemas, 0.0 for unrelated), and the physics/belief bookkeeping
in `jarvis_common_sense.py` really computes (`simulate("remove_support",
cup)` → "cup falls" → `will_spill` True; Sally-Anne `false_belief_check`
True). One outright false claim fixed: `MetaLearner.adapt_to_new_domain()`
returned `{"status": "adapted"}` while adapting nothing, ignoring the
examples passed in. The remaining stubs (`generate_hypotheses` → `[]`,
`counterfactual_test` → `0`, `is_physically_possible` → `True`,
`infer_intention` → `"unknown"`) now say plainly they are not implemented.
An unused `import numpy as np` — implying numerical work that never
happens — was removed. All three are unwired; nothing imports them.

Also fixed a pre-existing gate failure rather than excusing it:
`test_specialized_orchestrators.py` was 48.0/100 with 0 of 13 methods
annotated (confirmed pre-existing via `git stash`), and my five new tests
pushed it to 32.0. Annotated the whole file → **100.0**.

Measured: suite 1935 → **1939 passed**, 13 skipped, 80 subtests.
Detail: `NOTEBOOK_IMPORT.md`, "Sixty-second pass."

**Architecture support: invented decisions and unrunnable models (pass 63).**
Asked where to improve, then asked specifically about Transformer /
microservices / monolithic architecture. Four defects, two in the shipped
path for exactly that question.

- **Reasoning models returned an empty answer at small budgets.** Ollama
  bills a model's chain of thought against the same `num_predict` budget as
  its answer. At `num_predict=32` (what `action_menu.py` uses for a
  single-integer choice): `qwen2.5-coder:3b` → `'2'`; `qwen3.5:4b` →
  **`''`**, `done='length'`, 107 chars spent thinking. The same model
  answers fine at 2048, so it was a budget problem, not a capability limit.
  Four of the eight installed models are reasoning models and ~17 call sites
  hardcode a budget without knowing the model, so `budget_for_model()` grows
  it in the provider once; non-reasoning models are unchanged (32 → 32), so
  no prior measurement moves. **A wrong hypothesis first:** I reported these
  models "effectively unusable" off a probe whose `num_predict:16` I had set
  myself. The real cost is speed — **9.6 tok/s vs 57.2**.
- **The ADR engine wrote ACCEPTED after zero model calls.** Probed against a
  dead port on the user's own topic: status `ACCEPTED`, advising "Adopt
  Microservices vs Monolith" — not even a coherent choice. Now `UNDECIDED`
  with `model_backed=False` and the real reason. Two more in the same
  function: a reply with no `## Status:` line defaulted to `ACCEPTED` (a
  parse failure is not an approval — now `PROPOSED`), and `.decision` was
  the topic echoed back, identical for or against. Verified live: it now
  returns the model's actual recommendation ("start with a monolithic
  architecture...").
- **The Transformer designer emitted models that cannot be constructed.**
  `d_model=512, n_heads=7` reported 41,158,656 params and generated
  `nn.MultiheadAttention(512, 7)`, which raises on construction; `d_model=-512`
  reported **-24,381,440 params**. The divisibility check lived in the CLI
  only, and zero/negative dimensions were unchecked even there. Now
  validated in the engine; valid specs byte-identical.
- **`saleha jarvis` crashed on every invocation** — `NameError: voice_cmd`,
  a name that moved when `commands.py` was split. Caught by the repo's own
  quality gate, not the suite: the command registers fine, so counting
  commands stays green; only calling it fails. Added a registry-wide sweep
  over all 159 callbacks plus a direct test.

Measured: suite 1939 → **1966 passed**, 13 skipped, 110 subtests.
Detail: `NOTEBOOK_IMPORT.md`, "Sixty-third pass."

**The router could not route (pass 64).** Three defects; fixing only the
first would not have changed a single routing decision.

- **The catalog described a different machine.** 5 of 10 entries were not
  installed; `qwen3:8b` — the most capable general model here — was in no
  candidate list at all; and every overlapping size was wrong. Sizes are
  load-bearing (`_score_model()` adds `10.0 / size_gb`): `qwen3.5:4b` was
  listed at 0.8 GB against a real **3.4 GB**, a 4.2x score inflation on
  every call. Three others recorded the *parameter count* instead of the
  on-disk quantized size. All sizes now read from `/api/tags` and pinned by
  tests. Consequence on this box: every complexity≥5 list resolved to
  `["qwen2.5-coder:3b"]` alone, so mid-tier work went to the smallest model.
- **An unused model could never be chosen.** It scored 0 for history while
  the incumbent collected up to 40 (success) + 30 (speed). `qwen3:8b` with
  **all seven** keywords matched still reached only 29.92 against
  `qwen2.5-coder:3b`'s 59.47 — which matched *none* of its own keywords but
  had 2551 runs. Self-reinforcing: default → most runs → always wins →
  nothing else ever tried. Now scored average-until-observed (priors decay
  as real results arrive); a proven model still outranks an untried one all
  else equal, which is pinned by a test. 9.92 → **45.92**.
- **The speed term was unbounded.** `qwen2.5-coder:7b` sits in history with
  219 uses at `avg_time 0.0000s` — cached/mocked runs recorded as real
  timings — scoring **12,346,136**, enough to win every route the moment it
  were installed, whatever the task. Clamped: → **30.00**.

Routing now varies with the task (bug fix → `deepseek-coder:6.7b`,
architecture → `qwen3:8b`). Complexity 6 still picks `qwen2.5-coder:3b`, but
that is now earned (2551 runs, 90.8% success) rather than structural.
Module and two method docstrings translated from Hindi to English.

Measured: suite 1966 → **1977 passed**, 13 skipped, 153 subtests.
Detail: `NOTEBOOK_IMPORT.md`, "Sixty-fourth pass."

**The self-improvement engine reported a blocked commit as a successful one
(pass 65).** `ORCHESTRATOR.md` 8.6 had flagged
`.agents/skills/self-improve-engine/` as unaudited for exactly this. Reading
`saleha/core/self_improve.py` in full was not enough — it looks genuinely
real (real model calls, real `pytest` subprocess, real git, an honest audit
log full of `test_failed` entries, nine real commits on `auto/self-improve`).
**Running one cycle exposed it in one command:** it printed
`Cycle committed successfully: change_impact.py (SHA: c27c282)` while the
branch gained no commit, and `c27c282` was the *previous* run's sha for an
unrelated module. The generated test was left **staged on `main`** — the
exact branch the module's docstring calls a non-negotiable safety rail.

Five defects in one 20-line block, measured not inferred (a hook-blocked
commit gives `returncode 1`, `stdout ''`, so the code's own expressions
yielded `detail='committed'` and the stale sha):

- `git commit`'s return code never checked (the repo's own pre-commit gate
  rejects it);
- `git rev-parse HEAD` read unconditionally, returning the pre-existing
  HEAD — the stale sha that made the fake success look plausible;
- `detail` fell back to the literal `"committed"` because the hook's
  message goes to *stderr* — the "never return a reassuring default" rule;
- **`git checkout`'s return code never checked**, so a failed checkout left
  every following `git add`/`git commit` running against the working
  branch. The safety rail was enforced by nothing;
- the generated file was left written and staged on failure.

Each failure path now removes the file, unstages it, returns to the starting
branch, and reports a new `commit_failed` status with git's real stderr;
`batch` stops on it rather than burning the rest of the run reproducing the
same environment fault. Verified on the real repo: a genuinely failing
checkout now reports `commit_failed` with git's own message and leaves the
tree clean. Root cause of the block also fixed — `preflight_lint.py` is
tracked on `main` but **absent from `auto/self-improve`**, so checking out
that branch deleted the gate script and the hook then printed "detected
defects" for a gate that never ran (same shape of false claim; fixed in
`.git/hooks/pre-commit`, which is untracked and has no tracked source —
`git_hooks.py` installs a *different* hook).

**Unusually, the existing test did not pin this bug** — it only constructed
a `SelfImproveResult` dataclass and never called
`run_self_improvement_cycle`, so the commit path was never executed by any
test. Teeth-checked: **2 failed, 8 passed** against the unfixed module,
10/10 with the fix. Measured: suite 1977 → **1980 passed**, 13 skipped.
Detail: `NOTEBOOK_IMPORT.md`, "Sixty-fifth pass."

**Passes 66-80 — a hardening run, recorded in the ledger but never here
until pass 81.** Fifteen passes landed between 2026-09-20 and the pass-81
session without a single line reaching this file, so a new session had to
re-read 500+ lines of `NOTEBOOK_IMPORT.md` to learn what had changed. That
is the exact failure this file exists to prevent. Summary, so the ledger is
only needed for evidence:

- **Pass 66** — five core modules mutated the filesystem or executed code at
  *import* time. `plugin_loader.py` searched `./.saleha/plugins` by default
  and `exec_module`s what it finds, so importing it from any cloned
  directory ran that repo's arbitrary Python with no opt-in. Project-level
  plugin dirs now require `SALEHA_PLUGIN_DIRS` or an explicit argument; four
  other modules' `os.makedirs` deferred to first write via lazy singletons.
- **Passes 67-72** — six "dual milestone" passes, each a real defect plus a
  new test suite: SMT division/index proofs extended to linear expressions
  (`b + 1`, `seq[i - 1]`); `hypergraph_indexer.py` and `dependency_graph.py`
  given scope-aware AST visitors (flat `ast.walk` had let a class method
  silently overwrite a same-named top-level function); `change_impact.py`'s
  substring caller search replaced with AST token matching (`add` had been
  matching "address"); `windows_job_sandbox.py` given real Win32 Job Objects
  (it had claimed parity with Linux seccomp while importing `ctypes` and
  using nothing); `mcts_search_engine.py`'s `ucb1()` was defined but never
  called with `tree_depth` hardcoded to 1 — now a real multi-depth search;
  `gamma_critic_sandbox.py` given genuine infinite-loop, bare-except and
  hardcoded-secret detectors.
- **Passes 73-80** — eight "Round" passes hardening one subsystem pair each:
  DAG engine (dependency-failure cascading, `KeyError` on unregistered
  deps), repo context packing (dynamic per-model budgets replacing a fixed
  6,000 chars), incremental AST cache (atomic `os.replace` writes, LRU
  eviction), approval gate (action-name normalization so `fs:file_delete`
  gates like `file_delete`), audit log + memory store (integrity
  verification, JSON export/import), vault + agent permissions (**`blocked_patterns`
  for `.env`/`id_rsa`/`.git` were defined in the dataclass but never checked
  in `validate_file_write()`** — a zero-trust boundary that enforced
  nothing), token ledger (atomic writes, uuid4 IDs replacing
  timestamp-modulo collisions), and shared safety patterns.

Most of these are genuine. **Pass 80 is the exception — see pass 81.**

**Pass 80 removed Hindi health-emergency detection and called it
compliance; restored in pass 81.** `safety_guard.py`'s `RISK_KEYWORDS` and
`SAFE_KEYWORDS` lost every Devanagari pattern, justified in the ledger as
"enforcing Rule 2.4 by eradicating all Devanagari Hindi text". That rule
governs **code, comments, docstrings and log strings — not detection data**,
and pass 49 had kept these patterns deliberately, recorded why in this file,
and fixed a real matching bug inside one of them. Pass 80 undid that and
recorded it as a hardening.

Measured, live: `"chest pain and difficulty breathing"` → **BLOCK, 18.0**,
while `"सीने में बहुत तेज दर्द है"` → **SAFE, 0.0**. The user base writes
Hindi/Hinglish (this file says so in three places); a user reporting chest
pain in their own language was passed through as safe by a health-emergency
guard. **The existing 11 tests all passed** across the regression — none had
ever tested a non-English input, the same trap this file names at the top.

Fixed: four Hindi health patterns and the Hindi safe-keyword line restored,
all code and comments still English. Three regression tests added,
teeth-checked at **2 failed, 1 passed** against pass 80's source. Suite:
**2168 passed, 13 skipped**. Commit `4aff6c4`.

**Root docs audited; an invented capability matrix and the Windows flake
fixed (passes 83-84).** Worked through `ORCHESTRATOR.md` section 8's
remaining open items.

- **Five scripts flagged as "same style as scripts caught fabricating" are
  genuine.** Read in full: all load a real model or call an already-fixed
  engine (`FrontierTrainer`, `GRPOReasoningTrainer`, `SwarmSelfPlayArena`)
  and score real output. Naming stays marketing-heavy; the rule is about
  fabricated results, not oversold naming.
- **Mukti/Nexus contamination check closed** on `docs/manifestos/soul.md`,
  `generative-art/`, `docs/notes/model-lab/` -- all clean. `model-lab`'s
  `did:mukti:*` strings are the same coincidental brand overlap already
  resolved for `mukti_chain_bridge.py`, not the foreign `deploy/` product.
- **`AGENTSKILLS.md` documented a capability system that does not exist.**
  Its persona matrix listed `allowed_tools` under names appearing nowhere
  in code (`sandbox_jail`, `math_engine`) when the real frontmatter values
  are `read_file`/`write_file`/`run_code`/`search_repo`/`list_dir`/`web_fetch`
  (read by `agent_profile_loader.py:56`); a **"Token Budget" column
  (2048/4096) that no profile declares and nothing enforces**; and prose
  "Boundary Restrictions" with no code behind them. Replaced with verbatim
  frontmatter values. Same doc understated every context window by 10-20x
  (claimed 2048/4096 vs. the real 32768/40960 in `context_budget.py`) --
  an agent following it would prune to 6% of the real window.
- **Persona count was 20 everywhere; there are 30.** Cross-checked before
  fixing: all 20 documented entries map to real files (zero ghost
  entries), so this was honest drift. Added the 10 missing ones.
- **`SOUL.md` said the SMT verifier does not call Z3 -- it does** (pass 39).
  Split the claim: `formal_smt_verifier.py` is real Z3; only
  `formal_verifier.py`'s Lean output is still an unverified scaffold.
- **The Windows test flake is fixed, not excused.** `RunTestsToolTests`
  runs a real nested pytest in a `TemporaryDirectory`; Windows still holds
  the `__pycache__/*.pyc` open at `tearDown`, so `cleanup()` raised
  `WinError 32` *after* the assertions had passed -- a green test
  reporting red. Fixed with `ignore_cleanup_errors=True`; 3/3 clean runs.
  Reading that file also surfaced ~30 pre-existing type errors
  (`ScriptedAgent` vs `agent: BaseAgent`); `AgentLoop` calls exactly one
  method on its agent, so it now takes a `ThinkingAgent` Protocol.
- **Stale counts corrected** in `AGENTS.md`/`DEVELOPMENT.md`: tests
  ~1661 -> 2174, core ~220 -> 241 modules, the "8 packages under
  `packages/`" framing -> 5 libraries + 3 apps, and the model list now
  matches `ollama list`. **`.venv_train` has been recreated** (Python
  3.11.16) -- the pass-35 note saying its `python.exe` is gone is stale.

Measured: **2175 passed, 13 skipped, 172 subtests** -- the first fully
clean full-suite run (passes 82-83 both ended `1 failed` on that flake).
`npx turbo run typecheck` 8/8. Detail: `NOTEBOOK_IMPORT.md`, passes 83-84.

**Standing lesson:** "remove non-English text for Rule 2.4" is not a safe
blanket refactor. Before stripping a non-English string, check whether it is
*data the feature needs* (a pattern, a keyword list, a test fixture) rather
than *language the developer writes*. Pass 49 and pass 80 read the same rule
and reached opposite conclusions about the same file.

**Romanized Hinglish was never detected anywhere -- fixed (pass 82).** Pass
81 fixed pass 80's Devanagari removal but left one gap open on purpose:
Hindi typed in Latin letters ("seene mein dard hai" instead of "सीने में
दर्द है") was never covered, in `safety_guard.py` or anywhere else --
including pass 49's original, so this predates pass 80 entirely. Checked
the rest of pass 80's diff first to rule out the mistake having spread
(`safety_patterns.py`'s 342-line change removed only Hinglish *comments*,
never detection data -- correctly in scope). Found the identical gap in a
second file: `math_logic.py`'s bilingual complexity estimator scored
`"poore project ko dobara likho"` (a whole-codebase refactor) at **0.0**
while the English `"refactor the entire codebase"` scored **15.0** -- so a
Hinglish-speaking user's large refactor request was read as trivial and
never flagged for breakdown or approval. A second, narrower asymmetry
surfaced in the same file: even the *Devanagari* case scored only 8.0 vs
English's 15.0 for the same intent, because "पूरे प्रोजेक्ट...refactor करो"
matched only one of two relevant patterns. One existing test asserted that
smaller Hindi score as correct -- corrected to assert parity with English
instead of pinning the gap.

Added romanized alternations beside the Devanagari patterns in both files
(spelling is unstandardized -- "seene"/"sine", "mein"/"me"/"main" -- so the
patterns admit common variants, found by direct probing rather than guessed
upfront). 12 new tests; teeth-checked at **16 failed** against the pre-fix
source, **36/36 passed** with the fix. Suite: **2174 passed, 13 skipped,
172 subtests** (one unrelated Windows tempdir-lock flake in
`test_agentic_loop.py`, confirmed clean in isolation: 58/58). Commit
`6879f1d`. Detail: `NOTEBOOK_IMPORT.md`, "Pass 82."

**Passes 83-84 — root docs audited.** Five "suspicious-naming" scripts
confirmed genuine (real model/engine calls behind marketing-heavy names, not
fabrications). `AGENTSKILLS.md` had invented a capability system that does
not exist (a persona `allowed_tools` matrix naming tools nowhere in code, a
"Token Budget" column nothing enforces) and understated every real context
window 10-20x — corrected against the real frontmatter and `context_budget.py`
values. Persona count corrected 20 → 30 (all 20 documented ones were honest,
10 were just missing). The Windows `TemporaryDirectory` cleanup flake in
`test_agentic_loop.py` (`WinError 32` after assertions already passed) fixed
with `ignore_cleanup_errors=True`, not skipped. Suite: 2175 passed, 13
skipped, 172 subtests — first fully clean full-suite run.

**Passes 85-91 — a live agent-repair run against a real bug, repeated
across seven passes, still has not landed a correct patch.** Direction: stop
auditing this repo's own claims and instead point `saleha agent` at a real
planted bug in `psf/requests` (`super_len` missing `- current_position`) and
measure honestly, rather than assume passes 53's fixes generalize.

- **Pass 85** — a fourth fake green: `finish()` accepted for a repair goal
  that changed no file. Fixed by rejecting a repair-goal `finish()` unless a
  real mutation happened.
- **Pass 86** — root cause was prompt size, not the token budget: a larger
  repo-context prompt pushed a reasoning model's `<think>` block past its
  output budget, producing empty replies. Sized the prompt to the model;
  added doc-drift tests. The full 8B run this pass measured: no crash, no
  patch either.
- **Pass 87** — root-caused the empty-reply wall precisely: Ollama's
  `thinking` field, not the visible budget. Added the ability to disable a
  reasoning model's `<think>` block in the loop.
- **Pass 88** — two navigation defects: `find_symbols` could not resolve a
  bare test-method name (class methods were indexed only as
  `"ClassName.method"`), and a failed `read_file` gave no bridge to a better
  guess. Both fixed; re-run showed the model reaching the right file in half
  the steps, then reading it five more times without ever calling
  `patch_file`.
- **Pass 89** — added `reads_since_mutation_attempt`: a nudge appended after
  4 consecutive read-only calls telling the model to stop reading and patch.
  Instrumented the live re-run to confirm the nudge fired exactly on
  schedule — and the model read on anyway. A suggestion embedded in an
  observation did not change the next action.
- **Pass 90** — escalated from suggesting to refusing: once
  `reads_since_mutation_attempt` hits the threshold, read-only tools are
  hard-blocked before their handler runs, forcing a mutating call.
  `patch_file`/`write_file`/`finish` stay exempt; the gate is off entirely
  under `allow_write=False`.
- **Pass 91 — the hard gate worked, and produced a fake green.** Forced to
  act, qwen3:8b patched `tests/test_utils.py` (changing an unrelated
  assertion, not the planted bug) and called `finish()` claiming success;
  the loop reported `success=True`. `git diff` showed the real bug
  untouched, `pytest` still 4 failed — editing the test instead of the code
  it exercises, the exact fake-green shape this file names at the top,
  found this time inside the very mechanism pass 90 had just built. Fixed
  two ways: a repair-goal `patch_file`/`write_file` targeting a test path is
  now rejected outright before it runs (names the real next move instead);
  and the read-only hard block now requires `located_region` — it must not
  fire before the model has actually found a real definition to patch,
  since firing blind was what forced the wrong-file patches. Threshold
  raised 4 → 7 for the hard block, keeping the softer nudge at 4.

**Honest state, not yet resolved:** across all seven passes, no patch has
landed correctly against this planted bug. Each pass fixed a real, measured
defect in the loop itself — the underlying question, whether this loop can
get a local model to correctly fix someone else's real bug, is still open.
The next live re-run with pass 91's fixes in place has not been done yet.

Full suite: 2175 (pass 84) → 2199 (pass 89) → 2203 (pass 90) →
**2207 passed, 13 skipped** (pass 91). Detail for all seven passes:
`NOTEBOOK_IMPORT.md`, "Pass 85" through "Pass 91."

**Pass 92 — official SWE-bench Lite infrastructure installed and run
end-to-end for the first time.** Docker Desktop was installed but its
daemon was not running (found at
`AppData\Local\Programs\DockerDesktop\`, a user-scoped install); started
it. Installed `swebench==5.0.2` and `datasets==5.0.1`. Re-checked
`scored_swebench_availability()` (pass 52): **`available=True`** for the
first time on this machine — all 300 real SWE-bench Lite instances load
from HuggingFace. Ran one real instance (`psf__requests-3362`, chosen for
being the smallest/simplest) end-to-end: real repo clone at the
instance's `base_commit` → Saleha's real `AgentLoop` via
`swe_bench_runner.run_benchmark()` → the official
`swebench.harness.run_evaluation`. Result, from the official harness's
own report: **`Instances resolved: 0`, `Instances with empty patches: 1`**
— the agent made no edit to the real repo, consistent with every prior
real-repository measurement (passes 53, 85-91). One instance is not a
benchmark score; a full-sample Pass@1 has not been attempted, and this
machine's Docker VM is capped at 7.61 GiB memory, an unmeasured
constraint on how large a real run this machine can sustain. Also fixed
in the file this pass touched: `swe_bench_runner.py`'s module docstring
was romanized Hinglish (English-only rule, found in a fourth file after
`orchestrator.py`/`safety_guard.py`/`self_healing.py`) and stale
(described a "synthetic diff" fallback the code no longer has) —
rewritten in English and corrected to match the real code. Detail:
`NOTEBOOK_IMPORT.md`, "Pass 92."

**Pass 93 — a fifth fake green in the agent loop, fixed: a "successfully
patched" tool response was never proof the fix was correct.** Probed
isolated capability first: given the exact buggy lines with no navigation
needed, `qwen2.5-coder:3b` diagnosed the bug correctly but never emitted
`patch_file` (2/2 trials, called `finish()` with an explanation instead,
even with `patch_file` the only tool offered); `qwen3:8b` emitted a
byte-correct patch (2/2). Different gaps, so tested each model's
different failure mode in the full loop next. `qwen3:8b` through
`AgentLoop` against a fresh planted `super_len` bug: navigated correctly,
`patch_file` reported success, `finish()` claimed the bug fixed — verified
against reality, the edit landed on the wrong line and the real suite went
**4 failed → 6 failed**. Every existing gate (pass 85's zero-mutation gate,
pass 91's test-file guard) passed it through, because
`mutations_succeeded > 0` was true — the tool genuinely did not error, so
"did a write succeed?" was still the only question ever asked, three fixes into this
exact lineage. Root cause: `run_tests`/`TESTS_PASSED` have existed since
pass 53 and no production `AgentLoop` construction site (`saleha agent`,
`swe_bench_runner.py`) has ever passed `require_evidence` as `True` — the
verification machinery had never once executed on a live repair run.
**Fix: the loop verifies itself** — once a repair-goal run has a
successful mutation, before admitting `finish()`, the loop calls its own
`_tool_run_tests()` directly (no model turn, no opt-in flag needed). No
discoverable test command → stays out of the way; tests pass → admits
normally; tests fail → REJECTED with the real pytest output embedded,
cached so a retry does not re-run the whole suite. A second, real bug
found while testing: the new step was only `emit()`-ted to the event
stream, never appended to `result.steps` — the exact gap pass 90 named and
fixed for its own `-blocked` observations, reproduced in new code three
passes later. Fixed for the new step; the same gap pre-exists on four
older `finish-rejected` sites (passes 53/85/89) — left as a separate,
recorded finding, not folded into this fix. Teeth-checked: 2/4 new tests
fail against the unfixed loop. Live re-run twice against a fresh planted
bug each time: both end **`success: False`, max_steps exhausted** — the
wrong patch is genuinely on disk, the suite genuinely reports 6 failed,
and the CLI-facing result is now an honest failure instead of a green
tick over a broken fix. **Honest state: `qwen3:8b` still has not landed a
correct patch across nine measured attempts (passes 53, 85-93) — this
pass did not fix that. What changed is that a wrong fix is now reported
as wrong**, which is what lets a future pass tell "the loop is broken"
apart from "the model cannot do this yet" instead of both producing the
identical false `success: True`. Measured: `test_agentic_loop.py` 76 →
**80/80**; full suite 2207 → **2211 passed, 13 skipped, 172 subtests**,
zero regressions. Detail: `NOTEBOOK_IMPORT.md`, "Pass 93."

**Pass 94 — two more real defects for `qwen2.5-coder:3b`, both isolated
before being fixed.** Followed up pass 93's open item: measured
`qwen2.5-coder:3b`'s different failure mode (never calling `patch_file`
at all) inside the full loop, not just in isolation. Found two genuine
bugs, neither assumed going in. **Defect 1:** `get_file_outline`'s hint
and the `located_region` the loop remembers both used `re.search()`
(first match only) against a multi-function outline, so whichever
function happened to sit first in the file always won — a live run's
rejection told the model to read `dict_to_sequence()`'s lines instead of
the goal's actual `super_len()`. Invisible in every earlier pass because
`super_len` happened to be first at the commit those passes used; a
fresh clone put a different function first. Fixed with
`_find_goal_relevant_outline_entry()` — an outline entry whose name the
goal actually mentions now wins over position; falls back to the first
entry, unchanged, when the goal names nothing identifiable. **Defect 2,
the bigger one:** isolated probing showed `qwen2.5-coder:3b` calls
`finish()` with a prose diagnosis on turn one of a repair goal, 2/2
trials — and an explicit prompt sentence ("finish() is not available
until...") changed nothing, 3rd identical trial. Removing the `finish`
option from the prompt structurally (no textual substitute) fixed it
immediately: identical goal, first-turn `get_file_outline` call. Added
`SYSTEM_PROMPT_NO_FINISH`, selected per-step while
`successful_actions < min_actions_before_finish`; the existing rejection
path is untouched for a model that invents `finish()` anyway. 4 new
tests, teeth-checked against `HEAD`. **Live re-run after both fixes:**
real progress, not yet a fix — `qwen2.5-coder:3b` called `list_dir` on
turn one (never before this pass), reached `get_file_outline` and
`read_file`, but one successful action re-opens `finish()` and the model
reaches for it again instead of continuing to `patch_file`; `patch_file`
was never called and `git diff --stat` showed only the planted bug.
`min_actions_before_finish=1` is armed and disarmed too easily for this
model's pattern — recorded as the next candidate (raise the threshold,
or hide `finish()` until a mutation attempt rather than any success),
not implemented this pass. Measured: `test_agentic_loop.py` 80 →
**84/84**; full suite 2211 → **2215 passed, 13 skipped, 172 subtests**,
zero regressions. Detail: `NOTEBOOK_IMPORT.md`, "Pass 94."

**Pass 95 — `qwen2.5-coder:3b` calls `patch_file` for the first time
ever in this lineage; the patch is still wrong, and the loop honestly
says so.** Picked up pass 94's own recorded next candidate: `finish()`
was re-armed by any successful action (`successful_actions`), so a
single `list_dir` satisfied `min_actions_before_finish=1` and the model
reached for `finish()` again instead of continuing toward `patch_file`.
Fixed narrowly: for a repair goal with `allow_write` on, `finish()`
readiness is now gated on `mutations_attempted`, not
`successful_actions` — reading alone never repairs anything. Every
other case (investigative goals, `allow_write=False`, an explicit
`min_actions_before_finish=0`) is untouched. **Live re-run result:** the
model completed the full navigate-to-mutation path for the first time in
nine full-lineage attempts (passes 53, 85-95) —
`list_dir → get_file_outline → read_file → patch_file` — and the
pass-93 auto-verify gate caught the result being wrong (real suite
4 failed → **10 failed**: the model added `o.tell()` at the top of the
function, crashing on non-file-like inputs, and actually *removed*
`- current_position` from the return statement rather than adding it).
`success: False`, honest, no fake green. New failure mode recorded, not
yet fixed: the model gave up retrying `patch_file` after one rejection
and spent the remaining steps repeating `finish()` instead, despite the
rejection naming the real next move each time. 1 new test, teeth-checked
against the pre-pass state. Measured: `test_agentic_loop.py` 84 →
**85/85**; full suite 2215 → **2216 passed, 13 skipped, 172 subtests**,
zero regressions. Detail: `NOTEBOOK_IMPORT.md`, "Pass 95."

**Passes 96-102 — the finish()/patch_file lineage lands a real repair, then
four Master Vision pillars get built and wired together.**

- **Pass 96** — `finish()` stays hidden after auto-verify records a failing
  test, not just for one turn: `qwen2.5-coder:3b` had been calling
  `finish()` seven times in a row after a rejection instead of retrying
  `patch_file`. Fixed in `agentic_loop.py`; re-opens automatically once a
  new mutation is attempted.
- **Pass 97 — first real end-to-end repair.** `qwen2.5-coder:3b` fixed a
  planted arithmetic bug in a fresh repo (`double(x)` missing `* 2`),
  verified by a real pytest run, `finish()` admitted honestly: 0 failed,
  3 passed. First time any local model completed the full
  explore→patch→verify journey in this lineage (passes 53, 85-96 had all
  failed or produced a caught-wrong patch).
- **Pass 98 — `saleha solve` / `IssueResolver` autonomous mode.** Wired
  `AgentLoop` into `IssueResolver`; new `--autonomous` path drives a real
  git branch, commits atomically, and generates an honest diff. Fixed a
  real `diff_engine.py` bug found during this work: `lineterm=""` stripped
  newlines from diff headers, corrupting single-line-deletion diffs.
- **Pass 99 — ToolForge wired into `AgentLoop`** (`forge_tool` action,
  gated by `approve()` + AST security + sandboxed pytest) and a multi-cycle
  batch self-improvement engine (`run_self_improvement_batch`), fixing two
  real bugs found while building it (a `skip_set` extension-mismatch, a
  `FileNotFoundError` on branch switch when `TEST_DIR` didn't exist yet).
- **Pass 100 — `OctopusCoordinator`** (`saleha octopus <goal>`): a real
  9-brain coordination engine (Planner/Architect/Coder/Security/QA/
  SRE/Critic/ToolForge arms + a central synthesizing mind), concurrent
  phases via `AgentWorkerPool`, physical sandbox execution — a failing test
  in the QA arm's sandbox genuinely sets `success=False`, no fabricated
  green.
- **Pass 101 — `LocalSupremacyEngine`** (`saleha supremacy <problem>`): real
  test-time-compute tournament — 4 stratified trajectories at different
  temperatures, scored through real AST/security/sandbox checks, with
  traceback-conditioned Reflexion repair on the best near-miss candidate.
  Reports a measured amplification factor, not an asserted one.
- **Pass 102 — harmonization.** `OctopusCoordinator`'s coder arm can now
  route through `LocalSupremacyEngine` (`--supremacy` flag on both `saleha
  octopus` and the new `/api/octopus/run` endpoint). Fixed a real Python
  3.14 import-lock deadlock (pre-warming `planner`/`architect` module
  imports on the main thread before worker-pool dispatch). Added 5 real
  REST/SSE endpoints in `web_server.py` (`/api/stream/octopus`,
  `/api/octopus/run`, `/api/supremacy/run`, `/api/solve/run`,
  `/api/tools/forge`) — read in full, genuinely wired to the real engines,
  the SSE stream correctly opts out of the pass-50 keep-alive framing with
  `Connection: close` since it's the one unbounded response. Live-measured
  on real `qwen2.5-coder:3b`: 4-trajectory tournament, one candidate
  genuinely failed sandbox tests (score 40.0) while three passed (100.0),
  proving the sandbox actually discriminates rather than rubber-stamping.
  Claimed **37/37 passed** across the 4 affected test files — independently
  re-run and confirmed. Full suite (session-verified, not just the
  ledger's claim): 2255 passed, 13 skipped — 1 failure
  (`test_project_scaffolder.py::test_existing_dir_needs_force`) that
  reproduced only under full-suite load and passed clean in isolation;
  root-caused to the same Windows temp-cleanup race documented in pass 84,
  just surfacing in a new file. **Fixed, not just noted**: the nested
  `pytest test_main.py` subprocess `_verify_fastapi()` runs was writing
  `.pyc`/`.pytest_cache` files under the scaffolded temp dir, which Windows
  can still hold open for a moment after the subprocess exits — the
  caller's own `tearDown` then raced `WinError 32` when removing that temp
  dir. Fixed by running the nested pytest with `-p no:cacheprovider` and
  `PYTHONDONTWRITEBYTECODE=1`, removing the cache files rather than timing
  around them. Teeth-checked: 5/5 clean repeated runs after the fix.
  Detail for all seven passes: `NOTEBOOK_IMPORT.md`, "Pass 96" through
  "Pass 102."

**Pass 103 — verified Pass 102's own claims before committing, fixed a
full-suite-only Windows flake.** Independently re-ran Pass 102's claimed
37/37 and reviewed its diffs before trusting them (confirmed genuine).
Full suite then showed 1 failure
(`test_project_scaffolder.py::test_existing_dir_needs_force`, passed clean
in isolation) — root-caused to a nested `pytest test_main.py` subprocess
writing `.pyc`/`.pytest_cache` files that Windows can still hold open
briefly after the subprocess exits, racing the caller's own temp-dir
cleanup. Fixed with `-p no:cacheprovider` + `PYTHONDONTWRITEBYTECODE=1` on
that subprocess call, removing the cache files instead of timing around
the race. Teeth-checked: 5/5 clean repeated runs after the fix, then a
full-suite re-run at 2256 passed / 0 failed confirmed it holds under load.

**Pass 104 — ran a real, official SWE-bench Lite instance against the
hardened loop; found and fixed a real fallback-nudge bug, capability gap
remains open.** Followed up the standing open item (no local model has
correctly fixed a real repository bug end-to-end, only pass 97's
hand-planted toy bug). Ran `psf__requests-3362` (real dataset instance,
real base_commit checkout, no file/line hint) through `qwen2.5-coder:3b`.
First run: empty patch, 14 wasted steps — the model guessed a nonexistent
`./src/main.py` at step 1 and oscillated between that dead guess and
re-listing the repo root for the rest of the budget, because
`agentic_loop.py`'s repeat-nudge fallback (used when `located_region` is
empty) named no concrete path to try instead. Fixed: track subdirectories
seen via `list_dir` but never themselves explored, and name one in the
nudge. Teeth-checked against the pre-fix code. Live re-run: the fix
demonstrably fired (the nudge correctly named a real `docs/` directory)
— but the run still failed differently: the model invented a *second*
nonexistent filename and, even after its own tool calls showed the real
`requests/` package directory, never entered it. **Honest state: this is
a real, newly-observed capability gap — the model does not act on
evidence its own tool calls just produced — distinct from every prior
fixed pattern in this lineage (passes 89-91, 95). Not fixed this pass;
recorded rather than prompt-tuned around one transcript.** Also incidentally
caused, then immediately caught and reverted, a process-hygiene mistake:
an old `requests` checkout's `pip install -e .` was first run against the
project's own `.venv` by accident (should have used an isolated venv from
the start), downgrading its `requests` to 2.10.0 and breaking `saleha`
imports; caught by a sanity check before continuing, reverted, and
verified `import saleha` + a real test passed clean afterward. A second,
unrelated full-suite-only flake was also observed while re-verifying
(`test_mcts_search_engine.py`, real sandboxed-execution timing, not this
session's diff) — recorded as a known intermittent, not fixed. Full
suite: 2256 passed, 13 skipped (test_agentic_loop.py 90 → 91/91 with the
new test). Detail: `NOTEBOOK_IMPORT.md`, "Pass 103" and "Pass 104."

**Pass 105 — fixed the evidence-ignoring bug pass 104 found; still didn't
solve the instance.** Added `confirmed_files` tracking (from real
`list_dir`/`find_symbols`/`search_repo` results) and a hard gate:
`patch_file`/`get_file_outline` on a path never confirmed to exist are
rejected outright once any real evidence exists, naming a real file
instead of letting the model repeat an invented one. Live re-run of the
same `psf__requests-3362` instance: the invented-filename defect is
gone, confirmed in the transcript — but the model then wandered into the
real `docs/` directory instead of the relevant `requests/` package and
got stuck re-reading `docs/conf.py`, never calling `find_symbols` or
`patch_file`. Honest failure, clean tree. **Two fix passes (104, 105)
against this one real instance, no patch landed yet.** Next-session
decision recorded, not made unilaterally: try a bigger local model
(`qwen3:8b`/`qwen3.5:9b`) on this same instance, or treat this as a
measured `qwen2.5-coder:3b` capability ceiling and move on. Full suite:
2259 passed, 13 skipped (test_agentic_loop.py 91 → 93/93). Detail:
`NOTEBOOK_IMPORT.md`, "Pass 105."

**Pass 106 — tried the bigger model on the same instance: navigation
solved, correctness didn't.** `qwen3:8b` against the identical hardened
loop and the identical `psf__requests-3362` instance: found the exact
right function (`requests/models.py:653`, `iter_content`) and the target
test by step 3 using `search_repo`, no wasted calls, `patch_file`
succeeded at step 5 — the fewest steps to a real mutation of any run in
this lineage. But the edit (flipping `iter_content`'s default parameter)
is a **provably wrong fix**: the real bug is one function deeper, in
`stream_decode_response_unicode()` (`requests/utils.py`, confirmed
against the dataset's own gold patch), and the target test always passes
`decode_unicode=True` explicitly, so the model's default-flip can never
affect it either way. The loop correctly did not report success — `run_tests`
failed and `finish()` was never admitted. **Conclusion: bigger model fixed
navigation, not correctness.** The open gap has narrowed from "can't find
the file" to "picks a plausible-looking function one level too shallow
when multiple functions relate to the symptom." No code change this pass
— a measurement, recorded for the next session. Detail:
`NOTEBOOK_IMPORT.md`, "Pass 106."

**Pass 107 — resumed the `saleha/core/` bulk audit sweep, stalled since
pass 48.** Read four never-before-audited modules in full, prioritized by
real importer count: `security_scanner.py` (16 importers),
`fast_inference.py` (11), `codebase_indexer.py` (10),
`polyglot_executor.py` (7). All four are genuinely real; five real
defects found and fixed:

- `security_scanner.py` — the JS/TS hardcoded-secret regex matched only
  snake_case (`api_key`), missing camelCase (`apiKey`, `jwtSecret`,
  `secretKey`, `authToken`) — measured before fixing: all four scored 0
  vulnerabilities. Fixed with an optional-underscore pattern.
- `fast_inference.py` — the docstring claimed a `tenacity`-gated retry
  fallback that never existed in the code; `HAVE_TENACITY` was checked but
  `tenacity` itself was never imported or used. Measured:
  `max_retries=2` produced 3 real attempts regardless of tenacity's
  presence. Removed the dead detection, corrected the docstring.
- `codebase_indexer.py` — three real bugs in `SmartPatcher.apply_search_replace`,
  the function behind the live `patch_file` tool that passes 53-106 have
  been hardening: (1) the fuzzy blank-line skip indexed the wrong list
  (`search_lines[k]` instead of `trimmed_search[k]`), aborting a match
  that should have succeeded whenever a blank line appeared at the same
  position in both search and source; (2) the indentation-tolerant match
  mode spliced in the replacement's own literal leading whitespace instead
  of the source's real indentation, silently reformatting untouched code
  (a tab-indented line patched via a 4-space block lost its tab); (3) a
  `replace_block` with no trailing newline glued the next real source line
  onto the end of the replacement. All three teeth-checked against pre-fix
  code.
- `polyglot_executor.py` — the exact class of bug `CLAUDE.md` already
  names for this file (pass 36: `subprocess.run` with `text=True` and no
  `encoding=`) in two sibling calls (`javac`, `rustc` compile invocations)
  the earlier pass didn't touch. Measured live with a real `rustc` on
  PATH: a CJK compiler error came back as mojibake before the fix,
  correct after.

Full suite: 2259 (pass 106) → **2270 passed, 13 skipped, 172 subtests**,
zero failures. ~111 of the ~115 never-before-named `saleha/core/` modules
remain; next candidates by importer count: `task_scheduler.py`,
`soul_engine.py`, `mcp_engine.py` (4 each), then `vision_coder.py`,
`tri_tier_memory.py`, `tech_debt_analyzer.py`, `sre_responder.py`,
`mcp_hub.py`, `lora_tuner.py`, `evaluator.py`, `deliberation_engine.py`,
`conflict_resolver.py` (3 each). Detail: `NOTEBOOK_IMPORT.md`, "Pass 107."

**Passes 108-111 — the `saleha/core/` sweep continued, then the agent-repair
lineage got a depth/coverage gate.** Pass 108 read the next 10-module batch
(all remaining 4-and-3-importer modules): 9 real defects fixed across 7 of
them, including a cron weekday-numbering mismatch (`task_scheduler.py`), a
swallowed disk-write failure that let `soul_engine.py` report a soul switch
as successful while the persisted active soul silently stayed unchanged, and
`mcp_hub.py`'s `connect_server()` — the same "Simulated successful handshake"
pattern this project's audit exists to catch, now checking `shutil.which()`
instead of unconditionally returning `success=True`. Pass 109 followed up
with 9 leftover defects plus 1 caller bug (`chat_session.py`'s `/schedule`
mis-split a cron string, registering a task that could never fire while
printing "Successfully"), all red-confirmed by direct probe before fixing,
13 new tests. Pass 110 closed pass 106's open gap (the agent picks a
plausible function one level too shallow): repair-goal success now
additionally requires a real test-file read plus a revert-check (the suite
must fail with the patch removed, or the fix is unproven). Pass 111 went one
level deeper with a stdlib-`trace`-based coverage prover — the failing
tests must actually execute at least one changed line, not just still exist.
Suite: 2290 (pass 108) → 2303 → 2309 → **2313 passed, 13 skipped, 172
subtests** (pass 111). Detail: `NOTEBOOK_IMPORT.md`, "Pass 108" through
"Pass 111."

**Passes 112-117 — six more itemized `saleha/core/` audit passes, each with
real defects found and fixed.** `vault.py`'s save path crashed outright on
Windows for a bare filename (`os.makedirs('')` → `FileNotFoundError`), and
its `rekey()` was not atomic — a crash mid-write could permanently lock the
vault under a new key with the old salt still on disk; both fixed (pass
112). `dependency_graph.py`'s cycle detector used recursive DFS, risking
`RecursionError` past ~1000 files in an import chain (this repo's own
`saleha/core/` already has 252 modules) — rewritten as an iterative,
stack-based DFS (pass 113), plus a same-day follow-up fixing a real
`float(None)` `TypeError` risk and a missing `disable_reasoning`/`**kwargs`
parameter gap between `ProfileAgent.think` and `BaseAgent.think`. Pass 114
was confirmed fully mechanical (type hints, `contextlib.suppress`, import
sorting) with no defect claimed or found. Pass 115 found a real measurement
bug: `change_impact.py`'s blast-radius denominator walked the whole repo
with **no directory pruning**, so every `.py` file under `.venv`/
`node_modules`/`build` inflated the file count and deflated every blast-radius
percentage — fixed to prune the same directories the file's own caller-search
already pruned. Pass 116 found `approval_gate.py`'s constructor bypassing its
own `_MODE_ALIASES` normalization table (the module-level function used it
correctly; the class constructor didn't), and `agent_contracts.py` silently
excluding every `async def` from `functions_defined`. Pass 117's `text()`
closure fix in `debate_consensus_orchestrator.py` was checked against the
diff and found to be a defensive ruff-B023 fix, not a live bug (the closure
is always called synchronously within the same loop iteration it's defined
in) — recorded precisely rather than taken at the commit message's word;
`persona_debate.py`'s five-emoji markdown report headers were a genuine
Rule 3 fix. Detail for all six: `NOTEBOOK_IMPORT.md`, "Pass 112" through
"Pass 117."

**Passes 118-132 — fifteen one-line-commit-message "hardening" passes,
read in full rather than trusted: mostly mechanical, with three real
fabrications and several real robustness bugs mixed in.** The bulk of
~65 touched files across this range are confirmed purely mechanical
(`-> None` annotations, modernized `list[str]`/`dict[str, Any]` generics,
dead-import removal, `contextlib.suppress` conversions, Rule-3 emoji
removal) — but reading every diff rather than accepting "hardening" at
face value surfaced real content:

- **Two fabricated-success responses found and fixed in `voice_live.py`
  (pass 126).** `_default_executor()` returned hardcoded outcome claims
  for voice commands that never actually ran anything — "All tests now
  passing," "100% tests passed," "Score is 98/100, zero critical issues,"
  a STATUS reply inventing "20 agents active... 558 tests green." Same
  fabricated-outcome shape this project's whole audit history exists to
  catch, found in a live voice-command path. Fixed to state only that an
  action is starting, not its invented result. The same pass also fixed a
  real crash: `voice_assistant.py`'s auto-exec path called a
  `SalehaOrchestrator.run_task()` method that **does not exist** (the real
  method is `execute_task`) — every real call through that lambda would
  have raised `AttributeError`, and it called the (nonexistent) method up
  to three times per invocation besides.
- **One fabrication found and left unfixed — flagged here as open, not
  resolved by pass 130.** `sidecar_daemon.py` (a real, reachable local
  HTTP daemon wired to the live `saleha sidecar` CLI command) still
  returns the **unmodified input code** claiming `"Handled edge cases
  safely"` for its Auto-Fix action, and a fixed `assertTrue(True)` stub
  for Gen Tests regardless of what was submitted. Pass 130's actual diff
  for this file only touched emoji/whitespace — the fabricated bodies are
  untouched. A real user clicking Auto-Fix or Gen Tests in the sidecar
  today gets a fabricated success claim.
- Real, smaller robustness fixes recur across the range: `sys.executable`
  preferred over `shutil.which("python3")` for running generated code (4
  separate files: `polyglot_executor.py`, `project_builder.py`,
  `code_executor.py`, consistent with `sandbox_runner.py`'s pre-existing
  behavior) so generated code runs under the same interpreter as Saleha
  itself rather than an unrelated `python3` on PATH; a real double-count
  bug in `code_migrator.py` (`changes += 1` duplicated on one line,
  inflating the reported migration change count by one); and the same
  PID-suffixed atomic-temp-file pattern (`f"{path}.tmp.{os.getpid()}"` +
  `os.replace()`) applied to `stats_tracker.py`, `diff_engine.py`,
  `project_memory.py`, `cloud_deployer.py`, and `deployer.py`.

No full-suite pass/fail count is recorded in any of these 15 commit
messages for this specific range (most report only a ruff-clean claim or a
file-scoped test count) — none is invented here to fill the gap. Detail for
all fifteen: `NOTEBOOK_IMPORT.md`, "Passes 118-132."

**Pass 133 — `sidecar_daemon.py`'s Auto-Fix and Gen Tests were fabricating
results; pass 130 had labelled this file "hardening" but only touched
emoji/whitespace in it.** Found immediately after writing up the summary
above. Confirmed live-wired (`saleha sidecar`, via `sandbox_exec.py`)
before treating it as urgent. Three of four action branches were
fabricated: `"fix"` returned the caller's own unmodified input with a
hardcoded `"Handled edge cases safely"` comment appended (no repair
attempted); `"test"` returned a fixed `assertTrue(True)` stub regardless
of input (the same shape as passes 23 and 30's fabricated tests, found a
third time); the default `"explain"` branch returned a fixed "Code
defines standard execution logic with clean structure" string regardless
of input. `"sast"` was already genuine. Rewired to existing, already-
audited machinery: `"explain"` now calls the real AST analyzer behind
`saleha explain-code`; `"fix"`/`"test"` now call the same real
`CoderAgent.generate_code`/`generate_tests` path `saleha build` uses,
reporting the model's actual failure instead of a fabricated success.
The existing test file had exactly one test (asserting HTML button
labels only) — zero coverage of the actually-fabricated dispatch logic,
the same trap this file names repeatedly. Added 7 tests; teeth-checked
at 7/8 failing against the unfixed file. Full suite: 2314 → **2321
passed, 13 skipped, 0 failures**. Detail: `NOTEBOOK_IMPORT.md`,
"Pass 133."

**Pass 134 — `agentic_loop.py` read in full (2391 lines, user-requested
audit); `test_timeout_sec` was not bounded by the run's own
`timeout_sec`.** This is the most heavily hardened file in the repo
(passes 53, 85-111) and the read confirmed almost all of it clean — one
real gap survived. `test_timeout_sec` defaults to 600s, `timeout_sec`
300s, and nothing bounded the former by the latter: the outer per-step
deadline check cannot interrupt a `subprocess.run` call already in
flight. Confirmed real exposure by reading the caller: `saleha agent`
exposes a user-facing `--timeout` flag (30-7200s, printed in its own
startup panel) but never passes `test_timeout_sec` — a user setting
`--timeout 30` could have the run block up to 20x longer than promised
the moment the repair-goal auto-verify or coverage-check gate fired a
real test run. `swe_bench_runner.py` has the same exposure from the
other side. Fixed with `_bounded_test_timeout()`, capping
`test_timeout_sec` against whatever remains of `timeout_sec` (floor
1.0s). 5 new tests; teeth-checked at 5/5 failing against the unfixed
file. Live probe: a real 10s-sleeping test, run with ~1s of budget
remaining, was actually cut off at ~1.02s. Full suite: 2321 → **2326
passed, 13 skipped, 0 failures**. Detail: `NOTEBOOK_IMPORT.md`,
"Pass 134."

**Pass 135 — top-5 never-audited `saleha/core/` modules by importer
count (a prior research agent found the "~111 unread" note stale: 118
of 242 were already covered by passes 108-134, leaving 124 genuinely
unread).** Read `team_orchestrator.py` (13 importers), `path_utils.py`
(12), `git_native.py` (11), `task_history.py` (10),
`neuro_symbolic_engine.py` (8) in full. All five genuinely real, two
real defects confirmed by direct reproduction:

- **`team_orchestrator.py`** — a failed security-agent model call fell
  back to fixed text containing neither VULNERABLE nor WARNINGS, so the
  verdict parser read a review that never ran as `APPROVED` — the same
  fake-green shape pass 30 fixed once in `pr_generator.py`, found a
  second time. Fixed with an explicit `UNAVAILABLE` verdict.
- **`git_native.py`** — `create_task_branch()` never checked `git
  checkout -B`'s return code, so it returned a truthy branch name even
  when the checkout genuinely failed (reproduced with a locked git
  index: branch never changed, function still returned the name).
  `repo_orchestrator.py` treats that return as proof a branch was
  created — the same shape as pass 65's unchecked `git checkout` in
  `self_healing.py`/`self_improve.py`. Fixed to return `""` on failure.
- **`neuro_symbolic_engine.py`** — its security-scoring dimension used
  substring matching, defeated by a realistic import-alias evasion
  (`from os import system` then `system(cmd)`), measured to score
  "OWASP Top-10 SAST Clean" before the fix. This scorer is a real
  ranking signal for the self-play arena, MCTS search, GRPO trainer,
  and self-evolving loop. Fixed via AST alias resolution; deliberately
  does not attempt full taint tracking (`run = os.system` remains
  undetected — confirmed to be a gap the repo's more thorough
  `ASTSecurityScanner` shares, not unique to this file).
- `path_utils.py`/`task_history.py` — both genuinely correct;
  Rule 1/3 cleanup only. Several Rule 3 emoji removals across this pass
  were measured, not assumed, to *not* be live crashers via their real
  entry points (an existing UTF-8-reconfigure guard or explicit
  UTF-8 subprocess encoding already protects them) — verified directly
  rather than repeating the "crash risk" framing from files where it's
  proven true.

11 new/regression tests, teeth-checked against git-stashed pre-fix
code. Full suite: 2327 → **2332 passed, 13 skipped, 0 failures**.
Detail: `NOTEBOOK_IMPORT.md`, "Pass 135."

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
  never tests. It was kept for `torch` (the LoRA/training path). Pass 35
  recorded that its `Scripts/` had no `python.exe`; **it has since been
  recreated and works — verified pass 84, Python 3.11.16.** Still never run
  the suite there: 3.11 is below the `requires-python = ">=3.12"` floor. `.vscode/settings.json`
  (gitignored) now points `defaultInterpreterPath` at `.venv`. The GPU
  training tests are backend-aware since pass 35: with no `torch` they
  assert the honest `success=False`, not a skip or a crash.
- `pip install -e ".[dev]"` alone does **not** give a passing test run: two SMT
  tests need `z3-solver`, which lives in the `[formal]` extra. A working test
  environment also wants `tree-sitter*` and `numpy`. `graphifyy` is now in
  the `[dev]` extra too (pass 35) -- without it 8 real-graph tests in
  `test_repo_graph.py` skip.
- Test suite: `python -m pytest saleha/tests/ -q` — 2303 passed, 13 skipped,
  172 subtests, ~227s (as of pass 109, measured this session). Set `PYTHONIOENCODING=utf-8`; the console is cp1252 and
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
