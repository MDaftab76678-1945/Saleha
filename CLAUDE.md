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

**Still template (documented in `ARCHITECTURE.md`, not yet fixed):**

- `cloud-plan` (`cloud_infra_orchestrator.py`) — 4 of 5 artifacts byte-identical
  across unrelated goals; cost always $142.50, CIS score always 96.
  `--output-dir` writes these to disk as real-looking `main.tf` / `iam-policy.json`.
- `silicon-build` (`silicon_circuit_orchestrator.py`) — same fixed ALU for every
  request; 184 LUTs / 450 MHz constant; `is_synthesizable=True` unconditional.
- `causal-eval` (`causal_world_model.py`) — the "intervention" layer calls the
  same code path as the "association" layer.
- `multirepo` (`multirepo_orchestrator.py`) — every field identical across goals.

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
- Test suite: `python -m pytest saleha/tests/ -q` — ~1559 tests, takes ~5 min.
  Set `PYTHONIOENCODING=utf-8`; the console is cp1252 and emoji in output will
  otherwise crash the run.
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

## Communication

- The user writes in Hindi/Hinglish. Reply in the same.
- Be direct. Report what was found, including what is still broken.
- Report failures plainly. If tests fail, say so with the output. If a step was
  skipped, say that. Never dress up a partial result as a finished one.
- The user also runs other agents in parallel (Gemini has been used alongside),
  coordinating through `COORDINATION.md`. Keep that file usable.
