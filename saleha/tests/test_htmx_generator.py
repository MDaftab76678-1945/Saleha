"""Unit tests for Zero-JS HTMX Web App Generator."""

import unittest
import tempfile
import os
import shutil
from saleha.core.htmx_generator import HTMXGenerator, HTMXAppPackage


class TestHTMXGenerator(unittest.TestCase):
    """Test suite for HTMXGenerator app synthesis."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.generator = HTMXGenerator()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_generate_app_creates_valid_bundle(self):
        pkg = self.generator.generate_app("MetricsHub", "Live Server Telemetry")
        self.assertIsInstance(pkg, HTMXAppPackage)
        self.assertIn("main.py", pkg.files)
        self.assertIn("index.html", pkg.files)
        self.assertIn("README.md", pkg.files)
        self.assertIn("hx-get", pkg.html_template)
        self.assertIn("FastAPI", pkg.backend_code)

    def test_write_to_disk(self):
        pkg = self.generator.generate_app("DemoApp")
        self.generator.write_to_disk(self.tmp_dir, pkg)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "main.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "index.html")))


if __name__ == "__main__":
    unittest.main()
