"""Auto-extracted from the former monolithic saleha/cli/commands.py.

Imports `cli` to register commands against the same Click group, and `_cmds`
(the package module itself) so any reference to a lazily-imported name (see
_LAZY_IMPORT_MAP in __init__.py) or a shared helper resolves through the
original module -- this keeps mock.patch("saleha.cli.commands.X") working
for tests that patch those names, and preserves the PEP 562 lazy-loading
behavior for whatever this file's commands use.
"""
import click
from saleha.cli.commands import cli, console
from saleha.cli import commands as _cmds

from typing import Optional, Tuple, List, Dict, Any, Callable, Union, Set, TYPE_CHECKING
import os
import sys
import re
import time
import json
import io
import subprocess
import contextlib
from pathlib import Path
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax
from saleha import __version__

@cli.command(name='deploy')
@click.option('--target', '-t', default='all', type=click.Choice(['docker', 'k8s', 'all']), help='Deployment manifest target')
@click.option('--output-dir', '-o', default='./deploy', help='Output directory for manifests')
@click.option('--name', '-n', default='saleha-service', help='Service name')
@click.option('--port', '-p', default=8000, type=int, help='Exposed port')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def deploy_cmd(target, output_dir, name, port, as_json):
    """Generate production-ready Dockerfile, Compose, and Kubernetes manifests."""
    from saleha.core.deployer import cloud_deployer
    pkg = _cmds.cloud_deployer.generate_package(root_dir='.', app_name=name, port=port)
    written = _cmds.cloud_deployer.export_package(pkg, output_dir=output_dir)
    if as_json:
        click.echo(json.dumps({'app_name': pkg.app_name, 'runtime': pkg.runtime, 'port': pkg.port, 'output_dir': output_dir, 'files_generated': [os.path.basename(f) for f in written]}, ensure_ascii=True))
        return
    console.print(Panel(f'[bold cyan]App Name:[/] {pkg.app_name}\n[bold cyan]Detected Runtime:[/] {pkg.runtime.upper()}\n[bold cyan]Exposed Port:[/] {pkg.port}\n[bold cyan]Output Directory:[/] {output_dir}\n[bold green]Files Generated:[/]\n' + '\n'.join([f'  • {os.path.basename(f)}' for f in written]), title='[bold green]☁️ Saleha 1-Click Cloud & K8s Deployer[/]', border_style='green'))

@cli.command(name='migrate')
@click.argument('target_path')
@click.option('--from', 'source_fw', required=True, help='Source language/framework (e.g. js, flask, unittest)')
@click.option('--to', 'target_fw', required=True, help='Target language/framework (e.g. ts, fastapi, pytest)')
@click.option('--inplace', is_flag=True, help='Overwrite original files with migrated code')
def migrate_cmd(target_path, source_fw, target_fw, inplace):
    """
    Autonomously migrate legacy codebases (js->ts, flask->fastapi, unittest->pytest).
    
    Example: saleha migrate app.py --from flask --to fastapi
    """
    from saleha.core.code_migrator import code_migrator
    if not os.path.isfile(target_path):
        console.print(f'[bold red]Error:[/] Target file not found: {target_path}')
        return
    with open(target_path, 'r', encoding='utf-8') as f:
        code = f.read()
    res = code_migrator.migrate(code, source=source_fw, target=target_fw)
    console.print(f'[bold cyan]🔄 Codebase Migration:[/] [yellow]{source_fw} ➔ {target_fw}[/]')
    console.print(f'[dim]{res.summary}[/]\n')
    if inplace:
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(res.migrated_code)
        console.print(f'[bold green]✅ Saved migrated code in-place to:[/] {target_path}')
    else:
        console.print('[bold green]Migrated Code Preview:[/]')
        console.print(res.migrated_code)

@cli.command(name='generate-infra')
@click.option('--name', default='saleha-service', help='Application name')
@click.option('--port', default=8000, help='Port number')
def generate_infra_cmd(name: str, port: int):
    """
    Synthesize Docker, Kubernetes, and Terraform IaC manifests.
    
    Example: saleha generate-infra --name api-service --port 8000
    """
    from saleha.core.infra_generator import infra_generator
    b = infra_generator.generate_infrastructure(name, port)
    console.print(Panel(f'[bold blue]🏗️ Infrastructure-as-Code Generated for {name}[/bold blue]', border_style='blue'))
    console.print(f"Synthesized: {', '.join(b.files.keys())}")

@cli.command(name='cloud-plan')
@click.argument('goal')
@click.option('--provider', '-p', default='aws', type=click.Choice(['aws', 'gcp', 'azure', 'cloudflare'], case_sensitive=False), help='Target cloud provider')
@click.option('--ha/--no-ha', default=True, help='Enable Multi-AZ High Availability')
@click.option('--output-dir', '-o', default=None, help='Directory to save generated IaC manifests')
def cloud_plan_cmd(goal: str, provider: str, ha: bool, output_dir: Optional[str]):
    """Autonomously synthesize Terraform, Kubernetes manifests, Helm values & IAM security policies."""
    from saleha.core.cloud_infra_orchestrator import cloud_infra_orchestrator
    console.print(f'[bold cyan]☁️ Synthesizing Enterprise Cloud Architecture for:[/] [white]{goal}[/]')
    plan = cloud_infra_orchestrator.plan_and_generate_infra(goal=goal, cloud_provider=provider, high_availability=ha)
    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        (out_p / 'main.tf').write_text(plan.terraform_code, encoding='utf-8')
        (out_p / 'k8s-deployment.yaml').write_text(plan.kubernetes_manifests, encoding='utf-8')
        (out_p / 'values.yaml').write_text(plan.helm_values, encoding='utf-8')
        (out_p / 'iam-policy.json').write_text(plan.iam_policy_json, encoding='utf-8')
        (out_p / 'deploy.yml').write_text(plan.ci_cd_workflow, encoding='utf-8')
        console.print(f'[bold green]✅ Wrote 5 cloud manifests to:[/] {output_dir}')
    console.print(Panel(plan.terraform_code[:380] + '\n  ...', title=f'Terraform ({provider.upper()})', border_style='cyan'))
    console.print(f'[green]💰 Estimated Monthly Cost:[/] ${plan.finops_estimated_monthly_cost:.2f}/mo | [yellow]🛡️ Security CIS Score:[/] {plan.security_score}/100')

@cli.command(name='silicon-build')
@click.argument('goal')
@click.option('--name', '-n', default=None, help='Custom hardware module name')
@click.option('--output-dir', '-o', default=None, help='Directory to save synthesizable Verilog & testbench')
def silicon_build_cmd(goal: str, name: Optional[str], output_dir: Optional[str]):
    """Synthesize synthesizable Verilog / SystemVerilog RTL, self-checking testbenches & SDC timing."""
    from saleha.core.silicon_circuit_orchestrator import silicon_circuit_orchestrator
    console.print(f'[bold yellow]⚡ Synthesizing Silicon Hardware Circuit for:[/] [white]{goal}[/]')
    design = silicon_circuit_orchestrator.synthesize_hardware_circuit(spec_goal=goal, module_name=name)
    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        (out_p / f'{design.module_name}.v').write_text(design.verilog_rtl, encoding='utf-8')
        (out_p / f'tb_{design.module_name}.v').write_text(design.testbench_sv, encoding='utf-8')
        (out_p / f'{design.module_name}.sdc').write_text(design.timing_constraints_sdc, encoding='utf-8')
        console.print(f'[bold green]✅ Wrote hardware RTL, testbench & SDC timing to:[/] {output_dir}')
    console.print(Panel(design.verilog_rtl[:380] + '\n  ...', title=f'Verilog RTL: {design.module_name}', border_style='yellow'))
    console.print(f'[cyan]📊 Estimated LUTs:[/] {design.estimated_lut_count} | [magenta]⏱️ Max Frequency:[/] {design.estimated_max_freq_mhz} MHz | [green]Synthesizable:[/] {design.is_synthesizable}')

