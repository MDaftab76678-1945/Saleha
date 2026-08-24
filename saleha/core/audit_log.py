"""
Saleha Core: Audit Log (New -- security checklist item #2)

Har code-execution attempt ka record rakhta hai -- chahe wo allow hua ho
ya block. Isse baad me review kiya ja sakta hai ki Saleha ne kya-kya chalane
ki koshish ki, khaas kar agar kabhi lage ki kuch galat hua.

File: ~/.saleha/audit_log.jsonl (append-only, JSONL format)
"""

import json
import os
import time
import hashlib


DEFAULT_AUDIT_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "audit_log.jsonl")


class AuditLog:
    def __init__(self, path: str = DEFAULT_AUDIT_PATH):
        self.path = path

    def record(
        self,
        code: str,
        allowed: bool,
        reason: str = "",
        executed: bool = False,
        success: bool = None,
        exit_code: int = None,
    ):
        entry = {
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

    def recent(self, n: int = 20):
        if not os.path.exists(self.path):
            return []
        entries = []
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

    def blocked_entries(self):
        return [e for e in self.recent(n=10**9) if not e["allowed"]]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "audit.jsonl")
        log = AuditLog(path=path)

        log.record(code="print('hello')", allowed=True, executed=True, success=True, exit_code=0)
        log.record(code="import socket", allowed=False, reason="network access blocked")

        print("Recent entries:")
        for e in log.recent():
            status = "✅ allowed" if e["allowed"] else "🚫 blocked"
            print(f"  [{e['timestamp']}] {status} -- {e['code_preview']} ({e['reason'] or 'no issue'})")

        print(f"\nBlocked count: {len(log.blocked_entries())}")