"""
Unit tests for the STRIDE mitigation checklist.

The old suite ran against an empty temp directory and asserted
`total_threats >= 6`, which pinned the defect: `analyze_workspace` took a
directory, stored it, and returned six hardcoded findings without opening a
single file. An empty directory produced 6 threats and 4 HIGH, naming
`SmartPatcher` and `AgenticLoop` as affected components of a tree with no
files in it.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from saleha.core.threat_modeler import ThreatModeler, ThreatModelReport


class EmptyTreeTests(unittest.TestCase):
    """Nothing to read means nothing to conclude."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.modeler = ThreatModeler(root_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_tree_reports_unknown_not_high(self):
        rep = self.modeler.analyze_workspace()
        self.assertEqual(rep.files_scanned, 0)
        self.assertEqual(rep.total_threats, 0)
        self.assertEqual(rep.high_threats, 0)
        self.assertEqual(rep.unknown_count, len(ThreatModeler.CHECKS))

    def test_empty_tree_report_says_it_concluded_nothing(self):
        rep = self.modeler.analyze_workspace()
        self.assertIn("says nothing about security", rep.markdown_matrix)
        self.assertIn("UNKNOWN", rep.markdown_matrix)


class EvidenceTests(unittest.TestCase):
    """Findings must come from the files actually on disk."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.modeler = ThreatModeler(root_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write(self, name: str, content: str):
        with open(os.path.join(self.temp_dir, name), "w", encoding="utf-8") as fh:
            fh.write(content)

    def test_missing_mitigation_is_reported_as_a_gap(self):
        self._write("plain.py", "def add(a, b):\n    return a + b\n")
        rep = self.modeler.analyze_workspace()
        self.assertEqual(rep.files_scanned, 1)
        self.assertGreater(rep.total_threats, 0)
        spoof = next(f for f in rep.findings if f.category == "Spoofing")
        self.assertEqual(spoof.impact_level, "HIGH")
        self.assertEqual(spoof.evidence, [])

    def test_present_mitigation_is_found_and_cited(self):
        self._write("auth.py", "import hmac\n"
                               "def check(sig, exp):\n"
                               "    return hmac.compare_digest(sig, exp)\n")
        rep = self.modeler.analyze_workspace()
        spoof = next(f for f in rep.findings if f.category == "Spoofing")
        self.assertEqual(spoof.impact_level, "MITIGATED")
        self.assertIn("auth.py", spoof.evidence)
        self.assertFalse(spoof.is_gap)

    def test_different_trees_give_different_results(self):
        """
        The core regression: this repo and an empty directory previously
        returned identical findings.
        """
        self._write("plain.py", "x = 1\n")
        bare = self.modeler.analyze_workspace()

        self._write("sandboxed.py", "import resource\n"
                                    "resource.setrlimit(resource.RLIMIT_AS, (1, 1))\n")
        after = self.modeler.analyze_workspace()
        self.assertNotEqual(bare.total_threats, after.total_threats)

    def test_evidence_paths_are_relative_to_the_scanned_root(self):
        self._write("audit.py", "audit_log = []\n")
        rep = self.modeler.analyze_workspace()
        rep_finding = next(f for f in rep.findings if f.category == "Repudiation")
        self.assertEqual(rep_finding.evidence, ["audit.py"])

    def test_unreadable_file_does_not_abort_the_scan(self):
        self._write("good.py", "import hmac\n")
        # A file with undecodable bytes must be skipped, not raise.
        with open(os.path.join(self.temp_dir, "bad.py"), "wb") as fh:
            fh.write(b"\xff\xfe\x00binary")
        rep = self.modeler.analyze_workspace()
        self.assertEqual(rep.files_scanned, 2)

    def test_vendored_directories_are_skipped(self):
        os.makedirs(os.path.join(self.temp_dir, "node_modules"))
        self._write(os.path.join("node_modules", "dep.py"), "import hmac\n")
        self._write("mine.py", "x = 1\n")
        rep = self.modeler.analyze_workspace()
        self.assertEqual(rep.files_scanned, 1)


class RealRepoTests(unittest.TestCase):
    """Against this repository, where the mitigations genuinely exist."""

    def test_this_repo_scans_real_files_and_finds_its_own_controls(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        rep = ThreatModeler(root_dir=root).analyze_workspace()
        self.assertIsInstance(rep, ThreatModelReport)
        self.assertGreater(rep.files_scanned, 100)
        # approval_gate.py and the sandbox modules are real and present.
        priv = next(f for f in rep.findings
                    if f.category == "ElevationOfPrivilege")
        self.assertEqual(priv.impact_level, "MITIGATED")
        self.assertTrue(priv.evidence)

    def test_report_states_its_own_limits(self):
        rep = ThreatModeler().analyze_workspace()
        self.assertIn("not whether it is", rep.markdown_matrix)
        self.assertIn("not a penetration", rep.markdown_matrix.lower())


class SaveReportTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_report(self):
        modeler = ThreatModeler(root_dir=self.temp_dir)
        rep = modeler.analyze_workspace()
        out_p = os.path.join(self.temp_dir, "threat.md")
        saved = modeler.save_report(rep, output_path=out_p)
        self.assertTrue(os.path.isfile(saved))
        with open(saved, encoding="utf-8") as fh:
            self.assertIn("STRIDE checklist", fh.read())

    def test_save_leaves_no_temp_file_behind(self):
        modeler = ThreatModeler(root_dir=self.temp_dir)
        rep = modeler.analyze_workspace()
        out_p = os.path.join(self.temp_dir, "threat.md")
        modeler.save_report(rep, output_path=out_p)
        leftovers = [n for n in os.listdir(self.temp_dir) if ".tmp." in n]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
