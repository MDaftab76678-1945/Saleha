"""Turn `saleha receipt --json` into a pull-request comment and GitHub Actions outputs.

Used by action.yml (mode: verify) to check any pull request -- written by a
person, Copilot, Devin, Claude or Saleha -- by running its tests, not by
reading it. Writes `verdict` and `ok` to $GITHUB_OUTPUT, the comment to the
path given as the second argument, and the same text to the job summary.
Output that cannot be read is HARNESS_ERROR, never a pass.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

MEANING = {
    "PROVEN": ("The change is proven by its tests",
               "The tests pass with this change and fail without it, in a clean checkout of the "
               "base, and no test was weakened."),
    "UNPROVEN": ("The tests pass, but they do not prove this change",
                 "Either they pass without the change too -- so nothing here would catch it breaking "
                 "-- or tests were weakened. A test that fails without the change would prove it."),
    "FAILING": ("The tests fail with this change", ""),
    "NOT_CHECKED": ("The change could not be checked", ""),
    "HARNESS_ERROR": ("The check itself did not complete", ""),
}


def read_receipt(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        return json.loads(text[text.index("{"):])
    except (OSError, ValueError) as exc:
        return {"verdict": "HARNESS_ERROR", "reason": f"could not read saleha receipt output: {exc}"}


def _run(label: str, run: Any) -> str:
    if not isinstance(run, dict):
        return f"- {label}: not run"
    if not run.get("ran"):
        return f"- {label}: could not run ({str(run.get('tail', ''))[:200]})"
    return f"- {label}: {'PASS' if run.get('passed') else 'FAIL'} ({run.get('seconds', 0)}s)"


def comment(r: Dict[str, Any]) -> str:
    verdict = str(r.get("verdict", "HARNESS_ERROR"))
    head, explain = MEANING.get(verdict, MEANING["HARNESS_ERROR"])
    lines = [f"### Saleha proof receipt: `{verdict}` -- {head}", ""]
    if explain:
        lines += [explain, ""]
    lines += [f"**Why:** {r.get('reason', '')}", ""]
    files = r.get("changed_files") or []
    if files:
        lines.append(f"- Changed files: {len(files)} ({len(r.get('source_files') or [])} source, "
                     f"{len(r.get('test_files') or [])} test)")
    if r.get("test_command"):
        lines.append(f"- Test command: `{' '.join(r['test_command'])}`")
    lines += [_run("Tests with the change", r.get("head_run")),
              _run("Same tests without the change", r.get("base_run"))]
    if r.get("control_run") is not None:
        lines.append(_run("Control: the change in a clean checkout of the base", r.get("control_run")))
    weak = r.get("weakening") or []
    lines.append(f"- Test weakening: {'; '.join(weak) if weak else 'none found'}")
    lines += ["", "_What this does not prove: that the tests cover every behaviour that matters._"]
    return "\n".join(lines) + "\n"


def main() -> int:
    r = read_receipt(sys.argv[1] if len(sys.argv) > 1 else "saleha-receipt.json")
    verdict = str(r.get("verdict", "HARNESS_ERROR"))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"verdict={verdict}\n")
            fh.write(f"ok={'true' if verdict == 'PROVEN' else 'false'}\n")
    text = comment(r)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
