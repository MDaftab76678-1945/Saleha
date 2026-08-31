"""
Saleha Core: Interactive Project Onboarding Wizard

Detects workspace programming language, framework dependencies, initializes
codebase architectural conventions (.saleharules), and builds baseline AST indices.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.core.dependency_graph import dependency_graph


@dataclass
class ProjectInitSummary:
    project_name: str
    detected_languages: List[str]
    rules_file_created: str
    ast_symbols_indexed: int
    files_indexed: int
    success: bool = True


class ProjectInitializer:
    """Initializes new or existing codebases for Saleha autonomous engineering."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)

    def detect_stack(self) -> List[str]:
        """Scans workspace markers to determine language and framework ecosystem."""
        langs = []
        if os.path.exists(os.path.join(self.root_dir, "pyproject.toml")) or any(f.endswith(".py") for f in os.listdir(self.root_dir) if os.path.isfile(os.path.join(self.root_dir, f))):
            langs.append("Python")
        if os.path.exists(os.path.join(self.root_dir, "package.json")):
            langs.append("TypeScript/JavaScript")
        if os.path.exists(os.path.join(self.root_dir, "go.mod")):
            langs.append("Go")
        if os.path.exists(os.path.join(self.root_dir, "Cargo.toml")):
            langs.append("Rust")
        if os.path.exists(os.path.join(self.root_dir, "pom.xml")) or os.path.exists(os.path.join(self.root_dir, "build.gradle")):
            langs.append("Java")

        return langs or ["Python"]

    def create_saleharules(self, force: bool = False) -> str:
        """Generates standard .saleharules conventions file in workspace root."""
        rules_path = os.path.join(self.root_dir, ".saleharules")
        if os.path.exists(rules_path) and not force:
            return rules_path

        p_name = os.path.basename(self.root_dir)
        langs = ", ".join(self.detect_stack())

        content = f"""# Saleha AI Project Architecture Rules
# Project: {p_name}
# Stack: {langs}
# Generated: {time.strftime('%Y-%m-%d')}

[conventions]
- Maintain 100% type annotations across all function signatures.
- All code modifications must use surgical Aider-style search/replace diffs.
- Run tests in sandbox before committing changes.
- Never commit unmasked secrets, private keys, or plain-text credentials.

[models]
fast_tier = "qwen2.5-coder:1.5b"
reasoning_flagship = "deepseek-r1:8b"

[sandboxing]
mode = "subprocess_hardened"
timeout_sec = 300
"""
        tmp_p = f"{rules_path}.tmp.{os.getpid()}"
        with open(tmp_p, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_p, rules_path)

        return rules_path

    def initialize_workspace(self, force: bool = False) -> ProjectInitSummary:
        """Executes full project onboarding sequence."""
        stack = self.detect_stack()
        rules_p = self.create_saleharules(force=force)

        # Build baseline AST dependency index
        dependency_graph.build_graph(root_dir=self.root_dir)

        return ProjectInitSummary(
            project_name=os.path.basename(self.root_dir),
            detected_languages=stack,
            rules_file_created=rules_p,
            ast_symbols_indexed=len(dependency_graph.definitions),
            files_indexed=len(dependency_graph.files_indexed),
            success=True
        )


# Global instance
project_initializer = ProjectInitializer()

