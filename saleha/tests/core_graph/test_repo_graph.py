"""
Tests for the cross-file repository graph (saleha/core/graph/repo_graph.py).

The real gap this closes: our own CodebaseDependencyGraph answered
get_impacted_files("agentic_loop.py") with [] on this very repo, while six
files actually import it. These tests build a real graph over real files on
disk (no mocks) and assert the cross-file edges are genuinely found.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from saleha.core.graph.repo_graph import (
    CODE_SUFFIXES,
    DEFAULT_EXCLUDES,
    STORE_VERSION,
    RepoGraph,
)


class DiscoveryTests(unittest.TestCase):
    """File discovery works without graphify installed."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "pkg"))
        os.makedirs(os.path.join(self.tmp, "node_modules", "junk"))
        os.makedirs(os.path.join(self.tmp, "__pycache__"))
        self._w("pkg/a.py", "x = 1\n")
        self._w("pkg/b.ts", "export const x = 1;\n")
        self._w("pkg/notes.md", "# not code\n")
        self._w("node_modules/junk/vendor.py", "y = 2\n")
        self._w("__pycache__/cached.py", "z = 3\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _w(self, rel, content):
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def test_finds_real_source_and_skips_noise(self) -> None:
        found = {p.name for p in RepoGraph(self.tmp).discover_files()}
        self.assertIn("a.py", found)
        self.assertIn("b.ts", found)
        self.assertNotIn("notes.md", found)      # not a code suffix
        self.assertNotIn("vendor.py", found)     # node_modules excluded
        self.assertNotIn("cached.py", found)     # __pycache__ excluded

    def test_any_virtualenv_is_skipped_even_if_not_listed(self) -> None:
        """A venv with an unlisted name (.venv_laya) must not flood the scan."""
        self._w(".venv_other/pyvenv.cfg", "home = x\n")
        self._w(".venv_other/Lib/site-packages/lib.py", "q = 1\n")
        found = {p.name for p in RepoGraph(self.tmp).discover_files()}
        self.assertNotIn("lib.py", found)
        self.assertIn("a.py", found)

    def test_excludes_and_suffixes_are_configurable(self) -> None:
        g = RepoGraph(self.tmp, excludes=set(), suffixes={".md"})
        found = {p.name for p in g.discover_files()}
        self.assertIn("notes.md", found)
        self.assertNotIn("a.py", found)

    def test_querying_before_build_raises(self) -> None:
        g = RepoGraph(self.tmp)
        with self.assertRaises(RuntimeError):
            g.importers_of("a.py")

    def test_module_key_accepts_path_or_name(self) -> None:
        self.assertEqual(RepoGraph._module_key("saleha/core/agentic_loop.py"),
                         "agentic_loop")
        self.assertEqual(RepoGraph._module_key("agentic_loop"), "agentic_loop")

    def test_defaults_are_sane(self) -> None:
        self.assertIn("__pycache__", DEFAULT_EXCLUDES)
        self.assertIn("node_modules", DEFAULT_EXCLUDES)
        self.assertIn(".py", CODE_SUFFIXES)
        self.assertIn(".rs", CODE_SUFFIXES)


class RealCrossFileGraphTests(unittest.TestCase):
    """Builds a real graph over real files -- the behaviour that matters."""

    @classmethod
    def setUpClass(cls) -> None:
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
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_produced_a_real_graph(self) -> None:
        self.assertGreater(self.stats.files_scanned, 0)
        self.assertGreater(self.stats.nodes, 0)
        self.assertGreater(self.stats.edges, 0)
        self.assertIn("imports", self.stats.relations)

    def test_finds_cross_file_importers(self) -> None:
        """The exact query our own dependency_graph returned [] for."""
        importers = self.graph.importers_of("mypkg/engine.py")
        names = {os.path.basename(p) for p in importers}
        self.assertIn("driver.py", names)
        self.assertIn("cli.py", names)

    def test_module_does_not_count_as_its_own_importer(self) -> None:
        importers = self.graph.importers_of("mypkg/engine.py")
        self.assertNotIn("mypkg/engine.py", importers)

    def test_module_with_no_importers_reports_none(self) -> None:
        self.assertEqual(self.graph.importers_of("mypkg/orphan.py"), [])

    def test_neighbors_returns_real_edges_with_locations(self) -> None:
        hits = self.graph.neighbors_of("engine")
        self.assertTrue(hits)
        for h in hits:
            self.assertIn("relation", h)
            self.assertIn("at", h)

    def test_unused_candidates_include_orphan_only(self) -> None:
        cands = self.graph.find_unused_module_candidates()
        names = {os.path.basename(c) for c in cands}
        self.assertIn("orphan.py", names)
        self.assertNotIn("engine.py", names)   # really is imported

    def test_summary_reports_real_numbers(self) -> None:
        s = self.graph.summary()
        self.assertEqual(s["nodes"], self.stats.nodes)
        self.assertEqual(s["edges"], self.stats.edges)
        self.assertGreaterEqual(s["build_seconds"], 0.0)

    def test_all_python_fixtures_are_represented_in_the_graph(self) -> None:
        """Coverage is reported, not assumed.

        files_scanned counts what was handed to the extractor; a file whose
        grammar is missing yields no nodes and would otherwise be invisible.
        These fixtures are all plain Python, so coverage must be complete.
        """
        self.assertEqual(self.stats.files_absent, [])
        self.assertTrue(self.stats.coverage_is_complete)
        self.assertEqual(self.stats.files_with_symbols, self.stats.files_scanned)

    def test_same_path_passed_twice_counts_once(self) -> None:
        """A duplicate path is one file, not two -- it must not inflate totals."""
        target = Path(self.tmp) / "mypkg" / "engine.py"
        g = RepoGraph(self.tmp)
        stats = g.build(files=[target, target])

        self.assertEqual(stats.files_scanned, 1)
        self.assertEqual(stats.files_with_symbols, 1)

    def test_absent_paths_are_normalised_consistently(self) -> None:
        """Every files_absent entry uses forward slashes, whatever was passed in."""
        tmp = tempfile.mkdtemp()
        try:
            outside = Path(tmp) / "outside.sql"
            outside.write_text("CREATE TABLE t (id INT);\n")

            g = RepoGraph(self.tmp)
            stats = g.build(files=[outside])

            for entry in stats.files_absent:
                self.assertNotIn("\\", entry)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unparseable_file_is_reported_absent_not_silently_dropped(self) -> None:
        """A file the extractor cannot represent must be named, not hidden."""
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "real.py"), "w") as f:
                f.write("def hello():\n    return 1\n")
            # .sql needs a grammar graphify does not ship by default; this is
            # the exact case that silently vanished from this repo's own graph.
            with open(os.path.join(tmp, "schema.sql"), "w") as f:
                f.write("CREATE TABLE t (id INT);\n")

            g = RepoGraph(tmp)
            stats = g.build()

            self.assertGreater(stats.files_with_symbols, 0)
            if stats.files_absent:
                self.assertFalse(stats.coverage_is_complete)
                self.assertLess(stats.files_with_symbols, stats.files_scanned)
                self.assertNotIn("real.py", stats.files_absent)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_root_reached_through_a_symlink_still_represents_its_files(self) -> None:
        """macOS tmp is /var -> /private/var: files resolve to the real path, the root was the link."""
        real = tempfile.mkdtemp()
        link = real + "_link"
        try:
            try:
                os.symlink(real, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("cannot create a symlink here")
            with open(os.path.join(real, "real.py"), "w") as f:
                f.write("def hello():\n    return 1\n")
            stats = RepoGraph(link).build()
            self.assertEqual(stats.files_scanned, 1)
            self.assertEqual(stats.files_absent, [])
        finally:
            if os.path.islink(link):
                os.unlink(link)
            shutil.rmtree(real, ignore_errors=True)


class PersistenceTests(unittest.TestCase):
    """The graph survives a restart -- and is never served out of date."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp = self._td.name
        self._w("mypkg/engine.py", "class Engine:\n    def run(self):\n        return 42\n")
        self._w("mypkg/driver.py",
                "from mypkg.engine import Engine\n\ndef go():\n    return Engine().run()\n")

    def tearDown(self) -> None:
        self._td.cleanup()

    def _w(self, rel: str, content: str) -> None:
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def test_first_call_builds_and_saves_under_dot_saleha(self) -> None:
        g = RepoGraph(self.tmp)
        stats = g.load_or_build()
        self.assertEqual(stats.source, "built")
        self.assertEqual(stats.reason, "no saved graph")
        self.assertTrue(stats.saved, stats.save_error)
        # The root is kept as its real path (macOS tmp /var is /private/var; a Windows
        # 8.3 name is expanded), so the same repo reached two ways shares one graph.
        self.assertEqual(g.store_path(), Path(os.path.realpath(self.tmp)) / ".saleha" / "repo_graph.json")
        self.assertTrue(g.store_path().is_file())

    def test_second_process_loads_the_same_graph_without_extracting(self) -> None:
        first = RepoGraph(self.tmp)
        built = first.load_or_build()

        second = RepoGraph(self.tmp)   # a fresh object == a restart
        loaded = second.load_or_build()

        self.assertEqual(loaded.source, "store")
        self.assertEqual((loaded.nodes, loaded.edges), (built.nodes, built.edges))
        self.assertEqual(second.importers_of("mypkg/engine.py"),
                         first.importers_of("mypkg/engine.py"))
        self.assertIn("driver.py", {os.path.basename(p) for p in second.importers_of("mypkg/engine.py")})

    def test_edited_file_forces_rebuild_and_names_the_file(self) -> None:
        RepoGraph(self.tmp).load_or_build()
        self._w("mypkg/engine.py", "class Engine:\n    def run(self):\n        return 43\n\n# edit\n")

        g = RepoGraph(self.tmp)
        stats = g.load_or_build()

        self.assertEqual(stats.source, "built")
        self.assertIn("mypkg/engine.py", stats.reason)

    def test_new_importer_appears_after_a_file_is_added(self) -> None:
        """The stale-graph trap: a saved graph must not hide a new dependant."""
        RepoGraph(self.tmp).load_or_build()
        self._w("mypkg/cli.py", "import mypkg.engine\n\ndef main():\n    return mypkg.engine.Engine()\n")

        g = RepoGraph(self.tmp)
        g.load_or_build()

        names = {os.path.basename(p) for p in g.importers_of("mypkg/engine.py")}
        self.assertIn("cli.py", names)

    def test_deleted_file_forces_rebuild(self) -> None:
        RepoGraph(self.tmp).load_or_build()
        os.remove(os.path.join(self.tmp, "mypkg", "driver.py"))

        g = RepoGraph(self.tmp)
        stats = g.load_or_build()

        self.assertEqual(stats.source, "built")
        self.assertIn("mypkg/driver.py", stats.reason)
        self.assertNotIn("driver.py", {os.path.basename(p) for p in g.importers_of("mypkg/engine.py")})

    def test_corrupt_store_is_rebuilt_not_trusted(self) -> None:
        g = RepoGraph(self.tmp)
        g.load_or_build()
        g.store_path().write_text("{ not json", encoding="utf-8")

        stats = RepoGraph(self.tmp).load_or_build()

        self.assertEqual(stats.source, "built")
        self.assertIn("unreadable", stats.reason)
        self.assertTrue(stats.saved)

    def test_wrong_version_is_rebuilt(self) -> None:
        g = RepoGraph(self.tmp)
        g.load_or_build()
        data = json.loads(g.store_path().read_text(encoding="utf-8"))
        data["version"] = STORE_VERSION + 1
        g.store_path().write_text(json.dumps(data), encoding="utf-8")

        stats = RepoGraph(self.tmp).load_or_build()

        self.assertEqual(stats.source, "built")
        self.assertIn("version", stats.reason)

    def test_store_with_missing_fields_is_rebuilt(self) -> None:
        g = RepoGraph(self.tmp)
        g.load_or_build()
        g.store_path().write_text(json.dumps({"version": STORE_VERSION, "root": str(g.root)}),
                                  encoding="utf-8")

        stats = RepoGraph(self.tmp).load_or_build()

        self.assertEqual(stats.source, "built")
        self.assertIn("unreadable", stats.reason)

    def test_rebuild_flag_ignores_a_valid_store(self) -> None:
        RepoGraph(self.tmp).load_or_build()
        stats = RepoGraph(self.tmp).load_or_build(rebuild=True)
        self.assertEqual(stats.source, "built")
        self.assertEqual(stats.reason, "rebuild requested")

    def test_partial_graph_is_never_saved(self) -> None:
        g = RepoGraph(self.tmp)
        g.build(files=[Path(self.tmp) / "mypkg" / "engine.py"])
        with self.assertRaises(RuntimeError):
            g.save()
        self.assertFalse(g.store_path().exists())

    def test_failed_save_is_reported_not_claimed(self) -> None:
        """The graph still works, and the stats say it was NOT saved."""
        blocker = Path(self.tmp) / ".saleha"
        blocker.write_text("i am a file, so .saleha/ cannot be a directory", encoding="utf-8")

        g = RepoGraph(self.tmp)
        stats = g.load_or_build()

        self.assertFalse(stats.saved)
        self.assertTrue(stats.save_error)
        self.assertIn("driver.py", {os.path.basename(p) for p in g.importers_of("mypkg/engine.py")})

    def test_store_written_for_another_root_is_not_reused(self) -> None:
        g = RepoGraph(self.tmp)
        g.load_or_build()
        data = json.loads(g.store_path().read_text(encoding="utf-8"))
        data["root"] = str(Path(self.tmp) / "somewhere_else")
        g.store_path().write_text(json.dumps(data), encoding="utf-8")

        stats = RepoGraph(self.tmp).load_or_build()

        self.assertEqual(stats.source, "built")
        self.assertIn("different root", stats.reason)


class RealSalehaRepoTests(unittest.TestCase):
    """Regression guard on this repo itself, using the known-true answer."""

    def test_agentic_loop_importers_are_found_in_this_repo(self) -> None:
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        core = os.path.join(repo_root, "saleha", "core")
        cli = os.path.join(repo_root, "saleha", "cli")
        if not os.path.isdir(core):
            self.skipTest("not running from a source checkout")

        g = RepoGraph(repo_root)
        files = [p for p in g.discover_files()
                 if str(p).startswith((core, cli)) and p.suffix == ".py"]
        g.build(files=files)
        importers = g.importers_of("saleha/core/loop/agentic_loop.py")
        # core_agentic.py genuinely imports AgentLoop; our old graph said [].
        self.assertTrue(
            any(p.endswith("core_agentic.py") for p in importers),
            f"expected cli/commands/core_agentic.py among importers, got {importers}",
        )


if __name__ == "__main__":
    unittest.main()
