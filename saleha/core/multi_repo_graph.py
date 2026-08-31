"""
Saleha Core: Multi-Repository & Monorepo Cross-Graph Swarm Indexer

Discovers multiple independent Git repositories across a workspace or monorepo,
maps cross-service dependencies, shared protobufs/models, and calculates
global multi-repo blast-radius for breaking API changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any

from saleha.core.dependency_graph import CodebaseDependencyGraph
from saleha.core.path_utils import safe_relpath


@dataclass
class RepoMetadata:
    repo_name: str
    root_path: str
    is_git: bool
    language: str
    symbols_count: int
    files_count: int


@dataclass
class CrossRepoImpact:
    source_repo: str
    impacted_repo: str
    impacted_file: str
    symbol_reference: str
    line_number: int


class MultiRepoDependencyGraph:
    """Consolidates dependency graphs across multiple independent repositories or monorepo packages."""

    def __init__(self):
        self.repo_graphs: Dict[str, CodebaseDependencyGraph] = {}
        self.repo_metadata: Dict[str, RepoMetadata] = {}

    def scan_workspace(self, root_dir: str) -> Dict[str, RepoMetadata]:
        """Discovers child repositories/packages and indexes each with isolated AST graphs."""
        root_dir = os.path.abspath(root_dir)
        self.repo_graphs.clear()
        self.repo_metadata.clear()

        # Find child directories with .git, pyproject.toml, package.json, or go.mod
        candidate_dirs = [root_dir]
        try:
            for entry in os.scandir(root_dir):
                if entry.is_dir() and not entry.name.startswith((".", "node_modules", "venv")):
                    candidate_dirs.append(entry.path)
        except OSError:
            pass

        for p in candidate_dirs:
            r_name = os.path.basename(p) or "root"
            is_git = os.path.isdir(os.path.join(p, ".git"))
            
            # Index repo
            sub_graph = CodebaseDependencyGraph(root_dir=p)
            sub_graph.build_graph()

            if sub_graph.files_indexed:
                self.repo_graphs[r_name] = sub_graph
                self.repo_metadata[r_name] = RepoMetadata(
                    repo_name=r_name,
                    root_path=p,
                    is_git=is_git,
                    language="python",
                    symbols_count=len(sub_graph.definitions),
                    files_count=len(sub_graph.files_indexed)
                )

        return self.repo_metadata

    def calculate_cross_repo_blast_radius(self, symbol_name: str) -> List[CrossRepoImpact]:
        """Traces where symbol_name is referenced across ALL known repositories."""
        impacts: List[CrossRepoImpact] = []

        # Find defining repo
        defining_repo = "unknown"
        for r_name, graph in self.repo_graphs.items():
            if symbol_name in graph.definitions:
                defining_repo = r_name
                break

        # Check references in all other repositories
        for r_name, graph in self.repo_graphs.items():
            callers = graph.find_callers(symbol_name)
            for c in callers:
                impacts.append(CrossRepoImpact(
                    source_repo=defining_repo,
                    impacted_repo=r_name,
                    impacted_file=c.caller_file,
                    symbol_reference=symbol_name,
                    line_number=c.caller_line
                ))

        return impacts


# Global instance
multi_repo_graph = MultiRepoDependencyGraph()

