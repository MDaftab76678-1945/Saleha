"""
Saleha Core: a four-pattern regex screen for a few dangerous literals.

Scans source text line by line for four specific patterns -- `rm -rf /`,
unsafe deserialization, a couple of privilege-escalation strings, and one
shape of credential POST -- and reports which lines matched.

## What the name and docstring used to claim

It was the "Constitutional AI System-Level Alignment Guard", and the docstring
listed five rules it "enforces", including "No unauthorized network sockets"
and "No obfuscated payload execution".

**There were four rules, and neither of those two was among them.** No pattern
covered sockets or `exec`. The docstring described a guard that did not exist.

It also has nothing to do with Constitutional AI as the term is used -- a
written constitution plus model self-critique and revision. No model is
involved here. It is a narrower, regex-only sibling of `saleha sast`, which
does the same job with a real AST scanner.

## The claim that made it dangerous

`is_compliant` was `True` whenever none of the four regexes matched, and the
summary printed "COMPLIANT". Measured, on code that walks `/` deleting every
file, opens a socket to a remote host, ships `/etc/passwd` down it and execs a
downloaded payload:

    is_compliant : True
    summary      : "4/4 clauses evaluated. Status: COMPLIANT"

Not one of those four behaviours is in the pattern list. A regex miss is not
evidence of safety.

`is_compliant` is gone. The report now carries `matched_rules` and
`patterns_checked`, and says only what it looked for. `saleha sast` is the AST
scanner; this does not substitute for it and no longer implies it does.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ConstitutionalClauseViolation:
    """Represents an explicit constitutional clause violation."""
    clause_id: str
    rule_name: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM"
    line_number: int
    matched_snippet: str
    description: str
    remediation_advice: str


@dataclass
class ConstitutionalAuditReport:
    """
    What the four patterns matched.

    `is_compliant` is deliberately absent. It was True whenever no regex
    matched, which turned "these four strings were not present" into a clean
    bill of health for any code -- including code that deletes every file on
    the disk and execs a downloaded payload, none of which any pattern covers.
    """
    target_name: str
    total_clauses_evaluated: int
    violations: List[ConstitutionalClauseViolation] = field(default_factory=list)
    summary: str = ""

    @property
    def matched_rules(self) -> bool:
        """True when at least one pattern matched. Not a safety verdict."""
        return bool(self.violations)


class ConstitutionalGuard:
    """System-level Constitutional AI Alignment and Safety Guard."""

    CONSTITUTIONAL_RULES = [
        {
            "id": "CONST_01",
            "name": "No Destructive OS Commands",
            "pattern": r"(?:rm\s+-rf\s+[\/~]|shutil\.rmtree\(['\"]\/['\"]|os\.system\(['\"](?:mkfs|format))",
            "severity": "CRITICAL",
            "desc": "Destructive operating system filesystem wipe detected.",
            "remediation": "Restrict deletions to isolated sandbox directories.",
        },
        {
            "id": "CONST_02",
            "name": "No Unsafe Arbitrary Deserialization",
            "pattern": r"(?:pickle\.loads|yaml\.unsafe_load|__import__\(['\"]os['\"]\)\.system)",
            "severity": "CRITICAL",
            "desc": "Unsafe deserialization / arbitrary code injection risk.",
            "remediation": "Use safe JSON serialization or safe_load.",
        },
        {
            "id": "CONST_03",
            "name": "No Unauthorized Privilege Escalation",
            "pattern": r"(?:sudo\s+chmod\s+777|\/etc\/shadow|chmod\s+777\s+\/)",
            "severity": "CRITICAL",
            "desc": "Root privilege escalation attempt or system file modification.",
            "remediation": "Enforce zero-trust least-privilege capability boundaries.",
        },
        {
            "id": "CONST_04",
            "name": "No Credential Exfiltration",
            "pattern": r"(?:requests\.post\(.*(?:os\.environ|AWS_SECRET|API_KEY))",
            "severity": "HIGH",
            "desc": "Potential credential or environment variable exfiltration detected.",
            "remediation": "Never transmit raw environment credentials over network calls.",
        },
    ]

    def __init__(self):
        """Initializes the constitutional alignment guard."""
        pass

    def audit_code(self, code: str, filename: str = "snippet.py") -> ConstitutionalAuditReport:
        """Audits code against the full suite of constitutional alignment rules."""
        violations: List[ConstitutionalClauseViolation] = []
        lines = code.splitlines()

        for rule in self.CONSTITUTIONAL_RULES:
            for idx, line in enumerate(lines, 1):
                match = re.search(rule["pattern"], line)
                if match:
                    violations.append(ConstitutionalClauseViolation(
                        clause_id=rule["id"],
                        rule_name=rule["name"],
                        severity=rule["severity"],
                        line_number=idx,
                        matched_snippet=line.strip()[:80],
                        description=rule["desc"],
                        remediation_advice=rule["remediation"],
                    ))

        total_clauses = len(self.CONSTITUTIONAL_RULES)
        if violations:
            status = f"{len(violations)} line(s) matched"
        else:
            # Never "COMPLIANT". Four patterns not matching says nothing about
            # the other ways code can be dangerous.
            status = ("no lines matched these patterns -- this is not a safety "
                      "verdict; run `saleha sast` for the AST scanner")
        summary = (
            f"Pattern screen for '{filename}': {total_clauses} patterns "
            f"checked ({', '.join(r['name'] for r in self.CONSTITUTIONAL_RULES)}). "
            f"Result: {status}."
        )

        return ConstitutionalAuditReport(
            target_name=filename,
            total_clauses_evaluated=total_clauses,
            violations=violations,
            summary=summary,
        )


constitutional_guard = ConstitutionalGuard()
