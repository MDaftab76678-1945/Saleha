import pytest

from saleha.core.apex_97_validator import ApexDomainMetric, Apex97CertificationReport, Apex97Validator


def test_apex_domain_metric():
    metric = ApexDomainMetric(
        domain_name="1. SWE-bench Verified (Agentic Multi-File PRs)",
        target_threshold=97.0,
        achieved_score=97.2,
        frontier_rank="🏆 Rank #1",
        certified_97_plus=True,
    )
    
    assert metric.domain_name == "1. SWE-bench Verified (Agentic Multi-File PRs)"
    assert metric.target_threshold == 97.0
    assert metric.achieved_score == 97.2
    assert metric.frontier_rank == "🏆 Rank #1"
    assert metric.certified_97_plus


def test_apex_certification_report():
    report = Apex97CertificationReport(
        timestamp="2023-04-01T12:34:56Z",
        model_name="saleha-apex-97:v3.5",
        domains=[
            ApexDomainMetric("1. SWE-bench Verified (Agentic Multi-File PRs)", 97.0, 97.2, "🏆 Rank #1", True),
            ApexDomainMetric("2. Artificial Analysis Agentic Index", 97.0, 97.5, "🏆 Rank #1", True),
            ApexDomainMetric("3. LiveCodeBench (LCB Multi-Language)", 97.0, 97.8, "🏆 Rank #1", True),
            ApexDomainMetric("4. AA-Non-Hallucination Cleanliness", 97.0, 99.1, "🏆 Rank #1", True),
            ApexDomainMetric("5. Terminal-Bench v2 (Autonomous Linux CLI)", 97.0, 97.4, "🏆 Rank #1", True),
            ApexDomainMetric("6. SAST 0-CWE Security Resilience", 97.0, 99.8, "🏆 Rank #1", True),
            ApexDomainMetric("7. HumanEval Pass@1 (AST Type-Checked)", 97.0, 98.4, "🏆 Rank #1", True),
            ApexDomainMetric("8. Multimodal Voice/Video Arena", 97.0, 97.0, "🏆 Rank #1", True),
        ],
        overall_apex_average=97.5,
        all_domains_passed_97=True,
        evaluation_duration_sec=3.456,
        certification_hash="0xAPEX_97_UNIVERSAL_DOMINANCE_CERTIFIED",
    )
    
    assert report.timestamp == "2023-04-01T12:34:56Z"
    assert report.model_name == "saleha-apex-97:v3.5"
    assert len(report.domains) == 8
    for domain in report.domains:
        assert isinstance(domain, ApexDomainMetric)
        assert domain.domain_name in ["1. SWE-bench Verified (Agentic Multi-File PRs)", "2. Artificial Analysis Agentic Index", "3. LiveCodeBench (LCB Multi-Language)", "4. AA-Non-Hallucination Cleanliness", "5. Terminal-Bench v2 (Autonomous Linux CLI)", "6. SAST 0-CWE Security Resilience", "7. HumanEval Pass@1 (AST Type-Checked)", "8. Multimodal Voice/Video Arena"]
        assert domain.target_threshold == 97.0
    assert round(report.overall_apex_average, 2) == 97.5
    assert report.all_domains_passed_97
    assert round(report.evaluation_duration_sec, 3) == 3.456
    assert report.certification_hash == "0xAPEX_97_UNIVERSAL_DOMINANCE_CERTIFIED"