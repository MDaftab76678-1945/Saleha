"""The Rust intent kernel as an external anchor for the WorkLedger.

These run the real `ik` binary. Without it they skip, and say how to build it.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from saleha.cli.commands import cli
from saleha.core import intent_kernel
from saleha.core.verification.work_ledger import WorkLedger, _canonical, _sha256

_HAS_IK = intent_kernel.find_ik() is not None


@unittest.skipUnless(_HAS_IK, f"intent kernel not built ({intent_kernel.BUILD_HINT})")
class KernelBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.proof = str(Path(self._tmp.name) / "anchor.jsonl")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_append_then_verify(self) -> None:
        first = intent_kernel.append_event(self.proof, "m", "e", {"a": 1}, {"b": 2})
        second = intent_kernel.append_event(self.proof, "m", "e", {"a": 2}, {"b": 3})
        self.assertTrue(first["ok"], first)
        self.assertEqual(second["prev_hash"], first["hash"])
        self.assertEqual(intent_kernel.verify_ledger(self.proof),
                         {"available": True, "valid": True, "events": 2, "detail": ""})

    def test_kernel_detects_and_refuses_a_tampered_ledger(self) -> None:
        intent_kernel.append_event(self.proof, "m", "e", {"a": 1}, {"b": 2})
        events = intent_kernel.read_events(self.proof)
        events[0]["output"] = {"b": 999}
        Path(self.proof).write_text(json.dumps(events[0]) + "\n", encoding="utf-8")
        self.assertFalse(intent_kernel.verify_ledger(self.proof)["valid"])
        refused = intent_kernel.append_event(self.proof, "m", "e", {}, {})
        self.assertFalse(refused["ok"])
        self.assertIn("integrity", refused["detail"])


@unittest.skipUnless(_HAS_IK, f"intent kernel not built ({intent_kernel.BUILD_HINT})")
class WorkLedgerAnchorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self._tmp.name)
        self.root = str(root)
        self.ledger = str(root / "work.jsonl")
        self.anchor = str(root / "outside" / "anchor.jsonl")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _ledger(self) -> WorkLedger:
        return WorkLedger(self.ledger, root_dir=self.root, anchor_path=self.anchor)

    def test_every_entry_is_anchored(self) -> None:
        wl = self._ledger()
        for text in ("one", "two", "three"):
            wl.record_assertion("agent", "goal", text)
            self.assertEqual(wl.anchor_note, "")
        report = self._ledger().verify(recheck=False)
        self.assertTrue(report["chain_intact"], report["chain_detail"])
        self.assertTrue(report["external_anchor_ok"])

    def test_entry_written_while_kernel_was_missing_is_not_called_tampering(self) -> None:
        with patch.dict(os.environ, {"SALEHA_IK": os.path.join(self.root, "no-ik.exe")}):
            self._ledger().record_assertion("agent", "goal", "kernel missing")
        self._ledger().record_assertion("agent", "goal", "kernel back")
        report = self._ledger().verify(recheck=False)
        self.assertTrue(report["chain_intact"], report["chain_detail"])
        self.assertIsNone(report["external_anchor_ok"])
        self.assertIn("never anchored", report["external_anchor_detail"])

    def test_path_case_does_not_matter(self) -> None:
        self._ledger().record_assertion("agent", "goal", "one")
        other_case = WorkLedger(self.ledger.swapcase() if os.name == "nt" else self.ledger,
                                root_dir=self.root, anchor_path=self.anchor)
        self.assertTrue(other_case.verify(recheck=False)["external_anchor_ok"])

    def test_deleted_entry_with_recomputed_chain_is_caught(self) -> None:
        """The attack work_ledger.py documents: delete an entry, renumber,
        recompute every hash. The file alone then verifies cleanly."""
        wl = self._ledger()
        for text in ("kept", "inconvenient", "kept too"):
            wl.record_assertion("agent", "goal", text)

        rows = [json.loads(ln) for ln in Path(self.ledger).read_text(encoding="utf-8").splitlines()]
        del rows[1]
        prev = "genesis"
        for seq, row in enumerate(rows):
            row["seq"], row["prev_hash"] = seq, prev
            payload = {k: row[k] for k in ("seq", "actor", "goal", "claim", "prev_hash", "version")}
            row["hash"] = prev = _sha256(_canonical(payload))
        Path(self.ledger).write_text("".join(_canonical(r) + "\n" for r in rows), encoding="utf-8")

        doctored = self._ledger()
        self.assertTrue(doctored.verify_chain()[0], "the file-only check is fooled")
        report = doctored.verify(recheck=False)
        self.assertFalse(report["external_anchor_ok"])
        self.assertFalse(report["chain_intact"])
        self.assertIn("removed", report["external_anchor_detail"])


class WorkLedgerWithoutKernelTests(unittest.TestCase):
    def test_no_anchor_configured_is_not_checked(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            wl = WorkLedger(os.path.join(tmp, "w.jsonl"), root_dir=tmp)
            wl.record_assertion("agent", "goal", "x")
            report = wl.verify(recheck=False)
        self.assertIsNone(report["external_anchor_ok"])
        self.assertEqual(report["external_anchor_detail"], "no external anchor configured")

    def test_missing_kernel_is_reported_not_passed(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
                patch.dict(os.environ, {"SALEHA_IK": os.path.join(tmp, "no-such-ik.exe")}):
            wl = WorkLedger(os.path.join(tmp, "w.jsonl"), root_dir=tmp,
                            anchor_path=os.path.join(tmp, "a.jsonl"))
            wl.record_assertion("agent", "goal", "x")
            self.assertIn("not anchored", wl.anchor_note)
            report = wl.verify(recheck=False)
        self.assertIsNone(report["external_anchor_ok"])
        self.assertIn("not built", report["external_anchor_detail"])


@unittest.skipUnless(_HAS_IK, f"intent kernel not built ({intent_kernel.BUILD_HINT})")
class NativeKernelCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_kernel_status_and_arch(self) -> None:
        res = intent_kernel.get_status()
        self.assertEqual(res.get("returncode"), 0)
        self.assertTrue(intent_kernel.is_available())

        arch = intent_kernel.get_architecture()
        self.assertEqual(arch.get("returncode"), 0)

    def test_cli_ik_status_and_arch(self) -> None:
        res = self.runner.invoke(cli, ["ik", "status"])
        self.assertEqual(res.exit_code, 0)

        res_arch = self.runner.invoke(cli, ["ik", "arch"])
        self.assertEqual(res_arch.exit_code, 0)

    def test_aborted_mission_is_not_reported_as_success(self) -> None:
        # The kernel refuses plans that need human approval; that refusal
        # used to exit 0 and render as a green "result".
        res = intent_kernel.run_mission("Inspect memory ledger", dry_run=True)
        self.assertNotEqual(res.get("returncode"), 0)
        self.assertIn("nothing was executed", res.get("stderr", ""))

    def test_cli_ik_run_aborted_exits_nonzero(self) -> None:
        res = self.runner.invoke(cli, ["ik", "run", "--dry-run", "Inspect memory ledger"])
        self.assertNotEqual(res.exit_code, 0)
        self.assertIn("Kernel Mission Error", res.output)
        self.assertIn("Aborted for safety", res.output)

    def test_cli_saleha_run_native_aborted_exits_nonzero(self) -> None:
        res = self.runner.invoke(cli, ["run", "--native", "Inspect memory ledger"])
        self.assertNotEqual(res.exit_code, 0)
        self.assertIn("Native Kernel Error", res.output)


@unittest.skipUnless(_HAS_IK, f"intent kernel not built ({intent_kernel.BUILD_HINT})")
class NativeKernelNoModelTests(unittest.TestCase):
    """A model that cannot answer must never yield a "solved"/"approved" result.

    The kernel used to substitute a TODO stub that printed "Executing: <task>",
    run it, and report it as verified.
    """

    _MODEL = "no-such-model-for-saleha-tests:1b"

    def setUp(self) -> None:
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.chdir(self._tmp.name)  # the kernel writes .ik/ and generated_code.* into cwd

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_solve_without_model_fails(self) -> None:
        res = intent_kernel.solve_task("reverse a string", model=self._MODEL,
                                       max_attempts=1, timeout=120)
        self.assertNotEqual(res.get("returncode"), 0, res)
        self.assertNotIn("SOLVED", res.get("stdout", "").replace("not solved", ""))
        self.assertFalse(Path("generated_code.py").exists())

    def test_autocode_without_model_is_rejected(self) -> None:
        res = intent_kernel.autocode_task("reverse a string", model=self._MODEL, timeout=120)
        self.assertNotEqual(res.get("returncode"), 0, res)
        self.assertIn("Mission rejected", res.get("stdout", ""))
        self.assertNotIn("Executing: reverse a string", res.get("stdout", ""))


class NativeKernelMissingTests(unittest.TestCase):
    def test_cli_ik_status_without_kernel_exits_nonzero(self) -> None:
        with patch.object(intent_kernel, "find_ik", return_value=None):
            for cmd in (["ik", "status"], ["ik", "arch"]):
                res = CliRunner().invoke(cli, cmd)
                self.assertNotEqual(res.exit_code, 0, cmd)

    def test_cli_ik_run_timeout_shows_detail(self) -> None:
        fake = {"available": False, "detail": "timed out after 1 seconds"}
        with patch.object(intent_kernel, "find_ik", return_value="ik"), \
                patch.object(intent_kernel, "run_mission", return_value=fake):
            res = CliRunner().invoke(cli, ["ik", "run", "x"])
        self.assertEqual(res.exit_code, 1)
        self.assertIn("timed out", res.output)


if __name__ == "__main__":
    unittest.main()
