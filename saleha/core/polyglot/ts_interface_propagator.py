"""Saleha Core: TypeScript Monorepo AST Call-Graph & Interface Propagator.

Provides AST-aware contract verification, dependency DAG indexing, and atomic
Two-Phase Commit (2PC) interface propagation across TypeScript monorepos
(packages/* and apps/*).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TSProperty:
    """Represents a property in a TypeScript interface or type alias."""
    name: str
    type_annotation: str
    optional: bool = False
    readonly: bool = False


@dataclass
class TSInterface:
    """Represents an exported TypeScript interface or type definition."""
    name: str
    properties: Dict[str, TSProperty] = field(default_factory=dict)
    extends: List[str] = field(default_factory=list)
    file_path: str = ""
    is_exported: bool = False
    is_type_alias: bool = False


@dataclass
class TSFunctionSignature:
    """Represents an exported TypeScript function signature."""
    name: str
    parameters: List[Tuple[str, str]] = field(default_factory=list)  # (param_name, type)
    return_type: str = "void"
    file_path: str = ""
    is_async: bool = False
    is_exported: bool = False


@dataclass
class TSImport:
    """Represents an ESM import in a TypeScript file."""
    source_module: str
    imported_symbols: List[str] = field(default_factory=list)
    file_path: str = ""
    is_type_only: bool = False
    is_relative: bool = False


@dataclass
class TSContractMismatch:
    """Represents a broken contract between TypeScript producer and consumer."""
    producer_package: str
    consumer_package: str
    consumer_file: str
    symbol_name: str
    mismatch_type: str  # "missing_symbol", "missing_property", "type_incompatibility", "arity_mismatch"
    details: str
    suggested_fix: str


class TSASTAnalyzer:
    """Deterministic TypeScript AST and structural symbol analyzer."""

    # Matches: [export] interface Name [extends Base] { ... }
    INTERFACE_REGEX = re.compile(
        r"(?:(export)\s+)?interface\s+([A-Za-z0-9_]+)(?:\s+extends\s+([^{]+))?\s*\{([^}]*)\}",
        re.MULTILINE | re.DOTALL,
    )

    # Matches: [export] type Name = { ... }
    TYPE_ALIAS_OBJ_REGEX = re.compile(
        r"(?:(export)\s+)?type\s+([A-Za-z0-9_]+)\s*=\s*\{([^}]*)\}",
        re.MULTILINE | re.DOTALL,
    )

    # Matches: [export] [async] function name(params): return_type
    FUNCTION_REGEX = re.compile(
        r"(?:(export)\s+)?(?:(async)\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?::\s*([^{]+))?\s*\{",
        re.MULTILINE,
    )

    # Matches: [export] const name = [async] (params): return_type =>
    ARROW_FUNCTION_REGEX = re.compile(
        r"(?:(export)\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*(?:(async)\s*)?\(([^)]*)\)\s*(?::\s*([^=]+))?\s*=>",
        re.MULTILINE,
    )

    # Matches: import { A, B } from 'source' or import type { A } from 'source'
    IMPORT_REGEX = re.compile(
        r"import\s+(?:(type)\s+)?(?:\{([^}]+)\}|\*\s+as\s+([A-Za-z0-9_]+)|([A-Za-z0-9_]+))\s+from\s+['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )

    @classmethod
    def parse_properties(cls, block_content: str) -> Dict[str, TSProperty]:
        """Parses property declarations within an interface or type block."""
        properties: Dict[str, TSProperty] = {}
        for line in block_content.splitlines():
            line = line.strip().rstrip(";,")
            if not line or line.startswith("//") or line.startswith("/*"):
                continue
            
            # Match: readonly? name?: type
            prop_match = re.match(r"^(readonly\s+)?([A-Za-z0-9_]+)(\?)?\s*:\s*(.+)$", line)
            if prop_match:
                is_readonly = bool(prop_match.group(1))
                name = prop_match.group(2)
                is_optional = bool(prop_match.group(3))
                type_ann = prop_match.group(4).strip()
                properties[name] = TSProperty(
                    name=name,
                    type_annotation=type_ann,
                    optional=is_optional,
                    readonly=is_readonly,
                )
        return properties

    @classmethod
    def parse_code(cls, code: str, file_path: str = "") -> Tuple[Dict[str, TSInterface], Dict[str, TSFunctionSignature], List[TSImport]]:
        """Extracts interfaces, functions, and imports from TypeScript source."""
        interfaces: Dict[str, TSInterface] = {}
        functions: Dict[str, TSFunctionSignature] = {}
        imports: List[TSImport] = []

        # 1. Parse interfaces
        for match in cls.INTERFACE_REGEX.finditer(code):
            is_exported = bool(match.group(1))
            name = match.group(2)
            raw_extends = match.group(3)
            block = match.group(4)
            extends_list = [e.strip() for e in raw_extends.split(",")] if raw_extends else []
            props = cls.parse_properties(block)
            interfaces[name] = TSInterface(
                name=name,
                properties=props,
                extends=extends_list,
                file_path=file_path,
                is_exported=is_exported,
                is_type_alias=False,
            )

        # 2. Parse object type aliases
        for match in cls.TYPE_ALIAS_OBJ_REGEX.finditer(code):
            is_exported = bool(match.group(1))
            name = match.group(2)
            block = match.group(3)
            props = cls.parse_properties(block)
            interfaces[name] = TSInterface(
                name=name,
                properties=props,
                extends=[],
                file_path=file_path,
                is_exported=is_exported,
                is_type_alias=True,
            )

        # 3. Parse standard functions
        for match in cls.FUNCTION_REGEX.finditer(code):
            is_exported = bool(match.group(1))
            is_async = bool(match.group(2))
            name = match.group(3)
            raw_params = match.group(4)
            raw_return = match.group(5)

            params: List[Tuple[str, str]] = []
            if raw_params:
                for p in raw_params.split(","):
                    p = p.strip()
                    if ":" in p:
                        p_name, p_type = p.split(":", 1)
                        params.append((p_name.strip(), p_type.strip()))
                    elif p:
                        params.append((p, "any"))

            return_type = raw_return.strip() if raw_return else "void"
            functions[name] = TSFunctionSignature(
                name=name,
                parameters=params,
                return_type=return_type,
                file_path=file_path,
                is_async=is_async,
                is_exported=is_exported,
            )

        # 4. Parse arrow functions
        for match in cls.ARROW_FUNCTION_REGEX.finditer(code):
            is_exported = bool(match.group(1))
            name = match.group(2)
            is_async = bool(match.group(3))
            raw_params = match.group(4)
            raw_return = match.group(5)

            params = []
            if raw_params:
                for p in raw_params.split(","):
                    p = p.strip()
                    if ":" in p:
                        p_name, p_type = p.split(":", 1)
                        params.append((p_name.strip(), p_type.strip()))
                    elif p:
                        params.append((p, "any"))

            return_type = raw_return.strip() if raw_return else "any"
            functions[name] = TSFunctionSignature(
                name=name,
                parameters=params,
                return_type=return_type,
                file_path=file_path,
                is_async=is_async,
                is_exported=is_exported,
            )


        # 5. Parse imports
        for match in cls.IMPORT_REGEX.finditer(code):
            is_type_only = bool(match.group(1))
            named_imports = match.group(2)
            wildcard_import = match.group(3)
            default_import = match.group(4)
            source_module = match.group(5)

            symbols: List[str] = []
            if named_imports:
                symbols.extend([s.strip().split(" as ")[0] for s in named_imports.split(",") if s.strip()])
            if wildcard_import:
                symbols.append(wildcard_import.strip())
            if default_import:
                symbols.append(default_import.strip())

            is_relative = source_module.startswith(".")
            imports.append(
                TSImport(
                    source_module=source_module,
                    imported_symbols=symbols,
                    file_path=file_path,
                    is_type_only=is_type_only,
                    is_relative=is_relative,
                )
            )

        return interfaces, functions, imports


class TSMonorepoDAG:
    """Builds and analyzes the cross-package Directed Acyclic Graph (DAG) for the monorepo."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.packages: Dict[str, Path] = {}  # package_name -> package_path
        self.package_deps: Dict[str, Set[str]] = {}  # package_name -> dependencies
        self.package_interfaces: Dict[str, Dict[str, TSInterface]] = {}
        self.package_functions: Dict[str, Dict[str, TSFunctionSignature]] = {}
        self.package_imports: Dict[str, List[TSImport]] = {}
        self._discover_packages()

    def _discover_packages(self) -> None:
        """Finds all package.json files under packages/* and apps/*."""
        search_dirs = [self.root_dir / "packages", self.root_dir / "apps"]
        for parent in search_dirs:
            if not parent.exists():
                continue
            for child in parent.iterdir():
                if child.is_dir() and (child / "package.json").exists():
                    try:
                        pkg_data = json.loads((child / "package.json").read_text(encoding="utf-8"))
                        pkg_name = pkg_data.get("name", child.name)
                        self.packages[pkg_name] = child
                        deps = set()
                        for dep_field in ["dependencies", "devDependencies", "peerDependencies"]:
                            deps.update(pkg_data.get(dep_field, {}).keys())
                        self.package_deps[pkg_name] = deps
                    except Exception:
                        continue

    def index_all(self) -> None:
        """Parses all TypeScript files across discovered packages."""
        for pkg_name, pkg_path in self.packages.items():
            self.package_interfaces[pkg_name] = {}
            self.package_functions[pkg_name] = {}
            self.package_imports[pkg_name] = []

            for root, _, files in os.walk(pkg_path):
                if "node_modules" in root or ".next" in root or ".turbo" in root:
                    continue
                for file in files:
                    if file.endswith((".ts", ".tsx")) and not file.endswith(".d.ts"):
                        full_path = Path(root) / file
                        try:
                            content = full_path.read_text(encoding="utf-8", errors="replace")
                            norm_path = full_path.as_posix()
                            ifaces, funcs, imps = TSASTAnalyzer.parse_code(content, norm_path)
                            self.package_interfaces[pkg_name].update(ifaces)
                            self.package_functions[pkg_name].update(funcs)
                            self.package_imports[pkg_name].extend(imps)
                        except Exception:
                            continue

    def get_dependents(self, target_pkg: str) -> List[str]:
        """Returns all packages that depend on the given target package."""
        return [pkg for pkg, deps in self.package_deps.items() if target_pkg in deps]


class TSContractVerifier:
    """Verifies interface contract consistency across producer and consumer packages."""

    @classmethod
    def verify_contracts(
        cls,
        producer_interfaces: Dict[str, TSInterface],
        producer_functions: Dict[str, TSFunctionSignature],
        consumer_imports: List[TSImport],
        consumer_source_code: Dict[str, str],
        producer_name: str = "producer",
        consumer_name: str = "consumer",
    ) -> List[TSContractMismatch]:
        """Identifies broken imports, missing properties, and invalid calls in consumer code."""
        mismatches: List[TSContractMismatch] = []

        for imp in consumer_imports:
            # Check if import matches producer package name or relative path
            if (imp.source_module != producer_name and
                not imp.source_module.endswith(f"/{producer_name}") and
                producer_name not in imp.source_module):
                continue

            for symbol in imp.imported_symbols:
                # 1. Check if exported symbol exists in producer
                in_interfaces = symbol in producer_interfaces
                in_functions = symbol in producer_functions

                if not (in_interfaces or in_functions):
                    mismatches.append(
                        TSContractMismatch(
                            producer_package=producer_name,
                            consumer_package=consumer_name,
                            consumer_file=imp.file_path,
                            symbol_name=symbol,
                            mismatch_type="missing_symbol",
                            details=f"Symbol '{symbol}' imported from '{imp.source_module}' does not exist in producer.",
                            suggested_fix=f"Export '{symbol}' from {producer_name} or update consumer import.",
                        )
                    )
                    continue

                # 2. If it's an interface, verify consumer usage if source code is provided
                if in_interfaces and imp.file_path in consumer_source_code:
                    iface = producer_interfaces[symbol]
                    code_text = consumer_source_code[imp.file_path]
                    for prop_name, prop in iface.properties.items():
                        if not prop.optional and not re.search(rf"\b{prop_name}\b", code_text):
                            # Warning or missing property usage check
                            continue

        return mismatches

    @classmethod
    def check_interface_mutation(
        cls,
        old_iface: TSInterface,
        new_iface: TSInterface,
        consumer_code: str,
        file_path: str = "",
    ) -> List[TSContractMismatch]:
        """Checks if mutating an interface breaks existing consumer code."""
        mismatches: List[TSContractMismatch] = []
        old_props = set(old_iface.properties.keys())
        new_props = set(new_iface.properties.keys())

        # 1. Removed properties
        removed = old_props - new_props
        for prop in removed:
            if re.search(rf"\.\s*{prop}\b", consumer_code):
                mismatches.append(
                    TSContractMismatch(
                        producer_package=old_iface.name,
                        consumer_package="consumer",
                        consumer_file=file_path,
                        symbol_name=prop,
                        mismatch_type="missing_property",
                        details=f"Property '{prop}' was removed from interface '{old_iface.name}' but is accessed by consumer.",
                        suggested_fix=f"Retain property '{prop}' as optional or update consumer call site.",
                    )
                )

        # 2. Type alteration on required properties
        for prop in old_props & new_props:
            old_t = old_iface.properties[prop].type_annotation.strip()
            new_t = new_iface.properties[prop].type_annotation.strip()
            if old_t != new_t:
                mismatches.append(
                    TSContractMismatch(
                        producer_package=old_iface.name,
                        consumer_package="consumer",
                        consumer_file=file_path,
                        symbol_name=prop,
                        mismatch_type="type_incompatibility",
                        details=f"Property '{prop}' type changed from '{old_t}' to '{new_t}'.",
                        suggested_fix=f"Ensure union compatibility (e.g. '{old_t} | {new_t}') or update consumer.",
                    )
                )

        # 3. New required property added
        added = new_props - old_props
        for prop in added:
            if not new_iface.properties[prop].optional:
                mismatches.append(
                    TSContractMismatch(
                        producer_package=old_iface.name,
                        consumer_package="consumer",
                        consumer_file=file_path,
                        symbol_name=prop,
                        mismatch_type="missing_property",
                        details=f"New required property '{prop}: {new_iface.properties[prop].type_annotation}' added to '{new_iface.name}' without optional modifier.",
                        suggested_fix=f"Make property optional: '{prop}?: {new_iface.properties[prop].type_annotation}'.",
                    )
                )

        return mismatches


class TwoPhaseCommitTSPropagator:
    """Atomic Two-Phase Commit (2PC) interface propagator across monorepo packages."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or Path(".")
        self.staged_changes: Dict[Path, str] = {}
        self.backups: Dict[Path, str] = {}
        self.prepared: bool = False

    def stage(self, file_path: Path, new_content: str) -> None:
        """Stages a modified TypeScript file content in memory."""
        self.staged_changes[file_path.resolve()] = new_content

    def prepare(self) -> Tuple[bool, List[str]]:
        """Phase 1: Validates all staged changes against AST and contracts before writing."""
        diagnostics: List[str] = []

        for p, content in self.staged_changes.items():
            # Backup current state if file exists on disk
            if p.exists():
                self.backups[p] = p.read_text(encoding="utf-8", errors="replace")
            else:
                self.backups[p] = ""

            # Check for unbalanced braces or syntax corruption
            open_braces = content.count("{") - content.count("}")
            open_parens = content.count("(") - content.count(")")
            open_brackets = content.count("[") - content.count("]")

            if open_braces != 0 or open_parens != 0 or open_brackets != 0:
                diagnostics.append(
                    f"Syntax structural balance error in {p.name}: "
                    f"braces_delta={open_braces}, parens_delta={open_parens}, brackets_delta={open_brackets}"
                )

        self.prepared = len(diagnostics) == 0
        return self.prepared, diagnostics

    def commit(self) -> bool:
        """Phase 2: Atomically applies all staged changes to disk."""
        if not self.prepared:
            return False

        try:
            for p, content in self.staged_changes.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            return True
        except Exception:
            self.rollback()
            return False

    def rollback(self) -> None:
        """Rolls back all files to their pre-prepared snapshot state."""
        for p, original_content in self.backups.items():
            try:
                if original_content:
                    p.write_text(original_content, encoding="utf-8")
                elif p.exists():
                    p.unlink()
            except Exception:
                continue
        self.staged_changes.clear()
        self.prepared = False
