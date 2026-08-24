"""
docs/CLI_REFERENCE.md ko Click CLI se AUTO-GENERATE karta hai.

Usage: python scripts/gen_cli_docs.py
Kabhi naya command add ho to bas ye script chala do -- docs hamesha
code ke saath sync rehte hain.
"""
import io
import sys

import click

from saleha.cli.commands import cli


def format_params(cmd) -> str:
    parts = []
    for p in cmd.params:
        if isinstance(p, click.Argument):
            parts.append(f"`<{p.name.upper()}>`")
        elif isinstance(p, click.Option):
            names = "/".join(p.opts)
            arg = "" if p.is_flag else f" `{p.name.upper()}`"
            parts.append(f"`{names}{arg}`")
    return " ".join(parts) if parts else "-"


def describe(cmd) -> str:
    return (cmd.help or "").strip().splitlines()[0] if cmd.help else ""


def render_group(group: click.Group, title: str, out: List[str]):
    out.append(f"### {title}\n")
    out.append("| Command | Description | Options |")
    out.append("|---|---|---|")
    for name in sorted(group.commands):
        c = group.commands[name]
        if isinstance(c, click.Group):
            continue  # sub-groups alag section me
        out.append(f"| `saleha {name}` | {describe(c)} | {format_params(c)} |")
    out.append("")

    for gname in sorted(group.commands):
        sub = group.commands[gname]
        if isinstance(sub, click.Group):
            out.append(f"#### `saleha {gname}` group\n")
            out.append("| Sub-command | Description | Options |")
            out.append("|---|---|---|")
            for sname in sorted(sub.commands):
                sc = sub.commands[sname]
                out.append(f"| `saleha {gname} {sname}` | {describe(sc)} | {format_params(sc)} |")
            out.append("")


def main():
    out: List[str] = [
        "# 🛠️ Saleha CLI Reference",
        "",
        "> ⚠️ Ye file **auto-generated** hai -- `python scripts/gen_cli_docs.py`",
        f"> (Generated against Saleha CLI, {len(cli.commands)} top-level commands)",
        "",
        "## Commands\n",
    ]
    render_group(cli, "All Commands", out)

    target = "docs/CLI_REFERENCE.md"
    io.open(target, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print(f"wrote {target}: {len(out)} lines")


if __name__ == "__main__":
    sys.exit(main())
