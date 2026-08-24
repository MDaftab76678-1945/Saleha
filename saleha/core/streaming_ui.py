"""
Saleha Core: Real-Time Token Streaming & Live Syntax UI

Streams tokens chunk-by-chunk from local Ollama with rich syntax highlighting
and typewriter rendering directly inside the user's terminal session.
"""

import sys
from typing import Optional, Callable
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown

from saleha.core.model_provider import default_provider, ProviderResponse

console = Console()


class StreamRenderer:
    """Manages live token-by-token terminal rendering."""

    def __init__(self, console_instance: Optional[Console] = None):
        self.console = console_instance or console

    def stream_to_terminal(self, model: str, prompt: str, title: str = "Saleha Stream") -> str:
        """Streams Ollama generation in real-time with Markdown and live updates."""
        accumulated_text = ""

        with Live(
            Panel(
                Markdown("*(Thinking...)*"),
                title=f"[bold green]🌊 {title} ({model})[/]",
                border_style="green"
            ),
            console=self.console,
            refresh_per_second=10
        ) as live:
            def on_token(token: str):
                nonlocal accumulated_text
                accumulated_text += token
                clean_display = accumulated_text or "*(Streaming...)*"
                live.update(Panel(
                    Markdown(clean_display),
                    title=f"[bold green]🌊 {title} ({model})[/]",
                    border_style="green"
                ))

            res = default_provider.stream_generate(model=model, prompt=prompt, callback=on_token)
            if not res.success:
                live.update(Panel(
                    f"[bold red]Stream Error:[/] {res.error_message}",
                    title="[bold red]Stream Failed[/]",
                    border_style="red"
                ))

        return accumulated_text


# Global instance
streaming_ui = StreamRenderer()

