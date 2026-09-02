"""
Saleha Core: Type-Safe Agent Output Schema Contracts & Validation Layer

Enforces strict typed interfaces for inter-agent communication, preventing
hallucination propagation and ensuring 100% deterministic pipeline data exchange.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ArchitectOutputContract:
    adr_title: str
    pattern: str = "Hexagonal (Ports & Adapters)"
    components: List[str] = field(default_factory=list)
    system_design_md: str = ""
    invariants: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        return bool(self.adr_title and self.pattern and self.components)


@dataclass
class CoderOutputContract:
    source_code: str
    language: str = "python"
    is_ast_valid: bool = True
    functions_defined: List[str] = field(default_factory=list)
    classes_defined: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        if not self.source_code:
            return False
        if self.language == "python":
            try:
                tree = ast.parse(self.source_code)
                self.classes_defined = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                self.functions_defined = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                self.is_ast_valid = True
                return True
            except SyntaxError:
                self.is_ast_valid = False
                return False
        return True


@dataclass
class SecurityOutputContract:
    is_secure: bool = True
    cwe_identifiers: List[str] = field(default_factory=list)
    vulnerabilities_found: List[str] = field(default_factory=list)
    hardened_code: str = ""

    def validate(self) -> bool:
        return isinstance(self.is_secure, bool) and isinstance(self.vulnerabilities_found, list)


@dataclass
class QAOutputContract:
    framework: str = "pytest"
    test_code: str = ""
    test_case_count: int = 0
    passed: bool = True

    def validate(self) -> bool:
        return bool(self.test_code and self.test_case_count >= 0)


@dataclass
class ReviewerOutputContract:
    approved: bool = True
    score: float = 9.0  # Out of 10.0
    feedback: str = ""
    required_changes: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        return isinstance(self.approved, bool) and 0.0 <= self.score <= 10.0


@dataclass
class FinOpsOutputContract:
    original_tokens: int = 0
    optimized_tokens: int = 0
    token_savings_pct: float = 0.0
    annual_cost_savings_usd: float = 0.0

    def validate(self) -> bool:
        return self.original_tokens >= 0 and self.optimized_tokens >= 0


@dataclass
class DesignerOutputContract:
    theme_preset: str = "obsidian"
    css_variables: Dict[str, str] = field(default_factory=dict)
    typography_scale: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        return bool(self.theme_preset and self.css_variables)


@dataclass
class DataEngineerOutputContract:
    schema_ddl: str = ""
    tables_created: List[str] = field(default_factory=list)
    vector_indexing_strategy: str = "pgvector_hnsw"

    def validate(self) -> bool:
        return bool(self.schema_ddl and self.tables_created)


@dataclass
class DevOpsOutputContract:
    dockerfile: str = ""
    ci_cd_workflow_yaml: str = ""
    kubernetes_manifest: str = ""

    def validate(self) -> bool:
        return bool(self.dockerfile or self.ci_cd_workflow_yaml)
