import math
import os
import random
import threading
import unittest
from typing import Tuple
from unittest.mock import patch

from saleha.core.platform import circuit_breaker as cb
from saleha.core.platform.circuit_breaker import (
    Admission,
    AttemptOutcome,
    BreakerPolicy,
    BreakerSnapshot,
    CircuitBreaker,
    CircuitState,
    Health,
    InMemoryBreakerStore,
    RetryPolicy,
    admit_call,
    classify_status,
    next_delay,
    parse_retry_after,
    record_result,
    reset_shared_breaker,
    shared_breaker,
)

POLICY = BreakerPolicy(failure_threshold=2, open_seconds=10.0)
CLOSED_CALL = Admission(True)


def opened(at: float = 0.0, failures: int = 2) -> BreakerSnapshot:  # an OPEN snapshot as a store would hold it
    return BreakerSnapshot(state=CircuitState.OPEN, failures=failures, opened_at=at, last_error="refused")


class TransitionTests(unittest.TestCase):
    """The pure state machine: every edge, including the racy ones."""

    def test_closed_admits_without_changing_state(self) -> None:
        snap = BreakerSnapshot()
        new, adm = admit_call(snap, 0.0, POLICY)
        self.assertIs(new, snap)
        self.assertEqual(adm, Admission(True))

    def test_consecutive_failures_open_the_circuit(self) -> None:
        one = record_result(BreakerSnapshot(), CLOSED_CALL, Health.UNHEALTHY, 1.0, POLICY, "refused")
        self.assertEqual((one.state, one.failures, one.last_error), (CircuitState.CLOSED, 1, "refused"))
        two = record_result(one, CLOSED_CALL, Health.UNHEALTHY, 2.0, POLICY, "timeout")
        self.assertEqual((two.state, two.failures, two.opened_at, two.last_error),
                         (CircuitState.OPEN, 2, 2.0, "timeout"))

    def test_a_success_between_failures_resets_the_count(self) -> None:
        one = record_result(BreakerSnapshot(), CLOSED_CALL, Health.UNHEALTHY, 1.0, POLICY, "refused")
        healed = record_result(one, CLOSED_CALL, Health.HEALTHY, 2.0, POLICY)
        self.assertEqual(healed, BreakerSnapshot())
        clean = BreakerSnapshot()
        self.assertIs(record_result(clean, CLOSED_CALL, Health.HEALTHY, 3.0, POLICY), clean)

    def test_unknown_outcome_changes_nothing_while_closed(self) -> None:
        one = record_result(BreakerSnapshot(), CLOSED_CALL, Health.UNHEALTHY, 1.0, POLICY, "refused")
        self.assertIs(record_result(one, CLOSED_CALL, Health.UNKNOWN, 2.0, POLICY), one)

    def test_open_circuit_rejects_until_the_cool_down_ends(self) -> None:
        snap, adm = admit_call(opened(at=100.0), 104.0, POLICY)
        self.assertFalse(adm.allowed)
        self.assertEqual(adm.retry_after, 6.0)
        self.assertEqual(adm.reason, "circuit open after 2 failure(s): refused")
        self.assertIs(snap.state, CircuitState.OPEN)

    def test_after_the_cool_down_exactly_one_probe_goes_through(self) -> None:
        snap, first = admit_call(opened(at=100.0), 110.0, POLICY)
        self.assertEqual((first.allowed, first.probe, first.epoch), (True, True, 1))
        self.assertEqual((snap.state, snap.probes, snap.epoch), (CircuitState.HALF_OPEN, 1, 1))
        snap, second = admit_call(snap, 110.5, POLICY)
        self.assertFalse(second.allowed)
        self.assertEqual(second.retry_after, 0.0)
        self.assertIn("a probe is in flight", second.reason)

    def test_probe_success_closes_and_keeps_the_epoch(self) -> None:
        snap, probe = admit_call(opened(at=0.0), 10.0, POLICY)
        closed = record_result(snap, probe, Health.HEALTHY, 11.0, POLICY)
        self.assertEqual(closed, BreakerSnapshot(epoch=1))

    def test_probe_failure_reopens_with_a_fresh_cool_down(self) -> None:
        snap, probe = admit_call(opened(at=0.0), 10.0, POLICY)
        reopened = record_result(snap, probe, Health.UNHEALTHY, 12.0, POLICY, "still refused")
        self.assertEqual((reopened.state, reopened.opened_at, reopened.failures, reopened.probes),
                         (CircuitState.OPEN, 12.0, 3, 0))
        self.assertEqual(reopened.last_error, "still refused")
        kept = record_result(snap, probe, Health.UNHEALTHY, 12.0, POLICY, "")
        self.assertEqual(kept.last_error, "refused")  # no new detail: the old one stays

    def test_cancelled_probe_hands_its_slot_back(self) -> None:
        snap, probe = admit_call(opened(at=0.0), 10.0, POLICY)
        released = record_result(snap, probe, Health.UNKNOWN, 11.0, POLICY)
        self.assertEqual((released.state, released.probes), (CircuitState.HALF_OPEN, 0))
        _, again = admit_call(released, 11.5, POLICY)
        self.assertTrue(again.probe)

    def test_a_late_probe_from_an_earlier_round_decides_nothing(self) -> None:
        snap, old_probe = admit_call(opened(at=0.0), 10.0, POLICY)
        snap = record_result(snap, old_probe, Health.UNHEALTHY, 11.0, POLICY, "refused")
        snap, new_probe = admit_call(snap, 30.0, POLICY)
        self.assertEqual(new_probe.epoch, 2)
        self.assertIs(record_result(snap, old_probe, Health.HEALTHY, 31.0, POLICY), snap)

    def test_results_of_earlier_calls_do_not_decide_an_open_circuit(self) -> None:
        snap = opened(at=0.0)
        self.assertIs(record_result(snap, CLOSED_CALL, Health.HEALTHY, 1.0, POLICY), snap)
        half, _ = admit_call(snap, 10.0, POLICY)
        self.assertIs(record_result(half, CLOSED_CALL, Health.UNHEALTHY, 11.0, POLICY), half)

    def test_second_probe_counts_as_an_ordinary_result_once_the_first_closed_it(self) -> None:
        two = BreakerPolicy(failure_threshold=2, open_seconds=10.0, half_open_probes=2)
        snap, a = admit_call(opened(at=0.0), 10.0, two)
        snap, b = admit_call(snap, 10.1, two)
        self.assertTrue(b.probe)
        snap = record_result(snap, a, Health.HEALTHY, 11.0, two)
        snap = record_result(snap, b, Health.UNHEALTHY, 11.5, two, "flaky")
        self.assertEqual((snap.state, snap.failures), (CircuitState.CLOSED, 1))

    def test_policy_rejects_values_that_would_never_open_or_never_close(self) -> None:
        for kwargs in ({"failure_threshold": 0}, {"open_seconds": 0.0}, {"open_seconds": math.nan},
                       {"open_seconds": math.inf}, {"half_open_probes": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BreakerPolicy(**kwargs)  # type: ignore[arg-type]


class StoreAndBreakerTests(unittest.TestCase):
    def test_store_applies_each_step_atomically_across_threads(self) -> None:
        store = InMemoryBreakerStore()

        def bump(snap: BreakerSnapshot) -> Tuple[BreakerSnapshot, None]:
            return BreakerSnapshot(failures=snap.failures + 1), None

        threads = [threading.Thread(target=lambda: [store.transact("k", bump) for _ in range(2000)])
                   for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(store.get("k").failures, 16000)
        self.assertEqual(store.get("other"), BreakerSnapshot())
        store.clear()
        self.assertEqual(store.get("k"), BreakerSnapshot())

    def test_breaker_walks_the_whole_cycle_and_logs_each_move(self) -> None:
        now = [0.0]
        breaker = CircuitBreaker(POLICY, clock=lambda: now[0])
        log = "saleha.core.platform.circuit_breaker"
        breaker.record("u", breaker.admit("u"), Health.UNHEALTHY, "refused")
        with self.assertLogs(log, "WARNING") as opened_log:
            breaker.record("u", breaker.admit("u"), Health.UNHEALTHY, "refused")
        self.assertIn("circuit u opened for 10s: refused", opened_log.output[0])
        self.assertFalse(breaker.admit("u").allowed)
        now[0] = 10.0
        with self.assertLogs(log, "INFO") as probe_log:
            probe = breaker.admit("u")
        self.assertIn("half-open", probe_log.output[0])
        with self.assertLogs(log, "INFO") as close_log:
            after = breaker.record("u", probe, Health.HEALTHY)
        self.assertIn("circuit u closed", close_log.output[0])
        self.assertIs(after.state, CircuitState.CLOSED)
        self.assertEqual(breaker.snapshot("u"), after)

    def test_keys_are_independent(self) -> None:
        breaker = CircuitBreaker(BreakerPolicy(failure_threshold=1))
        breaker.record("a", breaker.admit("a"), Health.UNHEALTHY, "down")
        self.assertFalse(breaker.admit("a").allowed)
        self.assertTrue(breaker.admit("b").allowed)


class RetryPolicyTests(unittest.TestCase):
    def test_full_jitter_stays_under_a_doubling_capped_ceiling(self) -> None:
        policy = RetryPolicy(max_attempts=10, base_delay=0.5, max_delay=4.0)
        rng = random.Random(7)
        for retry, ceiling in ((1, 0.5), (2, 1.0), (3, 2.0), (4, 4.0), (9, 4.0), (500, 4.0)):
            delays = [policy.backoff(retry, rng) for _ in range(200)]
            self.assertTrue(all(0.0 <= d <= ceiling for d in delays), (retry, max(delays)))
            self.assertGreater(max(delays), ceiling * 0.8)  # really spread, not pinned at 0

    def test_retry_after_wins_but_is_capped(self) -> None:
        policy = RetryPolicy(max_delay=4.0)
        self.assertEqual(policy.backoff(1, random.Random(), retry_after=1.5), 1.5)
        self.assertEqual(policy.backoff(1, random.Random(), retry_after=60.0), 4.0)

    def test_policy_rejects_nonsense(self) -> None:
        for kwargs in ({"max_attempts": 0}, {"base_delay": -1.0}, {"base_delay": 5.0, "max_delay": 1.0},
                       {"max_delay": math.inf}, {"base_delay": math.nan}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                RetryPolicy(**kwargs)  # type: ignore[arg-type]

    def test_next_delay_stops_for_each_reason(self) -> None:
        policy = RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=1.0)
        rng = random.Random(1)
        transient = AttemptOutcome(Health.UNHEALTHY, retryable=True, retry_after=0.5)
        self.assertEqual(next_delay(policy, 1, transient, 10.0, rng), 0.5)
        self.assertIsNone(next_delay(policy, 3, transient, 10.0, rng))  # out of attempts
        self.assertIsNone(next_delay(policy, 1, transient, 0.5, rng))  # would sleep to the deadline
        final = AttemptOutcome(Health.UNHEALTHY, retryable=False)
        self.assertIsNone(next_delay(policy, 1, final, 10.0, rng))


class HttpClassificationTests(unittest.TestCase):
    def test_status_table(self) -> None:
        table = {200: (Health.HEALTHY, False), 204: (Health.HEALTHY, False),
                 400: (Health.HEALTHY, False), 404: (Health.HEALTHY, False),
                 408: (Health.UNHEALTHY, True), 429: (Health.UNHEALTHY, True),
                 500: (Health.UNHEALTHY, False), 501: (Health.UNHEALTHY, False),
                 502: (Health.UNHEALTHY, True), 503: (Health.UNHEALTHY, True),
                 504: (Health.UNHEALTHY, True), 101: (Health.UNKNOWN, False),
                 302: (Health.UNKNOWN, False), 600: (Health.UNKNOWN, False)}
        for status, expected in table.items():
            with self.subTest(status=status):
                self.assertEqual(classify_status(status), expected)

    def test_retry_after_accepts_only_sane_seconds(self) -> None:
        cases = {"3": 3.0, " 1.5 ": 1.5, "0": 0.0, None: None, "": None, "-1": None, "nan": None,
                 "inf": None, "Wed, 21 Oct 2015 07:28:00 GMT": None}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_retry_after(raw), expected)


class SharedBreakerTests(unittest.TestCase):
    def test_one_breaker_per_process_and_reset_keeps_it(self) -> None:
        first = shared_breaker()
        first.record("x", first.admit("x"), Health.UNHEALTHY, "down")
        reset_shared_breaker()
        self.assertIs(shared_breaker(), first)
        self.assertEqual(first.snapshot("x"), BreakerSnapshot())

    def test_policy_comes_from_the_environment(self) -> None:
        env = {"SALEHA_BREAKER_FAILURES": "5", "SALEHA_BREAKER_OPEN_SECONDS": "2.5"}
        with patch.dict(os.environ, env), patch.object(cb, "_shared", None):
            self.assertEqual(shared_breaker().policy, BreakerPolicy(failure_threshold=5, open_seconds=2.5))

    def test_bad_environment_values_fall_back_to_the_defaults_loudly(self) -> None:
        for env in ({"SALEHA_BREAKER_FAILURES": "many"}, {"SALEHA_BREAKER_OPEN_SECONDS": "0"}):
            with self.subTest(env=env), patch.dict(os.environ, env), patch.object(cb, "_shared", None), \
                    self.assertLogs("saleha.core.platform.circuit_breaker", "WARNING") as logs:
                self.assertEqual(shared_breaker().policy, BreakerPolicy())
            self.assertIn("ignoring SALEHA_BREAKER_* settings", logs.output[0])


if __name__ == "__main__":
    unittest.main()
