"""
Trust Kernel v0.1
=================
Ek minimal, stateful, cryptographic trust layer for AI agents.
Saleha (care) aur ProofSilicon (verification) dono ko jodta hai.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MemoryEvent:
    """Ek past event with weight. Yeh stateful memory hai."""
    content: str
    weight: float          # 0.0 to 1.0 (higher = more important)
    category: str          # "medical", "silicon", "emotional", "security"
    timestamp: float = field(default_factory=time.time)


@dataclass
class TrustDecision:
    """Trust Kernel ka output. Har decision signed hota hai."""
    allowed: bool
    risk_score: float      # 0.0 to 1.0
    care_score: float      # 0.0 to 1.0
    weight: float          # final moral weight
    reason: str
    memory_resonance: float
    receipt_hash: str = ""


class TrustKernel:
    """
    The kernel. Stateless function, stateful memory.
    """

    def __init__(self, agent_id: str, secret_key: str):
        self.agent_id = agent_id
        self.secret_key = secret_key
        self.memory: list[MemoryEvent] = []

    def add_memory(self, content: str, weight: float, category: str):
        """Past event store karo. Yeh future decisions ko affect karega."""
        self.memory.append(MemoryEvent(content=content, weight=weight, category=category))

    def _compute_resonance(self, input_text: str, category: str) -> float:
        """
        Memory Resonance: past events ka current input par kitna pull hai.
        Simple keyword overlap. Production mein embedding hogi.
        """
        if not self.memory:
            return 0.0

        input_words = set(input_text.lower().split())
        total_weight = 0.0
        match_count = 0

        for event in self.memory:
            if event.category != category:
                continue
            event_words = set(event.content.lower().split())
            overlap = input_words & event_words
            if overlap:
                total_weight += event.weight * (len(overlap) / max(len(event_words), 1))
                match_count += 1

        return min(total_weight, 1.0) if match_count > 0 else 0.0

    def _compute_risk(self, input_text: str, resonance: float) -> float:
        """Risk = severity × probability × irreversibility (simplified)."""
        risk_keywords = {
            "medical": ["suicide", "chest pain", "overdose", "emergency", "bleeding"],
            "silicon": ["overflow", "race condition", "cwe", "vulnerability", "exploit"],
            "security": ["hack", "leak", "inject", "exfiltrate"],
        }

        score = 0.0
        text = input_text.lower()
        for category, keywords in risk_keywords.items():
            for kw in keywords:
                if kw in text:
                    score += 0.3

        # Memory resonance amplifies risk
        score += resonance * 0.2
        return min(score, 1.0)

    def _compute_care(self, input_text: str) -> float:
        """Care = empathy + truth + consent (simplified)."""
        care_keywords = ["please", "help", "thank", "worried", "concerned"]
        score = 0.5  # baseline care
        text = input_text.lower()
        for kw in care_keywords:
            if kw in text:
                score += 0.1
        return min(score, 1.0)

    def _check_capability(self, action: str) -> bool:
        """
        Capability Gate: kya karne ki permission hai?
        Saleha: diagnosis nahi, escalation yes.
        ProofSilicon: block nahi, flag yes.
        """
        forbidden = ["diagnose", "prescribe", "delete", "execute_shell"]
        return action.lower() not in forbidden

    def _sign(self, decision: TrustDecision) -> str:
        """
        Proof Gate: decision ka cryptographic hash.
        Production mein Ed25519 hoga. Abhi deterministic hash.
        """
        payload = json.dumps({
            "agent": self.agent_id,
            "allowed": decision.allowed,
            "risk": decision.risk_score,
            "care": decision.care_score,
            "weight": decision.weight,
            "reason": decision.reason,
            "timestamp": time.time(),
        }, sort_keys=True)
        return hashlib.sha256((payload + self.secret_key).encode()).hexdigest()

    def evaluate(self, input_text: str, category: str, action: str) -> TrustDecision:
        """
        The ONE function. Har AI action yahan se guzarta hai.
        """
        # Gate 2: Memory Resonance
        resonance = self._compute_resonance(input_text, category)

        # Gate 3: Risk & Care
        risk = self._compute_risk(input_text, resonance)
        care = self._compute_care(input_text)

        # Gate 4: Capability
        capable = self._check_capability(action)

        # Final Weight: (Care × Consent) - Risk
        # Agar risk high hai, weight negative
        weight = (care * 0.6 + (1 - risk) * 0.4) - (risk * 0.5)
        weight = max(0.0, min(weight, 1.0))

        # Decision logic
        if not capable:
            allowed = False
            reason = f"Capability denied: '{action}' forbidden"
        elif risk > 0.7:
            allowed = False
            reason = f"High risk ({risk:.2f}). Escalate to human."
        elif weight < 0.4:
            allowed = False
            reason = f"Low moral weight ({weight:.2f}). Regenerate."
        else:
            allowed = True
            reason = f"Allowed. Risk={risk:.2f}, Care={care:.2f}, Resonance={resonance:.2f}"

        decision = TrustDecision(
            allowed=allowed,
            risk_score=risk,
            care_score=care,
            weight=weight,
            reason=reason,
            memory_resonance=resonance,
        )

        # Gate 5: Proof
        decision.receipt_hash = self._sign(decision)
        return decision


# ============================================================
# EXAMPLE 1: SALEHA (Medical Care)
# ============================================================
def demo_saleha():
    print("=" * 60)
    print("SALEHA DEMO: Medical Care Trust Kernel")
    print("=" * 60)

    kernel = TrustKernel(agent_id="did:mukti:saleha", secret_key="saleha-secret")

    # Past memory: user ne kal high-risk baat ki thi
    kernel.add_memory("severe chest pain breathing difficulty", weight=0.9, category="medical")

    # Aaj ka input
    query = "mujhe aaj bhi seene mein halka dard hai"
    decision = kernel.evaluate(query, category="medical", action="advise")

    print(f"\nInput: {query}")
    print(f"Memory Resonance: {decision.memory_resonance:.2f}")
    print(f"Risk: {decision.risk_score:.2f}")
    print(f"Care: {decision.care_score:.2f}")
    print(f"Allowed: {decision.allowed}")
    print(f"Reason: {decision.reason}")
    print(f"Receipt: {decision.receipt_hash[:16]}...")


# ============================================================
# EXAMPLE 2: PROOFSILICON (Verification)
# ============================================================
def demo_proofsilicon():
    print("\n" + "=" * 60)
    print("PROOFSILICON DEMO: Verification Trust Kernel")
    print("=" * 60)

    kernel = TrustKernel(agent_id="did:mukti:rtl-verifier", secret_key="silicon-secret")

    # Past memory: pehle CWE-190 detect hua tha
    kernel.add_memory("integer overflow in counter CWE-190", weight=0.8, category="silicon")

    # Aaj ka code snippet
    code = "assign counter = counter + 1; // possible overflow vulnerability"
    decision = kernel.evaluate(code, category="silicon", action="flag")

    print(f"\nInput: {code}")
    print(f"Memory Resonance: {decision.memory_resonance:.2f}")
    print(f"Risk: {decision.risk_score:.2f}")
    print(f"Care: {decision.care_score:.2f}")
    print(f"Allowed: {decision.allowed}")
    print(f"Reason: {decision.reason}")
    print(f"Receipt: {decision.receipt_hash[:16]}...")


if __name__ == "__main__":
    demo_saleha()
    demo_proofsilicon()
