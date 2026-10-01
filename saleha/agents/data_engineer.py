"""
Saleha Agents: Data Engineer Agent

Writes a SQL schema and a Python ETL step for a dataset, and checks both:
the SQL's statements and tables (by structure -- no database runs it), the
ETL's syntax, and -- when sample records are given -- the ETL itself, run
on them in a throwaway process, must return a list of records.

With no model answering, a fixed Postgres template is returned and marked
`is_template`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent


@dataclass
class DataPipelineSpec:
    pipeline_name: str
    sql_schema: str
    etl_script_py: str
    target_tables: List[str]
    model_used: str = ""
    # True when no model answered and the files are the fixed template.
    is_template: bool = True
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None
    sample_output: str = ""          # what the ETL returned for the sample records, when it ran


def _template(clean_name: str, dataset_name: str) -> Tuple[str, str]:
    schema = (f"-- Template (no model answered) for: {dataset_name}\n"
              f"CREATE TABLE IF NOT EXISTS {clean_name}_records (\n"
              "    id BIGSERIAL PRIMARY KEY,\n    payload JSONB NOT NULL,\n"
              "    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP\n);\n"
              f"CREATE INDEX IF NOT EXISTS idx_{clean_name}_payload ON {clean_name}_records USING GIN (payload);\n")
    etl = ("def transform_batch(raw_data: list) -> list:\n"
           '    """Drop records that are empty or not mappings. Adapt to the real dataset."""\n'
           "    return [dict(r) for r in raw_data if isinstance(r, dict) and r]\n")
    return schema, etl


def run_etl(etl: str, sample: List[Dict[str, Any]]) -> Tuple[ac.Check, str]:
    """Run transform_batch(sample) in a throwaway process; it must return a list of dicts."""
    harness = ("import json\nfrom etl import transform_batch\n"
               f"rows = transform_batch(json.loads({json.dumps(json.dumps(sample))}))\n"
               "rows = list(rows)\n"
               "assert all(isinstance(r, dict) for r in rows), 'transform_batch must return dicts'\n"
               "print(json.dumps(rows, default=str)[:2000])\n")
    check, out = ac.run_python(harness, files={"etl.py": etl}, name="ETL runs on the sample")
    return check, out if check.status == ac.PASS else ""


class DataEngineerAgent(BaseAgent):
    """Principal Data Engineer & Vector Pipeline Architect Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="DataEngineer", model=model)

    def build_data_pipeline(self, dataset_name: str, source_format: str = "json",
                            sample_records: Optional[List[Dict[str, Any]]] = None,
                            dialect: str = "postgres") -> DataPipelineSpec:
        """A schema and an ETL step for the dataset, checked; run on `sample_records` when given."""
        clean_name = re.sub(r"\W+", "_", dataset_name.lower()).strip("_") or "dataset"
        sample = list(sample_records or [])[:20]
        prompt = (
            f"Design storage and an ETL step for the dataset `{dataset_name}` (source format: {source_format}, "
            f"database: {dialect}).\n"
            + (f"Sample records:\n{json.dumps(sample[:5], indent=1, default=str)[:2500]}\n" if sample else "")
            + "Answer with exactly two fenced blocks:\n"
              "1. a sql block: CREATE TABLE statements (with types and keys) and useful indexes, each ending in ';'\n"
              "2. a python block: a function `transform_batch(raw_data: list) -> list` that cleans the raw "
              "records into rows for those tables, as a list of dicts, using only the Python standard library\n"
              "Put only the language after each opening fence. No other text.")

        ran: Dict[str, str] = {}

        def build(content: str) -> Tuple[Tuple[str, str], List[ac.Check]]:
            blocks = ac.fenced_blocks(content)
            sql = ac.pick(blocks, ("sql", "postgresql", "postgres"), contains=r"(?i)create\s+table")
            etl = ac.pick(blocks, ("python", "py"), contains=r"def\s+transform_batch")
            checks = [ac.check_sql(sql), ac.check_python(etl, "ETL syntax")]
            if "transform_batch" not in etl:
                checks.append(ac.Check("ETL defines transform_batch", ac.FAIL, "no transform_batch function"))
            if sample and checks[1].status == ac.PASS:
                check, ran[etl] = run_etl(etl, sample)
                checks.append(check)
            elif not sample:
                checks.append(ac.Check("ETL runs on the sample", ac.NOT_RUN, "no sample records were given"))
            return (sql, etl), checks

        files, checks, resp, _rounds = ac.produce(self, prompt, build)
        is_template = files is None or not files[0]
        if is_template:
            note = ac.fallback_note(checks, files is not None)
            schema, etl_t = _template(clean_name, dataset_name)
            files, template_checks = build(f"```sql\n{schema}```\n```python\n{etl_t}```")
            checks = note + template_checks
        sql, etl = files
        return DataPipelineSpec(
            pipeline_name=clean_name, sql_schema=sql, etl_script_py=etl,
            target_tables=ac.sql_tables(sql),
            model_used="template (no usable model answer)" if is_template else resp.model_used,
            is_template=is_template, checks=ac.as_dicts(checks),
            verified=ac.artifact_verdict(checks),
            sample_output=ran.get(etl, ""))
