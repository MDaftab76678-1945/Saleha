"""
Saleha Core: Human-In-The-Loop Approval Gate

Enforces physical boundaries on autonomous actions:

    SALEHA_APPROVAL=off        (default) Auto-approve all actions (unrestricted legacy mode)
    SALEHA_APPROVAL=dangerous  Require interactive confirmation for high-risk actions
                               (shell_exec, git_commit, vault_write, file_delete, file_write, etc.)
    SALEHA_APPROVAL=always     Require interactive confirmation for every gated action

In non-TTY environments (CI/headless scripts without active stdin), actions that require
approval fail closed (denied, returning False) unless SALEHA_APPROVAL=off is explicitly set.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set

CRITICAL_ACTIONS: Set[str] = {
    "git_reset_hard",
    "vault_write",
    "vault_export",
    "file_delete",
}

DANGEROUS_ACTIONS: Set[str] = {
    "shell_exec",
    "git_commit",
    "vault_write",
    "vault_export",
    "file_delete",
    "file_write",
    "file_patch",
    "git_reset_hard",
    "forge_tool",
}

_MODE_ALIASES = {
    "none": "off",
    "never": "off",
    "risky": "dangerous",
    "all": "always",
    "every": "always",
}
VALID_MODES = ("off", "dangerous", "always")


@dataclass
class ApprovalDecision:
    action_type: str
    description: str
    approved: bool
    reason: str
    timestamp: float = field(default_factory=time.time)


def normalize_action(action_type: str) -> str:
    """Normalizes namespaced or prefixed action types (e.g. 'fs:file_delete' -> 'file_delete')."""
    clean = action_type.strip().lower()
    if ":" in clean:
        clean = clean.split(":")[-1]
    if "." in clean:
        clean = clean.split(".")[-1]
    return clean


def get_action_risk_level(action_type: str) -> str:
    """Classifies an action into 'critical', 'dangerous', or 'standard' risk tier."""
    norm = normalize_action(action_type)
    if norm in CRITICAL_ACTIONS or action_type in CRITICAL_ACTIONS:
        return "critical"
    if norm in DANGEROUS_ACTIONS or action_type in DANGEROUS_ACTIONS:
        return "dangerous"
    return "standard"


def get_mode() -> str:
    raw = (os.getenv("SALEHA_APPROVAL") or "off").strip().lower()
    mode = _MODE_ALIASES.get(raw, raw)
    return mode if mode in VALID_MODES else "off"


def requires_approval(action_type: str) -> bool:
    mode = get_mode()
    if mode == "always":
        return True
    if mode == "dangerous":
        norm = normalize_action(action_type)
        return norm in DANGEROUS_ACTIONS or action_type in DANGEROUS_ACTIONS
    return False


def _cli_confirm(prompt: str) -> bool:
    """Interactive TTY confirmation; fails closed (False) in headless/non-TTY environments."""
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        import click
        return click.confirm(prompt, default=False)
    except Exception:
        return False


def _ask(
    action_type: str,
    description: str,
    confirmer: Optional[Callable[[str], bool]],
) -> bool:
    """Executes the confirmation callback for an action requiring explicit permission."""
    confirm = confirmer or _cli_confirm
    try:
        return confirm(f"[Saleha {action_type}] {description} -- approve?")
    except Exception:
        return False


class ApprovalGate:
    """Object-oriented interface for human-in-the-loop permission checking."""

    def __init__(self, mode: Optional[str] = None) -> None:
        self._override_mode = mode
        self.history: List[ApprovalDecision] = []

    def get_mode(self) -> str:
        return self._override_mode or get_mode()

    def requires_approval(self, action_type: str) -> bool:
        if self._override_mode:
            if self._override_mode == "always":
                return True
            if self._override_mode == "dangerous":
                norm = normalize_action(action_type)
                return norm in DANGEROUS_ACTIONS or action_type in DANGEROUS_ACTIONS
            return False
        return requires_approval(action_type)

    def record_decision(
        self, action_type: str, description: str, approved: bool, reason: str
    ) -> ApprovalDecision:
        decision = ApprovalDecision(
            action_type=action_type,
            description=description,
            approved=approved,
            reason=reason,
            timestamp=time.time(),
        )
        self.history.append(decision)
        return decision

    def get_history(self) -> List[ApprovalDecision]:
        return list(self.history)

    def clear_history(self) -> None:
        self.history.clear()

    def check(
        self,
        action_type: str,
        description: str,
        confirmer: Optional[Callable[[str], bool]] = None,
    ) -> bool:
        """Permission check for a gated action, honouring instance-level mode override and tracking history."""
        if not self.requires_approval(action_type):
            self.record_decision(action_type, description, True, "mode_bypassed")
            return True
        approved = _ask(action_type, description, confirmer)
        reason = "user_confirmed" if approved else "user_denied_or_non_tty"
        self.record_decision(action_type, description, approved, reason)
        return approved


def approve(
    action_type: str,
    description: str,
    confirmer: Optional[Callable[[str], bool]] = None,
) -> bool:
    """Request permission for a gated action. Auto-approves if gating is not required."""
    return approval_gate.check(action_type, description, confirmer)


approval_gate = ApprovalGate()


