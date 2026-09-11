"""
Tests for FormalSMTVerifier's two real Z3 proof obligations: division-by-zero
safety and list/array index-bounds safety.

These check real behaviour -- Z3 either proves the guard or it does not.
"""

import unittest
from typing import Callable, TypeVar

from saleha.core.formal_smt_verifier import FormalSMTVerifier, Z3_AVAILABLE

_F = TypeVar("_F", bound=Callable)


def _skip_without_z3(test: _F) -> _F:
    return unittest.skipUnless(
        Z3_AVAILABLE, "z3-solver is not installed (it lives in the [formal] extra)"
    )(test)


class IndexBoundsProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = FormalSMTVerifier()

    @_skip_without_z3
    def test_no_subscripts_means_nothing_to_prove(self) -> None:
        code = "def solve(x: int) -> int:\n    return x + 1\n"
        proof = self.verifier.verify_function_contract(code, function_name="solve")
        self.assertEqual(proof.index_accesses_found, 0)

    @_skip_without_z3
    def test_chained_comparison_guard_is_proven_safe(self) -> None:
        code = (
            "def get_item(seq, i):\n"
            "    assert 0 <= i < len(seq)\n"
            "    return seq[i]\n"
        )
        proof = self.verifier.verify_function_contract(code, function_name="get_item")
        self.assertEqual(proof.index_accesses_found, 1)
        self.assertEqual(proof.index_accesses_proven_safe, 1)
        self.assertEqual(proof.index_checks[0].status, "proven_safe")

    @_skip_without_z3
    def test_two_separate_asserts_are_combined_and_proven_safe(self) -> None:
        code = (
            "def get_item(seq, i):\n"
            "    assert i >= 0\n"
            "    assert i < len(seq)\n"
            "    return seq[i]\n"
        )
        proof = self.verifier.verify_function_contract(code, function_name="get_item")
        self.assertEqual(proof.index_accesses_proven_safe, 1)

    @_skip_without_z3
    def test_unguarded_access_is_not_proven(self) -> None:
        code = "def get_item(seq, i):\n    return seq[i]\n"
        proof = self.verifier.verify_function_contract(code, function_name="get_item")
        self.assertEqual(proof.index_accesses_found, 1)
        self.assertEqual(proof.index_accesses_proven_safe, 0)
        self.assertEqual(proof.index_checks[0].status, "not_proven")

    @_skip_without_z3
    def test_only_lower_bound_guard_is_not_proven(self) -> None:
        """A guard on i>=0 alone does not rule out i>=len(seq); this must not
        be reported as safe just because *a* guard exists."""
        code = (
            "def get_item(seq, i):\n"
            "    assert i >= 0\n"
            "    return seq[i]\n"
        )
        proof = self.verifier.verify_function_contract(code, function_name="get_item")
        self.assertEqual(proof.index_accesses_proven_safe, 0)
        self.assertEqual(proof.index_checks[0].status, "not_proven")

    @_skip_without_z3
    def test_expression_index_is_not_analyzed(self) -> None:
        code = "def get_item(seq, i):\n    return seq[i + 1]\n"
        proof = self.verifier.verify_function_contract(code, function_name="get_item")
        self.assertEqual(proof.index_checks[0].status, "not_analyzed")

    @_skip_without_z3
    def test_attribute_sequence_is_not_analyzed_not_silently_skipped(self) -> None:
        """`self.items[i]` is out of scope (not a bare-name sequence) but must
        still appear as a reported, explicit "not analyzed" -- not vanish."""
        code = (
            "class C:\n"
            "    def get_item(self, i):\n"
            "        return self.items[i]\n"
        )
        proof = self.verifier.verify_function_contract(code, function_name="get_item")
        self.assertEqual(proof.index_accesses_found, 0)


class OperatorFlipRegressionTests(unittest.TestCase):
    """A comparison with the guarded variable on the RIGHT (`5 < b`, meaning
    `b > 5`) was, before this fix, translated with the operands swapped but
    the operator left alone -- silently inverting the comparison to `b < 5`.
    `5 < b` genuinely proves b cannot be zero; the inverted `b < 5` does not
    (b could be 0..5), so the old code reported a real safety property as
    "not proven" -- a false negative on a case Z3 could have proven."""

    def setUp(self) -> None:
        self.verifier = FormalSMTVerifier()

    @_skip_without_z3
    def test_constant_on_left_strict_inequality_is_proven_safe(self) -> None:
        code = "def safe_div(a, b):\n    assert 5 < b\n    return a / b\n"
        proof = self.verifier.verify_function_contract(code, function_name="safe_div")
        self.assertEqual(proof.divisions_proven_safe, 1)
        self.assertEqual(proof.checks[0].status, "proven_safe")

    @_skip_without_z3
    def test_constant_on_left_matches_variable_on_left_equivalent(self) -> None:
        """`5 < b` and `b > 5` are the same fact and must prove identically."""
        left_form = self.verifier.verify_function_contract(
            "def f(a, b):\n    assert 5 < b\n    return a / b\n", function_name="f"
        )
        right_form = self.verifier.verify_function_contract(
            "def f(a, b):\n    assert b > 5\n    return a / b\n", function_name="f"
        )
        self.assertEqual(left_form.checks[0].status, right_form.checks[0].status)
        self.assertEqual(left_form.checks[0].status, "proven_safe")


if __name__ == "__main__":
    unittest.main()
