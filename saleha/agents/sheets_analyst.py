"""SheetsAnalystAgent: Autonomous Columnar Tabular Analytics, Anomaly Detection & SQL Synthesis."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, List, Optional

from saleha.agents.base_agent import AgentResponse, BaseAgent


@dataclass
class ColumnMetric:
    """Statistical summary for a single tabular column."""
    name: str
    dtype: str
    row_count: int
    null_count: int
    mean_or_mode: Optional[str] = None
    min_val: Optional[str] = None
    max_val: Optional[str] = None


@dataclass
class SheetAnomaly:
    """Identified data anomaly or outlier."""
    column: str
    row_index: int
    value: Any
    severity: str
    reason: str


@dataclass
class SheetAnalysisResult:
    """Complete tabular analysis report."""
    dataset_name: str
    total_rows: int
    total_columns: int
    columns: List[ColumnMetric]
    anomalies: List[SheetAnomaly]
    synthesized_sql_query: str
    ascii_table_preview: str
    csv_export_sample: str
    execution_time_ms: float = 0.0


class SheetsAnalystAgent(BaseAgent):
    """Specialist agent for tabular data processing, column statistics,
    anomaly detection, and SQL aggregation synthesis.
    """

    def __init__(self, role: str = "Tabular Data & Sheets Analyst", model: str = "auto"):
        super().__init__(role=role, model=model)
        self.name = "SheetsAnalystAgent"

    def execute(self, prompt: str) -> AgentResponse:
        """Standard Agent execution."""
        start = time.perf_counter()
        result = self.analyze_tabular_query(prompt)
        duration = (time.perf_counter() - start) * 1000

        content = f"""Tabular Analysis: {result.dataset_name}
Rows: {result.total_rows} | Columns: {result.total_columns} | Anomalies: {len(result.anomalies)}
(no tabular source was provided, so there is nothing to report)
"""
        return AgentResponse(
            success=True,
            content=content,
            model_used="template (no data source)",
            response_time=duration,
            tokens_used=0,
        )

    def analyze_tabular_query(self, query_or_name: str) -> SheetAnalysisResult:
        """No tabular source is loaded and no statistics are computed: the
        previous version returned a fixed 10,000-row dataset with fixed
        anomalies for every input. Returns an explicitly empty result."""
        start = time.perf_counter()
        name = query_or_name.strip() or "Production Analytics Dataset"

        duration = (time.perf_counter() - start) * 1000
        return SheetAnalysisResult(
            dataset_name=name,
            total_rows=0,
            total_columns=0,
            columns=[],
            anomalies=[],
            synthesized_sql_query="-- no tabular source was provided; no query synthesized",
            ascii_table_preview="(no data)",
            csv_export_sample="",
            execution_time_ms=round(duration, 2),
        )


sheets_analyst = SheetsAnalystAgent()
