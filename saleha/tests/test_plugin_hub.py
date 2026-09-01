"""Unit tests for Community Plugin Hub & Dynamic Skill Loader."""

import unittest
import tempfile
import os
import json
import shutil
from saleha.core.plugin_hub import SalehaPluginHub, CommunityPluginManifest


class TestPluginHub(unittest.TestCase):
    """Test suite for SalehaPluginHub catalog, dynamic scanning, and installation."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.hub = SalehaPluginHub(plugins_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_list_and_install_catalog_plugin(self):
        available = self.hub.list_available_hub_plugins()
        self.assertTrue(len(available) >= 3)

        success = self.hub.install_plugin("solidity_auditor")
        self.assertTrue(success)
        installed = self.hub.list_installed_plugins()
        self.assertEqual(len(installed), 1)
        self.assertEqual(installed[0].name, "solidity_auditor")

    def test_scan_directory_for_plugins(self):
        plugin_folder = os.path.join(self.tmp_dir, "custom_linter")
        os.makedirs(plugin_folder, exist_ok=True)
        manifest_path = os.path.join(plugin_folder, "plugin.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "name": "custom_linter",
                "version": "1.0.0",
                "description": "A custom linter",
                "author": "Community",
                "entrypoint": "main.py",
            }, f)

        count = self.hub.scan_directory_for_plugins(self.tmp_dir)
        self.assertEqual(count, 1)
        self.assertIn("custom_linter", self.hub.loaded_plugins)


if __name__ == "__main__":
    unittest.main()
