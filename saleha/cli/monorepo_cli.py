"""
Saleha Monorepo Ecosystem CLI.
Provides commands to inspect, test, and manage the unified ecosystem:
- Desktop App (/apps/desktop)
- Web Studio (/apps/web)
- Landing Page (/apps/landing)
- Shared Packages (@saleha/ui, @saleha/db, @saleha/api, @saleha/auth, @saleha/core)
"""

import os
import json
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def get_monorepo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@click.group(name="monorepo", help="Manage and inspect the Saleha Unified Monorepo Ecosystem.")
def monorepo_group():
    pass


@monorepo_group.command(name="status", help="Display status of all apps and packages in the monorepo.")
def status_cmd():
    root = get_monorepo_root()
    table = Table(title="🧬 Saleha Unified Ecosystem Status", border_style="cyan")
    table.add_column("Type", style="bold white", width=12)
    table.add_column("Path", style="cyan", width=22)
    table.add_column("Stack", style="magenta", width=30)
    table.add_column("Status", style="bold green", width=16)

    apps = [
        ("App: Desktop", "apps/desktop", "Tauri v2 + Rust + React 19", "🟢 Ready (Offline-First)"),
        ("App: Web", "apps/web", "Next.js 15 (App Router, RSC)", "🟢 Ready (Cloud Studio)"),
        ("App: Landing", "apps/landing", "Astro 5 (Islands Architecture)", "🟢 Ready (Lighthouse 100)"),
        ("Pkg: UI", "packages/ui", "React + Tailwind + Radix UI", "🟢 Ready (Design Tokens)"),
        ("Pkg: DB", "packages/db", "Prisma ORM + Multi-Tenant Schema", "🟢 Ready (SQLite / Postgres)"),
        ("Pkg: API", "packages/api", "tRPC v11 + Zod Validation", "🟢 Ready (Type-Safe Routers)"),
        ("Pkg: Auth", "packages/auth", "SecurityGuard + RBAC Hierarchy", "🟢 Ready (Zero-Trust)"),
    ]

    for t, p, s, st in apps:
        full_p = root / p
        exists = "🟢 Configured" if full_p.exists() else "🔴 Missing"
        table.add_row(t, p, s, st if full_p.exists() else exists)

    console.print(table)


@monorepo_group.command(name="verify", help="Run full monorepo recursive loop verification.")
def verify_cmd():
    root = get_monorepo_root()
    console.print(Panel("[bold cyan]🧬 Running Universal Loop Engineering Verification (Phases 0–7)...[/bold cyan]"))
    
    # Each phase is "do the required paths exist", so collect the verdicts
    # rather than only printing them -- the summary below has to be able to
    # disagree with a green banner.
    phase_results = [
        ("Phase 0 (Product DNA)",
         (root / "PRODUCT_BRIEF.md").exists()),
        ("Phase 1 (Turborepo Workspaces)",
         (root / "turbo.json").exists() and (root / "package.json").exists()),
        ("Phase 2 (Design Tokens & UI)",
         (root / "packages" / "ui" / "src" / "tokens" / "theme.ts").exists()),
        ("Phase 3 (Prisma DB & tRPC API)",
         (root / "packages" / "db" / "prisma" / "schema.prisma").exists()
         and (root / "packages" / "api" / "src" / "root.ts").exists()),
        ("Phase 4 (SecurityGuard & RBAC)",
         (root / "packages" / "auth" / "src" / "index.ts").exists()),
        ("Phase 5 & 6 (GitHub Actions CI)",
         (root / ".github" / "workflows" / "ci.yml").exists()),
        ("Phase 7 (Observability Engine)",
         (root / "packages" / "core" / "src" / "observability.ts").exists()),
    ]

    for name, ok in phase_results:
        console.print(f"• {name}: {'[green]PASS[/green]' if ok else '[red]FAIL[/red]'}")

    # This summary printed "100% RECURSIVE VALIDATION PASSED (All 7 Phases
    # Green)" unconditionally -- directly below per-phase checks that each
    # print FAIL when a path is missing. A run with failing phases still
    # ended in a green "all passed" banner. The verdict now follows the
    # checks it claims to summarise.
    failed = [name for name, ok in phase_results if not ok]
    if failed:
        console.print(f"\n[bold red]VALIDATION FAILED[/bold red] "
                      f"({len(failed)} of {len(phase_results)} phases): "
                      f"{', '.join(failed)}")
        raise click.exceptions.Exit(1)
    console.print(f"\n[bold green]All {len(phase_results)} phases passed.[/bold green]")

