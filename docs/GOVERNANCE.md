# Saleha Self-Governance

<!-- saleha:generated:doc-version -->
Document version 1.0.0 -- describes Saleha 2.6.0 -- updated 2026-09-25
<!-- /saleha:generated:doc-version -->

<!-- saleha:generated:project-version -->
Saleha version: **2.6.0**
<!-- /saleha:generated:project-version -->

Saleha checks, hardens and documents itself. Every step is gated on a
measurement Saleha cannot make up: executed controls, a ratchet that only
tightens, tests that must pass before and after a change, and docs rendered
from code.

## The loop

```text
saleha governance check        run the controls; FAIL exits 1
saleha governance improve      fix one finding, verified, on auto/governance
saleha governance check --update-baseline   record the lower count
saleha governance docs --apply regenerate doc regions, bump doc versions
saleha governance version      next SemVer from conventional commits
```

## Controls

`saleha governance check` runs each control against the working tree:

- **Executed, not trusted.** `GOV-LOCAL-ONLY` runs every cloud provider with
  `SALEHA_LOCAL_ONLY=1` and intercepts network and CLI calls. It records an
  attempted call instead of making it.
- **Three results.** `PASS`, `FAIL`, or `NOT_CHECKED`. A control that crashes,
  or a scan that could not parse a file, is `NOT_CHECKED`, never `PASS`.
- **Ratchet.** Counted controls compare against
  `saleha/core/governance/baseline.json`. A higher count fails.
  `--update-baseline` only lowers a value. Raising one is a human edit that
  shows up in review.

<!-- saleha:generated:governance-controls -->
| Control | What it checks | Ratchet baseline |
|---|---|---|
| `GOV-SAST-CATALOG` | Parses security_scanner.py; every emitted rule_id/severity must equal RULE_CATALOG. | - |
| `GOV-SAST-TESTS` | Each RULE_CATALOG id must be named in a saleha/tests file (ratchet). | `untested_scanner_rules` <= 0 |
| `GOV-DOCS-RULES` | The generated rule table must equal a fresh render of RULE_CATALOG. | - |
| `GOV-LOCAL-ONLY` | Runs each cloud provider with local-only set and intercepts network/CLI calls. | - |
| `GOV-COMMIT-GATE` | Checks .git/hooks/pre-commit exists and invokes preflight_lint.py. | - |
| `GOV-SUBPROCESS-TIMEOUT` | Counts run/call/check_call/check_output without timeout= (ratchet). | `subprocess_without_timeout` <= 27 |
| `GOV-SUBPROCESS-ENCODING` | Counts text=True calls without encoding= (ratchet). | `subprocess_text_without_encoding` <= 48 |
| `GOV-SAST-SELF` | Runs the SAST scanner over saleha/ excluding tests (ratchet). | `high_sast_findings` <= 12 |
| `GOV-DOCS-STALE` | Checks backticked `saleha ...` commands and repo paths in docs (ratchet). | `stale_doc_claims` <= 0 |
| `GOV-VERSION` | pyproject.toml and saleha/__init__.py must declare the same version. | - |
<!-- /saleha:generated:governance-controls -->

## Autonomous hardening

`saleha governance improve --metric encoding|timeout` picks one open finding
and changes only the function that contains it. The change is committed on
the `auto/governance` branch (in a temporary worktree) only if:

1. the tests that import the module pass before the change,
2. only lines inside that function changed and the file parses,
3. the finding is gone and no ratcheted count went up,
4. `preflight_lint` passes on the file,
5. the same tests pass after the change, against the worktree's own copy
   of `saleha`.

A module that no test imports is skipped and the skip is logged. The
`encoding` fix is a deterministic AST edit; the `timeout` fix is written by
a local model and kept only if the gates pass. Nothing is pushed and the
checked-out branch is never touched. `saleha governance log` shows every
cycle, including the ones that failed.

## Documents and versions

- A doc marks a region with `<!-- saleha:generated:NAME -->` and
  `<!-- /saleha:generated:NAME -->`. `saleha governance docs --apply`
  re-renders it from the code. `docs/CLI_REFERENCE.md` is generated whole.
- Backticked `saleha ...` commands and repository paths in the docs are
  checked against the real CLI and filesystem, and reported as stale. They
  are reported, not rewritten: fixing prose needs judgment.
- `docs/doc_versions.json` holds each managed doc's own version and content
  hash. A changed doc gets a patch bump and a stamp naming the Saleha version
  it describes.
- `saleha governance version` derives the next version from commits since
  `version` last changed in `pyproject.toml`: a breaking change bumps major,
  `feat` bumps minor, `fix`/`perf` bumps patch. `--apply` writes
  `pyproject.toml`, `saleha/__init__.py` and a `CHANGELOG.md` entry. It
  never commits or tags.

## Limits

- The controls check what they name, nothing more. A `PASS` on
  `GOV-SAST-TESTS` means every rule id appears in a test, not that the
  tests are thorough.
- Stale-claim detection covers backticked commands and paths only.
- The improver fixes only mechanical, locally checkable findings. It does
  not redesign the security framework.
