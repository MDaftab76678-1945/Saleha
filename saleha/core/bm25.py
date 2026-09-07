"""
Saleha Core: BM25 (Okapi BM25 ranking)

Why this exists
---------------
The notebook's `AdvancedRAGPipeline._text_to_sparse_vector` is labelled
"simplified BM25" and computes raw word counts:

    word_counts[word] = word_counts.get(word, 0) + 1

That is term frequency and nothing else -- no IDF, no saturation, no length
normalisation. It is not BM25, and a long document wins simply by being long.

`vector_store.py` here already does real TF-IDF with a proper IDF term, which
is a genuine ranker. What it does not model is the other half of BM25:

  * **Saturation (k1)** -- the 10th occurrence of a word says far less than
    the 2nd. TF-IDF grows linearly and lets one repeated token dominate.
  * **Length normalisation (b)** -- without it, a 2000-line file outranks the
    30-line file that actually answers the query, purely on term count.

Both matter for code search, where file lengths differ by orders of magnitude
and boilerplate repeats terms constantly.

Parameters
----------
`k1=1.5` and `b=0.75` are the standard Robertson/Sparck-Jones defaults from
the TREC experiments. They are not tuned for this repo -- tuning them would
need a labelled relevance set, which does not exist here. They are named as
defaults, not as measurements.

Scores are NOT probabilities and are not comparable across different corpora;
BM25 is a ranking function. `search()` returns them in order and the number
itself should only be compared within one result set.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

# Robertson/Sparck-Jones defaults. See module docstring: defaults, not tuning.
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75

_WORD = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> List[str]:
    """
    Split text into terms, splitting identifiers as well as keeping them.

    `getUserName` yields `getusername`, `get`, `user`, `name`, so a query for
    "user name" matches a camelCase identifier. Code search fails badly
    without this: identifiers are where the meaning lives.
    """
    out: List[str] = []
    for word in _WORD.findall(text or ""):
        lowered = word.lower()
        out.append(lowered)

        # snake_case and camelCase sub-tokens. Collected in a set first: an
        # identifier like `parse_config_file` is split by BOTH rules and would
        # otherwise emit each part twice, doubling its term frequency and
        # letting the tokenizer inflate a document's own score.
        pieces = {p.lower() for p in re.split(r"_+", word) if p}
        pieces |= {p.lower() for p in
                   re.findall(r"[A-Z]?[a-z]+|[A-Z]{2,}(?![a-z])|\d+", word)}
        pieces.discard(lowered)
        out.extend(sorted(pieces))
    return out


@dataclass
class BM25Result:
    doc_id: str
    score: float
    matched_terms: List[str] = field(default_factory=list)


class BM25Index:
    """
    Okapi BM25 over an in-memory corpus.

    Deliberately not a drop-in replacement for the TF-IDF cosine store in
    `vector_store.py`: that one is a similarity measure between two vectors,
    this is a query-document ranking function. They answer different questions
    and `hybrid_search()` combines them.
    """

    def __init__(self, k1: float = DEFAULT_K1, b: float = DEFAULT_B,
                 tokenizer=None):
        self.k1 = k1
        self.b = b
        self._tokenize = tokenizer or tokenize
        self.doc_ids: List[str] = []
        self.doc_terms: List[Counter] = []
        self.doc_lengths: List[int] = []
        self.doc_freq: Counter = Counter()
        self.avg_doc_length: float = 0.0

    # -- building ------------------------------------------------------
    def add(self, doc_id: str, text: str) -> None:
        terms = Counter(self._tokenize(text))
        self.doc_ids.append(doc_id)
        self.doc_terms.append(terms)
        length = sum(terms.values())
        self.doc_lengths.append(length)
        for term in terms:
            self.doc_freq[term] += 1
        self._recompute_avg()

    def add_many(self, documents: Iterable[Tuple[str, str]]) -> None:
        for doc_id, text in documents:
            terms = Counter(self._tokenize(text))
            self.doc_ids.append(doc_id)
            self.doc_terms.append(terms)
            self.doc_lengths.append(sum(terms.values()))
            for term in terms:
                self.doc_freq[term] += 1
        self._recompute_avg()

    def _recompute_avg(self) -> None:
        self.avg_doc_length = (sum(self.doc_lengths) / len(self.doc_lengths)
                               if self.doc_lengths else 0.0)

    @property
    def size(self) -> int:
        return len(self.doc_ids)

    # -- scoring -------------------------------------------------------
    def idf(self, term: str) -> float:
        """
        Robertson-Sparck-Jones IDF with the +0.5 smoothing.

        The classic form can go negative for a term appearing in more than
        half the corpus; the max() floor keeps a very common term at a small
        positive weight instead of actively penalising documents that contain
        it, which is the standard Lucene correction.
        """
        n = self.size
        if n == 0:
            return 0.0
        df = self.doc_freq.get(term, 0)
        value = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
        return max(value, 0.0)

    def score(self, query: str, doc_index: int) -> float:
        """BM25 score of one document against a query."""
        if not (0 <= doc_index < self.size):
            raise IndexError(f"no document at index {doc_index}")
        terms = self.doc_terms[doc_index]
        length = self.doc_lengths[doc_index]
        avg = self.avg_doc_length or 1.0

        total = 0.0
        for term in self._tokenize(query):
            freq = terms.get(term, 0)
            if not freq:
                continue
            # Saturation: numerator grows with freq, denominator too, so the
            # ratio approaches (k1 + 1) instead of growing without bound.
            # Length normalisation: a longer-than-average document needs more
            # occurrences to reach the same score.
            denominator = freq + self.k1 * (
                1.0 - self.b + self.b * (length / avg))
            total += self.idf(term) * (freq * (self.k1 + 1.0)) / denominator
        return total

    def search(self, query: str, top_k: int = 5,
               min_score: float = 0.0) -> List[BM25Result]:
        """
        Rank documents against a query, best first.

        Ties break on document index so the result is deterministic -- two
        runs over the same corpus must not disagree.
        """
        query_terms = set(self._tokenize(query))
        scored: List[Tuple[float, int]] = []
        for i in range(self.size):
            value = self.score(query, i)
            if value > min_score:
                scored.append((value, i))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [
            BM25Result(
                doc_id=self.doc_ids[i],
                score=round(value, 6),
                matched_terms=sorted(query_terms & set(self.doc_terms[i])),
            )
            for value, i in scored[:top_k]
        ]

    def explain(self, query: str, doc_id: str) -> Dict[str, float]:
        """
        Per-term contribution to one document's score.

        A ranker nobody can inspect is a ranker nobody should trust; this
        shows exactly which terms earned the score.
        """
        if doc_id not in self.doc_ids:
            return {}
        i = self.doc_ids.index(doc_id)
        terms = self.doc_terms[i]
        length = self.doc_lengths[i]
        avg = self.avg_doc_length or 1.0
        out: Dict[str, float] = {}
        for term in self._tokenize(query):
            freq = terms.get(term, 0)
            if not freq:
                continue
            denominator = freq + self.k1 * (
                1.0 - self.b + self.b * (length / avg))
            out[term] = round(
                self.idf(term) * (freq * (self.k1 + 1.0)) / denominator, 6)
        return out


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]],
                           k: int = 60) -> List[Tuple[str, float]]:
    """
    Combine several ranked lists into one, by rank rather than by score.

    RRF is used here instead of a weighted score blend because BM25 scores
    and cosine similarities are on different, incomparable scales -- adding
    them with weights is a made-up number. Rank position is comparable.

    `k=60` is the constant from Cormack et al. (2009); it damps the influence
    of the very top position so one ranker cannot dominate outright.
    """
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


def hybrid_search(bm25: BM25Index, query: str, dense_ranking: Sequence[str],
                  top_k: int = 5) -> List[Tuple[str, float]]:
    """
    Fuse BM25 with an existing dense/TF-IDF ranking via RRF.

    `dense_ranking` is a list of doc_ids already ordered by the other ranker
    (for example `VectorStore.search`). Keeping it as an argument rather than
    calling into the vector store keeps this module dependency-free and
    testable without building an embedding index.
    """
    lexical = [r.doc_id for r in bm25.search(query, top_k=max(top_k * 4, 20))]
    return reciprocal_rank_fusion([lexical, list(dense_ranking)])[:top_k]
