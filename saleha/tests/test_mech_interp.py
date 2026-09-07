"""
Unit tests for the code structure explainer (formerly "MechInterpEngine").

The old suite asserted the substring behaviour directly -- it expected exactly
4 attributions for a 4-line snippet and checked bucket counts -- so it would
have passed forever while the module classified `x = "raise the roof"` as a
defensive error guard at 0.95 confidence.

These tests pin what the AST version actually guarantees: classification comes
from node type rather than text, complexity matches `radon`, scope is real, and
an unparseable file degrades visibly instead of silently.
"""

from __future__ import annotations

import textwrap
import unittest

from saleha.core.mech_interp import (
    CodeStructureEngine, MechInterpEngine, MechInterpReport,
    ERROR_GUARD, TYPE_CONTRACT, CORE_LOGIC, RESOURCE_MGMT, CONTROL_FLOW,
)


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


class ClassificationTests(unittest.TestCase):

    def setUp(self):
        self.engine = CodeStructureEngine()

    def _types_by_line(self, code: str):
        rep = self.engine.explain_code(code)
        return {a.line_number: a.circuit_type for a in rep.attributions}

    def test_keyword_inside_a_string_is_not_an_error_guard(self):
        """
        The regression that motivated the rewrite. The substring version
        classified this as `error_guard` at 0.95 because the line contains
        the characters "raise ".
        """
        types = self._types_by_line('x = "raise the roof"\n')
        self.assertEqual(types[1], CORE_LOGIC)

    def test_keyword_in_a_comment_is_not_classified(self):
        code = src("""
            # raise an issue with the team
            y = 1
        """)
        rep = self.engine.explain_code(code)
        lines = {a.line_number for a in rep.attributions}
        self.assertNotIn(1, lines)

    def test_real_raise_is_an_error_guard(self):
        types = self._types_by_line("raise ValueError('bad')\n")
        self.assertEqual(types[1], ERROR_GUARD)

    def test_node_types_map_to_expected_circuits(self):
        code = src("""
            import os
            def f(a: int) -> int:
                total: int = 0
                if a > 0:
                    for i in range(a):
                        total += i
                try:
                    with open('x') as fh:
                        fh.read()
                except OSError:
                    raise RuntimeError('nope')
                return total
        """)
        types = self._types_by_line(code)
        self.assertEqual(types[1], CORE_LOGIC)       # import
        self.assertEqual(types[2], TYPE_CONTRACT)    # annotated def
        self.assertEqual(types[3], TYPE_CONTRACT)    # annotated assignment
        self.assertEqual(types[4], CONTROL_FLOW)     # if
        self.assertEqual(types[5], CONTROL_FLOW)     # for
        self.assertEqual(types[7], ERROR_GUARD)      # try
        self.assertEqual(types[8], RESOURCE_MGMT)    # with
        self.assertEqual(types[10], ERROR_GUARD)     # except
        self.assertEqual(types[11], ERROR_GUARD)     # raise
        self.assertEqual(types[12], CONTROL_FLOW)    # return

    def test_bare_except_is_called_out_specifically(self):
        code = src("""
            try:
                risky()
            except:
                pass
        """)
        rep = self.engine.explain_code(code)
        bare = [a for a in rep.attributions if "Bare `except:`" in a.rationale]
        self.assertEqual(len(bare), 1)
        self.assertEqual(bare[0].line_number, 3)

    def test_confidence_is_full_for_parsed_source(self):
        rep = self.engine.explain_code("x = 1\n")
        self.assertTrue(all(a.confidence == 1.0 for a in rep.attributions))


class ComplexityTests(unittest.TestCase):

    def setUp(self):
        self.engine = CodeStructureEngine()

    def _complexity(self, code: str, name: str) -> int:
        rep = self.engine.explain_code(code)
        return next(f.complexity for f in rep.functions if f.name == name)

    def test_straight_line_function_is_one(self):
        self.assertEqual(self._complexity("def f():\n    return 1\n", "f"), 1)

    def test_branches_count(self):
        code = src("""
            def f(a):
                if a:
                    return 1
                for _ in range(3):
                    pass
                while a:
                    break
                return 0
        """)
        self.assertEqual(self._complexity(code, "f"), 4)

    def test_boolop_adds_one_per_extra_operand(self):
        code = src("""
            def f(a, b, c):
                if a and b and c:
                    return 1
                return 0
        """)
        # 1 base + 1 if + 2 extra operands
        self.assertEqual(self._complexity(code, "f"), 4)

    def test_with_is_not_a_decision_point(self):
        """`with` takes no branch; counting it disagreed with radon."""
        code = src("""
            def f():
                with open('x') as fh:
                    return fh.read()
        """)
        self.assertEqual(self._complexity(code, "f"), 1)

    def test_comprehension_if_filter_counts(self):
        code = src("""
            def f(xs):
                return [x for x in xs if x > 0]
        """)
        # 1 base + 1 comprehension + 1 filter
        self.assertEqual(self._complexity(code, "f"), 3)

    def test_nested_function_branches_are_not_charged_to_the_parent(self):
        """
        A factory that returns a branchy closure is itself simple. Walking
        into the nested def reported one such factory as complexity 24.
        """
        code = src("""
            def factory():
                def inner(a):
                    if a:
                        for _ in range(3):
                            if a > 1:
                                return 1
                    return 0
                return inner
        """)
        self.assertEqual(self._complexity(code, "factory"), 1)
        self.assertEqual(self._complexity(code, "inner"), 4)

    def test_lambda_branches_are_charged_to_the_enclosing_function(self):
        """A lambda gets no profile of its own, so its branch must land here."""
        code = src("""
            def f(xs):
                g = lambda v: 1 if v else 0
                return g(xs)
        """)
        self.assertEqual(self._complexity(code, "f"), 2)

    def test_matches_radon_on_this_repos_own_source(self):
        """
        Cross-check against the reference implementation. Skipped when radon
        is not installed rather than silently passing.
        """
        radon_cc = __import__("importlib").util.find_spec("radon")
        if radon_cc is None:
            self.skipTest("radon not installed")
        from radon.complexity import cc_visit

        import pathlib
        target = pathlib.Path(__file__).resolve().parents[1] / "core" / "bm25.py"
        if not target.exists():
            self.skipTest("bm25.py not present")
        code = target.read_text(encoding="utf-8")

        rep = self.engine.explain_code(code)
        mine = {f.line_number: f.complexity for f in rep.functions}
        checked = 0
        for block in cc_visit(code):
            # cc_visit yields classes too; only functions/methods have a
            # matching FunctionProfile.
            if block.letter == "C":
                continue
            if block.lineno in mine:
                self.assertEqual(
                    mine[block.lineno], block.complexity,
                    f"{block.name} at line {block.lineno}")
                checked += 1
        self.assertGreater(checked, 0)


class StructureTests(unittest.TestCase):

    def setUp(self):
        self.engine = CodeStructureEngine()

    def test_scope_records_the_enclosing_chain(self):
        code = src("""
            class Outer:
                def method(self):
                    x = 1
                    return x
        """)
        rep = self.engine.explain_code(code)
        by_line = {a.line_number: a.scope for a in rep.attributions}
        self.assertEqual(by_line[3], ["Outer", "method"])
        self.assertEqual(rep.classes, ["Outer"])

    def test_scope_does_not_leak_between_files(self):
        """
        `_scope_at` was a class attribute in the first draft, so scopes from
        one analysed file were reported against another file's lines.
        """
        engine = CodeStructureEngine()
        engine.explain_code("class Alpha:\n    def one(self):\n        pass\n")
        rep = engine.explain_code("x = 1\n")
        self.assertEqual([a.scope for a in rep.attributions], [[]])

    def test_qualname_includes_the_class(self):
        code = src("""
            class Outer:
                def method(self):
                    pass
        """)
        rep = self.engine.explain_code(code)
        self.assertEqual([f.qualname for f in rep.functions], ["Outer.method"])

    def test_annotation_and_docstring_flags(self):
        code = src("""
            def documented(a: int) -> int:
                '''Doc.'''
                return a

            def bare(a):
                return a
        """)
        rep = self.engine.explain_code(code)
        by_name = {f.name: f for f in rep.functions}
        self.assertTrue(by_name["documented"].has_docstring)
        self.assertTrue(by_name["documented"].is_annotated)
        self.assertFalse(by_name["bare"].has_docstring)
        self.assertFalse(by_name["bare"].is_annotated)

    def test_partially_annotated_signature_is_not_annotated(self):
        code = src("""
            def half(a: int, b):
                return a
        """)
        rep = self.engine.explain_code(code)
        self.assertFalse(rep.functions[0].is_annotated)

    def test_async_function_is_flagged(self):
        rep = self.engine.explain_code("async def go():\n    return 1\n")
        self.assertTrue(rep.functions[0].is_async)

    def test_most_complex_picks_the_worst_function(self):
        code = src("""
            def simple():
                return 1

            def branchy(a):
                if a:
                    return 1
                if a > 2:
                    return 2
                return 0
        """)
        rep = self.engine.explain_code(code)
        worst = rep.most_complex
        self.assertIsNotNone(worst)
        self.assertEqual(worst.name, "branchy")

    def test_most_complex_is_none_without_functions(self):
        rep = self.engine.explain_code("x = 1\n")
        self.assertIsNone(rep.most_complex)

    def test_per_function_circuit_counts_are_scoped_to_that_function(self):
        code = src("""
            def guarded():
                raise ValueError()

            def plain():
                x = 1
                return x
        """)
        rep = self.engine.explain_code(code)
        by_name = {f.name: f for f in rep.functions}
        self.assertEqual(by_name["guarded"].circuits[ERROR_GUARD], 1)
        self.assertEqual(by_name["plain"].circuits[ERROR_GUARD], 0)

    def test_code_lines_excludes_blanks_and_comments(self):
        code = "x = 1\n\n# a comment\ny = 2\n"
        rep = self.engine.explain_code(code)
        self.assertEqual(rep.total_lines, 4)
        self.assertEqual(rep.code_lines, 2)


class FallbackTests(unittest.TestCase):

    def setUp(self):
        self.engine = CodeStructureEngine()

    def test_unparseable_source_is_reported_not_guessed(self):
        rep = self.engine.explain_code("def broken( :\n", "broken.py")
        self.assertFalse(rep.parsed)
        self.assertIsNotNone(rep.parse_error)
        self.assertIn("could not be parsed", rep.summary)
        self.assertEqual(rep.functions, [])

    def test_fallback_marks_lower_confidence_and_claims_no_labels(self):
        rep = self.engine.explain_code("def broken( :\n    raise X\n")
        self.assertTrue(all(a.confidence == 0.5 for a in rep.attributions))
        # It must not label the `raise` line, having no AST to judge from.
        self.assertTrue(all(a.circuit_type == CORE_LOGIC
                            for a in rep.attributions))

    def test_empty_source_is_parsed_and_empty(self):
        rep = self.engine.explain_code("")
        self.assertTrue(rep.parsed)
        self.assertEqual(rep.attributions, [])
        self.assertEqual(rep.code_lines, 0)


class CompatibilityTests(unittest.TestCase):

    def test_legacy_names_still_resolve(self):
        """Existing callers import MechInterpEngine / mech_interp_engine."""
        from saleha.core.mech_interp import mech_interp_engine
        self.assertIs(MechInterpEngine, CodeStructureEngine)
        rep = mech_interp_engine.explain_code("x = 1\n", "legacy.py")
        self.assertIsInstance(rep, MechInterpReport)
        self.assertEqual(rep.target_name, "legacy.py")

    def test_report_carries_the_expected_circuit_keys(self):
        rep = CodeStructureEngine().explain_code("x = 1\n")
        self.assertEqual(
            set(rep.circuits_identified),
            {ERROR_GUARD, TYPE_CONTRACT, CORE_LOGIC, RESOURCE_MGMT, CONTROL_FLOW},
        )

    def test_saliency_score_is_gone(self):
        """The field was a constant per label; it must not come back."""
        rep = CodeStructureEngine().explain_code("x = 1\n")
        self.assertFalse(hasattr(rep.attributions[0], "saliency_score"))


if __name__ == "__main__":
    unittest.main()
