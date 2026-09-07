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

@cli.command()
@click.argument('directory', default='.', type=click.Path(exists=True, file_okay=False))
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def scan(directory, as_json):
    """Scan and index codebase AST symbols (classes, methods, functions, imports)."""
    indexer = _cmds.CodebaseIndexer(root_dir=directory)
    indexed = indexer.scan()
    summary = indexer.get_summary()
    if as_json:
        payload = {'summary': summary, 'files': {rel_path: {'lines_of_code': f.lines_of_code, 'classes': [c.name for c in f.classes.values()], 'functions': [fn.name for fn in f.functions.values()], 'imports': f.imports, 'syntax_error': f.syntax_error} for rel_path, f in indexed.items()}}
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    console.print(Panel.fit(f"[bold cyan]📁 Root Directory:[/] {summary['root_dir']}\n[bold cyan]📄 Total Python Files:[/] {summary['total_files']}\n[bold cyan]📝 Lines of Code:[/] {summary['total_loc']}\n[bold cyan]🏛️ Classes Found:[/] {summary['total_classes']}\n[bold cyan]⚡ Functions Found:[/] {summary['total_functions']}", title='[bold green]Codebase AST Indexer[/]', border_style='green'))
    table = Table(title='📄 Indexed Codebase Files', show_header=True, header_style='bold magenta')
    table.add_column('File Path', style='cyan')
    table.add_column('LOC', justify='right', style='dim')
    table.add_column('Classes', style='green')
    table.add_column('Functions', style='yellow')
    for rel_path, f in sorted(indexed.items())[:20]:
        cls_names = ', '.join(list(f.classes.keys())[:3]) or '-'
        fn_names = ', '.join(list(f.functions.keys())[:3]) or '-'
        table.add_row(rel_path, str(f.lines_of_code), cls_names, fn_names)
    if len(indexed) > 20:
        table.add_row('...', '-', f'+ {len(indexed) - 20} more files', '-')
    console.print(table)

@cli.command()
@click.option('--limit', '-n', default=20, help='Number of recent records to show')
@click.option('--blocked-only', is_flag=True, help='Show only blocked attempts')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def audit(limit, blocked_only, as_json):
    """Show recent code-execution audit records."""
    from saleha.core.audit_log import AuditLog
    audit_log = AuditLog()
    records = audit_log.blocked_entries() if blocked_only else audit_log.recent(limit)
    if not records:
        if as_json:
            click.echo(json.dumps({'records': []}, ensure_ascii=False))
            return
        console.print('[yellow]No audit records found.[/]')
        return
    if as_json:
        click.echo(json.dumps({'records': records}, ensure_ascii=False))
        return
    table = Table(title='Execution Audit Log', show_header=True, header_style='bold magenta')
    table.add_column('Status', justify='center')
    table.add_column('Time', style='dim')
    table.add_column('Executed', justify='center')
    table.add_column('Code Hash', style='cyan')
    table.add_column('Reason', style='yellow')
    for record in records:
        allowed = record.get('allowed', False)
        status = '[green]ALLOWED[/]' if allowed else '[red]BLOCKED[/]'
        table.add_row(status, record.get('timestamp', '-'), 'yes' if record.get('executed') else 'no', record.get('code_hash', '-')[:16], record.get('reason', '')[:70] or '-')
    console.print(table)

@cli.command()
@click.argument('path', default='.', required=False)
@click.option('--severity', '-s', type=click.Choice(['high', 'medium', 'low', 'all'], case_sensitive=False), default='all', help='Filter by minimum severity')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def sast(path, severity, as_json):
    """Deep AST Security SAST scanner for detecting SQL injection, hardcoded secrets, and unsafe execution."""
    scanner = _cmds.ASTSecurityScanner()
    if os.path.isfile(path):
        vulns = scanner.scan_file(path)
        total_files = 1
    else:
        report = scanner.scan_directory(path)
        vulns = report.vulnerabilities
        total_files = report.total_files_scanned
    filtered_vulns = vulns
    if severity.lower() == 'high':
        filtered_vulns = [v for v in filtered_vulns if v.severity == 'HIGH']
    elif severity.lower() == 'medium':
        filtered_vulns = [v for v in filtered_vulns if v.severity in ('HIGH', 'MEDIUM')]
    high_c = sum((1 for v in filtered_vulns if v.severity == 'HIGH'))
    med_c = sum((1 for v in filtered_vulns if v.severity == 'MEDIUM'))
    low_c = sum((1 for v in filtered_vulns if v.severity == 'LOW'))
    if as_json:
        payload = {'path': path, 'total_files': total_files, 'total_vulnerabilities': len(filtered_vulns), 'high': high_c, 'medium': med_c, 'low': low_c, 'vulnerabilities': [{'rule_id': v.rule_id, 'severity': v.severity, 'file': v.file_path, 'line': v.line_number, 'snippet': v.code_snippet, 'description': v.description, 'remediation': v.remediation} for v in filtered_vulns]}
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    console.print(Panel.fit(f'[bold cyan]📁 Target Path:[/] {path}\n[bold cyan]📄 Files Scanned:[/] {total_files}\n[bold cyan]🛡️ Total Issues:[/] {len(filtered_vulns)} ([red]High: {high_c}[/], [yellow]Med: {med_c}[/], [blue]Low: {low_c}[/])', title='[bold green]🛡️ Deep AST Security SAST Scanner[/]', border_style='green' if not high_c else 'red'))
    if not filtered_vulns:
        console.print('[bold green]✅ Zero security vulnerabilities detected. Codebase is clean![/]')
        return
    table = Table(title='🚨 Security Vulnerability Breakdown', show_header=True, header_style='bold magenta')
    table.add_column('Severity', justify='center')
    table.add_column('Rule ID', style='cyan')
    table.add_column('Location', style='yellow')
    table.add_column('Description & Remediation', style='white')
    for v in filtered_vulns:
        sev_color = 'red' if v.severity == 'HIGH' else 'yellow' if v.severity == 'MEDIUM' else 'blue'
        table.add_row(f'[{sev_color}]{v.severity}[/]', v.rule_id, f'{os.path.basename(v.file_path)}:{v.line_number}', f'{v.description}\n[dim]Fix: {v.remediation}[/]')
    console.print(table)

@cli.command(name='review')
@click.argument('target_file_or_dir', default='.')
@click.option('--ensemble', is_flag=True, help='Use 3-Agent Multi-Model Consensus (Security + Performance + QA)')
@click.option('--min-confidence', default=0.8, help='Minimum confidence threshold for approval')
def review_cmd(target_file_or_dir, ensemble, min_confidence):
    """
    Run automated code review with optional Multi-Model Ensemble Consensus.
    
    Example: saleha review saleha/core/agentic_loop.py --ensemble
    """
    if ensemble:
        from saleha.core.ensemble_reviewer import ensemble_reviewer
        content = ''
        if os.path.isfile(target_file_or_dir):
            with open(target_file_or_dir, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        else:
            from saleha.core.git_native import git_engine
            content = git_engine.get_status_summary().get('diff', 'Codebase audit')
        consensus = ensemble_reviewer.review_code(content, file_path=target_file_or_dir, min_confidence=min_confidence)
        console.print(Markdown(consensus.summary))
        if consensus.approved:
            console.print('\n[bold green]✅ Code change APPROVED by Ensemble Consensus![/]\n')
        else:
            console.print('\n[bold yellow]⚠️ Code change REQUIRES REVISION before merge.[/]\n')
    else:
        console.print('[yellow]Pass --ensemble to run the 3-Agent consensus reviewer (e.g. saleha review . --ensemble)[/]')

@cli.command(name='threat')
@click.option('--output', default='docs/threat_model.md', help='Output path for STRIDE matrix markdown')
def threat_cmd(output):
    """
    Generate automated Microsoft STRIDE Threat Modeling Security Matrix.
    
    Example: saleha threat --output docs/threat_model.md
    """
    from saleha.core.threat_modeler import threat_modeler
    console.print(f'[bold cyan]🛡️ Synthesizing STRIDE Threat Model Matrix...[/]')
    rep = threat_modeler.analyze_workspace()
    saved = threat_modeler.save_report(rep, output_path=output)
    console.print(Markdown(rep.markdown_matrix))
    console.print(f'\n[bold green]✅ STRIDE Threat Model saved to:[/] [cyan]{saved}[/]\n')

@cli.command(name='debt')
@click.option('--threshold', default=10, help='Cyclomatic complexity hotspot threshold')
@click.option('--dir', 'target_dir', default='.', help='Directory to analyze')
def debt_cmd(threshold, target_dir):
    """
    Analyze Cognitive & Cyclomatic Complexity and flag Technical Debt hotspots.
    
    Example: saleha debt --threshold 10
    """
    from saleha.core.tech_debt_analyzer import tech_debt_analyzer
    console.print(f'[bold cyan]📉 Auditing codebase Technical Debt & Cognitive Complexity for:[/] [yellow]{target_dir}[/]')
    rep = tech_debt_analyzer.analyze_workspace(root_dir=target_dir, threshold=threshold)
    console.print(f'\n[bold white]Functions Analyzed:[/] {rep.total_functions_analyzed} | [bold white]Average Cyclomatic:[/] {rep.average_cyclomatic} | [bold white]Hotspots Flagged:[/] [yellow]{rep.hotspots_count}[/]\n')
    if rep.hotspots:
        table = Table(title=f'⚠️ Maintainability Hotspots (Complexity >= {threshold})', show_header=True, header_style='bold red', expand=True)
        table.add_column('Location', style='cyan')
        table.add_column('Function', style='bold white')
        table.add_column('Cyclomatic', style='yellow')
        table.add_column('Cognitive', style='red')
        table.add_column('Refactor Recommendation', style='green')
        for h in rep.hotspots[:15]:
            loc_str = f'{h.file_path}:{h.line_number}'
            table.add_row(loc_str, f'{h.function_name}()', str(h.cyclomatic_complexity), str(h.cognitive_complexity), h.refactor_suggestion or 'Extract helper functions')
        console.print(table)
    else:
        console.print('[bold green]✨ Clean Codebase! Zero functions exceed the complexity threshold.[/]\n')

@cli.command(name='review-ai')
@click.argument('path', default='.')
@click.option('--html', is_flag=True, help='Generate HTML review dashboard')
@click.option('--out', default='review_report.html', help='Output HTML report path')
def review_ai_cmd(path, html, out):
    """
    Run AI-Powered Deep Code Review (OWASP Top-10, Code Smells, Security).
    
    Example: saleha review-ai . --html
    """
    from saleha.core.ai_reviewer import ai_reviewer
    from saleha.core.review_reporter import review_reporter
    reports = []
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        reports.append(ai_reviewer.review_file(path, content))
    else:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', '.venv', 'node_modules')]
            for f in files:
                if f.endswith('.py'):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='replace') as fp:
                            c = fp.read()
                        reports.append(ai_reviewer.review_file(fpath, c))
                    except OSError:
                        pass
    if not reports:
        console.print('[yellow]No Python files found to review.[/]')
        return
    from rich.table import Table
    table = Table(title='🔍 Saleha AI Code Review Summary', border_style='cyan')
    table.add_column('File', style='cyan')
    table.add_column('Score', justify='right')
    table.add_column('Issues', justify='right')
    table.add_column('Critical', style='bold red', justify='right')
    table.add_column('High', style='bold yellow', justify='right')
    for r in reports:
        sc_style = 'bold green' if r.score >= 80 else 'bold yellow' if r.score >= 60 else 'bold red'
        table.add_row(os.path.relpath(r.file_path, path) if os.path.isdir(path) else r.file_path, f'[{sc_style}]{r.score}/100[/]', str(len(r.issues)), str(r.critical_count), str(r.high_count))
    console.print(table)
    if html:
        saved = review_reporter.save_report(reports, output_path=out)
        console.print(f'[bold green]📊 HTML Review Report saved to:[/] [cyan]{saved}[/]')

@cli.command(name='redteam')
@click.argument('path', required=True)
@click.option('--model', default='auto', help='Model to use for red-team fuzzing')
def redteam_cmd(path: str, model: str):
    """
    Autonomous Adversarial Red-Team Fuzzer & Exploit Simulation (AgentShield).
    
    Example: saleha redteam saleha/core/security_scanner.py
    """
    from saleha.core.red_team_engine import RedTeamEngine
    if not os.path.exists(path):
        console.print(f"[bold red]❌ Error: Path '{path}' not found.[/bold red]")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
    console.print(Panel(f'[bold red]⚔️ AgentShield: Adversarial Red-Team Fuzzer[/bold red]\nTarget: {path}', border_style='red'))
    with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), transient=True) as progress:
        progress.add_task(description='Synthesizing adversarial fuzz vectors & stress tests...', total=None)
        engine = RedTeamEngine(model=model)
        report = engine.audit_and_attack(code, target_name=os.path.basename(path))
    status_color = 'green' if report.is_hardened else 'red'
    console.print(f'\n[bold {status_color}]{report.summary}[/bold {status_color}]\n')
    if report.findings:
        table = Table(title='Red-Team Vulnerabilities Discovered', border_style='red')
        table.add_column('Category', style='bold red')
        table.add_column('Severity', style='yellow')
        table.add_column('Payload / Traceback', style='white')
        for finding in report.findings:
            table.add_row(finding.category, finding.severity, finding.crash_traceback[:100])
        console.print(table)

@cli.command(name='constitutional-check')
@click.argument('path', required=True)
def constitutional_check_cmd(path: str):
    """
    Audit code against Constitutional AI Alignment Rules.
    
    Example: saleha constitutional-check saleha/core/security_scanner.py
    """
    from saleha.core.constitutional_guard import constitutional_guard
    if not os.path.exists(path):
        console.print(f"[bold red]❌ Error: Path '{path}' not found.[/bold red]")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
    rep = constitutional_guard.audit_code(code, filename=os.path.basename(path))
    status_col = 'green' if rep.is_compliant else 'red'
    console.print(Panel(f'[bold {status_col}]📜 Constitutional AI Alignment Report: {path}[/bold {status_col}]\n{rep.summary}', border_style=status_col))

@cli.command(name='godel-utility')
def godel_utility_cmd():
    """
    Evaluate system-level Gödel Machine formal utility proof.
    
    Example: saleha godel-utility
    """
    from saleha.core.godel_utility import godel_utility_engine, measure_current_state
    # This used to build both states from literals -- SystemStateUtility(0.92,
    # 0.88, 1.0, 0.75) vs (0.96, 0.94, 1.0, 0.82) -- and print "AUTHORIZED"
    # about a refactoring that did not exist. The engine's maths was fine; the
    # inputs were invented. Measure the real system instead.
    state = measure_current_state()
    dec = godel_utility_engine.evaluate_modification(state, state, 'current system state')
    col = 'green' if dec.is_authorized else ('yellow' if state.unmeasured_fields else 'red')
    lines = [
        f'U(s) = {state.total_utility}',
        '',
        f'  task_pass_rate    {state.task_pass_rate:.3f}   '
        f'{"measured" if state.measured.get("task_pass_rate") else "UNMEASURED"}',
        f'  safety_score      {state.safety_score:.3f}   '
        f'{"measured" if state.measured.get("safety_score") else "UNMEASURED"}',
        f'  efficiency_score  {state.efficiency_score:.3f}   '
        f'{"measured" if state.measured.get("efficiency_score") else "UNMEASURED"}',
        f'  alignment_score   {state.alignment_score:.3f}   '
        f'{"measured" if state.measured.get("alignment_score") else "UNMEASURED"}',
    ]
    if state.unmeasured_fields:
        lines += ['', 'Unmeasured: ' + ', '.join(state.unmeasured_fields),
                  'alignment_score is deliberately never self-scored -- a system',
                  'rating its own alignment proves nothing.']
    console.print(Panel(f'[bold {col}]⚖️ Gödel Machine Utility Measurement[/bold {col}]\n'
                        + '\n'.join(lines), border_style=col))

@cli.command(name='emergence-check')
@click.option('--clear', is_flag=True, help='Delete the recorded swarm message history.')
def emergence_check_cmd(clear):
    """
    Audit multi-agent swarm dynamics for circular deadlocks and Gini inequality.

    Reads the handoffs recorded by `saleha team` runs. With no recorded
    activity it reports that there is nothing to judge, rather than calling an
    empty graph healthy.

    Example: saleha emergence-check
    """
    from saleha.core.emergence_detector import emergence_detector

    if clear:
        emergence_detector.clear(wipe_persisted=True)
        console.print('[green]Swarm message history cleared.[/]')
        return

    # The workflow being asked about ran in a different process, so the
    # in-memory singleton is empty here; the persisted log is the real source.
    emergence_detector.load_history()
    rep = emergence_detector.evaluate_swarm_health()

    if not rep.has_data:
        console.print(Panel(
            f'[bold yellow]🕵️ Swarm Emergence & Collusion Monitor[/bold yellow]\n{rep.summary}',
            border_style='yellow'))
        return

    col = 'green' if rep.is_healthy else 'yellow'
    console.print(Panel(
        f'[bold {col}]🕵️ Swarm Emergence & Collusion Monitor[/bold {col}]\n{rep.summary}',
        border_style=col))
    for anomaly in rep.anomalies:
        console.print(f'  [yellow]•[/] {anomaly}')
    if rep.remediation_action != 'none':
        console.print(f'  [dim]Suggested remediation: {rep.remediation_action}[/]')

@cli.command(name='merkle-audit')
def merkle_audit_cmd():
    """
    Verify tamper-proof cryptographic Merkle tree audit provenance.
    
    Example: saleha merkle-audit
    """
    from saleha.core.merkle_provenance import merkle_provenance_ledger
    ok, msg = merkle_provenance_ledger.verify_integrity()
    col = 'green' if ok else 'red'
    console.print(Panel(f'[bold {col}]🌳 Cryptographic Merkle Audit Trail[/bold {col}]\n{msg}', border_style=col))

@cli.command(name='quadratic-vote')
def quadratic_vote_cmd():
    """
    Quadratic Voting & VCG Swarm Consensus Status.
    
    Example: saleha quadratic-vote
    """
    from saleha.core.quadratic_voting import quadratic_voting_engine
    p = quadratic_voting_engine.create_proposal('ARCH_V2', 'Enable Asynchronous Event Sourcing', 'ArchitectAgent')
    quadratic_voting_engine.cast_vote('CoderAgent', 'ARCH_V2', 3)
    quadratic_voting_engine.cast_vote('SecurityAgent', 'ARCH_V2', 2)
    rep = quadratic_voting_engine.tally_proposal('ARCH_V2')
    console.print(Panel(f'[bold magenta]🗳️ Quadratic Voting & VCG Allocation[/bold magenta]\n{rep.summary}', border_style='magenta'))



@cli.command(name='verify-work')
@click.argument('ledger', default='.saleha/work.jsonl')
@click.option('--dir', 'root_dir', default='.', help='Repository the claims are about')
@click.option('--chain-only', is_flag=True,
              help='Only check the record is unaltered; do not re-run claims')
@click.option('--expect', type=int, default=-1,
              help='Entry count from outside the file; catches silent deletion')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable output')
def verify_work_cmd(ledger, root_dir, chain_only, expect, as_json):
    """
    Independently re-verify what an agent claimed it did.

    Unlike an audit log, this does not ask you to trust the record. Every
    checkable claim carries the command or file check that produced it, so
    this re-runs them against the repo as it is now and reports what it
    could actually re-establish. Agent statements that cannot be re-run are
    reported as unverifiable and never counted as proof.

    Example: saleha verify-work .saleha/work.jsonl --dir .
    """
    from saleha.core.work_ledger import WorkLedger

    if not os.path.exists(ledger):
        msg = f'No ledger at {ledger}'
        if as_json:
            click.echo(json.dumps({'success': False, 'error': msg}))
        else:
            console.print(f'[bold red]{msg}[/]')
        return

    report = WorkLedger(ledger, root_dir=root_dir).verify(
        recheck=not chain_only, expect_entries=expect)

    if as_json:
        click.echo(json.dumps(report, indent=2))
        return

    ok = report['chain_intact']
    console.print(Panel(
        f"[bold {'green' if ok else 'red'}]"
        f"{'Record intact' if ok else 'RECORD TAMPERED'}[/]\n"
        f"{report['chain_detail']}",
        border_style='green' if ok else 'red'))

    if not ok:
        console.print('[bold red]The record was altered after it was written. '
                      'Nothing in it can be trusted.[/]')
        return

    if chain_only:
        console.print('[dim]--chain-only: claims were not re-run.[/]')
        return

    table = Table(title='Claim re-verification', show_lines=False)
    table.add_column('#', style='dim', width=4)
    table.add_column('Claim', style='cyan')
    table.add_column('Subject')
    table.add_column('Verdict')
    colours = {'confirmed': 'green', 'failed': 'red',
               'environment_diverged': 'yellow', 'unverifiable': 'dim'}
    for r in report['results']:
        table.add_row(str(r['seq']), str(r['kind']), r['subject'][:52],
                      f"[{colours.get(r['verdict'], 'white')}]{r['verdict']}[/]")
    console.print(table)

    rate = report['proof_rate']
    console.print(
        f"\n[bold]{report['independently_confirmed']}/"
        f"{report['checkable_claims']} checkable claims independently "
        f"re-established[/] (proof rate {rate:.0%})")
    if report['verdicts'].get('unverifiable'):
        console.print(f"[dim]{report['verdicts']['unverifiable']} agent "
                      f"statement(s) recorded but not counted as proof.[/]")

    if expect < 0:
        # Stating the limit is part of the guarantee. A holder of the file
        # can delete an entry and recompute the chain, and nothing left in
        # the file will look wrong -- so silence here would be misleading.
        console.print(
            "[dim]Note: this proves nothing was altered, not that nothing "
            "was omitted. Pass --expect N with a count from outside the "
            "file (a commit message, a CI record) to check for deletions.[/]")
