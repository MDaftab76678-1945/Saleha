"""`saleha governance`: security controls, autonomous hardening, docs and versions."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

import click
from rich.table import Table

from saleha.cli.commands import cli, console

_STYLE = {"PASS": "green", "FAIL": "red", "NOT_CHECKED": "yellow"}


@cli.group(name="governance")
def governance_group() -> None:
    """Measure and improve Saleha's own security framework, docs and version."""


@governance_group.command(name="check")
@click.option("--update-baseline", is_flag=True, help="Record improved ratchet counts (never raises one).")
@click.option("--only", multiple=True, help="Run only these control ids.")
@click.option("--verbose", "-v", is_flag=True, help="List every item behind each result.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def check_cmd(update_baseline: bool, only: tuple, verbose: bool, as_json: bool) -> None:
    """Run every security control. Exits 1 if any control FAILs."""
    from saleha.core.governance import controls

    results = controls.run_controls(only=list(only) or None)
    changed = controls.update_baseline(results) if update_baseline else {}
    if as_json:
        click.echo(json.dumps({"results": [r.to_dict() for r in results],
                               "baseline_changes": {k: list(v) for k, v in changed.items()}}, indent=2))
    else:
        table = Table(title="Saleha governance controls")
        for col in ("Control", "Status", "Evidence"):
            table.add_column(col)
        for r in results:
            table.add_row(r.control_id, f"[{_STYLE[r.status]}]{r.status}[/]", r.evidence)
        console.print(table)
        if verbose:
            for r in results:
                for item in r.items[:50]:
                    console.print(f"  {r.control_id}  {item}")
                if len(r.items) > 50:
                    console.print(f"  {r.control_id}  ... {len(r.items) - 50} more")
        for metric, (old, new) in changed.items():
            console.print(f"baseline {metric}: {old if old is not None else 'unset'} -> {new}")
        counts = {s: sum(1 for r in results if r.status == s) for s in _STYLE}
        console.print(f"{counts['PASS']} pass, {counts['FAIL']} fail, {counts['NOT_CHECKED']} not checked")
    if any(r.status == controls.FAIL for r in results):
        sys.exit(1)


@governance_group.command(name="improve")
@click.option("--metric", type=click.Choice(["encoding", "timeout"]), default="encoding",
              help="Which ratcheted finding to fix.")
@click.option("--model", "-m", default="qwen2.5-coder:3b", help="Model for fixes that need judgment (timeout).")
@click.option("--cycles", "-c", default=1, type=int, help="Cycles to run; each commits at most one fix.")
@click.option("--max-candidates", default=5, type=int, help="Findings to try per cycle.")
def improve_cmd(metric: str, model: str, cycles: int, max_candidates: int) -> None:
    """Fix one finding per cycle, verified, on branch auto/governance."""
    from saleha.core.governance import improver

    committed = 0
    for i in range(1, max(1, cycles) + 1):
        res = improver.run_cycle(metric=metric, model=model, max_candidates=max_candidates)
        colour = "green" if res.status == improver.COMMITTED else "yellow"
        console.print(f"[{colour}]cycle {i}: {res.status}[/] {res.detail}")
        if res.commit_sha:
            committed += 1
            console.print(f"  {improver.BRANCH} {res.commit_sha[:10]}  {res.before} -> {res.after}  "
                          f"tests: {', '.join(res.tests)}")
        for a in res.attempts:
            if a.get("outcome") != "committed":
                console.print(f"  {a['item']} ({a['function']}): {a.get('outcome', '')}")
        if res.status in (improver.NO_CANDIDATE, improver.SETUP_FAILED):
            break
    console.print(f"{committed} fix(es) committed to {improver.BRANCH}; nothing pushed, main untouched.")
    if committed == 0:
        sys.exit(1)


@governance_group.command(name="docs")
@click.option("--apply", "do_apply", is_flag=True, help="Write the regenerated docs and version manifest.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def docs_cmd(do_apply: bool, as_json: bool) -> None:
    """Regenerate marked doc regions, version each doc, and list stale claims."""
    from saleha.core.governance import doc_sync

    changes = doc_sync.plan_sync()
    written = doc_sync.apply_sync(changes) if do_apply else []
    stale = doc_sync.find_stale_claims()  # after writing: --apply may create referenced files
    if as_json:
        click.echo(json.dumps({
            "changes": [{k: v for k, v in asdict(c).items() if k != "new_text"} for c in changes],
            "stale_claims": [asdict(s) for s in stale], "written": written}, indent=2))
        return
    for c in changes:
        state = "changed" if c.content_changed else "current"
        regions = f" regions: {', '.join(c.regions_changed)}" if c.regions_changed else ""
        unknown = f" [yellow]unknown regions: {', '.join(c.unknown_regions)}[/]" if c.unknown_regions else ""
        console.print(f"{c.path}: {state} v{c.old_version or '-'} -> v{c.new_version}{regions}{unknown}")
    console.print(f"{len(stale)} stale claim(s)")
    for s in stale[:40]:
        console.print(f"  {s.doc}:{s.line} `{s.claim}` -- {s.reason}")
    if do_apply:
        console.print(f"wrote: {', '.join(written) if written else 'nothing (already current)'}")
    elif any(c.content_changed for c in changes):
        console.print("dry run; pass --apply to write")


@governance_group.command(name="version")
@click.option("--apply", "do_apply", is_flag=True, help="Write the new version and CHANGELOG entry.")
def version_cmd(do_apply: bool) -> None:
    """Compute the next SemVer from conventional commits since the last bump."""
    from saleha.core.governance import versioning

    plan = versioning.plan_bump()
    console.print(f"current {plan.current}; next {plan.next or '-'} ({plan.level}); {plan.reason}")
    by_type: dict = {}
    for c in plan.commits:
        by_type[c.type] = by_type.get(c.type, 0) + 1
    if by_type:
        console.print("commits: " + ", ".join(f"{k} {v}" for k, v in sorted(by_type.items())))
    if do_apply:
        if not plan.next:
            console.print("[yellow]nothing to apply[/]")
            sys.exit(1)
        written = versioning.apply_bump(plan)
        console.print(f"wrote: {', '.join(written)}; run `saleha governance docs --apply` next")
    elif plan.next:
        console.print("dry run; pass --apply to write")


@governance_group.command(name="log")
@click.option("--limit", "-n", default=10, type=int)
def log_cmd(limit: int) -> None:
    """Recent autonomous hardening cycles."""
    from saleha.core.governance import improver

    rows = improver.read_log(limit)
    if not rows:
        console.print("no cycles recorded yet")
    for r in rows:
        sha = f" {r['commit_sha'][:10]}" if r.get("commit_sha") else ""
        console.print(f"{r['timestamp']} {r['metric']} {r['status']}{sha}: {r['detail']}")
