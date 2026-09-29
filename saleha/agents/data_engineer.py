"""
Saleha Agents: Data Engineer Agent

Architects SQL/NoSQL schemas, vector databases, ETL data pipelines,
Polars/Pandas transformations, and streaming ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from saleha.agents.base_agent import BaseAgent


@dataclass
class DataPipelineSpec:
    pipeline_name: str
    sql_schema: str
    etl_script_py: str
    target_tables: List[str]
    model_used: str = ""
    # Always True: no model is called; fixed Postgres+pgvector scaffold.
    is_template: bool = True


class DataEngineerAgent(BaseAgent):
    """Principal Data Engineer & Vector Pipeline Architect Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="DataEngineer", model=model)

    def build_data_pipeline(
        self,
        dataset_name: str,
        source_format: str = "json"
    ) -> DataPipelineSpec:
        """Returns a fixed Postgres+pgvector scaffold. No model is called:
        the schema assumes a pgvector-enabled database and the ETL only
        drops nulls -- adapt both to the real dataset."""
        clean_name = dataset_name.lower().replace(" ", "_")

        schema = f"""-- ==============================================================================
-- Scaffold (no model called) for: {dataset_name}
-- Assumes Postgres with the pgvector extension (VECTOR, ivfflat).
-- ==============================================================================

CREATE TABLE IF NOT EXISTS {clean_name}_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payload JSONB NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_{clean_name}_payload ON {clean_name}_records USING GIN (payload);
CREATE INDEX IF NOT EXISTS idx_{clean_name}_vec ON {clean_name}_records USING ivfflat (embedding vector_cosine_ops);
"""

        etl = f"""# ETL Transformation Pipeline for {dataset_name}
import polars as pl

def transform_batch(raw_data: list[dict]) -> pl.DataFrame:
    df = pl.DataFrame(raw_data)
    # Clean nulls & standardize schema
    cleaned_df = df.drop_nulls()
    return cleaned_df
"""

        return DataPipelineSpec(
            pipeline_name=clean_name,
            sql_schema=schema,
            etl_script_py=etl,
            target_tables=[f"{clean_name}_records"],
            model_used=self.model_preference
        )
