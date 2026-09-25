"""Self-governance: controls, ratchet, doc sync, versioning, autonomous fixes.

Each test targets the case that would break the component, not the case
that works: a control that cannot run, a ratchet asked to loosen, a doc
edited by hand, a model rewriting the wrong function.
"""

from __future__ import annotations

import ast
import importlib
import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from saleha.core.governance import controls, doc_sync, improver, versioning

mp = importlib.import_module("saleha.core.platform.model_provider")
REPO = Path(__file__).resolve().parents[2]


def _tmp() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


class SubprocessDetectionTests(unittest.TestCase):
    def test_aliases_and_from_imports_are_found(self) -> None:
        with _tmp() as d:
            root = Path(d)
            _write(root, "saleha/mod.py", """
                import subprocess as sp
                from subprocess import check_output as co
                def a(cmd):
                    return sp.run(cmd, text=True)
                def b(cmd):
                    return co(cmd, universal_newlines=True, timeout=5)
                def c(cmd, **kw):
                    return sp.run(cmd, **kw)
                def d(cmd):
                    return sp.run(cmd, text=True, encoding="utf-8", timeout=9)
            """)
            timeouts, _ = controls.find_subprocess_issues(root, "timeout")
            encodings, _ = controls.find_subprocess_issues(root, "encoding")
        self.assertEqual(timeouts, ["saleha/mod.py:5"])  # c() hides its kwargs; b and d set timeout
        self.assertEqual(encodings, ["saleha/mod.py:5", "saleha/mod.py:7"])

    def test_unparsable_file_makes_the_control_not_checked(self) -> None:
        with _tmp() as d:
            root = Path(d)
            _write(root, "saleha/broken.py", "def f(:\n")
            res = controls._timeout_control(controls.ControlContext(root, {"subprocess_without_timeout": 5}))
        self.assertEqual(res.status, controls.NOT_CHECKED)
        self.assertIn("incomplete", res.evidence)


class RatchetTests(unittest.TestCase):
    def test_count_above_baseline_fails_and_below_passes(self) -> None:
        ctx = controls.ControlContext(REPO, {"m": 2})
        self.assertEqual(controls._ratchet(ctx, "X", "t", "m", ["a", "b", "c"], [], "x").status, controls.FAIL)
        self.assertEqual(controls._ratchet(ctx, "X", "t", "m", ["a"], [], "x").status, controls.PASS)
        no_base = controls._ratchet(controls.ControlContext(REPO, {}), "X", "t", "m", [], [], "x")
        self.assertEqual(no_base.status, controls.NOT_CHECKED)

    def test_update_baseline_never_raises_a_value(self) -> None:
        with _tmp() as d:
            path = Path(d) / "baseline.json"
            path.write_text(json.dumps({"metrics": {"m": 3, "n": 1}}), encoding="utf-8")
            results = [controls.ControlResult("A", "", controls.FAIL, "", "m", 7),
                       controls.ControlResult("B", "", controls.PASS, "", "n", 0),
                       controls.ControlResult("C", "", controls.NOT_CHECKED, "no baseline", "new", 4)]
            changed = controls.update_baseline(results, path=path)
            stored = controls.load_baseline(path)
        self.assertEqual(stored, {"m": 3, "n": 0, "new": 4})
        self.assertEqual(changed, {"n": (1, 0), "new": (None, 4)})

    def test_incomplete_scan_is_not_recorded(self) -> None:
        with _tmp() as d:
            path = Path(d) / "baseline.json"
            r = controls.ControlResult("A", "", controls.NOT_CHECKED, "2 found, but the scan was incomplete", "m", 2)
            self.assertEqual(controls.update_baseline([r], path=path), {})
            self.assertFalse(path.exists())


class CatalogControlTests(unittest.TestCase):
    def test_severity_mismatch_fails(self) -> None:
        with _tmp() as d:
            root = Path(d)
            _write(root, "saleha/core/verification/security_scanner.py", """
                def f():
                    return SecurityVulnerability(rule_id="SEC004", severity="HIGH")
            """)
            res = controls._catalog_control(controls.ControlContext(root, {}))
        self.assertEqual(res.status, controls.FAIL)
        self.assertTrue(any("SEC004 emitted as ['HIGH'] but catalogued as MEDIUM" in i for i in res.items))

    def test_real_scanner_agrees_with_catalog(self) -> None:
        res = controls._catalog_control(controls.ControlContext(REPO, {}))
        self.assertEqual(res.status, controls.PASS, res.items)


class LocalOnlyControlTests(unittest.TestCase):
    def test_current_providers_refuse_without_outbound_calls(self) -> None:
        res = controls._local_only_control(controls.ControlContext(REPO, {}))
        self.assertEqual(res.status, controls.PASS, res.items)

    def test_a_provider_that_calls_out_is_caught(self) -> None:
        # Reproduces the leak this control found: a cloud endpoint that
        # ignored SALEHA_LOCAL_ONLY and went on to call requests.post.
        def leaky_generate(self, **_kwargs):
            return mp.requests.post("https://api.openai.com/v1/chat/completions")
        with mock.patch.object(mp.OpenAICompatibleProvider, "generate", leaky_generate), \
                mock.patch.object(mp.OpenAICompatibleProvider, "is_available", lambda self: True):
            try:
                res = controls._local_only_control(controls.ControlContext(REPO, {}))
            except RuntimeError:
                self.fail("the control must record the intercepted call, not crash")
        self.assertEqual(res.status, controls.FAIL)
        self.assertTrue(any("is_available() is True" in i for i in res.items))

    def test_openai_compatible_refuses_cloud_but_keeps_localhost(self) -> None:
        with mock.patch.dict("os.environ", {"SALEHA_LOCAL_ONLY": "1", "OPENAI_API_KEY": "k"}), \
                mock.patch.object(mp.requests, "post", side_effect=AssertionError("network used")):
            cloud = mp.OpenAICompatibleProvider(base_url="https://api.openai.com/v1")
            self.assertFalse(cloud.is_available())
            resp = cloud.generate(model="m", prompt="p")
            self.assertFalse(resp.success)
            self.assertIn("SALEHA_LOCAL_ONLY", resp.error_message)
            local = mp.OpenAICompatibleProvider(base_url="http://127.0.0.1:1234/v1")
            self.assertTrue(local.is_available())
            # A hostname that merely contains "localhost" is not local.
            self.assertFalse(mp.OpenAICompatibleProvider(base_url="https://localhost.evil.com/v1")._is_local())


class ControlRunnerTests(unittest.TestCase):
    def test_crashing_control_reports_not_checked(self) -> None:
        def boom(_ctx: controls.ControlContext) -> controls.ControlResult:
            raise ValueError("kaboom")
        fake = [controls.Control("GOV-BOOM", "boom", "", boom)]
        with mock.patch.object(controls, "CONTROLS", fake):
            (res,) = controls.run_controls(baseline={})
        self.assertEqual(res.status, controls.NOT_CHECKED)
        self.assertIn("kaboom", res.evidence)


class DocSyncTests(unittest.TestCase):
    def _root(self, d: str) -> Path:
        root = Path(d)
        _write(root, "pyproject.toml", 'name = "saleha"\nversion = "3.1.4"\n')
        _write(root, "docs/A.md", """
            # A
            <!-- saleha:generated:doc-version -->
            <!-- /saleha:generated:doc-version -->
            <!-- saleha:generated:project-version -->
            stale
            <!-- /saleha:generated:project-version -->
            <!-- saleha:generated:no-such-region -->
            kept
            <!-- /saleha:generated:no-such-region -->
            hand written
        """)
        return root

    def test_regions_render_version_and_doc_versions_bump_only_on_change(self) -> None:
        with _tmp() as d:
            root = self._root(d)
            with mock.patch.object(doc_sync, "render_cli_reference", return_value=""):
                (first,) = doc_sync.plan_sync(root, today="2026-01-01")
                self.assertEqual((first.old_version, first.new_version), (None, "1.0.0"))
                self.assertEqual(first.regions_changed, ["project-version"])
                self.assertEqual(first.unknown_regions, ["no-such-region"])
                self.assertIn("Saleha version: **3.1.4**", first.new_text)
                self.assertIn("kept", first.new_text)
                self.assertIn("Document version 1.0.0 -- describes Saleha 3.1.4 -- updated 2026-01-01",
                              first.new_text)
                doc_sync.apply_sync([first], root, today="2026-01-01")

                (again,) = doc_sync.plan_sync(root, today="2026-02-02")
                self.assertFalse(again.content_changed)
                self.assertEqual(again.new_version, "1.0.0")
                self.assertIn("updated 2026-01-01", again.new_text)  # a no-op sync is not an update

                doc = root / "docs" / "A.md"
                doc.write_text(doc.read_text(encoding="utf-8") + "\nmore prose\n", encoding="utf-8")
                (edited,) = doc_sync.plan_sync(root, today="2026-03-03")
        self.assertTrue(edited.content_changed)
        self.assertEqual((edited.old_version, edited.new_version), ("1.0.0", "1.0.1"))

    def test_stale_commands_and_paths_are_reported(self) -> None:
        with _tmp() as d:
            root = Path(d)
            _write(root, "saleha/core/rag/graph_rag.py", "")
            _write(root, "README.md", """
                Run `saleha governance check` or `saleha no-such-command`.
                See `saleha/core/missing.py`, `rag/graph_rag.py` and `saleha governance nope`.
                ```
                `saleha inside-a-fence`
                ```
            """)
            _write(root, "docs/review-2026-01-01.md", "`saleha/old/path.py`\n")
            claims = {(c.claim, c.reason) for c in doc_sync.find_stale_claims(root)}
        self.assertEqual(claims, {
            ("saleha no-such-command", "no such CLI command"),
            ("saleha/core/missing.py", "path does not exist"),
            ("saleha governance nope", "no such `saleha governance` sub-command"),
        })

    def test_repo_docs_rule_table_is_current(self) -> None:
        text = (REPO / "docs" / "SECURITY_MODEL.md").read_text(encoding="utf-8")
        self.assertEqual(doc_sync.extract_region(text, "security-rules"),
                         doc_sync.render_region("security-rules", REPO))


class VersioningTests(unittest.TestCase):
    def test_commit_parsing_and_levels(self) -> None:
        c = versioning.parse_commit("a" * 40, "feat(cli)!: drop old flag", "")
        self.assertEqual((c.type, c.subject, c.breaking), ("feat", "drop old flag", True))
        self.assertTrue(versioning.parse_commit("b", "fix: x", "BREAKING CHANGE: api").breaking)
        self.assertEqual(versioning.parse_commit("c", "Merge branch x", "").type, "other")
        fix, feat = versioning.parse_commit("d", "fix: y", ""), versioning.parse_commit("e", "feat: z", "")
        self.assertEqual(versioning.level_for([fix]), "patch")
        self.assertEqual(versioning.level_for([fix, feat]), "minor")
        self.assertEqual(versioning.level_for([versioning.parse_commit("f", "docs: q", "")]), "none")
        self.assertEqual(versioning.bump("1.9.9", "major"), "2.0.0")
        self.assertEqual(versioning.bump("1.9.9", "minor"), "1.10.0")

    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, timeout=60,
                       encoding="utf-8", errors="replace")

    def test_plan_and_apply_from_a_real_history(self) -> None:
        with _tmp() as d:
            root = Path(d)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "t@example.com")
            self._git(root, "config", "user.name", "t")
            self._git(root, "config", "core.autocrlf", "false")
            (root / "pyproject.toml").write_bytes(b'name = "saleha"\r\nversion = "1.2.3"\r\n')
            _write(root, "saleha/__init__.py", '__version__ = "1.2.3"\n')
            self._git(root, "add", ".")
            self._git(root, "commit", "-q", "-m", "chore: release 1.2.3")

            none = versioning.plan_bump(root)
            self.assertEqual((none.next, none.level), (None, "none"))
            self.assertIn("no commits", none.reason)

            _write(root, "x.txt", "x")
            self._git(root, "add", ".")
            self._git(root, "commit", "-q", "-m", "fix(core): handle empty input")
            _write(root, "y.txt", "y")
            self._git(root, "add", ".")
            self._git(root, "commit", "-q", "-m", "feat: add governance")
            plan = versioning.plan_bump(root)
            self.assertEqual((plan.current, plan.next, plan.level), ("1.2.3", "1.3.0", "minor"))
            self.assertEqual([c.type for c in plan.commits], ["feat", "fix"])

            written = versioning.apply_bump(plan, root, today="2026-09-25")
            self.assertEqual(written, ["pyproject.toml", "saleha/__init__.py", "CHANGELOG.md"])
            self.assertEqual(versioning.version_declarations(root),
                             {"pyproject.toml": "1.3.0", "saleha/__init__.py": "1.3.0"})
            self.assertIn(b"\r\n", (root / "pyproject.toml").read_bytes())  # CRLF kept
            log = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("## [1.3.0] - 2026-09-25", log)
            self.assertIn("### Features\n\n- add governance", log)
            self.assertIn("### Fixes\n\n- handle empty input", log)

    def test_apply_refuses_when_declarations_disagree(self) -> None:
        with _tmp() as d:
            root = Path(d)
            _write(root, "pyproject.toml", 'version = "1.0.0"\n')
            _write(root, "saleha/__init__.py", '__version__ = "0.9.0"\n')
            plan = versioning.BumpPlan("1.0.0", "1.0.1", "patch", None)
            with self.assertRaises(ValueError):
                versioning.apply_bump(plan, root)


_OLD_METHOD = '''import os
import subprocess


class ChangelogGenerator:
    def extract_recent_commits(self, limit: int = 50):
        """Fetches commit messages from git log."""
        try:
            res = subprocess.run(
                ["git", "log", f"-n{limit}"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8", errors="replace",
            )
            if res.returncode == 0 and res.stdout.strip():
                return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            pass
        return []
'''

# What qwen2.5-coder:3b actually returned when asked only to add a timeout
# (commit 7f21d4e on auto/governance). The tests of that module still passed.
_MODEL_REWRITE = '''    def extract_recent_commits(self, limit: int = 50):
        """Fetches commit messages from git log."""
        try:
            res = subprocess.run(
                ["git", "log", f"-n{limit}"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,  # Set a sensible timeout value
                encoding="utf-8", errors="replace",
            )
            if res.returncode == 0 and res.stdout.strip():
                return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except subprocess.TimeoutExpired:
            print("Git log command timed out.")
            return []
        except Exception as e:
            print(f"An error occurred while fetching recent commits: {e}")
            raise
'''


class StructuralGateTests(unittest.TestCase):
    def _target(self, source: str) -> improver.Target:
        with _tmp() as d:
            root = Path(d)
            (root / "saleha").mkdir()
            (root / "saleha" / "m.py").write_text(source, encoding="utf-8")
            items, _ = controls.find_subprocess_issues(root, "timeout")
            target = improver.locate(root, items[0])
        assert target is not None
        return target

    def _splice(self, method: str) -> str:
        head = _OLD_METHOD.split("    def extract_recent_commits")[0]
        return head + method

    def test_the_real_model_rewrite_is_rejected(self) -> None:
        target = self._target(_OLD_METHOD)
        new = self._splice(_MODEL_REWRITE)
        self.assertTrue(improver._changes_confined(_OLD_METHOD, new, target))  # the old gate let it through
        problem = improver.structural_change_problem(_OLD_METHOD, new, target, "timeout")
        self.assertIsNotNone(problem)
        self.assertIn("changes more than", problem or "")

    def test_timeout_plus_plain_handler_is_accepted(self) -> None:
        target = self._target(_OLD_METHOD)
        good = _OLD_METHOD.replace("check=False,\n", "check=False,\n                timeout=30,\n").replace(
            "        except Exception:\n",
            "        except subprocess.TimeoutExpired:\n            return []\n        except Exception:\n")
        self.assertIsNone(improver.structural_change_problem(_OLD_METHOD, good, target, "timeout"))
        # ...but not under the encoding fix, which may not add a timeout.
        self.assertIsNotNone(improver.structural_change_problem(_OLD_METHOD, good, target, "encoding"))

    def test_method_returned_at_column_zero_is_reindented(self) -> None:
        # deepseek-coder returned methods without their class indentation;
        # stripping the class indent from that output flattened the body.
        target = self._target(_OLD_METHOD)
        reply = textwrap.dedent(_OLD_METHOD.split("class ChangelogGenerator:\n")[1]).replace(
            "check=False,\n", "check=False,\n    timeout=30,\n")
        out, why = improver.fix_timeout(_OLD_METHOD, target, lambda p: reply)
        self.assertEqual(why, "")
        assert out is not None
        self.assertIn("\n        try:\n", out)
        self.assertIsNone(improver.structural_change_problem(_OLD_METHOD, out, target, "timeout"))

    def _handled(self, body: str) -> bool:
        src = "import subprocess\n\n\ndef f(c):\n" + textwrap.indent(textwrap.dedent(body), "    ")
        return improver.timeout_already_handled(src, self._target(src))

    def test_existing_handler_detection(self) -> None:
        self.assertTrue(self._handled("""
            try:
                with open(c) as fh:
                    subprocess.run([c])
            except Exception:
                return None
        """))
        self.assertTrue(self._handled("""
            try:
                subprocess.run([c])
            except (OSError, subprocess.SubprocessError):
                return None
        """))
        self.assertFalse(self._handled("""
            try:
                subprocess.run([c])
            except OSError:
                return None
        """))
        self.assertFalse(self._handled("""
            try:
                pass
            except Exception:
                subprocess.run([c])
        """))  # inside the handler, not protected by it
        self.assertFalse(self._handled("subprocess.run([c])\n"))

    def test_deterministic_timeout_edit_passes_the_structural_gate(self) -> None:
        target = self._target(_OLD_METHOD)
        self.assertTrue(improver.timeout_already_handled(_OLD_METHOD, target))
        out = improver.add_keywords(_OLD_METHOD, target, "timeout=600")
        assert out is not None
        self.assertIn("timeout=600,", out)
        self.assertIsNone(improver.structural_change_problem(_OLD_METHOD, out, target, "timeout"))

    def test_handler_doing_new_work_is_rejected(self) -> None:
        target = self._target(_OLD_METHOD)
        busy = _OLD_METHOD.replace("check=False,\n", "check=False,\n                timeout=30,\n").replace(
            "        except Exception:\n",
            "        except subprocess.TimeoutExpired:\n            os.remove(self.repo_dir)\n"
            "            return []\n        except Exception:\n")
        problem = improver.structural_change_problem(_OLD_METHOD, busy, target, "timeout")
        self.assertIn("handler does more", problem or "")


class ImproverEditTests(unittest.TestCase):
    def _target(self, source: str) -> improver.Target:
        with _tmp() as d:
            root = Path(d)
            (root / "saleha").mkdir()
            (root / "saleha" / "m.py").write_bytes(source.encode("utf-8"))
            items, _ = controls.find_subprocess_issues(root, "encoding")
            self.assertEqual(len(items), 1, items)
            target = improver.locate(root, items[0])
        self.assertIsNotNone(target)
        assert target is not None
        return target

    def _encodings_left(self, source: str) -> int:
        tree = ast.parse(source)
        return sum(1 for c in controls.subprocess_calls(tree)
                   if not any(k.arg == "encoding" for k in c.keywords))

    def test_single_line_call(self) -> None:
        src = "import subprocess\ndef f(c):\n    return subprocess.run(c, text=True)\n"
        out = improver.fix_encoding(src, self._target(src))
        self.assertEqual(out, 'import subprocess\ndef f(c):\n    return subprocess.run(c, text=True, '
                              'encoding="utf-8", errors="replace")\n')

    def test_closing_paren_on_its_own_line_keeps_crlf(self) -> None:
        src = ("import subprocess\r\ndef f(c):\r\n    return subprocess.run(\r\n        c,\r\n"
               "        text=True\r\n    )\r\n")
        out = improver.fix_encoding(src, self._target(src))
        assert out is not None
        self.assertEqual(out, ("import subprocess\r\ndef f(c):\r\n    return subprocess.run(\r\n        c,\r\n"
                               "        text=True,\r\n        encoding=\"utf-8\", errors=\"replace\",\r\n    )\r\n"))
        self.assertEqual(self._encodings_left(out), 0)

    def test_trailing_comment_is_left_alone(self) -> None:
        src = "import subprocess\ndef f(c):\n    return subprocess.run(\n        c, text=True  # why\n    )\n"
        self.assertIsNone(improver.fix_encoding(src, self._target(src)))

    def test_timeout_fix_rejects_a_different_function(self) -> None:
        src = "import subprocess\ndef f(c):\n    return subprocess.run(c, text=True)\n"
        target = self._target(src)
        out, why = improver.fix_timeout(src, target, lambda p: "def g(c):\n    return 1\n")
        self.assertIsNone(out)
        self.assertIn("same name", why)
        out, why = improver.fix_timeout(src, target, lambda p: None)
        self.assertEqual((out, why), (None, "model returned nothing"))

    def test_timeout_fix_splices_only_the_function(self) -> None:
        src = "import subprocess\n\n\ndef f(c):\n    return subprocess.run(c, text=True)\n\n\nX = 1\n"
        target = self._target(src)
        reply = "```python\ndef f(c):\n    return subprocess.run(c, text=True, timeout=30)\n```"
        out, _ = improver.fix_timeout(src, target, lambda p: reply)
        assert out is not None
        self.assertTrue(improver._changes_confined(src, out, target))
        self.assertIn("timeout=30", out)
        self.assertTrue(out.endswith("\n\n\nX = 1\n"))
        widened = out.replace("X = 1", "X = 2")
        self.assertFalse(improver._changes_confined(src, widened, target))


if __name__ == "__main__":
    unittest.main()
