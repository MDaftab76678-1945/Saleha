"""`saleha doom audit <file>` must audit that file, not crash and not lie.

Two separate defects, both reachable from a plausible invocation -- the CLI
argument accepts any path, and typing a filename is a natural thing to do:

1. `DoomWorkspaceEngine(workspace_dir=<file>)` anchored its cache at
   `<file>/.saleha/ast_cache.json`, so `_save_cache()`'s `mkdir` -- which sits
   outside its own try/except -- raised FileExistsError [WinError 183] on
   every such run.

2. Behind that crash, `audit_directory_incremental` walked the target with
   `rglob`, which yields nothing for a file. Had the cache write succeeded it
   would have reported "0 files scanned, 0 violations" -- a clean bill of
   health for an audit that examined nothing.
"""

import tempfile
import unittest
from pathlib import Path

from saleha.core.doom_workspace_engine import DoomWorkspaceEngine
from saleha.core.incremental_ast_cache import IncrementalASTCache


class DoomAuditFileTargetTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clean = self.root / "clean.py"
        self.clean.write_text("def f():\n    return 1\n", encoding="utf-8")
        (self.root / "second.py").write_text("x = 2\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_engine_anchors_workspace_at_the_parent_for_a_file(self) -> None:
        """Constructing against a file used to make the file its own parent
        directory, which is what the cache mkdir then choked on."""
        engine = DoomWorkspaceEngine(workspace_dir=str(self.clean))
        self.assertEqual(engine.workspace_dir, self.root.resolve())

    def test_engine_still_uses_the_directory_itself_when_given_one(self) -> None:
        engine = DoomWorkspaceEngine(workspace_dir=str(self.root))
        self.assertEqual(engine.workspace_dir, self.root.resolve())

    def test_auditing_a_single_file_does_not_raise(self) -> None:
        engine = DoomWorkspaceEngine(workspace_dir=str(self.clean))
        res = engine.run_full_audit(str(self.clean))  # used to raise FileExistsError
        self.assertEqual(res["total_files_scanned"], 1)

    def test_a_single_file_is_actually_scanned_not_silently_skipped(self) -> None:
        """The quiet half of the bug: rglob over a file yields nothing, so a
        successful run would still have claimed zero files and no violations."""
        cache = IncrementalASTCache(
            cache_file_path=str(self.root / ".saleha" / "ast_cache.json"))
        res = cache.audit_directory_incremental(self.clean)
        self.assertEqual(res["total_files"], 1)
        self.assertEqual(res["clean_files"], 1)

    def test_directory_target_still_finds_every_file(self) -> None:
        cache = IncrementalASTCache(
            cache_file_path=str(self.root / ".saleha" / "ast_cache.json"))
        res = cache.audit_directory_incremental(self.root)
        self.assertEqual(res["total_files"], 2)

    def test_a_file_of_an_unhandled_type_reports_zero_rather_than_pretending(self) -> None:
        readme = self.root / "notes.md"
        readme.write_text("# not source\n", encoding="utf-8")
        cache = IncrementalASTCache(
            cache_file_path=str(self.root / ".saleha" / "ast_cache.json"))
        res = cache.audit_directory_incremental(readme)
        self.assertEqual(res["total_files"], 0)


if __name__ == "__main__":
    unittest.main()
