"""
Tests for the Apex-97 targets and the SMT verifier.

Every test in this file used to pin a fabrication in place:

    self.assertTrue(report.all_domains_passed_97)       # all() over literal Trues
    self.assertGreaterEqual(report.overall_apex_average, 97.0)   # hand-typed
    self.assertGreaterEqual(d.achieved_score, 97.0)     # eight literals
    self.assertTrue(d.certified_97_plus)                # literal True
    self.assertEqual(triplet.bug_type, "Off-by-One Boundary Invariant")
    self.assertGreaterEqual(report.average_margin_separation_sigma, 3.0)  # 3.42

Not one of those checked behaviour. They asserted that constants were still
the constants, so they would have passed forever while the modules measured
nothing -- which is exactly what happened.

`extreme_contrastive_trainer` is deleted (it returned the same loss for 5 and
for 500 triplets, and the same binary-search off-by-one for every prompt).
`apex_97_validator` keeps its targets but no longer dresses them as results.

The SMT tests stay, because that module genuinely runs Z3.
"""

import unittest

from saleha.core.formal_smt_verifier import (
    FormalSMTVerifier,
    FormalProofContract,
)
from saleha.core.apex_97_validator import (
    Apex97Validator,
    apex_97_validator,
    Apex97CertificationReport,
)


class FormalSMTTests(unittest.TestCase):
    """These check real behaviour: Z3 either proves the guard or it does not."""

    def setUp(self):
        self.verifier = FormalSMTVerifier()

    def test_a_function_with_no_division_has_nothing_to_prove(self):
        code = 'def solve(x: int) -> dict:\n    return {"res": x}\n'
        proof: FormalProofContract = self.verifier.verify_function_contract(
            code, function_name="solve")
        self.assertEqual(proof.divisions_found, 0)

    def test_a_guarded_division_is_proven_safe(self):
        if not self.verifier.verify_function_contract(
                "def f(a, b):\n    return a\n", function_name="f").z3_available:
            self.skipTest("z3-solver is not installed (it lives in the "
                          "[formal] extra, not [dev])")
        guarded = ("def safe_ratio(x: int, y: int) -> float:\n"
                   "    assert y != 0\n"
                   "    return x / y\n")
        proof = self.verifier.verify_function_contract(
            guarded, function_name="safe_ratio")
        self.assertEqual(proof.divisions_proven_safe, 1)

    def test_z3_availability_is_reported_not_assumed(self):
        """
        The old test asserted `proof.z3_available` outright, so a clean install
        without the [formal] extra failed with an unhelpful `False is not
        true`. Availability is a fact about the machine, not a requirement.
        """
        proof = self.verifier.verify_function_contract(
            "def f(a, b):\n    return a / b\n", function_name="f")
        self.assertIsInstance(proof.z3_available, bool)
        if not proof.z3_available:
            self.assertIn("z3", proof.mathematical_certificate.lower())


class Apex97TargetTests(unittest.TestCase):

    def test_report_is_labelled_as_unmeasured(self):
        """The property the module must never lose."""
        report: Apex97CertificationReport = (
            apex_97_validator.run_apex_certification())
        self.assertFalse(report.is_measured)
        self.assertIn("no benchmark", report.status_note.lower())

    def test_targets_are_present_but_carry_no_rank_or_certificate(self):
        report = Apex97Validator().run_apex_certification()
        self.assertEqual(len(report.domains), 8)
        for domain in report.domains:
            self.assertEqual(domain.target_score, 97.0)
            # A target cannot hold a rank or a certificate.
            self.assertFalse(hasattr(domain, "frontier_rank"))
            self.assertFalse(hasattr(domain, "certified_97_plus"))
            self.assertFalse(hasattr(domain, "achieved_score"))

    def test_the_fabricated_fields_are_gone(self):
        """
        `all_domains_passed_97` was all() over literal Trues and could not
        return False. `overall_apex_average` averaged eight hand-typed scores.
        `certification_hash` was the string
        "0xAPEX_97_UNIVERSAL_DOMINANCE_CERTIFIED".
        """
        report = apex_97_validator.run_apex_certification()
        self.assertFalse(hasattr(report, "all_domains_passed_97"))
        self.assertFalse(hasattr(report, "overall_apex_average"))
        self.assertFalse(hasattr(report, "certification_hash"))

    def test_the_deleted_trainer_stays_deleted(self):
        """
        `extreme_contrastive_trainer` returned `final_loss 0.12, sigma 3.42`
        for 5 triplets and for 500 alike, and generated the same
        binary-search off-by-one as its "extreme hard negative" for every
        prompt. The tests that stood here asserted those exact constants.
        """
        import importlib
        with self.assertRaises(ImportError):
            importlib.import_module("saleha.core.extreme_contrastive_trainer")


if __name__ == "__main__":
    unittest.main()
