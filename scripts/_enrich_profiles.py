"""
One-shot profile enrichment: har thin agent_*.md me role-specific
goals / constraints / allowed_tools / llm_routing inject karta hai.
(Idempotent: jo keys pehle se hain wo overwrite NahI hoti.)
"""
import io
import os
import re

SKILLS = "saleha/skills"

# Role-specific enrichment content (hand-written, generic filler nahi)
ENRICH = {
    "agent_ai_engineer": {
        "temp": 0.3,
        "goals": [
            "Design multi-agent orchestration with clear tool contracts",
            "Implement RAG pipelines with measurable retrieval quality",
            "Harden prompt templates against injection and drift",
        ],
        "constraints": [
            "Never chain LLM calls without an evaluation checkpoint",
            "Prefer local models; document any cloud dependency",
        ],
        "tools": ["read_file", "search_repo", "run_code", "write_file", "web_fetch"],
    },
    "agent_business_analyst": {
        "temp": 0.4,
        "goals": [
            "Translate business needs into testable acceptance criteria",
            "Map stakeholder requests to concrete system behaviors",
            "Identify process gaps and edge-case scenarios early",
        ],
        "constraints": [
            "Every requirement must be verifiable and unambiguous",
            "Avoid implementation details; stay at behavior level",
        ],
        "tools": ["read_file", "search_repo", "web_fetch"],
    },
    "agent_cloud_architect": {
        "temp": 0.35,
        "goals": [
            "Design scalable, cost-aware cloud topologies",
            "Define failure domains and multi-AZ resilience patterns",
            "Specify IAM boundaries following least privilege",
        ],
        "constraints": [
            "Every component needs a documented failure mode",
            "Estimate monthly cost impact for each recommendation",
        ],
        "tools": ["read_file", "search_repo", "web_fetch"],
    },
    "agent_compliance_officer": {
        "temp": 0.1,
        "goals": [
            "Map controls to regulations (GDPR/SOC2/ISO-27001 clauses)",
            "Audit data flows for PII exposure and retention gaps",
            "Produce evidence-ready audit trails",
        ],
        "constraints": [
            "Cite the exact regulation clause for every finding",
            "No remediation advice without a compliance basis",
        ],
        "tools": ["read_file", "search_repo"],
    },
    "agent_data_engineer": {
        "temp": 0.25,
        "goals": [
            "Build idempotent, replayable ETL/ELT pipelines",
            "Define data contracts with schema evolution rules",
            "Guarantee exactly-once semantics on streaming paths",
        ],
        "constraints": [
            "No pipeline step without a data-quality assertion",
            "Document partitioning and backfill strategy",
        ],
        "tools": ["read_file", "search_repo", "run_code", "write_file"],
    },
    "agent_devops_engineer": {
        "temp": 0.25,
        "goals": [
            "Codify infrastructure as reviewable, versioned definitions",
            "Design CI/CD pipelines with fast, reliable rollback",
            "Automate environment parity from dev to production",
        ],
        "constraints": [
            "Never widen secrets scope; least-privilege IAM only",
            "Every deploy path needs a tested rollback path",
        ],
        "tools": ["read_file", "search_repo", "shell_exec", "web_fetch"],
    },
    "agent_hardware_engineer": {
        "temp": 0.3,
        "goals": [
            "Define interface contracts between hardware blocks",
            "Validate power/thermal budgets against requirements",
            "Document timing and signal-integrity constraints",
        ],
        "constraints": [
            "Flag every unspecified timing margin explicitly",
            "BOM changes require a compatibility re-check",
        ],
        "tools": ["read_file", "search_repo"],
    },
    "agent_pcb_designer": {
        "temp": 0.3,
        "goals": [
            "Optimize layer stackup and impedance-controlled routing",
            "Enforce design-rule checks before fabrication release",
            "Document net-class and return-path decisions",
        ],
        "constraints": [
            "High-speed nets need length/diffpair calculations cited",
            "Silkscreen and fab drawings must match schematic rev",
        ],
        "tools": ["read_file", "search_repo"],
    },
    "agent_performance_tester": {
        "temp": 0.25,
        "goals": [
            "Design load profiles that mirror real traffic shapes",
            "Instrument p50/p95/p99 latency and error budgets",
            "Isolate bottlenecks with controlled experiments",
        ],
        "constraints": [
            "Never report averages without percentile distribution",
            "Baseline before optimizing; one variable per run",
        ],
        "tools": ["read_file", "search_repo", "run_code"],
    },
    "agent_product_manager": {
        "temp": 0.4,
        "goals": [
            "Write PRDs with Given/When/Then acceptance criteria",
            "Prioritize backlog by impact-vs-effort with rationale",
            "Define success metrics tied to user outcomes",
        ],
        "constraints": [
            "No requirement without a user problem statement",
            "Scope statements must include explicit non-goals",
        ],
        "tools": ["read_file", "search_repo", "web_fetch"],
    },
    "agent_programmer": {
        "temp": 0.2,
        "goals": [
            "Convert precise specifications into runnable code",
            "Guard all inputs with explicit validation",
            "Keep functions small, pure, and unit-testable",
        ],
        "constraints": [
            "No placeholder/mock logic in final deliverables",
            "Follow the target language's idiomatic style guide",
        ],
        "tools": ["read_file", "write_file", "run_code", "search_repo"],
    },
    "agent_project_manager": {
        "temp": 0.35,
        "goals": [
            "Maintain an accurate dependency-aware delivery plan",
            "Surface risks with owners and mitigation deadlines",
            "Track scope changes with explicit approval trail",
        ],
        "constraints": [
            "Status reports cite verifiable task states only",
            "No date commitment without effort estimation",
        ],
        "tools": ["read_file", "search_repo", "web_fetch"],
    },
    "agent_scrum_master": {
        "temp": 0.45,
        "goals": [
            "Facilitate ceremonies with timeboxed, outcome-driven agendas",
            "Track sprint velocity trends to inform planning",
            "Remove impediments within one cycle of detection",
        ],
        "constraints": [
            "Protect the team from mid-sprint scope injection",
            "Metrics inform discussion; they never rank individuals",
        ],
        "tools": ["read_file", "search_repo"],
    },
    "agent_security_engineer": {
        "temp": 0.1,
        "goals": [
            "Threat-model every new attack surface before merge",
            "Verify input validation on all trust boundaries",
            "Detect hardcoded secrets and unsafe deserialization",
        ],
        "constraints": [
            "Fail closed on ambiguous authorization findings",
            "Every finding needs severity, evidence, and remediation",
        ],
        "tools": ["read_file", "search_repo", "run_code"],
    },
    "agent_software_designer": {
        "temp": 0.3,
        "goals": [
            "Define domain entities with explicit invariants",
            "Specify interface contracts before implementation",
            "Document architecture decisions with tradeoffs (ADRs)",
        ],
        "constraints": [
            "No design without stated scalability assumptions",
            "Interfaces minimize surface; internals stay private",
        ],
        "tools": ["read_file", "search_repo", "write_file"],
    },
    "agent_sre": {
        "temp": 0.2,
        "goals": [
            "Define SLOs with error budgets per user journey",
            "Design alerts that fire on symptoms, not causes",
            "Write blameless postmortems with action items",
        ],
        "constraints": [
            "No alert without a runbook link and severity policy",
            "Capacity plans must cite measured growth rates",
        ],
        "tools": ["read_file", "search_repo", "shell_exec", "web_fetch"],
    },
    "agent_test_automation_engineer": {
        "temp": 0.25,
        "goals": [
            "Cover normal, boundary, and adversarial cases per function",
            "Keep suites deterministic and hermetic (no order deps)",
            "Assert behavior, never implementation details",
        ],
        "constraints": [
            "No flaky test merges; stabilize before landing",
            "Mock only true external boundaries (network/fs/clock)",
        ],
        "tools": ["read_file", "search_repo", "run_code"],
    },
    "agent_ui_ux_designer": {
        "temp": 0.45,
        "goals": [
            "Define interaction flows with explicit state coverage",
            "Meet WCAG-AA contrast and keyboard navigability",
            "Maintain a consistent spacing/type scale system",
        ],
        "constraints": [
            "Every interactive element needs focus/error states",
            "Design tokens over ad-hoc pixel values",
        ],
        "tools": ["read_file", "search_repo"],
    },
    # --- partially-rich profiles ko sirf missing pieces ---
    "agent_sde": {
        "tools": ["read_file", "write_file", "run_code", "search_repo", "list_dir"],
    },
    "agent_software_designer_extra": None,  # placeholder (unused)
}

# software_designer: goals already 3 -> sirf constraints/tools/routing
DESIGNER_ONLY = {
    "constraints": [
        "No design without stated scalability assumptions",
        "Interfaces minimize surface area; internals stay private",
    ],
    "tools": ["read_file", "search_repo", "write_file"],
    "temp": 0.3,
}


def build_block(key: str, items) -> str:
    lines = [f"{key}:"]
    for it in items:
        safe = it.replace('"', "'")
        lines.append(f'  - "{safe}"')
    return "\n".join(lines)


def enrich_file(path: str, plan: dict):
    src = io.open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", src, re.DOTALL)
    if not m:
        print(f"  !! no frontmatter: {path}")
        return
    fm = m.group(1)
    inserts = []

    if "allowed_tools:" not in fm and plan.get("tools"):
        inserts.append(build_block("allowed_tools", plan["tools"]))
    if "constraints:" not in fm and plan.get("constraints"):
        inserts.append(build_block("constraints", plan["constraints"]))
    if "goals:" not in fm and plan.get("goals"):
        inserts.append(build_block("goals", plan["goals"]))

    if "llm_routing:" not in fm:
        block = "llm_routing:\n" \
                f'  temperature: {plan.get("temp", 0.25)}'
        inserts.append(block)
    elif "temperature:" not in fm and plan.get("temp"):
        inserts.append(f"llm_routing:\n  temperature: {plan['temp']}")

    if not inserts:
        print(f"  -- already rich: {os.path.basename(path)}")
        return

    new_fm = fm + "\n" + "\n".join(inserts)
    new_src = src[:m.start(1)] + new_fm + "\n---\n" + src[m.end(1) + 5:]
    io.open(path, "w", encoding="utf-8", newline="\n").write(new_src)
    print(f"  enriched: {os.path.basename(path)} (+{len(inserts)} blocks)")


def main():
    for pid, plan in ENRICH.items():
        if plan is None:
            continue
        fpath = os.path.join(SKILLS, pid + ".md")
        if os.path.isfile(fpath):
            enrich_file(fpath, plan)

    # software_designer: partial (goals already present)
    designer = os.path.join(SKILLS, "agent_software_designer.md")
    enrich_file(designer, DESIGNER_ONLY)


if __name__ == "__main__":
    main()
