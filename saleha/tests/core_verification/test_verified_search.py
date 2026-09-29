import threading
import time
import unittest
from typing import Callable, List, Optional, cast

from saleha.core.verification.verified_search import (
    CandidateOutcome,
    NoCandidate,
    Outcome,
    SearchResult,
    Verification,
    VerifiedSearch,
)


def passes_if(good: str) -> Callable[[str], Verification]:  # accepts exactly one code string
    def verifier(code: str) -> Verification:
        return Verification(Outcome.PASSED if code == good else Outcome.FAILED, code)
    return verifier


def winner_of(res: SearchResult) -> CandidateOutcome:  # the winner, or a failure naming why there is none
    assert res.winner is not None, res.summary()
    return res.winner


class VerifiedSearchTests(unittest.TestCase):
    def test_first_passing_candidate_wins_and_later_ones_never_start(self) -> None:
        started = []

        def source(i: int) -> str:
            started.append(i)
            return f"c{i}"

        res = VerifiedSearch(source, passes_if("c2"), budget=10, concurrency=1).run()
        self.assertTrue(res.found)
        self.assertEqual(winner_of(res).index, 2)
        self.assertEqual(started, [0, 1, 2])
        self.assertEqual([o.outcome for o in res.outcomes],
                         [Outcome.FAILED, Outcome.FAILED, Outcome.PASSED])
        self.assertEqual(res.summary(), "candidate 3 passed (3 of 10 tried: 1 passed, 2 failed)")

    def test_nothing_passes_is_reported_as_not_found(self) -> None:
        res = VerifiedSearch(lambda i: f"c{i}", passes_if("never"), budget=4, concurrency=2).run()
        self.assertFalse(res.found)
        self.assertEqual(res.attempted, 4)
        self.assertEqual([o.index for o in res.outcomes], [0, 1, 2, 3])
        self.assertTrue(res.summary().startswith("no candidate passed (4 of 4 tried"))

    def test_zero_budget_finds_nothing_rather_than_passing(self) -> None:
        res = VerifiedSearch(lambda i: "x", passes_if("x"), budget=0).run()
        self.assertFalse(res.found)
        self.assertEqual(res.summary(), "no candidate passed (0 of 0 tried: none)")

    def test_crashing_source_is_did_not_run_and_search_continues(self) -> None:
        def source(i: int) -> str:
            if i == 0:
                raise ConnectionError("ollama down")
            return "good"

        with self.assertLogs("saleha.core.verification.verified_search", "WARNING") as logs:
            res = VerifiedSearch(source, passes_if("good"), budget=3).run()
        self.assertEqual(res.outcomes[0].outcome, Outcome.DID_NOT_RUN)
        self.assertIn("ConnectionError: ollama down", res.outcomes[0].detail)
        self.assertEqual(winner_of(res).index, 1)
        self.assertIn("source raised ConnectionError", logs.output[0])

    def test_source_can_say_why_it_produced_nothing(self) -> None:
        reasons = ["Ollama not called: circuit open", "Ollama not called: circuit open", ""]

        def source(i: int) -> str:
            raise NoCandidate(reasons[i])

        with self.assertNoLogs("saleha.core.verification.verified_search", "WARNING"):
            res = VerifiedSearch(source, passes_if("x"), budget=3).run()
        self.assertEqual([o.detail for o in res.outcomes],
                         ["Ollama not called: circuit open", "Ollama not called: circuit open",
                          "source produced no code"])
        self.assertEqual({o.outcome for o in res.outcomes}, {Outcome.DID_NOT_RUN})

    def test_failed_search_summary_names_the_most_common_problem(self) -> None:
        outputs = ["a", "b", "a", "c"]
        res = VerifiedSearch(lambda i: outputs[i], lambda code: Verification(Outcome.FAILED, "wrong on [7, 7]"),
                             budget=4).run()
        self.assertEqual(res.summary(), "no candidate passed (4 of 4 tried: 3 failed, 1 duplicate); "
                                        "most often: wrong on [7, 7] (x3)")
        once = VerifiedSearch(lambda i: "a", lambda code: Verification(Outcome.FAILED, "wrong"), budget=1).run()
        self.assertTrue(once.summary().endswith("; most often: wrong"))
        silent = VerifiedSearch(lambda i: "a", lambda code: Verification(Outcome.FAILED), budget=1).run()
        self.assertEqual(silent.summary(), "no candidate passed (1 of 1 tried: 1 failed)")

    def test_empty_or_non_string_code_is_did_not_run(self) -> None:
        outputs: List[Optional[str]] = ["", "   ", None]  # None breaks the protocol on purpose
        res = VerifiedSearch(lambda i: cast(str, outputs[i]), passes_if(""), budget=3).run()
        self.assertFalse(res.found)
        self.assertEqual({o.outcome for o in res.outcomes}, {Outcome.DID_NOT_RUN})
        self.assertEqual(res.outcomes[0].detail, "source produced no code")

    def test_crashing_verifier_is_did_not_run_never_passed(self) -> None:
        def verifier(_code: str) -> Verification:
            raise RuntimeError("subprocess died")

        with self.assertLogs("saleha.core.verification.verified_search", "WARNING"):
            res = VerifiedSearch(lambda i: f"c{i}", verifier, budget=2).run()
        self.assertFalse(res.found)
        self.assertEqual(res.outcomes[0].outcome, Outcome.DID_NOT_RUN)
        self.assertIn("verifier raised RuntimeError", res.outcomes[0].detail)

    def test_verifier_returning_a_bare_true_is_not_a_pass(self) -> None:
        res = VerifiedSearch(lambda i: "c", lambda code: True, budget=1).run()  # type: ignore[arg-type,return-value]
        self.assertFalse(res.found)
        self.assertEqual(res.outcomes[0].outcome, Outcome.DID_NOT_RUN)
        self.assertIn("returned bool", res.outcomes[0].detail)

    def test_duplicates_and_known_code_are_not_re_verified(self) -> None:
        verified = []

        def verifier(code: str) -> Verification:
            verified.append(code)
            return Verification(Outcome.FAILED)

        outputs = ["old bug", "a", " a \n", "b"]
        res = VerifiedSearch(lambda i: outputs[i], verifier, budget=4, known=["old bug\n", "  "]).run()
        self.assertEqual(verified, ["a", "b"])
        self.assertEqual([o.outcome for o in res.outcomes],
                         [Outcome.DUPLICATE, Outcome.FAILED, Outcome.DUPLICATE, Outcome.FAILED])

    def test_attempts_overlap_up_to_the_concurrency_limit(self) -> None:
        lock, live, peak = threading.Lock(), [0], [0]

        def source(i: int) -> str:
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.05)
            with lock:
                live[0] -= 1
            return f"c{i}"

        t0 = time.perf_counter()
        res = VerifiedSearch(source, passes_if("never"), budget=6, concurrency=3).run()
        elapsed = time.perf_counter() - t0
        self.assertEqual(peak[0], 3)
        self.assertEqual(res.attempted, 6)
        self.assertLess(elapsed, 0.25)  # sequential would be >= 0.30

    def test_running_attempts_finish_but_only_one_winner(self) -> None:
        res = VerifiedSearch(lambda i: f"c{i}", lambda code: Verification(Outcome.PASSED),
                             budget=5, concurrency=3).run()
        self.assertIn(winner_of(res).index, (0, 1, 2))  # whichever finished first
        self.assertLessEqual(res.attempted, 3)  # the 4th and 5th never start
        self.assertEqual(sum(o is res.winner for o in res.outcomes), 1)

    def test_clock_is_used_for_timings(self) -> None:
        ticks = iter([10.0, 12.5])
        res = VerifiedSearch(lambda i: "c", passes_if("c"), budget=1, clock=lambda: next(ticks)).run()
        self.assertEqual(winner_of(res).seconds, 2.5)

    def test_invalid_arguments_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "budget"):
            VerifiedSearch(lambda i: "", passes_if(""), budget=-1)
        with self.assertRaisesRegex(ValueError, "concurrency"):
            VerifiedSearch(lambda i: "", passes_if(""), budget=1, concurrency=0)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            Verification(Outcome.DUPLICATE)

    def test_search_result_defaults(self) -> None:
        res = SearchResult(winner=None)
        self.assertEqual((res.found, res.attempted, res.budget), (False, 0, 0))


if __name__ == "__main__":
    unittest.main()
