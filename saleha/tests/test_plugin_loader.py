"""Unit tests for Dynamic Plugin & Sidecar Hook Loader."""

import os
import shutil
import tempfile
import unittest
from saleha.core.plugin_loader import PluginLoader


class PluginLoaderTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_plugin_test_")
        
        # Create mock plugin file
        plugin_file = os.path.join(self.temp_dir, "custom_plugin.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write(
                "PLUGIN_NAME = 'TestPlugin'\n"
                "PLUGIN_VERSION = '2.0.0'\n"
                "PLUGIN_DESCRIPTION = 'Mock plugin for testing'\n\n"
                "def on_task_start(task):\n"
                "    return f'STARTED: {task}'\n"
            )

        self.loader = PluginLoader(plugin_dirs=[self.temp_dir])

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plugin_loaded_successfully(self):
        plugins = self.loader.list_plugins()
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0].name, "TestPlugin")
        self.assertEqual(plugins[0].version, "2.0.0")
        self.assertIn("on_task_start", plugins[0].hooks_registered)

    def test_trigger_event_dispatches_to_plugin(self):
        results = self.loader.trigger_event("on_task_start", task="Build auth service")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "STARTED: Build auth service")


if __name__ == "__main__":
    unittest.main()

