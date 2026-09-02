"""
Saleha Agents: Security Guard Agent

Executes AST SAST vulnerability scans, audits for OWASP Top 10 risks,
detects hardcoded credentials, and synthesizes automated cryptographic & boundary patches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.core.security_scanner import ASTSecurityScanner


@dataclass
class SecurityAuditResult:
    is_secure: bool
    vulnerabilities_found: List[str]
    cwe_identifiers: List[str]
    hardened_code: str
    audit_report: str
    model_used: str = ""


class SecurityGuardAgent(BaseAgent):
    """Principal DevSecOps & AST Vulnerability Guard Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="SecurityGuard", model=model)
        self.scanner = ASTSecurityScanner()

    def audit_and_harden(self, task: str, code: str) -> SecurityAuditResult:
        """Audits code for security vulnerabilities and synthesizes secure AST patches."""
        vulns: List[str] = []
        cwes: List[str] = []

        # 1. Static AST Scan
        scan_issues = self.scanner.scan_code(code)
        if scan_issues:
            for issue in scan_issues:
                vulns.append(f"Security Alert: {issue.rule_id} -> {issue.description}")
                cwes.append("CWE-AST-Violation")

        # 2. Heuristic OWASP checks (SQLi, hardcoded tokens, insecure hashes)
        if re.search(r"f['\"][^'\"]*SELECT\s+.*?FROM\s+.*?[{]", code, re.IGNORECASE) or re.search(r"SELECT\s+.*?FROM\s+.*?[{]", code, re.IGNORECASE):
            vulns.append("SQL Injection Vulnerability (CWE-89): Unparameterized dynamic string formatting detected.")
            cwes.append("CWE-89")

        if re.search(r"(?:api_key|secret|password|token)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]", code, re.IGNORECASE):
            vulns.append("Hardcoded Secret Detected (CWE-798): Plaintext API credentials in source.")
            cwes.append("CWE-798")

        if "hashlib.md5(" in code or "hashlib.sha1(" in code:
            vulns.append("Weak Cryptographic Hash (CWE-328): Insecure hashing algorithm in use.")
            cwes.append("CWE-328")

        is_secure = len(vulns) == 0

        # 3. Patch synthesis
        hardened = code
        if not is_secure:
            # Auto parameterize SQLi
            hardened = re.sub(
                r"f['\"]SELECT\s+(.*?)\s+FROM\s+(.*?)\s+WHERE\s+(.*?)\s*=\s*['\"]\{(\w+)\}['\"]['\"]",
                r'"SELECT \1 FROM \2 WHERE \3 = :param", {"param": \4}',
                hardened,
                flags=re.IGNORECASE
            )
            # Replace MD5 with SHA-256
            hardened = hardened.replace("hashlib.md5(", "hashlib.sha256(")
            hardened = hardened.replace("hashlib.sha1(", "hashlib.sha256(")

        report = f"""# Security Audit Report
Status: {"PASS (Clean)" if is_secure else f"FAIL ({len(vulns)} Vulnerabilities Detected)"}
Total Vulnerabilities: {len(vulns)}
CWEs: {', '.join(set(cwes)) if cwes else 'None'}

Details:
{chr(10).join(f"- {v}" for v in vulns) if vulns else "- Zero security vulnerabilities discovered."}
"""

        return SecurityAuditResult(
            is_secure=is_secure,
            vulnerabilities_found=vulns,
            cwe_identifiers=list(set(cwes)),
            hardened_code=hardened,
            audit_report=report,
            model_used=self.model_preference
        )
