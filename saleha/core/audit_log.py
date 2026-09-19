"""
Saleha Core: Security Audit Log

Records every code-execution attempt (both permitted and blocked) for security auditing,
forensic tracking, and runtime compliance verification.

File: ~/.saleha/audit_log.jsonl (append-only, JSONL format)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_AUDIT_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "audit_log.jsonl")


class AuditLog:
    def __init__(self, path: str = DEFAULT_AUDIT_PATH) -> None:
        self.path = path

    def record(
        self,
        code: str,
        allowed: bool,
        reason: str = "",
        executed: bool = False,
        success: Optional[bool] = None,
        exit_code: Optional[int] = None,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "code_hash": hashlib.sha256(code.encode("utf-8")).hexdigest()[:16],
            "code_preview": code[:120].replace("\n", " "),
            "allowed": allowed,
            "reason": reason,
            "executed": executed,
            "success": success,
            "exit_code": exit_code,
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def recent(self, n: int = 20) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        entries: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries[-n:]

    def blocked_entries(self) -> List[Dict[str, Any]]:
        return [e for e in self.recent(n=10**9) if not e.get("allowed", True)]

    def filter_by_status(
        self,
        allowed: Optional[bool] = None,
        executed: Optional[bool] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        all_entries = self.recent(n=10**9)
        filtered = []
        for e in all_entries:
            if allowed is not None and e.get("allowed") != allowed:
                continue
            if executed is not None and e.get("executed") != executed:
                continue
            if success is not None and e.get("success") != success:
                continue
            filtered.append(e)
        return filtered[-limit:]

    def stats(self) -> Dict[str, Any]:
        all_entries = self.recent(n=10**9)
        total = len(all_entries)
        allowed_count = sum(1 for e in all_entries if e.get("allowed"))
        blocked_count = total - allowed_count
        executed_count = sum(1 for e in all_entries if e.get("executed"))
        success_count = sum(1 for e in all_entries if e.get("success") is True)
        failed_count = sum(1 for e in all_entries if e.get("success") is False)

        return {
            "total_entries": total,
            "allowed_count": allowed_count,
            "blocked_count": blocked_count,
            "executed_count": executed_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "path": self.path,
        }

    def verify_integrity(self) -> Tuple[bool, int, List[str]]:
        """Verifies line-by-line JSON structure and schema compliance of the audit log."""
        if not os.path.exists(self.path):
            return True, 0, []

        errors: List[str] = []
        valid_count = 0
        required_keys = {"timestamp", "code_hash", "allowed"}

        with open(self.path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    missing = required_keys - set(data.keys())
                    if missing:
                        errors.append(f"Line {idx}: missing required schema keys {sorted(missing)}")
                    else:
                        valid_count += 1
                except json.JSONDecodeError as err:
                    errors.append(f"Line {idx}: JSON parse error: {err.msg}")

        is_valid = len(errors) == 0
        return is_valid, valid_count, errors


audit_log = AuditLog()
