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

@cli.command(name='voice')
@click.argument('prompt', required=False, default=None)
@click.option('--audio', type=click.Path(exists=True), default=None, help='Path to recorded audio wav file')
@click.option('--wake-word', default='saleha', help='Wake word to listen for (default: saleha)')
@click.option('--simulate', default=None, help='Simulate speech input string without microphone')
def voice_cmd(prompt: Optional[str], audio: Optional[str], wake_word: str, simulate: Optional[str]):
    """
    Jarvis-style Hands-Free Voice Assistant for Saleha.
    
    Example: saleha voice "build a rate limiter"
    """
    from saleha.core.voice_assistant import VoiceAssistant
    if not prompt and (not audio) and (not simulate):
        console.print('[bold red]❌ Error: Either prompt text, --audio, or --simulate must be provided.[/bold red]')
        sys.exit(2)
    va = VoiceAssistant(wake_word=wake_word)
    input_text = prompt or simulate or ''
    res = va.process_voice_prompt(input_text, audio_file=audio)
    if not res.success:
        console.print(f'[bold red]❌ {res.response_text}[/bold red]')
        sys.exit(1)
    console.print(f'[bold green]Response:[/bold green] {res.execution_result or res.response_text}')

@cli.command(name='vision')
@click.argument('spec')
@click.option('--framework', '-f', default='react', type=click.Choice(['react', 'html', 'flutter']), help='Target UI framework')
@click.option('--name', '-n', default='GeneratedComponent', help='Component name')
@click.option('--image', '-i', default=None, type=click.Path(exists=True), help='Screenshot/wireframe image -- REAL vision model se analyze hota hai (llava/qwen-vl)')
@click.option('--output-file', '-o', default=None, help='Save generated code to file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def vision_cmd(spec, framework, name, image, output_file, as_json):
    """Synthesize UI code from specs OR from a real screenshot via local vision models.

    Example: saleha vision "responsive dashboard" --image ./mockup.png -f react
    """
    from saleha.core.vision_coder import vision_coder
    res = vision_coder.synthesize_ui(layout_spec=spec, framework=framework, component_name=name, image_source=image)
    if as_json:
        click.echo(json.dumps({'framework': res.framework, 'component_name': res.component_name, 'dependencies': res.dependencies, 'code': res.code, 'used_vision': res.used_vision, 'model_used': res.model_used, 'source': res.source_note}, ensure_ascii=True))
        return
    source_label = f'[green]👁️ {res.source_note}[/]' if res.used_vision else f'[dim]{res.source_note}[/]'
    console.print(Panel(f"[bold cyan]Framework:[/] {res.framework.upper()}\n[bold cyan]Component:[/] {res.component_name}\n[bold cyan]Dependencies:[/] {', '.join(res.dependencies)}\n[bold cyan]Source:[/] {source_label}", title='[bold green]🖼️ Saleha Vision UI Synthesizer[/]', border_style='green'))
    syntax = Syntax(res.code, 'typescript' if framework == 'react' else 'dart' if framework == 'flutter' else 'html', theme='monokai', line_numbers=True)
    console.print(syntax)
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(res.code)
        console.print(f'\n[bold green]💾 Saved component to:[/] {output_file}')

@cli.command(name='voice-live')
@click.option('--speak', is_flag=True, default=True, help='Enable audio speech response')
def voice_live_cmd(speak):
    """
    Start Full-Duplex Real-Time Voice Terminal Assistant.
    
    Example: saleha voice-live
    """
    from saleha.core.voice_live import voice_live_assistant
    console.print('[bold green]🎙️ Saleha Voice-Live Terminal Assistant is listening...[/]')
    console.print("[dim]Type voice command or press Enter with speech. Type 'exit' to quit.[/]\n")
    try:
        while True:
            prompt = click.prompt('🎤 Voice Command', default='')
            if not prompt or prompt.strip().lower() in ('exit', 'quit'):
                break
            turn = voice_live_assistant.process_turn(input_text=prompt, speak=speak)
            console.print(f'[bold cyan]🤖 Action:[/] {turn.action_summary}')
            if turn.spoken_response != turn.action_summary:
                console.print(f'[bold green]🗣️ Spoken:[/] {turn.spoken_response}')
    except (KeyboardInterrupt, EOFError):
        pass
    console.print('\n[yellow]Voice assistant stopped.[/]')

@cli.command('design-vision')
@click.argument('prompt_or_path')
def design_vision_cli_cmd(prompt_or_path: str) -> None:
    """Generate React JSX and vanilla CSS from a textual UI description.

    The layout family (auth form, dashboard, pricing, article, settings,
    landing) is inferred from the prompt and drives the component set and
    palette. JSX/CSS come from the model when it is reachable; otherwise a
    layout-specific template is returned and labelled as a fallback. There
    is no image parsing -- a path is used as its filename text only.
    """
    from saleha.agents.vision_designer import vision_designer
    console.print(f'\n[bold cyan]Vision Designer -- synthesizing:[/] [yellow]"{prompt_or_path}"[/]\n')
    spec = vision_designer.synthesize_from_wireframe(prompt_or_path)
    source = 'model' if spec.used_model else 'template fallback (model unavailable)'
    console.print(f'[bold green]Synthesized {spec.layout_type} in {spec.generation_time_ms}ms[/bold green] '
                  f'[dim]via {source}[/dim]')
    console.print(f"  Components   : {', '.join(spec.components)}")
    console.print(f"  Palette      : {', '.join(spec.color_palette[:4])}")
    if spec.used_model:
        console.print(f"  Model tokens : {spec.total_tokens_generated}\n")
    else:
        console.print()
    console.print(Panel(spec.jsx_component, title='[bold cyan]React JSX[/]', border_style='cyan'))
    console.print(Panel(spec.css_styles, title='[bold magenta]Vanilla CSS[/]', border_style='magenta'))

