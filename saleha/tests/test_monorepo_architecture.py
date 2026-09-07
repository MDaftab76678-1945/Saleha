"""
Unit & Architecture tests for Saleha Ecosystem & Architecture.
Verifies core product architecture, design standards, and CI pipelines.
"""

import json
import re
import unittest
from pathlib import Path


class MonorepoArchitectureTests(unittest.TestCase):

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parents[2]

    def test_phase0_product_brief_exists_and_complete(self):
        brief_path = self.root_dir / "PRODUCT_BRIEF.md"
        self.assertTrue(brief_path.exists())
        content = brief_path.read_text(encoding="utf-8")
        self.assertIn("Saleha AI", content)
        # "Zero-leak" describes the real local encrypted vault (saleha/core/vault.py).
        self.assertIn("Zero-leak", content)
        # NOTE: this test previously also asserted the brief contained "LOOP_CHECK".
        # That token appears nowhere in the codebase - it only ever existed to be
        # asserted here, so requiring it forced a meaningless string into the doc.

    def test_architecture_documentation_exists(self):
        arch_path = self.root_dir / "ARCHITECTURE.md"
        self.assertTrue(arch_path.exists())
        content = arch_path.read_text(encoding="utf-8")
        self.assertIn("Saleha", content)

    def test_roadmap_documentation_exists(self):
        roadmap_path = self.root_dir / "ROADMAP.md"
        self.assertTrue(roadmap_path.exists())
        content = roadmap_path.read_text(encoding="utf-8")
        self.assertIn("Saleha", content)

    def test_github_actions_ci_workflow_configured(self):
        ci_yml = self.root_dir / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_yml.exists())
        ci_text = ci_yml.read_text(encoding="utf-8")
        self.assertTrue(len(ci_text) > 50)

    def test_optional_turborepo_configuration(self):
        turbo_path = self.root_dir / "turbo.json"
        if turbo_path.exists():
            with open(turbo_path, "r", encoding="utf-8") as f:
                turbo_cfg = json.load(f)
            self.assertIn("tasks", turbo_cfg)


class WorkspaceVersionTests(unittest.TestCase):
    """
    The workspace packages must not drift apart.

    `packages/core` sat at version 0.1.0 while its seven siblings were all at
    2.0.0, and it had drifted on three dependencies at the same time
    (typescript ^5.0.0 vs ^5.7.0, @types/node ^20 vs ^22, zod ^3.23.8 vs
    ^3.24.1). Nothing noticed, because nothing checked. These tests check.

    The @saleha/* packages are all `private: true` and are never published, so
    their version number is internal bookkeeping only -- it does not have to
    match the product version in the root package.json. What it does have to
    do is stay the same across all of them.
    """

    WORKSPACE_GLOBS = ("apps", "packages")

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parents[2]
        self.pkgs = {}
        for parent in self.WORKSPACE_GLOBS:
            base = self.root_dir / parent
            if not base.is_dir():
                continue
            for pkg_json in sorted(base.glob("*/package.json")):
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                rel = pkg_json.relative_to(self.root_dir).as_posix()
                self.pkgs[rel] = data
        if not self.pkgs:
            self.skipTest("no workspace packages found")

    def test_every_workspace_package_shares_one_version(self):
        versions = {rel: d.get("version") for rel, d in self.pkgs.items()}
        distinct = set(versions.values())
        self.assertEqual(
            len(distinct), 1,
            f"workspace packages disagree on version: {versions}",
        )

    def test_workspace_packages_are_private(self):
        """
        The shared-version rule above is only safe because these are never
        published. If one is ever made public, its version becomes meaningful
        on its own and this rule needs revisiting.
        """
        public = [rel for rel, d in self.pkgs.items() if not d.get("private")]
        self.assertEqual(
            public, [],
            f"these workspace packages are not private: {public}. "
            f"A published package needs its own version, so the "
            f"shared-version rule no longer applies to it.",
        )

    def test_no_dependency_is_declared_at_two_versions(self):
        """
        Every package.json in the repo, workspace or not -- templates and the
        vscode extension sit outside the workspace globs and so are never
        aligned by the package manager.
        """
        seen = {}
        for pkg_json in sorted(self.root_dir.glob("**/package.json")):
            parts = pkg_json.parts
            if any(p in ("node_modules", ".claude", ".next", "dist", "build")
                   for p in parts):
                continue
            rel = pkg_json.relative_to(self.root_dir).as_posix()
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                for name, spec in (data.get(section) or {}).items():
                    seen.setdefault(name, {})[rel] = spec

        conflicts = {
            name: locs for name, locs in seen.items()
            if len(set(locs.values())) > 1
        }
        self.assertEqual(
            conflicts, {},
            f"dependencies declared at conflicting versions: {conflicts}",
        )

    def test_declared_scripts_have_the_tools_they_run(self):
        """
        packages/core declared `"test": "jest"` while jest is declared nowhere
        in the repo -- the rest of the workspace uses vitest. That command
        could never have run.
        """
        runners = ("jest", "vitest", "mocha", "ava")
        problems = []
        for rel, data in self.pkgs.items():
            declared = set()
            for section in ("dependencies", "devDependencies"):
                declared |= set((data.get(section) or {}).keys())
            for script_name, body in (data.get("scripts") or {}).items():
                first = body.strip().split()[0] if body.strip() else ""
                if first in runners and first not in declared:
                    problems.append(f"{rel}: script '{script_name}' runs "
                                    f"'{first}', which it does not depend on")
        self.assertEqual(problems, [], "; ".join(problems))

    def test_typecheck_scripts_have_a_tsconfig_to_read(self):
        """
        Four packages declared `tsc --noEmit` with no tsconfig.json anywhere.
        tsc with no project prints its help text and exits 1, so
        `turbo run typecheck` reported 0 successful of 6 and had never checked
        a single type.
        """
        problems = []
        for rel, data in self.pkgs.items():
            pkg_dir = (self.root_dir / rel).parent
            scripts = data.get("scripts") or {}
            runs_tsc = any(body.strip().startswith("tsc")
                           for body in scripts.values())
            if runs_tsc and not (pkg_dir / "tsconfig.json").is_file():
                problems.append(f"{rel} runs tsc but has no tsconfig.json")
        self.assertEqual(problems, [], "; ".join(problems))


class PythonVersionTests(unittest.TestCase):
    """
    The declared Python version must agree with itself.

    Four places disagreed: pyproject.toml said `requires-python = ">=3.12"`,
    its own [tool.ruff] said `target-version = "py310"` and [tool.pyright]
    said `pythonVersion = "3.10"`, and a duplicate setup.py said
    `python_requires='>=3.10'`. Meanwhile the working venv ran 3.11.16 -- a
    version the project's own metadata does not allow and CI never tests.
    """

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parents[2]
        pyproject = self.root_dir / "pyproject.toml"
        if not pyproject.is_file():
            self.skipTest("no pyproject.toml")
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib requires Python 3.11+")
        self.cfg = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    @staticmethod
    def _minor(spec: str) -> int:
        """'>=3.12' -> 12, 'py312' -> 12, '3.12' -> 12."""
        digits = re.findall(r"3[.]?(\d+)", spec)
        if not digits:
            raise AssertionError(f"cannot read a 3.x version out of {spec!r}")
        return int(digits[0])

    def test_ruff_and_pyright_match_requires_python(self):
        required = self._minor(self.cfg["project"]["requires-python"])
        ruff = self.cfg.get("tool", {}).get("ruff", {}).get("target-version")
        pyright = self.cfg.get("tool", {}).get("pyright", {}).get("pythonVersion")

        if ruff:
            self.assertEqual(
                self._minor(ruff), required,
                f"ruff target-version {ruff} does not match "
                f"requires-python {self.cfg['project']['requires-python']}")
        if pyright:
            self.assertEqual(
                self._minor(pyright), required,
                f"pyright pythonVersion {pyright} does not match "
                f"requires-python {self.cfg['project']['requires-python']}")

    def test_no_duplicate_setup_py(self):
        """
        setup.py duplicated every field of pyproject.toml and drifted from it.
        Two files declaring the same package is how they end up disagreeing.
        """
        self.assertFalse(
            (self.root_dir / "setup.py").exists(),
            "setup.py is back; pyproject.toml already declares this package, "
            "and the duplicate is what drifted to python_requires>=3.10")

    def test_ci_matrix_covers_only_supported_versions(self):
        ci = self.root_dir / ".github" / "workflows" / "ci.yml"
        if not ci.is_file():
            self.skipTest("no ci.yml")
        text = ci.read_text(encoding="utf-8")
        match = re.search(r"python-version:\s*\[([^\]]+)\]", text)
        if not match:
            self.skipTest("no python-version matrix in ci.yml")

        required = self._minor(self.cfg["project"]["requires-python"])
        tested = [int(v) for v in re.findall(r"3\.(\d+)", match.group(1))]
        too_old = [f"3.{v}" for v in tested if v < required]
        self.assertEqual(
            too_old, [],
            f"CI tests {too_old}, which requires-python "
            f"{self.cfg['project']['requires-python']} does not allow")
        self.assertIn(
            required, tested,
            f"CI never tests 3.{required}, the minimum the project claims "
            f"to support")


if __name__ == "__main__":
    unittest.main()
