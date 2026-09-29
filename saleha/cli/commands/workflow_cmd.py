"""
Saleha CLI: Autonomous Workflow Engine (SalehaFlow).

Provides developer CLI tooling to run, list, validate, and inspect
autonomous, self-healing DAG workflows.
"""

from __future__ import annotations

import json
import os
import sys

import click
from rich.panel import Panel
from rich.table import Table

from saleha.cli.commands import cli, console


@cli.group(name="flow")
def flow_group():
    """Autonomous Self-Healing Workflow Automation Engine (SalehaFlow)."""


@flow_group.command(name="list")
def flow_list():
    """List all registered autonomous workflows."""
    from saleha.core.workflow.dsl import list_registered_workflows

    wfs = list_registered_workflows()
    if not wfs:
        console.print("[dim]No workflows registered in memory.[/]")
        return

    table = Table(title="SalehaFlow Registered Workflows", header_style="bold cyan")
    table.add_column("Workflow ID", style="bold")
    table.add_column("Name")
    table.add_column("Nodes", justify="right")
    table.add_column("Description")

    for wf in wfs:
        table.add_row(wf.workflow_id, wf.name, str(len(wf.nodes)), wf.description or "-")

    console.print(table)


@flow_group.command(name="validate")
@click.argument("workflow_file")
def flow_validate(workflow_file: str):
    """Validate a JSON workflow file for circular dependencies and syntax."""
    from saleha.core.workflow.workflow_engine import WorkflowDAG

    if not os.path.exists(workflow_file):
        console.print(f"[bold red]Error:[/] File not found: {workflow_file}")
        sys.exit(1)

    try:
        with open(workflow_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        dag = WorkflowDAG.from_dict(data)
        batches = dag.get_topological_batches()
        console.print(
            f"[bold green]Valid Workflow DAG:[/] '{dag.name}' with {len(dag.nodes)} nodes "
            f"across {len(batches)} parallel execution stages."
        )
    except Exception as e:
        console.print(f"[bold red]Validation Failed:[/] {e}")
        sys.exit(1)


@flow_group.command(name="run")
@click.argument("workflow_id_or_file")
def flow_run(workflow_id_or_file: str):
    """Execute a workflow by ID or from a JSON workflow file."""
    from saleha.core.workflow.dsl import get_workflow
    from saleha.core.workflow.workflow_engine import WorkflowDAG

    dag = None
    if os.path.exists(workflow_id_or_file):
        try:
            with open(workflow_id_or_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            dag = WorkflowDAG.from_dict(data)
        except Exception as e:
            console.print(f"[bold red]Error loading workflow file:[/] {e}")
            sys.exit(1)
    else:
        dag = get_workflow(workflow_id_or_file)

    if not dag:
        console.print(f"[bold red]Error:[/] Workflow '{workflow_id_or_file}' not found.")
        sys.exit(1)

    console.print(f"[bold cyan]Executing SalehaFlow:[/] {dag.name} ({dag.workflow_id})")

    res = dag.execute()

    table = Table(title=f"Workflow Execution Result ({res.execution_id})", header_style="bold blue")
    table.add_column("Node ID", style="bold")
    table.add_column("Status")
    table.add_column("Duration (ms)", justify="right")
    table.add_column("Details")

    for nid, node_data in res.node_results.items():
        st = node_data["status"]
        st_styled = st
        if st == "COMPLETED":
            st_styled = f"[green]{st}[/]"
        elif st == "HEALED":
            st_styled = f"[bold magenta]{st}[/]"
        elif st == "FAILED":
            st_styled = f"[red]{st}[/]"
        elif st == "SKIPPED":
            st_styled = f"[yellow]{st}[/]"

        detail = node_data.get("error") or "OK"
        table.add_row(nid, st_styled, str(node_data["duration_ms"]), detail[:60])

    console.print(table)
    summary_color = "green" if res.success else "red"
    console.print(
        Panel(
            f"[{summary_color}]Status: {'SUCCESS' if res.success else 'FAILED'}[/]\n"
            f"Total Duration: {res.total_duration_ms}ms\n"
            f"Completed: {len(res.completed_nodes)} | Healed: {len(res.healed_nodes)} | "
            f"Failed: {len(res.failed_nodes)} | Skipped: {len(res.skipped_nodes)}",
            title=f"SalehaFlow Verdict — {dag.name}",
            border_style=summary_color,
        )
    )


@flow_group.command(name="inspect")
@click.argument("workflow_id_or_file")
def flow_inspect(workflow_id_or_file: str):
    """Output visual Mermaid DAG flowchart for a workflow."""
    from saleha.core.workflow.dsl import get_workflow
    from saleha.core.workflow.workflow_engine import WorkflowDAG

    dag = None
    if os.path.exists(workflow_id_or_file):
        with open(workflow_id_or_file, "r", encoding="utf-8") as f:
            dag = WorkflowDAG.from_dict(json.load(f))
    else:
        dag = get_workflow(workflow_id_or_file)

    if not dag:
        console.print(f"[bold red]Workflow not found:[/] {workflow_id_or_file}")
        return

    console.print(Panel(dag.to_mermaid(), title=f"Mermaid DAG Topology: {dag.name}"))
