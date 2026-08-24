"""
Saleha Core: Interactive AI REPL & Live Debugger

Provides a stateful Python execution environment with runtime variable inspection,
memory state tracking, and live line-by-line debugging session.
"""

import sys
import io
import ast
import traceback
import contextlib
from dataclasses import dataclass
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class REPLExecutionResult:
    success: bool
    output: str
    error: Optional[str] = None
    result_val: Any = None


class StatefulREPL:
    """Stateful Python REPL and variable state debugger."""

    def __init__(self):
        self.globals_dict: Dict[str, Any] = {
            "__name__": "__saleha_repl__",
            "__doc__": None,
        }
        self.history: list = []

    def reset(self):
        """Resets REPL execution state."""
        self.globals_dict = {
            "__name__": "__saleha_repl__",
            "__doc__": None,
        }
        self.history.clear()

    def execute_statement(self, code_str: str) -> REPLExecutionResult:
        """Executes a code string within the stateful globals dictionary."""
        code_str = code_str.strip()
        if not code_str:
            return REPLExecutionResult(success=True, output="")

        self.history.append(code_str)
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        result_val = None

        try:
            # Check if code is a single expression (like `2 + 2` or `my_var`)
            parsed = ast.parse(code_str)
            is_single_expr = len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Expr)

            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                if is_single_expr:
                    # Evaluate expression and store/print result
                    expr_code = compile(ast.Expression(parsed.body[0].value), "<saleha-repl>", "eval")
                    result_val = eval(expr_code, self.globals_dict)  # noqa: SEC002 -- interactive REPL ka core feature hai
                    if result_val is not None:
                        stdout_buf.write(repr(result_val) + "\n")
                else:
                    exec_code = compile(parsed, "<saleha-repl>", "exec")
                    exec(exec_code, self.globals_dict)  # noqa: SEC002 -- interactive REPL ka core feature hai

            out = stdout_buf.getvalue()
            err = stderr_buf.getvalue()
            return REPLExecutionResult(
                success=True,
                output=(out + err).strip(),
                result_val=result_val
            )
        except Exception as e:
            err_msg = traceback.format_exc()
            return REPLExecutionResult(
                success=False,
                output=stdout_buf.getvalue().strip(),
                error=err_msg
            )

    def get_user_variables(self) -> Dict[str, Dict[str, str]]:
        """Returns non-internal variables in current memory state."""
        vars_info = {}
        for k, v in self.globals_dict.items():
            if not k.startswith("__"):
                vars_info[k] = {
                    "type": type(v).__name__,
                    "value": repr(v)[:80] + ("..." if len(repr(v)) > 80 else "")
                }
        return vars_info

    def interactive_loop(self):
        """Starts interactive terminal REPL loop."""
        console.print(Panel(
            "[bold green]🧠 Saleha Interactive AI REPL & Debugger[/]\n"
            "Commands: [cyan]:vars[/] (inspect memory), [cyan]:clear[/] (reset), [cyan]:exit[/] (quit)",
            border_style="green"
        ))

        while True:
            try:
                line = input("saleha-repl> ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Exiting Saleha REPL.[/]")
                break

            if not line:
                continue

            if line == ":exit":
                break
            elif line == ":clear":
                self.reset()
                console.print("[green]Session state cleared.[/]")
                continue
            elif line == ":vars":
                v_map = self.get_user_variables()
                if not v_map:
                    console.print("[dim]No user variables currently in memory.[/]")
                else:
                    t = Table(title="🔍 Active Variables in Memory", border_style="cyan")
                    t.add_column("Variable", style="bold cyan")
                    t.add_column("Type", style="yellow")
                    t.add_column("Value", style="green")
                    for var_name, info in v_map.items():
                        t.add_row(var_name, info["type"], info["value"])
                    console.print(t)
                continue

            res = self.execute_statement(line)
            if res.success:
                if res.output:
                    console.print(res.output)
            else:
                console.print(f"[bold red]{res.error}[/]")


# Global instance
repl = StatefulREPL()

