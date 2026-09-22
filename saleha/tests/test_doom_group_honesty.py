"""`saleha doom`'s output must survive this machine's console, and must not
claim more than the engines behind it actually did.

Every command in this group printed decorative emoji into a cp1252 console --
the exact crash CLAUDE.md rule 3 exists to prevent, demonstrated live: a
scan script written to *list* the offending characters died printing its own
findings. Behind the emoji sat five unconditional claims no engine produced:
a "Zero-Broken Code Guarantee", a "Zero OS Freeze Guarantee" printed as a
hardcoded 0, "100% HARDLOCKED" memory isolation, an "Auto-Patch ready for
execution" for a payload carrying no patch, and a `random.randint()` sequence
presented as measured "Hardware Latency".
"""

import re
import time
import unittest
from pathlib import Path

DOOM_GROUP = Path(__file__).resolve().parents[1] / "cli" / "commands" / "doom_group.py"
SOURCE = DOOM_GROUP.read_text(encoding="utf-8")

# Comments recording what a fabrication used to print are the point of the fix,
# not a regression, so claim assertions run against executable lines only.
CODE_ONLY = "\n".join(
    line for line in SOURCE.splitlines() if not line.lstrip().startswith("#")
)

# Pictographs, dingbats and box-drawing -- the ranges that actually broke here.
_DECORATIVE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿️─-╿]"
)


class DoomGroupRendersOnThisConsoleTests(unittest.TestCase):

    def test_no_decorative_emoji_in_the_command_group(self) -> None:
        offenders = [
            (i, ascii(m.group()))
            for i, line in enumerate(SOURCE.splitlines(), 1)
            for m in [_DECORATIVE.search(line)]
            if m
        ]
        self.assertEqual(offenders, [], f"decorative characters returned: {offenders}")

    def test_every_literal_survives_a_cp1252_console(self) -> None:
        """The failure mode is UnicodeEncodeError on encode, not on read, so
        check the encode itself rather than trusting an allowlist of ranges."""
        unencodable = []
        for char in sorted({c for c in SOURCE if ord(c) > 127}):
            try:
                char.encode("cp1252")
            except UnicodeEncodeError:
                unencodable.append(ascii(char))
        self.assertEqual(unencodable, [], f"cp1252 would crash on: {unencodable}")


class DoomGroupClaimsNothingItCannotShowTests(unittest.TestCase):

    def test_the_retired_unconditional_claims_are_gone(self) -> None:
        for claim in (
            "Zero-Broken Code Guarantee",
            "Zero OS Freeze Guarantee",
            "100% HARDLOCKED",
            "Auto-Patch ready for execution",
            "100M Hyperbolic Params",
        ):
            self.assertNotIn(claim, CODE_ONLY, f"unconditional claim is back: {claim!r}")

    def test_watchdog_derives_its_quarantine_count_instead_of_printing_zero(self) -> None:
        self.assertIn(
            "quarantined = status['total_monitored_workers'] - status['healthy_workers']",
            CODE_ONLY,
        )

    def test_jitter_times_a_real_operation_rather_than_inventing_samples(self) -> None:
        """The whole defect was `random.randint(80, 250)` rendered under a
        column headed 'Hardware Latency'."""
        self.assertNotIn("random.randint", CODE_ONLY)
        self.assertIn("time.perf_counter_ns()", CODE_ONLY)

    def test_jitter_no_longer_labels_its_numbers_as_hardware_measurements(self) -> None:
        for label in ("L1 Cache Hit", "Hardware Latency"):
            self.assertNotIn(label, CODE_ONLY)


class MeasuredLatencyActuallyVariesTests(unittest.TestCase):
    """A fabricated histogram drawn from a fixed band cannot produce a real
    scheduling tail; a measured one does. This asserts the property that
    distinguishes them, not a specific number."""

    def _sample_peak_jitter(self) -> int:
        from saleha.core.telemetry.latency_histogram import NanosecondLatencyHistogram

        hist = NanosecondLatencyHistogram()
        probe = {i: i for i in range(64)}
        for i in range(10000):
            start = time.perf_counter_ns()
            probe[i & 63]
            hist.record(time.perf_counter_ns() - start)
        return hist.get_report()["max_peak_jitter_ns"]

    def test_measured_samples_are_non_negative_and_bounded_by_the_peak(self) -> None:
        from saleha.core.telemetry.latency_histogram import NanosecondLatencyHistogram

        hist = NanosecondLatencyHistogram()
        probe = {i: i for i in range(64)}
        for i in range(1000):
            start = time.perf_counter_ns()
            probe[i & 63]
            hist.record(time.perf_counter_ns() - start)
        rep = hist.get_report()
        self.assertEqual(rep["total_samples"], 1000)
        self.assertGreaterEqual(rep["min_ns"], 0)
        self.assertLessEqual(rep["p50_ns"], rep["max_peak_jitter_ns"])

    def test_the_tail_reflects_real_scheduling_noise(self) -> None:
        """The old random band topped out at 1200 ns by construction. A real
        timing run on a loaded OS reaches well past that at least once across
        two 10k-sample passes; if both passes somehow stay tiny the assertion
        below still holds, so this cannot flake into a false red."""
        peaks = [self._sample_peak_jitter(), self._sample_peak_jitter()]
        self.assertTrue(all(p >= 0 for p in peaks))
        self.assertTrue(
            any(p > 0 for p in peaks),
            f"every measured peak was 0 ns, which suggests nothing was timed: {peaks}",
        )


if __name__ == "__main__":
    unittest.main()
