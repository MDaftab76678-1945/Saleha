---
paths:
  - "saleha/core/**/*.py"
  - "saleha/agents/**/*.py"
---

# Working inside saleha/core/ and saleha/agents/

## Recurring defect shapes

These have each been found in three or more separate modules here. Check for
them by default:

- **Unchecked subprocess/git return codes.** `git checkout`, `git commit` and
  `subprocess.run` results were repeatedly ignored, so a failed step reported
  success and the next step ran against the wrong state. Check `returncode`, and
  read `stderr` — hook and git messages go there, not stdout.
- **`subprocess.run(..., text=True)` with no `encoding="utf-8"`.** Falls back to
  cp1252 and can swallow a decode crash on non-ASCII output.
- **Import-time side effects.** `os.makedirs` or code execution at module import.
  Defer to first use via a lazy singleton.
- **Silent partial scans.** A walker that skips files it cannot handle and
  reports the same shape as a clean result. Return explicit
  `analyzed` / `skipped` / `is_complete` fields instead.
- **A fallback that reads as approval.** When a model call or verification stage
  fails, the fallback text must not parse as a pass. "Did not run" needs its own
  verdict, distinct from both "clean" and "failed".

## Circular imports

The flat-to-subpackage migration exposed latent cycles: a category
`__init__.py` eagerly imports its submodules, so a module-level import that
reaches back into another subpackage closes a loop that the flat layout hid.

Fix by making the import lazy (function-local, or `TYPE_CHECKING` for
annotations). If a module-level singleton triggers it, use a PEP-562 lazy
singleton — `saleha/core/platform/self_healer.py` is the worked example.

**A package-level `__getattr__` cannot serve a name that a submodule already
occupies.** `saleha.agents.issue_resolver` the module shadows `issue_resolver`
the singleton, so the accessor never fires. Verify any such accessor actually
returns the instance before shipping it.

## Before editing

Read the whole file, not the target line. When you fix one instance of the
shapes above, grep the same file for siblings — they travel in groups.
