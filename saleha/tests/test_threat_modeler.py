"""Unit tests for Automated STRIDE Threat Modeling Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.threat_modeler import ThreatModeler, ThreatModelReport


class ThreatModelerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.modeler = ThreatModeler(root_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_workspace_generates_stride_matrix(self):
        rep = self.modeler.analyze_workspace()
        self.assertGreaterEqual(rep.total_threats, 6)
        self.assertIn("STRIDE Threat Model", rep.markdown_matrix)
        self.assertIn("Spoofing", rep.markdown_matrix)
        self.assertIn("ElevationOfPrivilege", rep.markdown_matrix)

    def test_save_report(self):
        rep = self.modeler.analyze_workspace()
        out_p = os.path.join(self.temp_dir, "threat.md")
        saved = self.modeler.save_report(rep, output_path=out_p)
        self.assertTrue(os.path.isfile(saved))


if __name__ == "__main__":
    unittest.main()
