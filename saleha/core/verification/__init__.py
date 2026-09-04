"""
Saleha Core: Verification & Quality Subsystem (2026 Frontier Standard)

Provides AST syntactic & type safety, Test-Time Compute (TTC) search,
SAST security audits, formal SMT invariant proofs, and safety guard enforcement:
- QualityGuard / quality_guard (AST syntax, type annotation coverage, cyclomatic depth)
- TTCSolver / ttc_solver (Test-Time Compute multi-trajectory sampling & reranking)
- SecurityScanner / security_scanner (AST security & CWE SAST vulnerability scan)
- SafetyGuard / safety_guard (Prompt injection & destructive command interceptor)
- FormalSMTVerifier / formal_smt_verifier (Real AST Hoare logic & termination prover)
- Apex97Validator / apex_97_validator (Universal 8-domain 97%+ quality certification)
"""

from __future__ import annotations

from saleha.core.quality_guard import (
    QualityGuard,
    quality_guard,
    QualityReport,
    QualityIssue,
)

from saleha.core.ttc_solver import (
    TTCSolver,
    ttc_solver,
    TTCResult,
    Trajectory,
)
from saleha.core.security_scanner import (
    SecurityScanner,
    security_scanner,
)
from saleha.core.safety_guard import (
    SafetyGuard,
    safety_guard,
    SafetyResult,
)
from saleha.core.formal_smt_verifier import (
    FormalSMTVerifier,
    formal_smt_verifier,
    FormalProofContract,
)
from saleha.core.apex_97_validator import (
    Apex97Validator,
    apex_97_validator,
    Apex97CertificationReport,
)


__all__ = [
    "QualityGuard",
    "quality_guard",
    "QualityReport",
    "QualityIssue",
    "TTCSolver",

    "ttc_solver",
    "TTCResult",
    "Trajectory",
    "SecurityScanner",
    "security_scanner",
    "SafetyGuard",
    "safety_guard",
    "SafetyResult",
    "FormalSMTVerifier",
    "formal_smt_verifier",
    "FormalProofContract",
    "Apex97Validator",
    "apex_97_validator",
    "Apex97CertificationReport",
]
