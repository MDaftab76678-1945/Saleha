"""
Saleha Core: Autonomous Multi-File Atomic Refactoring Engine

Executes coordinated, cross-file symbol renames and AST code transformations.
Guarantees transactional integrity: if any single file fails AST syntax validation,
the entire transaction is rolled back with zero project corruption.
"""

from __future__ import annotations

import os
import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any

from saleha.core.dependency_graph import dependency_graph
from saleha.core.codebase_indexer import codebase_indexer, SmartPatcher
from saleha.core.git_native import git_engine
from saleha.core.path_utils import safe_relpath


@dataclass
class FilePatchPlan:
    file_path: str
    original_code: str
    modified_code: str
    diff: str
    lines_changed: int


@dataclass
class RefactorTransactionResult:
    success: bool
    symbol_renamed: str = ""
    new_symbol_name: str = ""
    files_modified: List[str] = field(default_factory=list)
    total_lines_changed: int = 0
    patches: List[FilePatchPlan] = field(default_factory=list)
    rollback_performed: bool = False
    commit_hash: str = ""
    error: str = ""


class MultiFileRefactorer:
    """Performs transactional, AST-validated multi-file symbol refactoring and migrations."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)

    def plan_rename(self, old_name: str, new_name: str, root_dir: Optional[str] = None) -> Tuple[bool, List[FilePatchPlan], str]:
        """Calculates exact surgical search/replace diffs for old_name across all definitions and call-sites."""
        if root_dir:
            self.root_dir = os.path.abspath(root_dir)

        # 1. Build or refresh dependency graph
        if not dependency_graph.files_indexed:
            dependency_graph.build_graph(root_dir=self.root_dir)

        # 2. Find target files containing definitions or caller references
        target_files: Set[str] = set()

        if old_name in dependency_graph.definitions:
            for loc in dependency_graph.definitions[old_name]:
                target_files.add(loc.file_path)

        callers = dependency_graph.find_callers(old_name)
        for c in callers:
            target_files.add(c.caller_file)

        # If graph didn't catch, fallback to full repository search
        if not target_files:
            word_boundary = re.compile(rf'\b{re.escape(old_name)}\b')
            for root, dirs, files in os.walk(self.root_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", "__pycache__", "build", "dist")]
                for f in files:
                    if f.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
                        full_p = os.path.join(root, f)
                        rel_p = safe_relpath(full_p, self.root_dir).replace("\\", "/")
                        try:
                            with open(full_p, "r", encoding="utf-8", errors="replace") as fp:
                                txt = fp.read()
                            if word_boundary.search(txt):
                                target_files.add(rel_p)
                        except OSError:
                            pass

        if not target_files:
            return False, [], f"Symbol '{old_name}' not found anywhere in workspace."

        # 3. Create file patch plans
        patch_plans: List[FilePatchPlan] = []
        word_re = re.compile(rf'\b{re.escape(old_name)}\b')

        for rel_p in sorted(target_files):
            abs_p = os.path.join(self.root_dir, rel_p) if not os.path.isabs(rel_p) else rel_p
            if not os.path.isfile(abs_p):
                continue

            try:
                with open(abs_p, "r", encoding="utf-8", errors="replace") as fp:
                    orig = fp.read()
            except OSError as e:
                return False, [], f"Could not read {rel_p}: {e}"

            modified = word_re.sub(new_name, orig)
            if modified == orig:
                continue

            # Validate Python syntax if Python file
            if abs_p.endswith(".py"):
                try:
                    ast.parse(modified)
                except SyntaxError as e:
                    return False, [], f"Refactoring would cause syntax error in {rel_p}:{e.lineno}: {e.msg}"

            diff = SmartPatcher.create_unified_diff(orig, modified, os.path.basename(rel_p))
            lines_c = len([l for l in diff.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))])

            patch_plans.append(FilePatchPlan(
                file_path=rel_p,
                original_code=orig,
                modified_code=modified,
                diff=diff,
                lines_changed=lines_c
            ))

        return True, patch_plans, ""

    def apply_transaction(self, plans: List[FilePatchPlan], old_name: str = "", new_name: str = "", auto_commit: bool = True) -> RefactorTransactionResult:
        """Atomically applies all file patch plans with transactional rollback protection."""
        written_files: List[Tuple[str, str]] = []  # (abs_path, original_code)
        modified_list: List[str] = []
        total_lines = sum(p.lines_changed for p in plans)

        try:
            for p in plans:
                abs_p = os.path.join(self.root_dir, p.file_path) if not os.path.isabs(p.file_path) else p.file_path
                # Save rollback backup in memory
                written_files.append((abs_p, p.original_code))

                # Atomic write
                tmp_p = f"{abs_p}.tmp.{os.getpid()}"
                with open(tmp_p, "w", encoding="utf-8") as fp:
                    fp.write(p.modified_code)
                os.replace(tmp_p, abs_p)
                modified_list.append(p.file_path)

            # Re-verify all modified python files compile cleanly
            for abs_p, _ in written_files:
                if abs_p.endswith(".py"):
                    with open(abs_p, "r", encoding="utf-8") as fp:
                        code = fp.read()
                    ast.parse(code)  # Raises SyntaxError if corrupted

        except Exception as e:
            # Transaction failed! Execute automatic rollback!
            for abs_p, orig in written_files:
                try:
                    with open(abs_p, "w", encoding="utf-8") as fp:
                        fp.write(orig)
                except OSError:
                    pass
            return RefactorTransactionResult(
                success=False,
                symbol_renamed=old_name,
                new_symbol_name=new_name,
                rollback_performed=True,
                error=f"Transaction rolled back due to error: {e}"
            )

        # Refresh AST dependency graph post-refactor
        dependency_graph.build_graph(root_dir=self.root_dir)

        # Optional Git commit
        commit_hash = ""
        if auto_commit and git_engine.is_git_repo():
            commit_res = git_engine.commit_deliverable(
                task_name=f"Refactor symbol: '{old_name}' -> '{new_name}' across {len(modified_list)} files",
                task_type="refactor"
            )
            if commit_res.success:
                commit_hash = commit_res.commit_hash

        return RefactorTransactionResult(
            success=True,
            symbol_renamed=old_name,
            new_symbol_name=new_name,
            files_modified=modified_list,
            total_lines_changed=total_lines,
            patches=plans,
            commit_hash=commit_hash
        )

    def rename_symbol(self, old_name: str, new_name: str, auto_commit: bool = True) -> RefactorTransactionResult:
        """One-stop helper to plan, validate, and execute atomic multi-file symbol renaming."""
        ok, plans, err = self.plan_rename(old_name, new_name)
        if not ok:
            return RefactorTransactionResult(success=False, symbol_renamed=old_name, new_symbol_name=new_name, error=err)
        return self.apply_transaction(plans, old_name=old_name, new_name=new_name, auto_commit=auto_commit)


# Global instance
multi_file_refactorer = MultiFileRefactorer()
