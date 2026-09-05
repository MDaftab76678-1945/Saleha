import pytest

from saleha.core.agent_contracts import (
    ArchitectOutputContract,
    CoderOutputContract,
    SecurityOutputContract,
    QAOutputContract,
    ReviewerOutputContract,
    FinOpsOutputContract,
    DesignerOutputContract,
    DataEngineerOutputContract,
    DevOpsOutputContract,
)

def test_architect_output_contract():
    contract = ArchitectOutputContract(
        adr_title="Hexagonal Architecture",
        pattern="Hexagonal (Ports & Adapters)",
        components=["domain", "adapter"],
        system_design_md="...",
        invariants=["...", "..."]
    )
    assert contract.validate()

def test_coder_output_contract():
    contract = CoderOutputContract(
        source_code="#!/usr/bin/env python\nprint('Hello, World!')",
        language="python",
        is_ast_valid=True,
        functions_defined=["print"],
        classes_defined=[]
    )
    assert contract.validate()

def test_security_output_contract():
    contract = SecurityOutputContract(
        is_secure=True,
        cwe_identifiers=["CWE-123", "CWE-456"],
        vulnerabilities_found=["Vulnerability 1", "Vulnerability 2"],
        hardened_code="#!/usr/bin/env python\nprint('Hello, World!')"
    )
    assert contract.validate()

def test_qa_output_contract():
    contract = QAOutputContract(
        framework="pytest",
        test_code="...",
        test_case_count=3,
        passed=True
    )
    assert contract.validate()

def test_reviewer_output_contract():
    contract = ReviewerOutputContract(
        approved=True,
        score=9.0,
        feedback="Good job!",
        required_changes=[]
    )
    assert contract.validate()

def test_fin_ops_output_contract():
    contract = FinOpsOutputContract(
        original_tokens=1000,
        optimized_tokens=800,
        token_savings_pct=20.0,
        annual_cost_savings_usd=500
    )
    assert contract.validate()

def test_designer_output_contract():
    contract = DesignerOutputContract(
        theme_preset="obsidian",
        css_variables={"primary-color": "#3498db", "secondary-color": "#2ecc71"},
        typography_scale=["h1", "h2"]
    )
    assert contract.validate()

def test_data_engineer_output_contract():
    contract = DataEngineerOutputContract(
        schema_ddl="CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT);",
        tables_created=["users"],
        vector_indexing_strategy="pgvector_hnsw"
    )
    assert contract.validate()

def test_dev_ops_output_contract():
    contract = DevOpsOutputContract(
        dockerfile="#!/bin/sh\npython app.py",
        ci_cd_workflow_yaml="...",
        kubernetes_manifest="..."
    )
    assert contract.validate()