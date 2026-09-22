# Auditing a file in this repo

Applies whenever you are asked to check, audit, or review a file.

1. **Read the whole file with `Read`. Not `grep`.** A grep for one pattern finds
   one bug and hides the rest. `orchestrator.py` was "checked" three times with
   grep; read in full the fourth time, it had six more bugs — one on a line that
   had already been scrolled past twice.
2. **Report the full list of findings, then stop.** Do not fix and commit unless
   asked.
3. **Never conclude "done" or "clear."** State what was examined and what was
   found. A green test count is not proof a file is clean.
4. **Prove every claim by running it.** Probe the defect, show the before/after.
   A finding without a measurement next to it is a guess.
5. **Check git and the docs before asking the user a question.** The answer is
   often already recorded.

## What a fabrication looks like

- A result reported with no computation behind it — hardcoded `True`, a fixed
  score, a literal "PASSED" string.
- A component that **generates the thing it then verifies itself against**: a
  probe that writes both the fixture and the fix, a benchmark whose candidate is
  a copy of its own input, a harness that grades against its own answer key.
- A fallback that returns a reassuring default when the real step could not run.
  "Did not run" and "passed" must never render the same.
- A claim in a docstring or `SKILL.md` that the code does not implement.

Naming that oversells is *not* a fabrication, as long as results are real and
the limits are stated. A template that says it is a template is a scaffold.

## Before changing what you find

Check whether the existing test asserts the broken behaviour. It usually does —
that is why the bug survived. Replace it, and teeth-check the replacement
against the pre-fix code (`git stash`) to confirm it actually fails there.
