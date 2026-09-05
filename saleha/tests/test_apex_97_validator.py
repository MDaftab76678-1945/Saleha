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
    assert metric.certified_97_plus


def test_run_apex_certification_returns_real_report():
    # The original version of this test never called run_apex_certification()
    # at all -- it hand-built ApexDomainMetric/Apex97CertificationReport
    # objects with the same numbers and asserted against its own fixture data,
    # so the validator's own logic (averaging, all-pass check, timing) was
    # never exercised.
    #
    # Calling it doesn't make the underlying numbers real: run_apex_certification()
    # itself returns fixed, hardcoded per-domain scores regardless of any
    # actual model or benchmark run (see saleha/core/apex_97_validator.py) --
    # it does not measure anything. This test verifies the validator computes
    # its aggregate fields (average, all-pass, hash) *correctly from* those
    # fixed inputs, which is a real (if narrow) thing to test; it is not a
    # test that Saleha achieves 97% on any benchmark.
    validator = Apex97Validator()
    report = validator.run_apex_certification(model_name="test-model")

    assert isinstance(report, Apex97CertificationReport)
    assert report.model_name == "test-model"
    assert len(report.domains) == 8
    assert all(isinstance(d, ApexDomainMetric) for d in report.domains)

    expected_avg = round(sum(d.achieved_score for d in report.domains) / len(report.domains), 2)
    assert report.overall_apex_average == expected_avg
    assert report.all_domains_passed_97 == all(d.certified_97_plus for d in report.domains)
    assert report.evaluation_duration_sec >= 0.0
    assert report.certification_hash
