"""Unit tests for Floating Desktop Sidecar Daemon & Micro-Server."""

import unittest
from saleha.core.sidecar_daemon import SidecarHandler, SIDECAR_HTML


class SidecarDaemonTests(unittest.TestCase):

    def test_sidecar_html_content(self):
        self.assertIn("Saleha Desktop Sidecar", SIDECAR_HTML)
        self.assertIn("runAction('explain')", SIDECAR_HTML)
        self.assertIn("runAction('sast')", SIDECAR_HTML)


if __name__ == "__main__":
    unittest.main()

