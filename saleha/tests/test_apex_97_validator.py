"""
Tests for `apex_97_validator`.

Worth recording what this file used to be, because it is an unusually clear
example of the trap this repo keeps hitting.

Its first version never called `run_apex_certification()` at all -- it
hand-built the result objects with the same numbers the module contained and
asserted against its own fixture. A later edit fixed that and left an honest
comment saying so:

    Calling it doesn't make the underlying numbers real:
    run_apex_certification() itself returns fixed, hardcoded per-domain scores
    regardless of any actual model or benchmark run -- it does not measure
    anything.

That comment was correct, and the fabrication still shipped for months
afterwards. Noticing a fake and testing around it is not the same as removing
it. The module now reports targets with `is_measured=False`, and these tests
pin that instead of the constants.
"""

import importlib

import pytest

from saleha.core.apex_97_validator import (
    ApexDomainTarget,
    Apex97CertificationReport,
    Apex97Validator,
)


def test_domain_target_holds_a_goal_not_a_result():
    target = ApexDomainTarget(
        domain_name="SWE-bench Verified (agentic multi-file PRs)",
        target_score=97.0,
    )
    assert target.target_score == 97.0
    # Renamed from ApexDomainMetric, which carried achieved_score,
    # frontier_rank ("Rank #1") and certified_97_plus (True) -- three claims
    # about a benchmark that was never run.
    assert not hasattr(target, "achieved_score")
    assert not hasattr(target, "frontier_rank")
    assert not hasattr(target, "certified_97_plus")


def test_report_declares_itself_unmeasured():
    report = Apex97Validator().run_apex_certification(model_name="test-model")

    assert isinstance(report, Apex97CertificationReport)
    assert report.model_name == "test-model"
    assert len(report.domains) == 8
    assert all(isinstance(d, ApexDomainTarget) for d in report.domains)

    assert report.is_measured is False
    assert "no benchmark" in report.status_note.lower()
    assert report.evaluation_duration_sec >= 0.0


def test_the_certified_fields_cannot_return():
    """
    `all_domains_passed_97` was `all()` over a list of literal `True`s, so it
    could not return False for any input -- there was no input.
    `certification_hash` was the string
    "0xAPEX_97_UNIVERSAL_DOMINANCE_CERTIFIED".
    """
    report = Apex97Validator().run_apex_certification()
    assert not hasattr(report, "all_domains_passed_97")
    assert not hasattr(report, "overall_apex_average")
    assert not hasattr(report, "certification_hash")


def test_target_average_is_of_targets_not_scores():
    report = Apex97Validator().run_apex_certification()
    expected = round(
        sum(d.target_score for d in report.domains) / len(report.domains), 2)
    assert report.target_average == expected


def test_deleted_trainer_stays_deleted():
    """`extreme_contrastive_trainer` returned the same loss for 5 triplets and
    for 500, and the same off-by-one for every prompt."""
    with pytest.raises(ImportError):
        importlib.import_module("saleha.core.extreme_contrastive_trainer")
