"""Tests for saleha.core.training_collector."""
import json
import os
import shutil
import tempfile
import unittest

from saleha.core.training_collector import TrainingCollector


class TrainingCollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dataset_dir = os.path.join(self.tmp, "nested", "training_data")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_constructing_does_not_create_directory(self):
        # Regression: importing/constructing this class must not have a
        # filesystem side effect on module import -- the directory should
        # only appear once a sample is actually written.
        TrainingCollector(dataset_dir=self.dataset_dir)
        self.assertFalse(os.path.exists(self.dataset_dir))

    def test_add_sample_creates_directory_and_persists(self):
        tc = TrainingCollector(dataset_dir=self.dataset_dir)
        sample = tc.add_sample("write a function", "def f(): pass", quality_score=0.9)
        self.assertTrue(os.path.exists(self.dataset_dir))
        with open(tc._path, encoding="utf-8") as f:
            line = f.readline()
        data = json.loads(line)
        self.assertEqual(data["sample_id"], sample.sample_id)
        self.assertEqual(data["quality_score"], 0.9)

    def test_load_samples_filters_by_quality_and_source(self):
        tc = TrainingCollector(dataset_dir=self.dataset_dir)
        tc.add_sample("a", "b", quality_score=0.9, source="session")
        tc.add_sample("c", "d", quality_score=0.3, source="manual")
        high = tc.load_samples(min_quality=0.7)
        self.assertEqual(len(high), 1)
        self.assertEqual(high[0].source, "session")
        manual_only = tc.load_samples(min_quality=0.0, source_filter="manual")
        self.assertEqual(len(manual_only), 1)
        self.assertEqual(manual_only[0].source, "manual")

    def test_stats_reports_real_counts(self):
        tc = TrainingCollector(dataset_dir=self.dataset_dir)
        tc.add_sample("a", "b", quality_score=0.9)
        tc.add_sample("c", "d", quality_score=0.5)
        stats = tc.stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["high_quality"], 1)

    def test_identical_sample_is_stored_once(self) -> None:
        tc = TrainingCollector(dataset_dir=self.tmp)
        first = tc.add_sample("p", "c", quality_score=0.9)
        again = tc.add_sample("p", "c", quality_score=0.9)
        tc.add_sample("p", "different", quality_score=0.9)

        self.assertEqual(first.sample_id, again.sample_id)
        self.assertEqual(tc.stats()["total"], 2)

    def test_export_drops_duplicates_already_on_disk(self) -> None:
        tc = TrainingCollector(dataset_dir=self.tmp)
        tc.add_sample("p", "c", quality_score=0.9)
        with open(tc._path, "r", encoding="utf-8") as f:
            line = f.readline()
        with open(tc._path, "a", encoding="utf-8") as f:
            f.write(line)  # the duplicate an older version would have written
        out = os.path.join(self.tmp, "out.json")

        self.assertEqual(tc.export_alpaca(out), 1)
        self.assertEqual(tc.export_sharegpt(os.path.join(self.tmp, "out.jsonl")), 1)

    def test_export_alpaca_and_sharegpt_formats(self):
        tc = TrainingCollector(dataset_dir=self.dataset_dir)
        tc.add_sample("prompt1", "completion1", quality_score=0.95)
        alpaca_path = os.path.join(self.tmp, "alpaca.json")
        sharegpt_path = os.path.join(self.tmp, "sharegpt.jsonl")
        count_a = tc.export_alpaca(alpaca_path)
        count_s = tc.export_sharegpt(sharegpt_path)
        self.assertEqual(count_a, 1)
        self.assertEqual(count_s, 1)
        with open(alpaca_path, encoding="utf-8") as f:
            alpaca_data = json.load(f)
        self.assertEqual(alpaca_data[0]["instruction"], "prompt1")
        with open(sharegpt_path, encoding="utf-8") as f:
            sharegpt_line = json.loads(f.readline())
        self.assertEqual(sharegpt_line["conversations"][0]["value"], "prompt1")


if __name__ == "__main__":
    unittest.main()
