"""Tests for the deterministic project scaffolder (`saleha new`)."""

import os
import shutil
import tempfile
import unittest

from saleha.core.project_scaffolder import ProjectScaffolder, TEMPLATES

# The express check runs `npm install` (tens of seconds, network). Off by
# default like the GPU training tests; set SALEHA_RUN_SLOW_TESTS=1 to run it.
_RUN_SLOW = os.environ.get("SALEHA_RUN_SLOW_TESTS") == "1"


class TestProjectScaffolder(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.scaffolder = ProjectScaffolder()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_declared_templates_exist_on_disk(self) -> None:
        available = self.scaffolder.available_stacks()
        self.assertEqual(sorted(available), sorted(TEMPLATES.keys()))

    def test_unknown_stack_is_rejected(self) -> None:
        res = self.scaffolder.scaffold("rails", "my-app", dest_parent=self.tmp)
        self.assertFalse(res.success)
        self.assertIn("Unknown stack", res.error)
        self.assertEqual(res.files_written, [])

    def test_scaffold_substitutes_name_and_is_deterministic(self) -> None:
        res1 = self.scaffolder.scaffold("go", "Orders Service", dest_parent=self.tmp)
        self.assertTrue(res1.project_dir.endswith("orders-service"))
        self.assertIn("main.go", res1.files_written)

        main_go = os.path.join(res1.project_dir, "main.go")
        with open(main_go, encoding="utf-8") as f:
            body = f.read()
        # Placeholder is gone, project name is in.
        self.assertNotIn("{{PROJECT_NAME}}", body)
        self.assertNotIn("{{PROJECT_SLUG}}", body)
        self.assertIn("Welcome to Orders Service", body)
        self.assertIn("orders-service", body)

        # Same inputs into a fresh dir -> byte-identical output (no model call).
        other = tempfile.mkdtemp()
        try:
            res2 = self.scaffolder.scaffold("go", "Orders Service", dest_parent=other)
            with open(os.path.join(res2.project_dir, "main.go"), encoding="utf-8") as f:
                self.assertEqual(f.read(), body)
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_existing_dir_needs_force(self) -> None:
        first = self.scaffolder.scaffold("fastapi", "dup", dest_parent=self.tmp)
        self.assertTrue(os.path.isdir(first.project_dir))

        again = self.scaffolder.scaffold("fastapi", "dup", dest_parent=self.tmp)
        self.assertFalse(again.success)
        self.assertIn("already exists", again.error)

        forced = self.scaffolder.scaffold("fastapi", "dup", dest_parent=self.tmp, force=True)
        self.assertTrue(os.path.isdir(forced.project_dir))

    @unittest.skipUnless(_RUN_SLOW, "runs npm install; set SALEHA_RUN_SLOW_TESTS=1")
    def test_express_scaffold_verifies_with_local_tsc(self) -> None:
        res = self.scaffolder.scaffold("express", "ts-check", dest_parent=self.tmp)
        self.assertIn("tsconfig.json", res.files_written)
        if res.verify_ran:
            self.assertTrue(res.verify_ok, msg=f"verification output:\n{res.verify_detail}")
            self.assertTrue(res.success)
        else:
            self.assertIsNone(res.verify_ok)
            self.assertIn("skipped", res.verify_detail.lower())

    def test_fastapi_scaffold_verifies_by_running_its_tests(self) -> None:
        """The fastapi template ships a test_main.py; scaffolding runs it.

        If fastapi/httpx/pytest are installed (they are, in the dev env) the
        verification actually runs and must pass. If the import fails for any
        reason the scaffolder reports verify_ran=False, never a false pass.
        """
        res = self.scaffolder.scaffold("fastapi", "verify-me", dest_parent=self.tmp)
        self.assertTrue(res.project_dir)
        if res.verify_ran:
            self.assertTrue(res.verify_ok, msg=f"verification output:\n{res.verify_detail}")
            self.assertTrue(res.success)
        else:
            # Skipped, not passed.
            self.assertIsNone(res.verify_ok)
            self.assertIn("skipped", res.verify_detail.lower())


if __name__ == "__main__":
    unittest.main()
