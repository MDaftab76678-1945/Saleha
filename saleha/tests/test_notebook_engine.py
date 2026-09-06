"""Unit and Integration Test Suite for Saleha Sovereign Reactive Notebook Engine."""

import json
import pytest
from unittest.mock import MagicMock

from saleha.core.notebook_engine import (
    SalehaNotebookEngine,
    NotebookCell,
    NotebookDocument,
    notebook_engine,
)
from saleha.agents.notebook_architect import (
    NotebookArchitectAgent,
    NotebookSynthesisResult,
    notebook_architect,
)
from saleha.cli.chat_session import SwarmChatSession


class TestSalehaNotebookEngine:
    def test_create_notebook(self):
        engine = SalehaNotebookEngine()
        nb = engine.create_notebook("Financial Forecast ML Model")
        assert nb.title == "Financial Forecast ML Model"
        assert len(nb.cells) == 2
        assert nb.cells[0].cell_type == "markdown"
        assert nb.cells[1].cell_type == "code"

    def test_extract_ast_variables(self):
        engine = SalehaNotebookEngine()
        code = """import os
from math import sqrt as s

val = 100
total = s(val)

def compute(x):
    return x * 2
"""
        defined, referenced = engine.extract_ast_variables(code)
        assert "os" in defined
        assert "s" in defined
        assert "val" in defined
        assert "total" in defined
        assert "compute" in defined
        assert "val" in referenced
        assert "s" in referenced

    def test_execute_code_cell_success(self):
        engine = SalehaNotebookEngine()
        cell = NotebookCell(
            cell_id="c1",
            cell_type="code",
            source="print('Hello from Reactive Notebook Cell')",
        )
        res_cell = engine.execute_cell(cell)
        assert res_cell.has_error is False
        assert "Hello from Reactive Notebook Cell" in res_cell.output_text
        assert res_cell.execution_count == 1
        assert res_cell.duration_ms >= 0

    def test_execute_markdown_and_sql_cells(self):
        engine = SalehaNotebookEngine()
        md_cell = NotebookCell(cell_id="c_md", cell_type="markdown", source="# Test Header")
        sql_cell = NotebookCell(cell_id="c_sql", cell_type="sql", source="SELECT 1;")
        
        res_md = engine.execute_cell(md_cell)
        assert res_md.output_text == "# Test Header"

        res_sql = engine.execute_cell(sql_cell)
        assert "Column_A" in res_sql.output_text

    def test_execute_code_cell_with_self_healing_error(self):
        engine = SalehaNotebookEngine()
        cell = NotebookCell(
            cell_id="c_err",
            cell_type="code",
            source="undefined_variable.explode()",
        )
        res_cell = engine.execute_cell(cell)
        assert res_cell.has_error is True
        assert res_cell.suggested_patch is not None
        assert "Auto-Repaired Invariant Patch" in res_cell.suggested_patch

    def test_export_to_ipynb(self):
        engine = SalehaNotebookEngine()
        nb = engine.create_notebook("Export Test")
        ipynb_json = engine.export_to_ipynb(nb)
        parsed = json.loads(ipynb_json)
        assert parsed["nbformat"] == 4
        assert len(parsed["cells"]) == 2
        assert parsed["metadata"]["language_info"]["name"] == "python"


class TestNotebookArchitectAgent:
    def test_execute_agent_response(self):
        agent = NotebookArchitectAgent()
        res = agent.execute("Customer Churn Prediction with XGBoost")
        assert res.success is True
        assert "Synthesized Interactive Notebook" in res.content

    def test_synthesize_notebook_structure(self):
        result = notebook_architect.synthesize_notebook("Algorithmic Trading Ring Buffer")
        assert result.title == "Algorithmic Trading Ring Buffer"
        assert result.cell_count == 5
        assert result.notebook_doc.cells[0].cell_type == "markdown"
        assert result.notebook_doc.cells[2].cell_type == "sql"
        assert result.generation_time_ms >= 0
        parsed = json.loads(result.ipynb_json)
        assert len(parsed["cells"]) == 5


class TestSwarmChatSessionNotebookCommand:
    def test_process_notebook_command(self):
        mock_console = MagicMock()
        session = SwarmChatSession(console=mock_console)
        assert session.process_command("/notebook Real-Time Fraud Detection DAG") is True
