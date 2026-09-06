"""
Tests for the cross-file repository graph (saleha/core/repo_graph.py).

The real gap this closes: our own CodebaseDependencyGraph answered
get_impacted_files("agentic_loop.py") with [] on this very repo, while six
files actually import it. These tests build a real graph over real files on
disk (no mocks) and assert the cross-file edges are genuinely found.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from saleha.core.repo_graph import (
    CODE_SUFFIXES,
    DEFAULT_EXCLUDES,
    RepoGraph,
    graphify_available,
)

requires_graphify = unittest.skipUnless(
    graphify_available(),
    "optional 'graphifyy' package not installed (pip install graphifyy)",
)


class DiscoveryTests(unittest.TestCase):
    """File discovery works without graphify installed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "pkg"))
        os.makedirs(os.path.join(self.tmp, "node_modules", "junk"))
        os.makedirs(os.path.join(self.tmp, "__pycache__"))
        self._w("pkg/a.py", "x = 1\n")
        self._w("pkg/b.ts", "export const x = 1;\n")
        self._w("pkg/notes.md", "# not code\n")
        self._w("node_modules/junk/vendor.py", "y = 2\n")
        self._w("__pycache__/cached.py", "z = 3\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _w(self, rel, content):
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def test_finds_real_source_and_skips_noise(self):
        found = {p.name for p in RepoGraph(self.tmp).discover_files()}
        self.assertIn("a.py", found)
        self.assertIn("b.ts", found)
        self.assertNotIn("notes.md", found)      # not a code suffix
        self.assertNotIn("vendor.py", found)     # node_modules excluded
        self.assertNotIn("cached.py", found)     # __pycache__ excluded

    def test_excludes_and_suffixes_are_configurable(self):
        g = RepoGraph(self.tmp, excludes=set(), suffixes={".md"})
        found = {p.name for p in g.discover_files()}
        self.assertIn("notes.md", found)
        self.assertNotIn("a.py", found)

    def test_querying_before_build_raises(self):
        g = RepoGraph(self.tmp)
        with self.assertRaises(RuntimeError):
            g.importers_of("a.py")

    def test_module_key_accepts_path_or_name(self):
        self.assertEqual(RepoGraph._module_key("saleha/core/agentic_loop.py"),
                         "agentic_loop")
        self.assertEqual(RepoGraph._module_key("agentic_loop"), "agentic_loop")

    def test_defaults_are_sane(self):
        self.assertIn("__pycache__", DEFAULT_EXCLUDES)
        self.assertIn("node_modules", DEFAULT_EXCLUDES)
        self.assertIn(".py", CODE_SUFFIXES)
        self.assertIn(".rs", CODE_SUFFIXES)


@requires_graphify
class RealCrossFileGraphTests(unittest.TestCase):
    """Builds a real graph over real files -- the behaviour that matters."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "mypkg")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(pkg, "engine.py"), "w") as f:
            f.write("class Engine:\n    def run(self):\n        return 42\n")
        # Two real, separate importers of engine.py.
        with open(os.path.join(pkg, "driver.py"), "w") as f:
            f.write("from mypkg.engine import Engine\n\n"
                    "def go():\n    return Engine().run()\n")
        with open(os.path.join(pkg, "cli.py"), "w") as f:
            f.write("import mypkg.engine\n\n"
                    "def main():\n    return mypkg.engine.Engine()\n")
        # A module nothing imports.
        with open(os.path.join(pkg, "orphan.py"), "w") as f:
            f.write("def lonely():\n    return None\n")

        cls.graph = RepoGraph(cls.tmp)
        cls.stats = cls.graph.build()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_produced_a_real_graph(self):
        self.assertGreater(self.stats.files_scanned, 0)
        self.assertGreater(self.stats.nodes, 0)
        self.assertGreater(self.stats.edges, 0)
        self.assertIn("imports", self.stats.relations)

    def test_finds_cross_file_importers(self):
        """The exact query our own dependency_graph returned [] for."""
        importers = self.graph.importers_of("mypkg/engine.py")
        names = {os.path.basename(p) for p in importers}
        self.assertIn("driver.py", names)
        self.assertIn("cli.py", names)

    def test_module_does_not_count_as_its_own_importer(self):
        importers = self.graph.importers_of("mypkg/engine.py")
        self.assertNotIn("mypkg/engine.py", importers)

    def test_module_with_no_importers_reports_none(self):
        self.assertEqual(self.graph.importers_of("mypkg/orphan.py"), [])

    def test_neighbors_returns_real_edges_with_locations(self):
        hits = self.graph.neighbors_of("engine")
        self.assertTrue(hits)
        for h in hits:
            self.assertIn("relation", h)
            self.assertIn("at", h)

    def test_unused_candidates_include_orphan_only(self):
        cands = self.graph.find_unused_module_candidates()
        names = {os.path.basename(c) for c in cands}
        self.assertIn("orphan.py", names)
        self.assertNotIn("engine.py", names)   # really is imported

    def test_summary_reports_real_numbers(self):
        s = self.graph.summary()
        self.assertEqual(s["nodes"], self.stats.nodes)
        self.assertEqual(s["edges"], self.stats.edges)
        self.assertGreaterEqual(s["build_seconds"], 0.0)


@requires_graphify
class RealSalehaRepoTests(unittest.TestCase):
    """Regression guard on this repo itself, using the known-true answer."""

    def test_agentic_loop_importers_are_found_in_this_repo(self):
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", ".."))
        core = os.path.join(repo_root, "saleha", "core")
        cli = os.path.join(repo_root, "saleha", "cli")
        if not os.path.isdir(core):
            self.skipTest("not running from a source checkout")

        g = RepoGraph(repo_root)
        files = [p for p in g.discover_files()
                 if str(p).startswith((core, cli)) and p.suffix == ".py"]
        g.build(files=files)
        importers = g.importers_of("saleha/core/agentic_loop.py")
        # core_agentic.py genuinely imports AgentLoop; our old graph said [].
        self.assertTrue(
            any(p.endswith("core_agentic.py") for p in importers),
            f"expected cli/commands/core_agentic.py among importers, got {importers}",
        )


if __name__ == "__main__":
    unittest.main()
