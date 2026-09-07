"""
Saleha Core: Gödel Machine Self-Proving Utility Engine (GodelUtilityEngine)

Implements formal utility theory and mathematical proof bounds for self-improving agents:
1. Universal Utility Metric: U(s) = 0.35·align + 0.30·pass_rate + 0.25·safety + 0.10·efficiency.
2. Positive Delta Proof: Only authorizes self-modifications with proven ΔU > 0.
3. Protects against Goodhart's Law and adversarial reward hacking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class SystemStateUtility:
    """
    Represents the multi-dimensional utility metrics of a state.

    `measured` records which fields came from a real signal. A utility proof
    over invented numbers proves nothing, so anything reporting a decision
    built from this state must say which inputs were actually measured --
    see `measure_current_state()`.
    """
    alignment_score: float  # 0.0 to 1.0
    task_pass_rate: float   # 0.0 to 1.0
    safety_score: float     # 0.0 to 1.0
    efficiency_score: float # 0.0 to 1.0
    measured: Dict[str, bool] = field(default_factory=dict)

    _FIELDS = ("alignment_score", "task_pass_rate",
               "safety_score", "efficiency_score")

    @property
    def unmeasured_fields(self) -> List[str]:
        """
        Fields known to be unmeasured.

        An empty `measured` dict means the caller supplied the numbers
        directly and vouches for them -- that is the long-standing API and
        stays trusted. Only a state that was *built by measurement* records
        provenance, and only then can a field be reported as unmeasured.
        """
        if not self.measured:
            return []
        return [k for k in self._FIELDS if not self.measured.get(k)]

    @property
    def fully_measured(self) -> bool:
        return not self.unmeasured_fields

    @property
    def total_utility(self) -> float:
        """Calculates global weighted utility U(s)."""
        u = (
            0.35 * self.alignment_score
            + 0.30 * self.task_pass_rate
            + 0.25 * self.safety_score
            + 0.10 * self.efficiency_score
        )
        return round(u, 4)


@dataclass
class GodelProofDecision:
    """Formal mathematical proof decision for an optimization or self-modification."""
    is_authorized: bool
    current_utility: float
    candidate_utility: float
    delta_utility: float
    safety_preserved: bool
    proof_summary: str


class GodelUtilityEngine:
    """Formal self-improving utility verifier."""

    def __init__(self):
        """Initializes the Gödel utility engine."""
        pass

    def evaluate_modification(
        self,
        current_state: SystemStateUtility,
        candidate_state: SystemStateUtility,
        action_name: str = "self_healing_patch",
    ) -> GodelProofDecision:
        """Mathematically evaluates whether candidate state strictly improves system utility."""
        u_curr = current_state.total_utility
        u_cand = candidate_state.total_utility
        delta_u = round(u_cand - u_curr, 4)

        # Invariant: Safety score must never degrade
        safety_ok = candidate_state.safety_score >= current_state.safety_score
        is_proven = (delta_u > 0.0) and safety_ok

        # A proof is only as good as its inputs. When either state carries
        # unmeasured fields, the arithmetic still holds but it says nothing
        # about this system -- so it is not reported as an authorisation.
        unmeasured = sorted(set(current_state.unmeasured_fields)
                            | set(candidate_state.unmeasured_fields))
        if unmeasured:
            is_proven = False
            verdict = ("INCONCLUSIVE (unmeasured inputs: "
                       + ", ".join(unmeasured) + ")")
        elif is_proven:
            verdict = "AUTHORIZED"
        else:
            verdict = "PROHIBITED (Negative Utility or Safety Breach)"

        summary = (
            f"Gödel Utility Proof for '{action_name}': U_curr={u_curr} -> U_cand={u_cand} "
            f"(ΔU={delta_u:+}, SafetyOK={safety_ok}) -> {verdict}."
        )

        return GodelProofDecision(
            is_authorized=is_proven,
            current_utility=u_curr,
            candidate_utility=u_cand,
            delta_utility=delta_u,
            safety_preserved=safety_ok,
            proof_summary=summary,
        )


def measure_current_state(repo_root: Optional[str] = None,
                          recent_tasks: int = 50) -> SystemStateUtility:
    """
    Build a SystemStateUtility from real signals instead of invented numbers.

    Why this exists
    ---------------
    `saleha godel-utility` used to construct its two states from literals:

        s_curr = SystemStateUtility(0.92, 0.88, 1.0, 0.75)
        s_cand = SystemStateUtility(0.96, 0.94, 1.0, 0.82)

    and print "AUTHORIZED (SafetyOK=True)" about a refactoring that did not
    exist. The engine's maths is sound -- it correctly rejects a worse
    candidate -- but a proof over fabricated inputs proves nothing about this
    system. Every field below is derived from something real, and any field
    that cannot be measured is reported as unmeasured rather than guessed.

    Signals used:
      task_pass_rate   -- success ratio of the last `recent_tasks` runs from
                          TaskHistory. Unmeasured when there is no history.
      safety_score     -- ConstitutionalGuard violations across saleha/core,
                          as 1 - (files_with_violations / files_scanned).
      efficiency_score -- mean attempts per successful task, mapped so that
                          one attempt is 1.0 and three or more approaches 0.
      alignment_score  -- NOT measurable from inside the system. It stays 0.0
                          and is flagged unmeasured; a system scoring its own
                          alignment is the trust failure this repo keeps
                          finding, so it is deliberately not faked here.
    """
    import os

    measured: Dict[str, bool] = {
        "alignment_score": False,     # see docstring -- never self-scored
        "task_pass_rate": False,
        "safety_score": False,
        "efficiency_score": False,
    }
    pass_rate = 0.0
    efficiency = 0.0
    safety = 0.0

    # -- task pass rate and efficiency, from real run history ---------------
    try:
        from saleha.core.task_history import TaskHistory

        records = TaskHistory().all()[-recent_tasks:]
        if records:
            successes = [r for r in records if r.success]
            pass_rate = round(len(successes) / len(records), 4)
            measured["task_pass_rate"] = True

            attempts = [getattr(r, "attempts", 1) or 1 for r in successes]
            if attempts:
                mean_attempts = sum(attempts) / len(attempts)
                # 1 attempt -> 1.0, 3+ attempts -> 0.0, linear between.
                efficiency = round(
                    max(0.0, min(1.0, (3.0 - mean_attempts) / 2.0)), 4)
                measured["efficiency_score"] = True
    except Exception:
        # A missing or unreadable history is "unmeasured", not "zero risk".
        pass

    # -- safety, from the constitutional guard over real source -------------
    try:
        from saleha.core.constitutional_guard import constitutional_guard

        root = repo_root or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")
        scanned = 0
        offending = 0
        if os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(root, name)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        report = constitutional_guard.audit_code(fh.read(),
                                                                 filename=name)
                except Exception:
                    continue
                scanned += 1
                if report.matched_rules:
                    offending += 1
        if scanned:
            # The fraction of scanned files matching none of the guard's four
            # patterns. Named honestly: a regex miss is not evidence of safety,
            # so this is a pattern-clean rate, not a safety measurement.
            safety = round(1.0 - (offending / scanned), 4)
            measured["safety_score"] = True
    except Exception:
        pass

    return SystemStateUtility(
        alignment_score=0.0,
        task_pass_rate=pass_rate,
        safety_score=safety,
        efficiency_score=efficiency,
        measured=measured,
    )


godel_utility_engine = GodelUtilityEngine()


if __name__ == "__main__":
    _gue = GodelUtilityEngine()
    _s1 = SystemStateUtility(0.9, 0.8, 1.0, 0.7)
    _s2 = SystemStateUtility(0.95, 0.9, 1.0, 0.8)
    _dec = _gue.evaluate_modification(_s1, _s2)
