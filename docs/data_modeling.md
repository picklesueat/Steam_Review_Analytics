# Steam Review Medallion Modeling

This proof of concept uses a DuckDB-backed medallion architecture to transform
Steam Store review payloads from raw JSONL drops into analytics-ready marts. The
flow is orchestrated by dbt and produces three layers plus a semantic overlay:

## Bronze – Raw landing

* **Storage**: JSONL files in `data/bronze/` remain immutable, while the
  pipeline appends each payload to `bronze.steam_reviews_raw` inside DuckDB with
  lineage columns (`load_id`, `ingested_at`, `cursor`, `hash_payload`).
* **Model**: `bronze.steam_reviews_raw` is exposed as a dbt view. A companion
  compacted view keeps the latest version of each
  `(appid, recommendationid, hash_payload)` tuple for downstream merges.
* **Watermarks**: `bronze.load_watermarks` tracks the last cursor and maximum
  `updated_at` observed per app ID so subsequent ingest runs can resume without a
  full scan.
* **Purpose**: Immutable audit log that supports replay. No merges are issued —
  the pipeline only appends new JSON blobs.

## Silver – Normalized reviews

* **Model**: `silver.steam_reviews_enriched` flattens JSON payloads, converts
  Unix epochs to timestamps, and materializes as a table keyed by
  `recommendationid`.
* **Lineage**: Bronze metadata (`hash_payload`, `load_id`, `ingested_at`) is
  preserved for debugging and delete detection (future work toggles `is_deleted`
  when the API surfaces tombstones).

## Gold – Adaptive review metrics

* **Model**: `gold.fct_steam_review_metrics_adaptive` aggregates Silver into per-game
  metrics with `record_changed_at` and a derived daily `snapshot_date` for lineage.
* **Metrics**:
  * **avg_rating** – Lifetime positivity (share of thumbs-up) in the range [0,1].
  * **edp_current** – Exponentially decayed positivity that emphasizes the latest sentiment.
  * **decay_ewrr** – Exponentially weighted rate ratio capturing popularity momentum (>1 rising).
  * **cult_score** – Lifetime positivity divided by `log1p(total_reviews)` to surface niche hits.

## Semantic layer

`semantic_models/steam_review_metrics_adaptive.yml` defines a MetricFlow semantic model that
exposes the adaptive review metrics directly from the Gold table with a daily time
dimension. BI tools can query `avg_rating`, `edp_current`, `decay_ewrr`, and `cult_score`
without hand-writing SQL.

## DuckDB configuration

The dbt project expects a DuckDB profile named `steam_duckdb` that points to a
local warehouse file. An example profile:

```yaml
steam_duckdb:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: data/warehouse/steam_reviews.duckdb
      threads: 4
```

Save this snippet to `~/.dbt/profiles.yml` (or provide `--profiles-dir` when
running dbt). dbt will create the DuckDB file on demand and materialize the
medallion models inside.

## Running the medallion pipeline

Once reviews are ingested into `data/bronze/` and appended to DuckDB, execute:

```bash
cd /path/to/repo
python -m pipelines.steam_reviews_poc 620 --max-pages 2 --run-dbt --document-modeling
```

This command fetches reviews, materializes the bronze/silver/gold layers in
DuckDB, and prints a summary of the medallion architecture so operators know how
metrics are produced.
