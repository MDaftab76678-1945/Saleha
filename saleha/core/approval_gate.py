"""
Saleha Core: Human-In-The-Loop Approval Gate (B2)

Purana permission_manager kabhi wired hi nahi hua tha (dead code ban gaya,
delete karna pada). Ye minimal, asli wired version hai:

    SALEHA_APPROVAL=off        (default) sab auto-approve -- legacy behavior
    SALEHA_APPROVAL=dangerous  sirf khatarnak actions poochhe
                               (shell_exec, git_commit, vault_write, file_delete)
    SALEHA_APPROVAL=always     har gated action poochhe

Non-TTY environments (CI/scripts) mein confirm possible nahi -- wahan deny
hota hai jab approval required ho (fail-closed), jab tak SALEHA_APPROVAL=off
na ho. Isse automation tootti nahi, par surprise bhi nahi hota.
"""

import os
import sys
from typing import Callable, Optional, Set

DANGEROUS_ACTIONS: Set[str] = {
    "shell_exec",
    "git_commit",
    "vault_write",
    "vault_export",
    "file_delete",
}

_MODE_ALIASES = {
    "none": "off",
    "never": "off",
    "risky": "dangerous",
    "all": "always",
    "every": "always",
}
VALID_MODES = ("off", "dangerous", "always")


def get_mode() -> str:
    raw = (os.getenv("SALEHA_APPROVAL") or "off").strip().lower()
    mode = _MODE_ALIASES.get(raw, raw)
    return mode if mode in VALID_MODES else "off"


def requires_approval(action_type: str) -> bool:
    mode = get_mode()
    if mode == "always":
        return True
    if mode == "dangerous":
        return action_type in DANGEROUS_ACTIONS
    return False


def _cli_confirm(prompt: str) -> bool:
    """TTY confirm; non-TTY pe fail-closed (False)."""
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        import click
        return bool(click.confirm(prompt, default=False))
    except Exception:
        return False


def approve(action_type: str, description: str,
            confirmer: Optional[Callable[[str], bool]] = None) -> bool:
    """Gated action ke liye permission. Approval required na ho -> True.

    `confirmer` injectable hai (tests / studio UI apna dialog laga sakte hain).
    """
    if not requires_approval(action_type):
        return True
    confirm = confirmer or _cli_confirm
    try:
        return bool(confirm(f"[Saleha {action_type}] {description} -- approve?"))
    except Exception:
        return False
