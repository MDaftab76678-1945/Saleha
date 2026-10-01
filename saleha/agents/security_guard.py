"""
Saleha Agents: Security Guard Agent

Scans code for vulnerabilities (the AST scanner plus checks for SQL built
from f-strings, hardcoded secrets and MD5/SHA-1), applies the mechanical
patches it has (parameterized SQL for the simple f-string case, SHA-256 for
weak hashes) -- and then scans the patched code again. What the second scan
still finds is reported as not fixed; the patch must also compile. A
hardcoded secret has no mechanical patch and is always left for a person.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from saleha.agents.base_agent import BaseAgent
from saleha.core.verification.security_scanner import ASTSecurityScanner


@dataclass
class SecurityAuditResult:
    is_secure: bool
    vulnerabilities_found: List[str]
    cwe_identifiers: List[str]
    hardened_code: str
    audit_report: str
    model_used: str = ""
    remaining_after_patch: List[str] = field(default_factory=list)   # found again in the patched code
    patch_compiles: Optional[bool] = None
    patch_verified: Optional[bool] = None   # True: the re-scan is clean and the patch compiles; None: nothing to patch


class SecurityGuardAgent(BaseAgent):
    """Principal DevSecOps & AST Vulnerability Guard Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="SecurityGuard", model=model)
        self.scanner = ASTSecurityScanner()

    def _findings(self, code: str) -> List[Tuple[str, str]]:
        """(description, CWE) for every finding in `code`."""
        found: List[Tuple[str, str]] = []
        for issue in self.scanner.scan_code(code) or []:
            found.append((f"Security Alert: {issue.rule_id} -> {issue.description}", "CWE-AST-Violation"))
        if re.search(r"SELECT\s+.*?FROM\s+.*?[{]", code, re.IGNORECASE):
            found.append(("SQL Injection Vulnerability (CWE-89): Unparameterized dynamic string formatting detected.",
                          "CWE-89"))
        if re.search(r"(?:api_key|secret|password|token)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]", code, re.IGNORECASE):
            found.append(("Hardcoded Secret Detected (CWE-798): Plaintext API credentials in source.", "CWE-798"))
        if "hashlib.md5(" in code or "hashlib.sha1(" in code:
            found.append(("Weak Cryptographic Hash (CWE-328): Insecure hashing algorithm in use.", "CWE-328"))
        return found

    def audit_and_harden(self, task: str, code: str) -> SecurityAuditResult:
        """Scan, patch what can be patched mechanically, and scan the patch again."""
        findings = self._findings(code)
        vulns = [d for d, _c in findings]
        cwes = sorted({c for _d, c in findings})
        is_secure = not findings

        hardened = code
        remaining: List[str] = []
        compiles: Optional[bool] = None
        if not is_secure:
            hardened = re.sub(
                r"f['\"]SELECT\s+(.*?)\s+FROM\s+(.*?)\s+WHERE\s+(.*?)\s*=\s*['\"]\{(\w+)\}['\"]['\"]",
                r'"SELECT \1 FROM \2 WHERE \3 = :param", {"param": \4}',
                hardened, flags=re.IGNORECASE)
            hardened = hardened.replace("hashlib.md5(", "hashlib.sha256(").replace("hashlib.sha1(", "hashlib.sha256(")
            remaining = [d for d, _c in self._findings(hardened)]
            try:
                compile(hardened, "<hardened>", "exec")
                compiles = True
            except SyntaxError:
                compiles = False
        verified = None if is_secure else (not remaining and bool(compiles))

        report = (f"# Security Audit Report\n"
                  f"Status: {'PASS (Clean)' if is_secure else f'FAIL ({len(vulns)} Vulnerabilities Detected)'}\n"
                  f"Total Vulnerabilities: {len(vulns)}\nCWEs: {', '.join(cwes) if cwes else 'None'}\n\nDetails:\n"
                  + ("\n".join(f"- {v}" for v in vulns) if vulns else "- Zero security vulnerabilities discovered.")
                  + ("" if is_secure else
                     f"\n\nAfter the automatic patch (scanned again): "
                     + ("clean, and it compiles." if verified else
                        f"{len(remaining)} finding(s) remain -- fix by hand:\n"
                        + "\n".join(f"- {r}" for r in remaining)
                        + ("" if compiles else "\n- the patched code does not compile"))) + "\n")
        return SecurityAuditResult(
            is_secure=is_secure, vulnerabilities_found=vulns, cwe_identifiers=cwes, hardened_code=hardened,
            audit_report=report, model_used=self.model_preference, remaining_after_patch=remaining,
            patch_compiles=compiles, patch_verified=verified)
