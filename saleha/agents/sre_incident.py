"""
Saleha Agents: SRE Incident Responder & Root Cause Analysis (RCA) Agent

Reads the logs first, by program: the error and warning counts, the
exception types, the stack frames (file, line, function), the components
named in the log lines, the first error's line. Severity comes from those
measured signals by a stated rule, and the affected components are the
ones the logs name -- the agent used to report the same three components
and three mitigations for every incident.

The model then writes the root-cause analysis from that evidence; it must
name at least one error actually in the logs and give at least two
mitigation steps (parsed from its answer), or it is asked once more.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent

_EXC = re.compile(r"\b([A-Z][A-Za-z0-9_.]*(?:Error|Exception|Timeout|Refused|Failure|Fault))\b")
_PY_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\w+)')
_JAVA_FRAME = re.compile(r"\bat ([\w.$]+)\(([\w.]+):(\d+)\)")
_LEVEL = re.compile(r"\b(FATAL|CRITICAL|ERROR|WARN(?:ING)?|INFO|DEBUG)\b")
_COMPONENT = re.compile(r"\[([A-Za-z][\w.-]{2,40})\]|\b(?:service|component|logger|svc)[=:]\s*\"?([\w.-]+)")
_LEVELS = {"FATAL", "CRITICAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"}   # [ERROR] is no component
_SEV1 = ("fatal","oom", "out of memory", "panic", "segmentation fault", "data loss", "database down", "outage")


@dataclass
class IncidentRCA:
    severity: str  # "SEV-1", "SEV-2", "SEV-3"
    root_cause_summary: str
    affected_components: List[str]
    mitigation_steps: List[str]
    slo_error_budget_impact: str
    runbook_md: str
    model_used: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)   # what was read from the logs
    severity_reason: str = ""
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None
    from_template: bool = False


def read_logs(logs: str) -> Dict[str, Any]:
    lines = [ln for ln in logs.splitlines() if ln.strip()]
    levels = Counter(m.group(1).replace("WARNING", "WARN") for ln in lines for m in [_LEVEL.search(ln)] if m)
    frames = [f"{f}:{n} in {fn}" for f, n, fn in _PY_FRAME.findall(logs)]
    frames += [f"{fl}:{n} in {meth}" for meth, fl, n in _JAVA_FRAME.findall(logs)]
    comps = Counter(c for a, b in _COMPONENT.findall(logs) for c in [a or b] if c.upper() not in _LEVELS)
    comps.update(f.split(":")[0].replace("\\", "/").rsplit("/", 1)[-1] for f in frames)
    first_error = next((ln.strip() for ln in lines if re.search(r"(?i)\b(error|exception|fatal|critical)\b", ln)), "")
    return {"lines": len(lines), "levels": dict(levels), "exceptions": [e for e, _n in Counter(_EXC.findall(logs)).most_common(8)],
            "frames": frames[:12], "components": [c for c, _n in comps.most_common(8)], "first_error": first_error[:300]}


def severity(logs: str, ev: Dict[str, Any]) -> Tuple[str, str]:
    low = logs.lower()
    hit = next((w for w in _SEV1 if w in low), "")
    errors = ev["levels"].get("ERROR", 0) + ev["levels"].get("FATAL", 0) + ev["levels"].get("CRITICAL", 0)
    if hit:
        return "SEV-1", f"the logs say '{hit}'"
    if ev["lines"] >= 20 and errors / ev["lines"] >= 0.5:
        # Only over a real stretch of log: a four-line excerpt with two errors
        # in it is no outage (measured: the traceback lines alone made it 50%).
        return "SEV-1", f"{errors} of {ev['lines']} log lines are errors"
    if errors or ev["exceptions"]:
        return "SEV-2", f"{errors} error line(s), exceptions: {', '.join(ev['exceptions'][:3]) or 'none named'}"
    if ev["levels"].get("WARN"):
        return "SEV-3", f"{ev['levels']['WARN']} warning(s) and no errors"
    return "SEV-3", "no error or warning lines found"


def steps_from(text: str) -> List[str]:
    block = re.search(r"(?is)mitigation[^\n]*\n(.*?)(?:\n\s*(?:#+|\d+\.\s*\**post|\*\*post)|\Z)", text)
    source = block.group(1) if block else text
    return [s.strip(" *") for s in re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+(.{8,200})$", source)][:8]


class SREIncidentAgent(BaseAgent):
    """Lead SRE Incident Responder & Autonomous Site Reliability Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="SREIncident", model=model)

    def diagnose_incident(self, error_logs: str, context: Optional[str] = None) -> IncidentRCA:
        """Evidence read from the logs, then an RCA grounded in it."""
        ev = read_logs(error_logs)
        sev, why = severity(error_logs, ev)
        evidence = (f"Measured from the logs: {ev['lines']} lines, levels {ev['levels']}, exceptions "
                    f"{ev['exceptions'] or 'none'}, frames {ev['frames'][:5] or 'none'}, components "
                    f"{ev['components'] or 'none named'}, first error: {ev['first_error'] or 'none'}")
        prompt = (f"You are a Lead Site Reliability Engineer. Diagnose this incident ({sev}: {why}).\n"
                  + (f"Context: {context}\n" if context else "")
                  + f"{evidence}\n\nLogs:\n```\n{error_logs[-6000:]}\n```\n"
                  "Write: '## Root cause' (name the actual error from the logs and where it happens), "
                  "'## Mitigation' (numbered steps, most urgent first), '## Post-mortem actions' (numbered). "
                  "Use only what the logs show; say what is unknown.")

        def build(content: str) -> Tuple[str, List[ac.Check]]:
            named = [e for e in ev["exceptions"] + ([ev["first_error"][:40]] if ev["first_error"] else [])
                     if e and e.lower() in content.lower()]
            steps = steps_from(content)
            checks = [ac.Check("steps parsed", ac.PASS if len(steps) >= 2 else ac.FAIL, f"{len(steps)} mitigation step(s)")]
            if ev["exceptions"] or ev["first_error"]:
                checks.insert(0, ac.Check("names an error from the logs", ac.PASS if named else ac.FAIL,
                                          f"named: {named[:3]}" if named else "names no error that is in the logs"))
            return content, checks

        content, checks, resp, _rounds = ac.produce(self, prompt, build)
        from_template = content is None
        if from_template:
            runbook = (f"# Incident Runbook (template -- no model reviewed these logs, {sev})\n\n"
                       f"## What the logs show\n{evidence}\n\n## Severity\n{sev}: {why}\n\n"
                       "## Generic first responses (not a diagnosis)\n1. Check the first error line above and the "
                       "frames under it.\n2. Roll back the most recent deploy to the components named, if any.\n"
                       "3. Watch error rate and latency while mitigating.\n")
            steps: List[str] = []
        else:
            runbook, steps = content, steps_from(content)
        return IncidentRCA(
            severity=sev,
            root_cause_summary=(f"{sev} ({why}). No root-cause investigation ran: no model answered."
                                if from_template else f"{sev} ({why}); see the runbook for the RCA."),
            affected_components=ev["components"], mitigation_steps=steps,
            slo_error_budget_impact="Not measured on this incident.", runbook_md=runbook,
            model_used=resp.model_used, evidence=ev, severity_reason=why, checks=ac.as_dicts(checks),
            verified=None if from_template else ac.verdict(checks), from_template=from_template)
