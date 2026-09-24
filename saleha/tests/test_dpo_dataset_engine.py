"""Tests for the curated DPO dataset engine and the DPO tuner's data gate.

The earlier version of these tests required build_dataset(target_count=50) to
return >= 50 pairs, which only the padding (one stub per language with the
topic name pasted in) could satisfy.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from saleha.core.dpo_dataset_engine import (
    MIN_DPO_PAIRS,
    POLYGLOT_DPO_TEMPLATES,
    SalehaDPODatasetEngine,
)
from saleha.core.lora_tuner import LoRATuner


class TestDPODatasetEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_dpo_")
        self.engine = SalehaDPODatasetEngine(output_dir=self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_never_pads_past_the_curated_pairs(self) -> None:
        dpo_count, sft_count = self.engine.build_dataset(target_count=1000)

        self.assertEqual(dpo_count, len(POLYGLOT_DPO_TEMPLATES))
        self.assertEqual(sft_count, dpo_count)
        self.assertEqual(len({p.chosen for p in self.engine.dpo_pairs}), dpo_count)
        self.assertFalse(any("(Task #" in p.prompt for p in self.engine.dpo_pairs))

    def test_target_count_caps_the_output(self) -> None:
        self.assertEqual(self.engine.build_dataset(target_count=2), (2, 2))
        self.assertEqual(self.engine.build_dataset(target_count=0), (0, 0))

    def test_dpo_pair_schema(self) -> None:
        self.engine.build_dataset()
        for pair in self.engine.dpo_pairs:
            self.assertTrue(pair.prompt and pair.chosen and pair.rejected)
            self.assertNotEqual(pair.chosen, pair.rejected)
            self.assertIn(pair.language, ["python", "typescript", "go", "rust", "sql"])
            self.assertEqual(pair.to_dict()["margin_score"], 1.0)

    def test_export_files_hold_exactly_the_curated_pairs(self) -> None:
        self.engine.build_dataset()
        paths = (self.engine.export_dpo_jsonl(), self.engine.export_sft_jsonl())
        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(sum(1 for line in f if line.strip()), len(POLYGLOT_DPO_TEMPLATES))
        with open(self.engine.export_alpaca_json(), "r", encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)), len(POLYGLOT_DPO_TEMPLATES))

    def _python_pair(self, keyword: str):
        return next(t for t in POLYGLOT_DPO_TEMPLATES if t[1] == "python" and keyword in t[0])

    def test_sql_chosen_is_safe_and_rejected_is_injectable(self) -> None:
        _, _, _, chosen, rejected = self._python_pair("database")
        db = os.path.join(self.temp_dir, "users.db")
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE users (id INTEGER, username TEXT, email TEXT, role TEXT, "
                         "created_at TEXT, is_active INTEGER)")
            conn.execute("INSERT INTO users VALUES (1, 'alice', 'a@x', 'admin', 't', 1)")
            conn.execute("INSERT INTO users VALUES (2, 'bob', 'b@x', 'user', 't', 1)")
        attack = "' OR 1=1 --"

        ns_good: dict = {}
        exec(chosen, ns_good)  # saleha: allow-exec
        ns_bad: dict = {}
        exec(rejected, ns_bad)  # saleha: allow-exec

        self.assertEqual([r["username"] for r in ns_good["get_active_users"](db, "alice", "admin")], ["alice"])
        self.assertEqual(ns_good["get_active_users"](db, attack, "user"), [])
        self.assertEqual(len(ns_bad["get_active_users"](db, attack, "user")), 2)

    def test_fetcher_chosen_really_retries_and_gives_up(self) -> None:
        import asyncio

        _, _, _, chosen, _ = self._python_pair("HTTP client")
        self.assertNotIn("Simulated", chosen)
        ns: dict = {}
        exec(chosen, ns)  # saleha: allow-exec
        calls = []
        fetcher = ns["ResilientAsyncFetcher"](max_retries=2, timeout=1.0)

        def failing_get(url: str) -> bytes:
            calls.append(url)
            raise ns["urllib"].error.URLError("unreachable")

        fetcher._get = failing_get
        ns["asyncio"].sleep = self._no_sleep
        self.assertIsNone(asyncio.run(fetcher.fetch("http://127.0.0.1:9/")))
        self.assertEqual(len(calls), 3)

    @staticmethod
    async def _no_sleep(_: float) -> None:
        return None

    def test_dpo_tuner_refuses_too_few_pairs_without_synthesizing(self) -> None:
        few = os.path.join(self.temp_dir, "few.jsonl")
        self.engine.build_dataset()
        self.engine.export_dpo_jsonl(few)
        missing = os.path.join(self.temp_dir, "missing.jsonl")
        tuner = LoRATuner(work_dir=os.path.join(self.temp_dir, "tuner"))

        for path in (few, missing):
            res = tuner.tune_dpo(dpo_dataset_path=path)
            self.assertFalse(res.success)
            self.assertIn(f"need >= {MIN_DPO_PAIRS}", res.error)
        self.assertFalse(os.path.exists(missing), "no pairs may be synthesized to fill the gap")

    @unittest.skipUnless(
        os.environ.get("SALEHA_RUN_GPU_TESTS") == "1",
        "real DPO training is minutes of GPU time; set SALEHA_RUN_GPU_TESTS=1 to run it",
    )
    def test_lora_tuner_dpo(self) -> None:
        """Real DPO attempt against datasets/saleha_dpo_pairs.jsonl. With only
        the curated pairs it must refuse with a real reason, never fake success."""
        res = LoRATuner().tune_dpo()
        self.assertEqual(res.output_model, "saleha-dpo-slm")
        if res.success:
            self.assertIsInstance(res.after_score, float)
        else:
            self.assertTrue(res.error)


if __name__ == "__main__":
    unittest.main()
