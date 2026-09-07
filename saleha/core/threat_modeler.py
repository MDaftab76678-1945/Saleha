"""
Saleha Core: STRIDE threat checklist, verified against the codebase.

Walks the tree and, for each STRIDE category, looks for the mitigation that
category needs. A finding is raised only when the evidence is absent, and every
finding names the files that were actually examined.

## What this used to be

It was the "Automated STRIDE Threat Modeling Engine", claiming to scan "attack
surfaces, authentication entrypoints, and data flows". It read nothing.

`analyze_workspace(root_dir)` accepted a directory, assigned it to
`self.root_dir`, and never opened it. Six `ThreatFinding` objects were appended
unconditionally and returned. `ast` and `dependency_graph` were both imported
and never called.

Measured, before the fix:

    analyze_workspace(<this repo>)   vs   analyze_workspace(<empty dir>)

    identical findings : True
    on the empty dir   : 6 threats, 4 HIGH

It named `SmartPatcher`, `AgenticLoop` and `SelfHealingEngine` as affected
components of a directory containing no files at all. The CLI then wrote that
to `docs/threat_model.md`, where it reads as a real audit.

## What it does now

Each check looks for evidence in the source and reports what it found:

  Spoofing              is there any request-authentication code?
  Tampering             are file writes atomic (temp file + os.replace)?
  Repudiation           is there an append-only audit log?
  InfoDisclosure        is there secret masking/redaction?
  DoS                   are there timeouts and step caps?
  ElevationOfPrivilege  is execution sandboxed, and is there an approval gate?

`evidence` on each finding lists the files that satisfied the check, and
`files_scanned` says how wide the search was. A check that finds nothing on an
empty tree reports `UNKNOWN` -- not `HIGH` -- because "no code" is not the same
as "insecure code", and the previous version could not tell those apart.

This is a checklist over source text, not a data-flow analysis. It detects
whether a mitigation is present, not whether it is correct. That limit is
stated in the report rather than left for the reader to assume.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# Directories that are not this project's source. `.claude/worktrees` holds
# checkouts of the repo itself, so leaving it in reported evidence paths like
# `.claude/worktrees/agent-a4f9.../saleha/core/...` -- the same file counted
# twice under a confusing name.
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", ".venv", ".venv_train",
    "build", "dist", ".pytest_cache", "Notebook", "graphify-out", ".saleha",
    ".claude", ".agents", "site-packages", ".mypy_cache", ".ruff_cache",
    "scratch", "test_dynamic_ws",
}


@dataclass
class ThreatFinding:
    category: str           # Spoofing | Tampering | Repudiation | InfoDisclosure | DoS | ElevationOfPrivilege
    threat_description: str
    # HIGH | MEDIUM | LOW -> a real gap. MITIGATED -> evidence found.
    # UNKNOWN -> nothing to judge (e.g. an empty tree).
    impact_level: str
    affected_component: str
    mitigation_strategy: str
    # Files that satisfied this check. Empty when the mitigation was not found.
    evidence: List[str] = field(default_factory=list)

    @property
    def is_gap(self) -> bool:
        return self.impact_level in ("HIGH", "MEDIUM", "LOW")


@dataclass
class ThreatModelReport:
    project_name: str
    generated_at: str
    total_threats: int
    high_threats: int
    medium_threats: int
    low_threats: int
    findings: List[ThreatFinding] = field(default_factory=list)
    markdown_matrix: str = ""
    # How much source the verdicts are based on. Zero means every category is
    # UNKNOWN and the report says nothing about security.
    files_scanned: int = 0
    mitigated_count: int = 0
    unknown_count: int = 0


class ThreatModeler:
    """Checks the codebase for the mitigation each STRIDE category needs."""

    # (category, description, component, mitigation, severity-if-missing,
    #  regex patterns that count as evidence)
    CHECKS: Tuple[Tuple[str, str, str, str, str, Tuple[str, ...]], ...] = (
        ("Spoofing",
         "Inbound requests accepted without verifying caller identity",
         "Request handlers / API surface",
         "Verify a signature or token on remote requests (HMAC, JWT)",
         "HIGH",
         (r"hmac\.", r"compare_digest", r"\bjwt\b", r"Authorization",
          r"verify_signature")),
        ("Tampering",
         "File writes that can leave a half-written file if interrupted",
         "Patchers and report writers",
         "Write to a temp file and os.replace() it into place",
         "MEDIUM",
         (r"os\.replace\(", r"NamedTemporaryFile", r"\.tmp\.")),
        ("Repudiation",
         "Autonomous changes made with no durable record of what was done",
         "Agent loops and self-healing",
         "Append-only audit log of actions taken",
         "MEDIUM",
         (r"audit_log", r"AuditLog", r"merkle", r"\.jsonl")),
        ("InfoDisclosure",
         "Secrets reaching logs, errors or generated output unmasked",
         "Diagnostics, vault and logging",
         "Mask or redact credentials before they are written anywhere",
         "HIGH",
         (r"redact", r"SecretVault", r"mask_secret", r"secret_mask")),
        ("DoS",
         "Loops or model calls with no bound, able to run indefinitely",
         "Agent loops and executors",
         "Wall-clock timeouts and a maximum step count",
         "MEDIUM",
         (r"timeout\s*=", r"max_steps", r"max_attempts", r"max_iterations")),
        ("ElevationOfPrivilege",
         "Generated code executed without a sandbox or human approval gate",
         "Code execution paths",
         "Run untrusted code sandboxed, and gate dangerous actions on approval",
         "HIGH",
         (r"approval_gate", r"setrlimit", r"docker", r"sandbox")),
    )

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)

    def _iter_sources(self, limit: int = 4000) -> List[str]:
        """Python files under root_dir, skipping vendored and generated trees."""
        found: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name.endswith(".py"):
                    found.append(os.path.join(dirpath, name))
                    if len(found) >= limit:
                        return found
        return found

    def analyze_workspace(self, root_dir: Optional[str] = None) -> ThreatModelReport:
        """
        Check each STRIDE category against the source actually present.

        The previous version took this argument, stored it, and then returned
        six hardcoded findings without opening a single file -- an empty
        directory produced 6 threats and 4 HIGH.
        """
        if root_dir:
            self.root_dir = os.path.abspath(root_dir)

        sources = self._iter_sources()
        # One pass over the tree: each file is read once and matched against
        # every category, rather than re-walking per check.
        hits: Dict[str, List[str]] = {c[0]: [] for c in self.CHECKS}
        compiled = [
            (cat, [re.compile(p, re.IGNORECASE) for p in pats])
            for cat, _d, _c, _m, _s, pats in self.CHECKS
        ]

        for path in sources:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except OSError:
                continue
            rel = os.path.relpath(path, self.root_dir)
            for cat, patterns in compiled:
                if any(p.search(text) for p in patterns):
                    hits[cat].append(rel)

        findings: List[ThreatFinding] = []
        for cat, desc, comp, mitigation, severity, _pats in self.CHECKS:
            evidence = hits[cat]
            if not sources:
                # Nothing was read. "No code" is not "insecure code", and
                # reporting HIGH here is what made the old version useless.
                level = "UNKNOWN"
            elif evidence:
                level = "MITIGATED"
            else:
                level = severity
            findings.append(ThreatFinding(
                category=cat,
                threat_description=desc,
                impact_level=level,
                affected_component=comp,
                mitigation_strategy=mitigation,
                evidence=sorted(evidence)[:5],
            ))

        gaps = [f for f in findings if f.is_gap]
        report = ThreatModelReport(
            project_name=os.path.basename(self.root_dir),
            generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            total_threats=len(gaps),
            high_threats=sum(1 for f in gaps if f.impact_level == "HIGH"),
            medium_threats=sum(1 for f in gaps if f.impact_level == "MEDIUM"),
            low_threats=sum(1 for f in gaps if f.impact_level == "LOW"),
            findings=findings,
            files_scanned=len(sources),
            mitigated_count=sum(1 for f in findings if f.impact_level == "MITIGATED"),
            unknown_count=sum(1 for f in findings if f.impact_level == "UNKNOWN"),
        )
        report.markdown_matrix = self._render(report)
        return report

    def _render(self, report: ThreatModelReport) -> str:
        lines = [
            f"# STRIDE checklist: {report.project_name}",
            "",
            f"**Generated:** {report.generated_at}  ",
            f"**Python files scanned:** {report.files_scanned}  ",
            f"**Gaps:** {report.total_threats} "
            f"(HIGH {report.high_threats}, MEDIUM {report.medium_threats}, "
            f"LOW {report.low_threats})  ",
            f"**Mitigation found:** {report.mitigated_count} of "
            f"{len(report.findings)} categories",
            "",
        ]
        if report.files_scanned == 0:
            lines += [
                "> No Python source was found under this path, so every category",
                "> is UNKNOWN. This report says nothing about security.",
                "",
            ]
        lines += [
            "| STRIDE | Status | Component | Threat | Expected mitigation | Evidence |",
            "|---|---|---|---|---|---|",
        ]
        for f in report.findings:
            evidence = ", ".join(f"`{e}`" for e in f.evidence) if f.evidence else "-"
            lines.append(
                f"| **{f.category}** | {f.impact_level} | {f.affected_component} "
                f"| {f.threat_description} | {f.mitigation_strategy} | {evidence} |"
            )
        lines += [
            "",
            "_This is a checklist over source text: it detects whether a",
            "mitigation is **present**, not whether it is **correct**. A",
            "MITIGATED row means a matching pattern was found in the listed",
            "files, not that the control was reviewed. It is not a penetration",
            "test and not a substitute for `saleha sast`._",
        ]
        return "\n".join(lines) + "\n"

    def save_report(self, report: ThreatModelReport, output_path: str = "docs/threat_model.md") -> str:
        """Saves the markdown report to disk (temp file + atomic replace)."""
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        tmp_p = f"{output_path}.tmp.{os.getpid()}"
        with open(tmp_p, "w", encoding="utf-8") as f:
            f.write(report.markdown_matrix)
        os.replace(tmp_p, output_path)
        return os.path.abspath(output_path)


# Global instance
threat_modeler = ThreatModeler()
