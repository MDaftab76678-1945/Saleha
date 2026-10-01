"""SheetsAnalystAgent: analysis of a real table -- statistics computed, questions answered by running SQL.

Give it a CSV/TSV/JSON file, inline CSV text, or a list of row dicts. The
statistics are computed from the data: per column the type, nulls, mean or
mode, min and max; the outliers are values outside 1.5 IQR of their column.
A question in plain words is answered by SQL the model writes -- and that
SQL is run on the data (loaded into an in-memory SQLite table named `data`),
so the answer comes from the database, not from the model. A query that
fails is shown to the model once with the error.

With no data given there is nothing to analyse, and the result says so.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
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
    """A value outside 1.5 IQR of its column."""
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
    question: str = ""
    answer_rows: List[Dict[str, Any]] = field(default_factory=list)   # what the SQL returned
    checks: List[Dict[str, str]] = field(default_factory=list)
    loaded: bool = False             # False: no table was given, nothing was analysed
    error: str = ""


def load_table(source: Any) -> Tuple[List[Dict[str, Any]], str]:
    """(rows, error). A path (.csv/.tsv/.json/.jsonl), CSV text, or a list of dicts."""
    if isinstance(source, list):
        return ([dict(r) for r in source if isinstance(r, dict)], "") if source else ([], "the list is empty")
    text = str(source or "")
    if text and len(text) < 1000 and "\n" not in text and os.path.isfile(text):
        try:
            with open(text, "r", encoding="utf-8-sig", errors="replace") as fh:
                body = fh.read()
        except OSError as exc:
            return [], f"could not read {text}: {exc}"
        if text.lower().endswith(".jsonl"):
            rows = [json.loads(ln) for ln in body.splitlines() if ln.strip()]
            return [r for r in rows if isinstance(r, dict)], ""
        if text.lower().endswith(".json"):
            data = json.loads(body)
            data = data.get("rows") or data.get("data") if isinstance(data, dict) else data
            return ([r for r in data if isinstance(r, dict)], "") if isinstance(data, list) else ([], "no rows in the JSON")
        text = body
    if "\n" not in text.strip():
        return [], "no table given: pass a CSV/TSV/JSON path, CSV text, or a list of rows"
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    return (rows, "") if rows else ([], "the table has a header but no rows")


def _number(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def column_metrics(rows: List[Dict[str, Any]]) -> Tuple[List[ColumnMetric], List[SheetAnomaly], Dict[str, str]]:
    names = list(dict.fromkeys(k for r in rows for k in r))
    metrics, anomalies, types = [], [], {}
    for name in names:
        values = [r.get(name) for r in rows]
        present = [v for v in values if v not in (None, "") and str(v).strip() != ""]
        nums = [_number(v) for v in present]
        numeric = bool(present) and all(n is not None for n in nums)
        types[name] = "REAL" if numeric else "TEXT"
        m = ColumnMetric(name, "number" if numeric else "text", len(values), len(values) - len(present))
        if numeric:
            xs = [n for n in nums if n is not None]
            m.mean_or_mode = f"{statistics.fmean(xs):.4g}"
            m.min_val, m.max_val = f"{min(xs):g}", f"{max(xs):g}"
            if len(xs) >= 4:
                q1, _q2, q3 = statistics.quantiles(xs, n=4)
                lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
                for i, v in enumerate(values):
                    n = _number(v)
                    if n is not None and (n < lo or n > hi):
                        far = n < q1 - 3 * (q3 - q1) or n > q3 + 3 * (q3 - q1)
                        anomalies.append(SheetAnomaly(name, i, v, "high" if far else "medium",
                                                      f"outside [{lo:g}, {hi:g}] (1.5 IQR)"))
        elif present:
            mode = statistics.mode(str(v) for v in present)
            m.mean_or_mode = mode
            texts = sorted(str(v) for v in present)
            m.min_val, m.max_val = texts[0], texts[-1]
        metrics.append(m)
    return metrics, anomalies, types


def to_sqlite(rows: List[Dict[str, Any]], types: Dict[str, str]) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    cols = list(types)
    con.execute("CREATE TABLE data (" + ", ".join(f'"{c}" {types[c]}' for c in cols) + ")")
    con.executemany(f"INSERT INTO data VALUES ({', '.join('?' for _ in cols)})",
                    [tuple((_number(r.get(c)) if types[c] == "REAL" else r.get(c)) for c in cols) for r in rows])
    return con


def run_sql(con: sqlite3.Connection, sql: str, limit: int = 50) -> Tuple[ac.Check, List[Dict[str, Any]]]:
    stmt = sql.strip().rstrip(";")
    if not re.match(r"(?is)^\s*(select|with)\b", stmt) or ";" in stmt:
        return ac.Check("SQL runs on the data", ac.FAIL, "only a single SELECT is run"), []
    try:
        cur = con.execute(stmt)
        names = [d[0] for d in cur.description or []]
        rows = [dict(zip(names, r)) for r in cur.fetchmany(limit)]
    except sqlite3.Error as exc:
        return ac.Check("SQL runs on the data", ac.FAIL, f"{type(exc).__name__}: {exc}"), []
    return ac.Check("SQL runs on the data", ac.PASS, f"{len(rows)} row(s)"), rows


def preview(rows: List[Dict[str, Any]], n: int = 5) -> str:
    if not rows:
        return "(no data)"
    cols = list(rows[0])
    widths = {c: max(len(c), *(len(str(r.get(c, ""))[:20]) for r in rows[:n])) for c in cols}
    line = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    body = [" | ".join(str(r.get(c, ""))[:20].ljust(widths[c]) for c in cols) for r in rows[:n]]
    return "\n".join([line, sep] + body)


class SheetsAnalystAgent(BaseAgent):
    """Statistics from the data, answers from SQL run on it."""

    def __init__(self, role: str = "Tabular Data & Sheets Analyst", model: str = "auto"):
        super().__init__(role=role, model=model)
        self.name = "SheetsAnalystAgent"

    def execute(self, prompt: str) -> AgentResponse:
        """Standard Agent execution: `prompt` is a path or CSV text."""
        start = time.perf_counter()
        r = self.analyze_tabular_query(prompt)
        if not r.loaded:
            content = f"Tabular Analysis: {r.dataset_name}\n(no table was loaded: {r.error})\n"
        else:
            content = (f"Tabular Analysis: {r.dataset_name}\nRows: {r.total_rows} | Columns: {r.total_columns} | "
                       f"Outliers: {len(r.anomalies)}\n\n{r.ascii_table_preview}\n")
        return AgentResponse(success=r.loaded, content=content, model_used="computed (no model)",
                             response_time=(time.perf_counter() - start) * 1000, tokens_used=0)

    def analyze_tabular_query(self, source: Any, question: str = "", name: str = "") -> SheetAnalysisResult:
        """Statistics and outliers of the table; `question` answered by model-written SQL run on it."""
        start = time.perf_counter()
        rows, err = load_table(source)
        label = name or (os.path.basename(source) if isinstance(source, str) and os.path.isfile(source[:1000])
                         else "table")
        if not rows:
            return SheetAnalysisResult(label, 0, 0, [], [], "", "(no data)", "", question=question, loaded=False,
                                       error=err, execution_time_ms=round((time.perf_counter() - start) * 1000, 2))
        metrics, anomalies, types = column_metrics(rows)
        con = to_sqlite(rows, types)
        sql, answer, checks = "", [], []
        if question:
            schema = ", ".join(f"{c} {t}" for c, t in types.items())
            prompt = (f"A SQLite table `data` has columns: {schema}.\nFirst rows:\n{preview(rows, 3)}\n\n"
                      f"Write ONE SQLite SELECT query that answers: {question}\n"
                      "Answer with one fenced sql block and nothing else. Quote column names with spaces.")

            def build(content: str) -> Tuple[Tuple[str, List[Dict[str, Any]]], List[ac.Check]]:
                q = ac.pick(ac.fenced_blocks(content), ("sql", "sqlite")) or content.strip().strip("`")
                check, out = run_sql(con, q)
                return (q, out), [check]

            got, checks, _resp, _rounds = ac.produce(self, prompt, build)
            if got is not None:
                sql, answer = got
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(types))
        writer.writeheader()
        writer.writerows([{k: r.get(k) for k in types} for r in rows[:5]])
        con.close()
        return SheetAnalysisResult(
            dataset_name=label, total_rows=len(rows), total_columns=len(types), columns=metrics,
            anomalies=anomalies, synthesized_sql_query=sql, ascii_table_preview=preview(rows),
            csv_export_sample=buf.getvalue(), question=question, answer_rows=answer,
            checks=ac.as_dicts(checks), loaded=True,
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2))


sheets_analyst = SheetsAnalystAgent()
