"""Documentation must not drift away from the code it describes.

Every check here replaces something that was found by hand. Pass 84 spent a
session manually diffing docs against the repo and found: a persona catalog
claiming 20 entries when 30 files existed, a capability matrix listing tool
names that appear nowhere in the codebase, context-window figures 10-20x
below the real registry, and referenced file paths that do not exist. All of
those are mechanically detectable, so a human should never be the mechanism
again.

These tests are deliberately about *checkable* facts -- counts, paths,
identifiers -- not prose. A doc may describe intent freely; it may not state
a number or a filename that the repository contradicts.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Set

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


class PersonaCatalogTests(unittest.TestCase):
    """docs/AGENT_PROFILES.md vs the real saleha/skills/agent_*.md files."""

    def setUp(self) -> None:
        self.doc = _read("docs/AGENT_PROFILES.md")
        self.actual: Set[str] = {
            p.stem for p in (REPO_ROOT / "saleha" / "skills").glob("agent_*.md")
        }
        self.documented: Set[str] = set(
            re.findall(r"`(agent_[a-z0-9_]+)`", self.doc)
        )

    def test_every_documented_persona_has_a_real_file(self) -> None:
        """A ghost entry is worse than a missing one -- it is a false claim."""
        ghosts = sorted(self.documented - self.actual)
        self.assertEqual(ghosts, [], f"documented but no file exists: {ghosts}")

    def test_every_real_persona_is_documented(self) -> None:
        missing = sorted(self.actual - self.documented)
        self.assertEqual(
            missing, [], f"persona files absent from the catalog: {missing}"
        )

    def test_the_stated_count_matches_the_file_count(self) -> None:
        """The doc claimed '20 specialized domain personas' while 30 shipped."""
        stated = {int(n) for n in re.findall(r"(\d+)\s+[Ss]pecialized", self.doc)}
        self.assertTrue(stated, "no 'N specialized' count found in the catalog")
        for n in stated:
            self.assertEqual(
                n, len(self.actual),
                f"catalog says {n} personas, {len(self.actual)} files exist",
            )


class CapabilityMatrixTests(unittest.TestCase):
    """AGENTSKILLS.md's tool names must be ones the loader really accepts."""

    def test_documented_tools_appear_in_real_profile_frontmatter(self) -> None:
        """The matrix once listed sandbox_jail / math_engine / ast_cache --
        module names, not tool identifiers. The real vocabulary is whatever
        the profiles declare and agent_profile_loader.py reads."""
        real_tools: Set[str] = set()
        for p in (REPO_ROOT / "saleha" / "skills").glob("agent_*.md"):
            head = p.read_text(encoding="utf-8").split("---")[:3]
            block = "\n".join(head)
            m = re.search(r"allowed_tools:(.*?)(?:\n[a-z_]+:|\Z)", block, re.S)
            if m:
                real_tools.update(re.findall(r'"([a-z_]+)"', m.group(1)))
        self.assertTrue(real_tools, "no allowed_tools found in any profile")

        doc = _read("AGENTSKILLS.md")
        table = "\n".join(
            ln for ln in doc.splitlines()
            if ln.startswith("| `agent_")
        )
        cited = set(re.findall(r"`([a-z_]+)`", table)) - {
            t for t in re.findall(r"`(agent_[a-z0-9_]+)`", table)
        }
        unknown = sorted(cited - real_tools)
        self.assertEqual(
            unknown, [],
            f"capability matrix cites tools no profile grants: {unknown}",
        )


class ContextWindowTests(unittest.TestCase):
    """Any context-window figure in a doc must match context_budget.py."""

    def test_documented_windows_match_the_registry(self) -> None:
        """AGENTSKILLS.md claimed 2048/4096; the registry says 32768/40960.
        An agent following the doc would prune to 6% of the real window."""
        from saleha.core.context_budget import KNOWN_CONTEXT_WINDOWS

        doc = _read("AGENTSKILLS.md")
        # Only inspect lines that name a model and a number together.
        for line in doc.splitlines():
            for model, real in KNOWN_CONTEXT_WINDOWS.items():
                if f"`{model}`" not in line:
                    continue
                numbers = {
                    int(n) for n in re.findall(r"\b(\d{3,6})\b", line)
                }
                # Ignore numbers that are clearly not window sizes.
                windows = {n for n in numbers if n >= 1024}
                if not windows:
                    continue
                self.assertIn(
                    real, windows,
                    f"{model}: doc line cites {sorted(windows)}, "
                    f"registry says {real} -- {line.strip()[:110]}",
                )


class ReferencedPathTests(unittest.TestCase):
    """A doc that names a file path must name one that exists."""

    DOCS = ("EVALS.md", "AGENTSKILLS.md", "AGENTS.md", "DEVELOPMENT.md")

    # Matches saleha/..., scripts/..., docs/... style paths with a real suffix.
    PATH_RE = re.compile(
        r"`((?:saleha|scripts|docs|packages|apps|tools|templates)"
        r"/[A-Za-z0-9_./-]+\.(?:py|md|json|toml|yaml|yml|ts|tsx))`"
    )

    def test_referenced_files_exist(self) -> None:
        """EVALS.md pointed at evaluate_artificial_analysis_benchmarks.py and
        test_emergence_honest.py; neither has ever existed."""
        missing = []
        for doc in self.DOCS:
            for rel in self.PATH_RE.findall(_read(doc)):
                if "*" in rel or "<" in rel:
                    continue
                if not (REPO_ROOT / rel).exists():
                    missing.append(f"{doc} -> {rel}")
        self.assertEqual(missing, [], f"docs cite non-existent files: {missing}")


class InstalledModelClaimTests(unittest.TestCase):
    """Model names quoted in docs must be ones the project actually targets."""

    def test_docs_do_not_cite_unknown_models(self) -> None:
        """.saleharules was generated with reasoning_flagship='deepseek-r1:8b',
        a model that is not installed and never was (it is 7b)."""
        from saleha.core.context_budget import KNOWN_CONTEXT_WINDOWS

        known = set(KNOWN_CONTEXT_WINDOWS) | {
            "nomic-embed-text", "gemma4:31b-cloud", "qwen3.5:4b",
            "qwen2.5-coder:1.5b",  # referenced historically in training configs
        }
        text = _read(".saleharules")
        cited = set(re.findall(r'"([a-z0-9.]+:[a-z0-9.]+)"', text))
        unknown = sorted(cited - known)
        self.assertEqual(
            unknown, [],
            f".saleharules names models absent from the registry: {unknown}",
        )


if __name__ == "__main__":
    unittest.main()
