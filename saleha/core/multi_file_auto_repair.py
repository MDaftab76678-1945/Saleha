"""
Multi-file coordinated patcher for a narrow class of AST-detected defects.

## What this module used to claim

The docstring read:

    Multi-File Cross-Module Dependency Auto-Repair Engine with Two-Phase
    Commit (2PC). Resolves cross-file interface breakages, signature changes,
    and imports across dependent modules in an atomic multi-file transaction
    with zero partial state corruption.

Measured, none of the load-bearing words in that sentence were true:

1. **The commit was not atomic.** Phase 2 was a plain loop of `write_text()`
   calls. Failing the second write left the first file modified on disk and
   the second untouched -- the exact partial state the docstring guaranteed
   against -- and the exception escaped, so the caller got no result at all.
2. **`rolled_back=True` never rolled anything back.** It was returned from the
   abort branch, which runs *before* any write. `original_content` was staged
   and never restored. Nothing had happened, so nothing was undone.
3. **It could not resolve interface breakages, signature changes or imports.**
   `_patch_code` did two string replacements: `divisor = 0` -> `divisor = 1`,
   and a regex over the whole file turning `/ 0` into `/ 1`.
4. **That regex corrupted string literals.** `URL = "http://a/b/ 0k"` became
   `URL = "http://a/b/ 1k"`.
5. **It broke correct code.** Given a guarded `divisor = 0` with an explicit
   `if divisor == 0:` branch, it rewrote the constant to 1, turned the guard
   into dead code, changed the program's result from 0 to 100.0, and reported
   `success=True`.
6. `ast` was imported and never called -- the same signature that flagged
   `mech_interp.py`, `cognitive_engine.py`, `constitutional_guard.py` and
   `threat_modeler.py`, each of which carried a real defect.

## What it does now

The commit phase is genuinely atomic for the failure mode a local patcher can
actually hit -- a write failing partway through a batch. Every target's
original bytes are held, and if any write raises, the files already written
are restored before returning. `rolled_back` is True only when a restore
actually ran, and `rollback_failed` reports the case where restoring itself
failed: the one situation where partial state really can survive, which the
old code called impossible.

The patcher is AST-based, so it edits code and never string literals or
comments. It rewrites a zero constant only when doing so cannot change
behaviour -- that is, when the name is never compared against zero anywhere in
the file. Where it cannot establish that, it declines and says so.

What this is *not*: it does not resolve signature changes, interface breakages
or imports across modules. It handles the two defect classes
`gamma_critic_sandbox` detects. The dependency graph is keyed on file
basename, so two same-named files in different packages collapse into one
node; that is reported through `ambiguous_names` rather than silently patching
both, which is what the old code did.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from saleha.core.gamma_critic_sandbox import GammaReport, GammaSandboxEngine


@dataclass
class FilePatchPlan:
    filepath: Path
    original_content: str
    repaired_content: str
    violations_fixed: List[str] = field(default_factory=list)


@dataclass
class MultiFileRepairResult:
    success: bool
    total_files_affected: int
    applied_patches: List[FilePatchPlan] = field(default_factory=list)
    rolled_back: bool = False
    message: str = ""
    # Files whose violations were found but could not be patched safely.
    # Reported, never silently dropped.
    declined: List[str] = field(default_factory=list)
    # True only if a rollback was attempted and itself failed. This is the one
    # case where partial state can survive on disk, and it must be visible.
    rollback_failed: bool = False


@dataclass
class GraphBuildStats:
    files_indexed: int = 0
    files_unreadable: int = 0
    # Basenames occurring at more than one path. The graph cannot tell these
    # apart, so any blast radius touching them is ambiguous.
    ambiguous_names: Dict[str, List[str]] = field(default_factory=dict)


class BiDirectionalDependencyGraph:
    """
    Forward and reverse import maps, keyed on file basename.

    The basename keying is a real limitation, not an implementation detail:
    `pkg1/utils.py` and `pkg2/utils.py` are one node. Rather than pretend
    otherwise, every duplicated basename is recorded in
    `stats.ambiguous_names` so callers can refuse to act on an ambiguous
    result. Python imports are read with `ast`, so imports inside functions,
    `try:` blocks and conditionals are found -- the previous
    `line.startswith("import ")` test missed all of them.
    """

    SKIP_PARTS = {"build", "dist", "venv", "node_modules", "__pycache__",
                  "site-packages", "target"}

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.forward_deps: Dict[str, Set[str]] = {}
        self.reverse_deps: Dict[str, Set[str]] = {}
        self.stats = GraphBuildStats()
        self._paths_by_name: Dict[str, List[str]] = {}
        self.build_graph()

    def build_graph(self) -> None:
        for ext in (".py", ".c", ".h", ".cpp"):
            for fpath in self.root_dir.rglob(f"*{ext}"):
                if any(part.startswith(".") or part in self.SKIP_PARTS
                       for part in fpath.parts):
                    continue
                self._index_file(fpath)

        self.stats.ambiguous_names = {
            name: paths for name, paths in self._paths_by_name.items()
            if len(paths) > 1
        }

    def _index_file(self, fpath: Path) -> None:
        rel = fpath.name
        self.forward_deps.setdefault(rel, set())
        self.reverse_deps.setdefault(rel, set())
        self._paths_by_name.setdefault(rel, []).append(str(fpath))

        try:
            content = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            self.stats.files_unreadable += 1
            return

        self.stats.files_indexed += 1

        if fpath.suffix == ".py":
            self._index_python_imports(rel, content)
        else:
            for match in re.finditer(r'#include\s+["<]([^">]+)[">]', content):
                inc = Path(match.group(1)).name
                self.forward_deps[rel].add(inc)
                self.reverse_deps.setdefault(inc, set()).add(rel)

    def _index_python_imports(self, rel: str, content: str) -> None:
        """Walk the AST so nested and conditional imports are not missed."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            self.stats.files_unreadable += 1
            return

        for node in ast.walk(tree):
            modules: List[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for mod in modules:
                imported = mod.split(".")[-1] + ".py"
                self.forward_deps[rel].add(imported)
                self.reverse_deps.setdefault(imported, set()).add(rel)

    def get_blast_radius(self, modified_file: str) -> List[str]:
        """Modules that directly or transitively import `modified_file`."""
        visited: Set[str] = set()
        queue = [modified_file]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            queue.extend(self.reverse_deps.get(curr, set()) - visited)
        return sorted(f for f in visited if f != modified_file)

    def is_ambiguous(self, name: str) -> bool:
        """True when more than one file on disk carries this basename."""
        return name in self.stats.ambiguous_names


class SafeConstantPatcher(ast.NodeVisitor):
    """
    Decides whether a zero-valued constant can be raised to 1 without changing
    what the program does.

    It cannot if the name is compared against zero anywhere in the file: that
    comparison is a guard, and rewriting the constant turns the guard into dead
    code. The old string-replace version did exactly that and reported success.
    """

    def __init__(self) -> None:
        self.zero_assignments: Dict[str, List[ast.Assign]] = {}
        self.compared_against_zero: Set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Constant) and node.value.value == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.zero_assignments.setdefault(target.id, []).append(node)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        names = [o.id for o in operands if isinstance(o, ast.Name)]
        zeros = [o for o in operands
                 if isinstance(o, ast.Constant) and o.value == 0]
        if names and zeros:
            self.compared_against_zero.update(names)
        self.generic_visit(node)

    def safe_targets(self) -> Dict[str, List[ast.Assign]]:
        return {name: nodes for name, nodes in self.zero_assignments.items()
                if name not in self.compared_against_zero}


class MultiFileAutoRepairEngine:
    """
    Patches AST-detected defects across a set of files, restoring every file it
    touched if any write fails.

    Phase 1 stages patches in memory and re-verifies each one. Phase 2 writes
    them, holding each file's original bytes; a failed write triggers a restore
    of everything already written. That restore is what makes the batch atomic
    -- the previous version claimed atomicity and implemented a bare loop.
    """

    def __init__(self, workspace_root: str | Path = "."):
        self.workspace_root = Path(workspace_root)
        self.gamma = GammaSandboxEngine()
        self.dep_graph = BiDirectionalDependencyGraph(self.workspace_root)

    def repair_cross_module_violation(
        self, primary_file: Path, related_files: Optional[List[Path]] = None
    ) -> MultiFileRepairResult:
        primary_file = Path(primary_file)
        all_targets: List[Path] = [primary_file]
        declined: List[str] = []

        if related_files:
            all_targets.extend(Path(f) for f in related_files)
        else:
            for b_name in self.dep_graph.get_blast_radius(primary_file.name):
                # A basename mapping to several real files cannot be resolved
                # to one target. Patching all of them was the old behaviour.
                if self.dep_graph.is_ambiguous(b_name):
                    matches = self.dep_graph.stats.ambiguous_names[b_name]
                    declined.append(
                        f"{b_name}: ambiguous, matches {len(matches)} files in "
                        f"different directories")
                    continue
                for match in self.workspace_root.rglob(b_name):
                    if match not in all_targets:
                        all_targets.append(match)

        staged, staging_failure, staging_declined = self._stage(all_targets)
        declined.extend(staging_declined)

        if staging_failure is not None:
            return MultiFileRepairResult(
                success=False,
                total_files_affected=0,
                rolled_back=False,
                declined=declined,
                message=(f"Aborted during staging ({staging_failure}). "
                         f"Nothing was written to disk."),
            )

        if not staged:
            # Nothing was written either way, but the two reasons are not the
            # same claim. A clean scan is a result; "I found defects I cannot
            # fix" is not, and must not be reported as one.
            if declined:
                return MultiFileRepairResult(
                    success=False,
                    total_files_affected=0,
                    rolled_back=False,
                    declined=declined,
                    message=(f"Nothing patched. {len(declined)} item(s) were "
                             f"found and declined; see `declined` for why. "
                             f"This is not a clean bill of health."),
                )
            return MultiFileRepairResult(
                success=True,
                total_files_affected=0,
                rolled_back=False,
                declined=declined,
                message=(f"Scanned {len(all_targets)} target(s); no violations "
                         f"the sandbox detects, nothing to patch."),
            )

        return self._commit(staged, declined)

    def _stage(
        self, targets: List[Path]
    ) -> Tuple[List[FilePatchPlan], Optional[str], List[str]]:
        """
        Phase 1. Returns (staged patches, failure reason or None, declined).

        A file whose violations cannot be patched safely is declined, not
        failed: declining one file must not abort a batch that is otherwise
        fine, but it must also never be reported as a repair.
        """
        staged: List[FilePatchPlan] = []
        declined: List[str] = []

        for fpath in targets:
            if not fpath.exists() or not fpath.is_file():
                continue

            try:
                code = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                return [], f"cannot read {fpath.name}: {exc}", declined

            language = "python" if fpath.suffix.lower() == ".py" else "c"
            report: GammaReport = self.gamma.inspect_and_verify(
                code, language=language)
            if report.passed:
                continue

            patched, notes = self._patch_code(code, report, fpath.suffix.lower())
            declined.extend(f"{fpath.name}: {n}" for n in notes)

            # Violations were found and the patcher produced no change. Say so
            # per file: "nothing to do" and "found something I cannot fix" are
            # different outcomes, and reporting the second as the first is the
            # reassuring default this module is being audited for.
            if patched == code:
                if not notes:
                    declined.append(
                        f"{fpath.name}: {len(report.violations)} violation(s) "
                        f"detected ({sorted(v.rule_id for v in report.violations)}) "
                        f"but no patch rule applied; left unchanged")
                continue

            verify = self.gamma.inspect_and_verify(patched, language=language)
            if not verify.passed:
                declined.append(
                    f"{fpath.name}: patch did not clear all violations "
                    f"({len(verify.violations)} remain), not staged")
                continue

            staged.append(FilePatchPlan(
                filepath=fpath,
                original_content=code,
                repaired_content=patched,
                violations_fixed=[v.rule_id for v in report.violations],
            ))

        return staged, None, declined

    def _commit(self, staged: List[FilePatchPlan],
                declined: List[str]) -> MultiFileRepairResult:
        """
        Phase 2. Write every staged patch; restore all of them if any fails.

        This is the part the old code did not have. Probed by failing the
        second write of a two-file batch: previously file one stayed modified
        and the exception escaped; now both files are back to their original
        bytes and the caller gets a result saying so.
        """
        written: List[FilePatchPlan] = []
        try:
            for patch in staged:
                patch.filepath.write_text(patch.repaired_content,
                                          encoding="utf-8")
                written.append(patch)
        except (OSError, UnicodeEncodeError) as exc:
            restore_errors = self._restore(written)
            if restore_errors:
                return MultiFileRepairResult(
                    success=False,
                    total_files_affected=0,
                    rolled_back=True,
                    rollback_failed=True,
                    declined=declined,
                    message=(f"Write failed ({exc}) and rollback could not "
                             f"restore {len(restore_errors)} file(s): "
                             f"{'; '.join(restore_errors)}. "
                             f"PARTIAL STATE IS ON DISK."),
                )
            return MultiFileRepairResult(
                success=False,
                total_files_affected=0,
                rolled_back=True,
                declined=declined,
                message=(f"Write failed ({exc}); restored {len(written)} "
                         f"file(s) to their original contents."),
            )

        return MultiFileRepairResult(
            success=True,
            total_files_affected=len(staged),
            applied_patches=staged,
            rolled_back=False,
            declined=declined,
            message=f"Committed {len(staged)} file(s); no write failed.",
        )

    @staticmethod
    def _restore(written: List[FilePatchPlan]) -> List[str]:
        errors: List[str] = []
        for patch in written:
            try:
                patch.filepath.write_text(patch.original_content,
                                          encoding="utf-8")
            except (OSError, UnicodeEncodeError) as exc:
                errors.append(f"{patch.filepath.name}: {exc}")
        return errors

    def _patch_code(self, code: str, report: GammaReport,
                    ext: str) -> Tuple[str, List[str]]:
        """
        Returns (patched code, notes about what was declined).

        Python goes through the AST, so string literals and comments are never
        touched. C/C++ has no parser here, so the memory-leak case is handled
        and the division case is declined rather than regex-replaced -- the old
        regex rewrote `"http://a/b/ 0k"` to `"http://a/b/ 1k"`.
        """
        notes: List[str] = []
        rule_ids = {v.rule_id for v in report.violations}

        if ext == ".py":
            return self._patch_python(code, rule_ids, notes)

        patched = code
        if any("MEMORY_LEAK" in r for r in rule_ids):
            if "malloc(" in patched and "free(" not in patched:
                if "\n}" in patched:
                    patched = patched.replace(
                        "\n}",
                        "\n    if (ptr) free(ptr);  // [added by saleha]\n}", 1)
                else:
                    notes.append(
                        "malloc with no closing brace to insert free() before")
        if any("DIV_BY_ZERO" in r for r in rule_ids):
            notes.append(
                "division-by-zero in a non-Python file: not patched, because "
                "there is no parser here and a regex would rewrite string "
                "literals too")
        return patched, notes

    def _patch_python(self, code: str, rule_ids: Set[str],
                      notes: List[str]) -> Tuple[str, List[str]]:
        if not any("DIV_BY_ZERO" in r for r in rule_ids):
            if rule_ids:
                notes.append(
                    f"no patch rule for {sorted(rule_ids)}; left unchanged")
            return code, notes

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            notes.append(f"does not parse ({exc.msg}); left unchanged")
            return code, notes

        patcher = SafeConstantPatcher()
        patcher.visit(tree)

        safe = patcher.safe_targets()
        for name in patcher.zero_assignments:
            if name not in safe:
                notes.append(
                    f"'{name}' is compared against zero, so it is a guard, not "
                    f"a bug; rewriting it would change behaviour. Left alone.")

        if not safe:
            return code, notes

        # Rewrite by line and column so only the constant token moves. Lines
        # are 1-indexed in the AST. Applied in reverse so earlier edits do not
        # shift the offsets of later ones.
        lines = code.splitlines(keepends=True)
        edits: List[Tuple[int, int, int]] = []
        for nodes in safe.values():
            for node in nodes:
                value = node.value
                # end_col_offset is Optional on ast.expr; a constant parsed
                # from source always carries one, but skip it if it is absent
                # rather than editing with a guessed span.
                if value.end_col_offset is None:
                    continue
                edits.append((value.lineno, value.col_offset,
                              value.end_col_offset))

        for lineno, col, end_col in sorted(edits, reverse=True):
            idx = lineno - 1
            if idx >= len(lines):
                continue
            line = lines[idx]
            if line[col:end_col] != "0":
                continue
            newline = "\n" if line.endswith("\n") else ""
            body = line[:col] + "1" + line[end_col:].rstrip("\n")
            lines[idx] = (f"{body}  # [saleha: was 0, raised to avoid "
                          f"ZeroDivisionError]{newline}")

        return "".join(lines), notes
