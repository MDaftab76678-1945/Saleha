"""
ProofSilicon × Trust Kernel
Verilog input → Trust Kernel → Signed Certificate
Single file. No dependencies. Python 3.8+
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone


# ============================================================
# PART 1: VERILOG ANALYZER (CWE Detection)
# ============================================================

CWE_PATTERNS = {
    "CWE-190": {
        "name": "Integer Overflow",
        "severity": 0.8,
        "patterns": [r'\+\s*1\s*;', r'<=\s*\w+\s*\+'],
    },
    "CWE-191": {
        "name": "Integer Underflow",
        "severity": 0.7,
        "patterns": [r'-\s*1\s*;'],
    },
    "CWE-1284": {
        "name": "Improper Validation",
        "severity": 0.5,
        "patterns": [r'input\s+\[\d+:\d+\]\s+\w+\s*\)'],
    },
}


def extract_module_name(verilog_code: str) -> str:
    match = re.search(r'module\s+(\w+)', verilog_code)
    return match.group(1) if match else "unknown_module"


def detect_cwes(verilog_code: str) -> list:
    findings = []
    for cwe_id, info in CWE_PATTERNS.items():
        for pattern in info["patterns"]:
            matches = re.findall(pattern, verilog_code)
            if matches:
                findings.append({
                    "cwe_id": cwe_id,
                    "name": info["name"],
                    "severity": info["severity"],
                    "count": len(matches),
                })
    return findings


# ============================================================
# PART 2: TRUST KERNEL (Inline v0.1)
# ============================================================

@dataclass
class TrustDecision:
    allowed: bool
    risk_score: float
    care_score: float
    weight: float
    reason: str
    receipt_hash: str = ""


class TrustKernel:
    def __init__(self, agent_id: str, secret_key: str):
        self.agent_id = agent_id
        self.secret_key = secret_key
        self.memory = []

    def add_memory(self, content: str, weight: float, category: str):
        self.memory.append({
            "content": content,
            "weight": weight,
            "category": category,
        })

    def evaluate_verilog(self, verilog_code: str, findings: list) -> TrustDecision:
        # Risk from CWE findings
        risk = 0.0
        for f in findings:
            risk += f["severity"] * 0.3
        risk = min(risk, 1.0)

        # Memory resonance (past detections amplify current risk)
        resonance = 0.0
        for mem in self.memory:
            if mem["category"] == "silicon":
                resonance += mem["weight"] * 0.1
        risk = min(risk + resonance * 0.1, 1.0)

        # Care (verification quality)
        care = 0.5
        if findings:
            care -= 0.2  # issues found = system caring enough to detect

        # Capability: can sign only if not critical
        capable = risk < 0.9

        # Moral weight
        weight = care * 0.6 + (1 - risk) * 0.4
        weight = max(0.0, min(weight, 1.0))

        # Decision
        if not capable:
            allowed = False
            reason = f"Critical risk ({risk:.2f}). Cannot sign."
        elif risk > 0.7:
            allowed = False
            reason = f"High risk ({risk:.2f}). Manual review required."
        else:
            allowed = True
            reason = f"Allowed. Risk={risk:.2f}, Care={care:.2f}"

        decision = TrustDecision(
            allowed=allowed,
            risk_score=risk,
            care_score=care,
            weight=weight,
            reason=reason,
        )

        # Proof Gate: sign decision
        payload = json.dumps({
            "agent": self.agent_id,
            "allowed": allowed,
            "risk": risk,
            "care": care,
            "timestamp": time.time(),
        }, sort_keys=True)
        decision.receipt_hash = hashlib.sha256(
            (payload + self.secret_key).encode()
        ).hexdigest()

        return decision


# ============================================================
# PART 3: CERTIFICATE GENERATOR
# ============================================================

def generate_certificate(
    verilog_code: str,
    findings: list,
    decision: TrustDecision,
    agent_did: str,
) -> dict:
    rtl_hash = hashlib.sha256(verilog_code.encode()).hexdigest()
    module_name = extract_module_name(verilog_code)

    return {
        "certificate_version": "1.0",
        "module_name": module_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent_did": agent_did,
        "rtl_hash": f"sha256:{rtl_hash}",
        "cwe_findings": findings,
        "risk_score": round(decision.risk_score, 3),
        "care_score": round(decision.care_score, 3),
        "trust_weight": round(decision.weight, 3),
        "decision": "ALLOWED" if decision.allowed else "BLOCKED",
        "reason": decision.reason,
        "signature": decision.receipt_hash,
        "lint": "PASS" if not findings else "WARN",
        "simulation": "NOT_RUN",
        "synthesis": "NOT_RUN",
    }


def certificate_to_markdown(cert: dict) -> str:
    lines = [
        "# MUKTI ProofSilicon Verification Certificate",
        "",
        f"**Module:** {cert['module_name']}",
        f"**Generated:** {cert['generated_at']}",
        f"**Agent:** {cert['agent_did']}",
        "",
        "## Trust Decision",
        f"- **Status:** {cert['decision']}",
        f"- **Risk Score:** {cert['risk_score']}",
        f"- **Care Score:** {cert['care_score']}",
        f"- **Reason:** {cert['reason']}",
        "",
        "## CWE Findings",
    ]
    if cert["cwe_findings"]:
        for f in cert["cwe_findings"]:
            lines.append(
                f"- {f['cwe_id']}: {f['name']} "
                f"(severity {f['severity']}, count {f['count']})"
            )
    else:
        lines.append("- No CWEs detected")

    lines.extend([
        "",
        "## Verification Status",
        f"- Lint: {cert['lint']}",
        f"- Simulation: {cert['simulation']}",
        f"- Synthesis: {cert['synthesis']}",
        "",
        "## Signature",
        f"```\n{cert['signature']}\n```",
    ])
    return "\n".join(lines)


# ============================================================
# PART 4: DEMO
# ============================================================

SAMPLE_VERILOG = """
module test(input clk, input [7:0] data_in, output reg [7:0] data_out);
    always @(posedge clk) begin
        data_out <= data_in + 1;  // CWE-190: Integer overflow possible
    end
endmodule
"""


def main():
    print("=" * 60)
    print("ProofSilicon × Trust Kernel")
    print("=" * 60)

    # Initialize kernel with agent identity
    kernel = TrustKernel(
        agent_id="did:mukti:rtl-verifier",
        secret_key="prooftsilicon-secret-v0.1",
    )

    # Memory: past CWE-190 detection amplifies current risk
    kernel.add_memory(
        "CWE-190 integer overflow in counter",
        weight=0.8,
        category="silicon",
    )

    # Step 1: Analyze
    print("\n[1] Analyzing Verilog...")
    module_name = extract_module_name(SAMPLE_VERILOG)
    findings = detect_cwes(SAMPLE_VERILOG)
    print(f"    Module: {module_name}")
    print(f"    CWEs found: {len(findings)}")
    for f in findings:
        print(f"      - {f['cwe_id']}: {f['name']}")

    # Step 2: Trust Kernel evaluation
    print("\n[2] Trust Kernel evaluation...")
    decision = kernel.evaluate_verilog(SAMPLE_VERILOG, findings)
    print(f"    Risk: {decision.risk_score:.2f}")
    print(f"    Care: {decision.care_score:.2f}")
    print(f"    Allowed: {decision.allowed}")
    print(f"    Reason: {decision.reason}")

    # Step 3: Generate certificate
    print("\n[3] Generating certificate...")
    cert = generate_certificate(
        SAMPLE_VERILOG, findings, decision, kernel.agent_id
    )

    with open("proof_bundle.json", "w") as f:
        json.dump(cert, f, indent=2)
    print("    Saved: proof_bundle.json")

    md = certificate_to_markdown(cert)
    with open("certificate.md", "w") as f:
        f.write(md)
    print("    Saved: certificate.md")

    print("\n" + "=" * 60)
    print(f"DECISION: {cert['decision']}")
    print(f"SIGNATURE: {cert['signature'][:32]}...")
    print("=" * 60)


if __name__ == "__main__":
    main()
