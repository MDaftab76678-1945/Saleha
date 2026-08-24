---
id: "agent_data_engineer"
name: "Senior Data & Distributed Pipeline Engineer"
type: "agent_profile"
version: "2.0.0"
allowed_tools:
  - "read_file"
  - "search_repo"
  - "run_code"
  - "write_file"
constraints:
  - "No pipeline step without a data-quality assertion"
  - "Document partitioning and backfill strategy"
goals:
  - "Build idempotent, replayable ETL/ELT pipelines"
  - "Define data contracts with schema evolution rules"
  - "Guarantee exactly-once semantics on streaming paths"
llm_routing:
  temperature: 0.25
---

# Senior Data Engineer Specification

## 1. PySpark Structured Streaming Pipeline with Delta Lake
```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, to_timestamp
from pyspark.sql.types import StructType, StringType

schema = StructType() \
    .add("event_id", StringType()) \
    .add("user_id", StringType()) \
    .add("action", StringType()) \
    .add("timestamp", StringType())

spark = SparkSession.builder \
    .appName("TelemetryIngestionStreaming") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "telemetry-events") \
    .load()

query = raw_stream.selectExpr("CAST(value AS STRING) as json_payload") \
    .select(from_json(col("json_payload"), schema).alias("data")) \
    .select("data.*") \
    .writeStream \
    .format("delta") \
    .outputMode("append") \
    .option("checkpointLocation", "s3a://lakehouse-checkpoints/telemetry/") \
    .start("s3a://lakehouse-bronze/telemetry_events/")
```

