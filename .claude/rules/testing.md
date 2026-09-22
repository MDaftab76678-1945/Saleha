---
paths:
  - "saleha/tests/**/*.py"
---

# Tests in this repo

`saleha/tests/conftest.py` sets `SALEHA_TEST_MODE=1` for the whole run, which is
what routes modules around real Ollama calls. If a test hangs for minutes, that
is almost always the bug: a module reaching a live model call it should have
mocked under that flag.

Run with `PYTHONIOENCODING=utf-8` — the console is cp1252 and emoji in output
crash the run.

## Writing a test for a bug

**Teeth-check it.** A new test must fail against the pre-fix code and pass after.
`git stash` the fix, run the test, confirm red, restore. A test that passes
before the fix proves nothing and is worse than none, because it looks like
coverage.

**Assert the reason, not just the boolean.** `assertTrue(res.success)` cannot
tell you why it failed. Assert on the real error/verdict field.

**Test the case that would break it, not the case that works.** The bug lives in
the input you did not think of: empty, whitespace-only, duplicate, `None`, the
step that never ran. Listing those is the work; the assertion is the easy part.

**Do not let the test construct what production must construct.** If the test
calls the recording function itself, it can pass forever while nothing in
production ever calls it. That exact trap shipped here once.

## Windows notes

`TemporaryDirectory` cleanup can raise `WinError 32` *after* assertions already
passed — a green test reporting red. Use `ignore_cleanup_errors=True`. For a
nested pytest subprocess, pass `-p no:cacheprovider` and
`PYTHONDONTWRITEBYTECODE=1` so it does not leave `.pyc` files the parent then
races to delete.

## Gate

`preflight_lint.py` runs on commit and requires full type annotations on test
methods (`def test_x(self) -> None:`). Fix a low score rather than bypassing
with `--no-verify` — but confirm first with `git stash` whether it is
pre-existing, and say so if it is.
