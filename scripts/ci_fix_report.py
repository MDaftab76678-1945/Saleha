"""Turn `saleha fix --json` output into GitHub Actions outputs and a job summary.

Used by action.yml (mode: fix). Reads the JSON result from the file given as
the first argument, writes `verdict`, `branch` and `ok` to $GITHUB_OUTPUT,
and a Markdown summary to $GITHUB_STEP_SUMMARY. A result that cannot be read
is reported as HARNESS_ERROR, never as a pass.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict


def read_result(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.startswith("{")]
        return json.loads(lines[-1])
    except (OSError, IndexError, json.JSONDecodeError) as exc:
        return {"verdict": "HARNESS_ERROR", "ok": False, "branch": "",
                "reason": f"could not read saleha fix output: {exc}"}


def summary(res: Dict[str, Any]) -> str:
    verdict = res.get("verdict", "HARNESS_ERROR")
    head = {
        "FIXED": "Saleha fixed the failing tests, and proved the fix",
        "ALREADY_PASSING": "The tests pass: nothing to fix",
        "FIXED_UNPROVEN": "Saleha made the tests pass, but could not prove the fix",
        "NOT_FIXED": "Saleha could not fix the failing tests; nothing was changed",
        "FLAKY": "The failing tests passed on a re-run: flaky, so nothing was changed",
        "CANNOT_RUN": "Saleha could not run",
    }.get(verdict, "Saleha fix did not complete")
    parts = [f"## {head}", "", f"**Verdict:** `{verdict}` -- {res.get('reason', '')}", ""]
    if res.get("failing_before"):
        parts += ["**Failing tests:** " + ", ".join(f"`{t}`" for t in res["failing_before"][:10]), ""]
    if res.get("changed_files"):
        parts += ["**Changed:** " + ", ".join(f"`{p}`" for p in res["changed_files"]), ""]
    if res.get("diff"):
        parts += ["```diff", res["diff"].rstrip(), "```", ""]
    if res.get("receipt_markdown"):
        parts += [res["receipt_markdown"]]
    parts += [f"_{res.get('model', '')} · {res.get('agent_steps', 0)} agent steps · "
              f"{res.get('seconds', 0)}s_"]
    return "\n".join(parts) + "\n"


def main() -> int:
    res = read_result(sys.argv[1] if len(sys.argv) > 1 else "saleha-fix.json")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"verdict={res.get('verdict', 'HARNESS_ERROR')}\n")
            fh.write(f"branch={res.get('branch', '')}\n")
            fh.write(f"ok={'true' if res.get('ok') else 'false'}\n")
    text = summary(res)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
