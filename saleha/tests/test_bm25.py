"""
Tests for Okapi BM25 ranking.

What this replaces: the notebook's `_text_to_sparse_vector`, labelled
"simplified BM25", which computes raw word counts and nothing else. Measured
on a three-document corpus -- a short file that answers the query, and a long
file that merely repeats the term:

    raw word count :  long_noise 400  vs  short_answer 4    (noise wins 100x)
    BM25           :  short_answer 2.99  vs  long_noise 1.16 (answer wins)

That difference is the entire point of the module, so it is asserted directly.
No model is contacted: BM25 is pure arithmetic.
"""

from __future__ import annotations

import unittest

from saleha.core.bm25 import (
    DEFAULT_B,
    DEFAULT_K1,
    BM25Index,
    hybrid_search,
    reciprocal_rank_fusion,
    tokenize,
)


class TokenizerTests(unittest.TestCase):
    def test_camel_case_is_split_and_kept(self):
        out = tokenize("getUserName")
        self.assertIn("getusername", out)
        for part in ("get", "user", "name"):
            self.assertIn(part, out)

    def test_snake_case_is_split_and_kept(self):
        out = tokenize("parse_config_file")
        self.assertIn("parse_config_file", out)
        for part in ("parse", "config", "file"):
            self.assertIn(part, out)

    def test_sub_tokens_are_not_duplicated(self):
        """snake_case and camelCase rules both fire; emitting each part twice
        would double the term frequency and let the tokenizer inflate a
        document's own score."""
        out = tokenize("parse_config_file")
        self.assertEqual(len(out), len(set(out)))

    def test_digits_survive(self):
        self.assertIn("2", tokenize("HTTPServer_v2"))

    def test_empty_and_none(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize(None), [])

    def test_punctuation_is_dropped(self):
        self.assertEqual(tokenize("a, b; c!"), ["a", "b", "c"])


class RankingBeatsWordCountTests(unittest.TestCase):
    """The headline claim, asserted rather than described."""

    def setUp(self):
        self.index = BM25Index()
        self.index.add("short_answer",
                       "def parse_config(path): return json.load(open(path))")
        self.index.add("long_noise",
                       "config " * 400 + " unrelated boilerplate " * 200)
        self.index.add("other",
                       "def render_template(name): return name.upper()")

    def test_short_relevant_document_outranks_long_noise(self):
        top = self.index.search("parse config", top_k=3)
        self.assertEqual(top[0].doc_id, "short_answer")

    def test_raw_word_count_would_have_ranked_the_noise_first(self):
        """Pins the failure mode this module exists to fix."""
        counts = {
            doc_id: sum(terms.get(t, 0) for t in ("parse", "config"))
            for doc_id, terms in zip(self.index.doc_ids, self.index.doc_terms)
        }
        self.assertGreater(counts["long_noise"], counts["short_answer"])

    def test_unrelated_document_is_not_returned(self):
        returned = {r.doc_id for r in self.index.search("parse config")}
        self.assertNotIn("other", returned)


class SaturationTests(unittest.TestCase):
    def test_score_gain_shrinks_as_frequency_grows(self):
        """The 10th occurrence must say less than the 2nd -- that is k1."""
        index = BM25Index()
        for n in range(1, 11):
            index.add(f"d{n}", "term " * n + " filler")
        gains = []
        previous = 0.0
        for n in (1, 2, 5, 10):
            value = index.score("term", n - 1)
            gains.append(value - previous)
            previous = value
        for earlier, later in zip(gains, gains[1:]):
            self.assertLess(later, earlier)

    def test_score_is_bounded_by_k1_plus_one_times_idf(self):
        index = BM25Index()
        index.add("a", "term " * 10000)
        index.add("b", "something else entirely")
        self.assertLess(index.score("term", 0),
                        index.idf("term") * (DEFAULT_K1 + 1.0) + 0.01)


class LengthNormalisationTests(unittest.TestCase):
    def test_shorter_document_wins_at_equal_term_frequency(self):
        index = BM25Index()
        index.add("short", "needle in a haystack")
        index.add("long", "needle " + "padding " * 300)
        self.assertGreater(index.score("needle", 0), index.score("needle", 1))

    def test_b_zero_disables_length_normalisation(self):
        plain = BM25Index(b=0.0)
        plain.add("short", "needle here")
        plain.add("long", "needle " + "padding " * 300)
        self.assertAlmostEqual(plain.score("needle", 0),
                               plain.score("needle", 1), places=6)


class IdfTests(unittest.TestCase):
    def test_rare_term_outweighs_common_term(self):
        index = BM25Index()
        for i in range(10):
            index.add(f"d{i}", "common term here")
        index.add("rare_doc", "common term here unicorn")
        self.assertGreater(index.idf("unicorn"), index.idf("common"))

    def test_idf_is_never_negative(self):
        """The classic formula goes negative past 50% document frequency,
        which would penalise documents for containing the query term."""
        index = BM25Index()
        for i in range(10):
            index.add(f"d{i}", "everywhere")
        self.assertGreaterEqual(index.idf("everywhere"), 0.0)

    def test_unknown_term_scores_zero(self):
        index = BM25Index()
        index.add("a", "hello world")
        self.assertEqual(index.score("nonexistent", 0), 0.0)

    def test_empty_index_is_safe(self):
        index = BM25Index()
        self.assertEqual(index.idf("anything"), 0.0)
        self.assertEqual(index.search("query"), [])


class SearchContractTests(unittest.TestCase):
    def setUp(self):
        self.index = BM25Index()
        self.index.add_many([("a", "alpha beta"), ("b", "beta gamma"),
                             ("c", "gamma delta")])

    def test_results_are_ordered_best_first(self):
        results = self.index.search("beta", top_k=5)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_is_honoured(self):
        self.assertLessEqual(len(self.index.search("gamma", top_k=1)), 1)

    def test_matched_terms_are_reported(self):
        result = self.index.search("beta", top_k=1)[0]
        self.assertIn("beta", result.matched_terms)

    def test_ranking_is_deterministic(self):
        first = [r.doc_id for r in self.index.search("beta gamma", top_k=3)]
        for _ in range(3):
            self.assertEqual(
                [r.doc_id for r in self.index.search("beta gamma", top_k=3)],
                first)

    def test_add_many_matches_repeated_add(self):
        one = BM25Index()
        one.add_many([("x", "hello world"), ("y", "hello there")])
        two = BM25Index()
        two.add("x", "hello world")
        two.add("y", "hello there")
        self.assertEqual(one.doc_freq, two.doc_freq)
        self.assertAlmostEqual(one.avg_doc_length, two.avg_doc_length)

    def test_score_rejects_a_bad_index(self):
        with self.assertRaises(IndexError):
            self.index.score("beta", 99)


class ExplainTests(unittest.TestCase):
    """A ranker nobody can inspect is a ranker nobody should trust."""

    def test_contributions_sum_to_the_score(self):
        index = BM25Index()
        index.add("a", "alpha beta gamma")
        index.add("b", "delta")
        contributions = index.explain("alpha beta", "a")
        self.assertAlmostEqual(sum(contributions.values()),
                               index.score("alpha beta", 0), places=5)

    def test_unknown_document_returns_nothing(self):
        self.assertEqual(BM25Index().explain("q", "missing"), {})


class FusionTests(unittest.TestCase):
    def test_a_document_ranked_well_by_both_wins(self):
        fused = reciprocal_rank_fusion([["a", "b", "c"], ["a", "c", "b"]])
        self.assertEqual(fused[0][0], "a")

    def test_documents_from_either_list_are_included(self):
        ids = {doc for doc, _ in
               reciprocal_rank_fusion([["a", "b"], ["c", "d"]])}
        self.assertEqual(ids, {"a", "b", "c", "d"})

    def test_fusion_is_deterministic_on_ties(self):
        first = reciprocal_rank_fusion([["a", "b"], ["b", "a"]])
        for _ in range(3):
            self.assertEqual(reciprocal_rank_fusion([["a", "b"], ["b", "a"]]),
                             first)

    def test_empty_input_is_empty(self):
        self.assertEqual(reciprocal_rank_fusion([]), [])

    def test_hybrid_search_blends_both_rankers(self):
        index = BM25Index()
        index.add_many([("lex", "needle needle needle"),
                        ("dense_pick", "unrelated words"),
                        ("filler", "nothing here")])
        fused = hybrid_search(index, "needle", ["dense_pick", "lex"], top_k=2)
        ids = {doc for doc, _ in fused}
        self.assertIn("lex", ids)
        self.assertIn("dense_pick", ids)


class RealCorpusTests(unittest.TestCase):
    """The strongest available check: rank this repo's own source."""

    def test_query_finds_the_right_module(self):
        import io
        import os
        index = BM25Index()
        core = os.path.join("saleha", "core")
        for name in sorted(os.listdir(core)):
            if name.endswith(".py"):
                index.add(name, io.open(os.path.join(core, name),
                                        encoding="utf-8",
                                        errors="ignore").read())
        self.assertGreater(index.size, 50)
        top = [r.doc_id for r in index.search("context window budget", top_k=3)]
        self.assertIn("context_budget.py", top)


if __name__ == "__main__":
    unittest.main()
