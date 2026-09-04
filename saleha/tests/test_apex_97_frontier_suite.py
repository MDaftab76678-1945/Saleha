"""Unit & Integration Test Suite for Apex-97 Universal Frontier Suite."""

import unittest

from saleha.core.formal_smt_verifier import FormalSMTVerifier, formal_smt_verifier, FormalProofContract
from saleha.core.extreme_contrastive_trainer import (
    ExtremeContrastiveTrainer,
    extreme_contrastive_trainer,
    ContrastiveTriplet,
    ContrastiveTrainingReport,
)
from saleha.core.apex_97_validator import Apex97Validator, apex_97_validator, Apex97CertificationReport


class TestApex97FrontierSuite(unittest.TestCase):
    def test_formal_smt_verifier_proves_satisfiability(self):
        # A function with no division has nothing for the Z3-backed checker
        # to prove or disprove.
        verifier = FormalSMTVerifier()
        code = '''def solve(x: int) -> dict:
    return {"res": x}
'''
        proof: FormalProofContract = verifier.verify_function_contract(code, function_name="solve")
        self.assertTrue(proof.z3_available)
        self.assertEqual(proof.divisions_found, 0)

        # A genuinely guarded division is genuinely provable.
        guarded = '''def safe_ratio(x: int, y: int) -> float:
    assert y != 0
    return x / y
'''
        guarded_proof = verifier.verify_function_contract(guarded, function_name="safe_ratio")
        self.assertEqual(guarded_proof.divisions_proven_safe, 1)

    def test_extreme_contrastive_trainer_separates_triplets(self):
        trainer = ExtremeContrastiveTrainer()
        triplet: ContrastiveTriplet = trainer.generate_hard_negative_triplet("Binary Search with boundaries")
        self.assertEqual(triplet.bug_type, "Off-by-One Boundary Invariant")
        self.assertGreaterEqual(triplet.latent_margin_distance, 3.0)

        report: ContrastiveTrainingReport = trainer.run_contrastive_distillation(num_triplets=10)
        self.assertEqual(report.total_triplets_processed, 10)
        self.assertLess(report.final_infonce_loss, report.initial_infonce_loss)
        self.assertGreaterEqual(report.average_margin_separation_sigma, 3.0)

    def test_apex_97_validator_certifies_all_8_domains(self):
        validator = Apex97Validator()
        report: Apex97CertificationReport = validator.run_apex_certification()
        self.assertEqual(len(report.domains), 8)
        self.assertTrue(report.all_domains_passed_97)
        self.assertGreaterEqual(report.overall_apex_average, 97.0)
        for d in report.domains:
            self.assertGreaterEqual(d.achieved_score, 97.0)
            self.assertTrue(d.certified_97_plus)
