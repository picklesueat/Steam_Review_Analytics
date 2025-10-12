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
  Unix epochs to timestamps, and MERGEs into an incremental table keyed by
  `recommendationid`.
* **Incremental window**: Only Bronze rows whose `updated_at` (or `ingested_at`
  fallback) exceeds the existing table watermark minus two days are processed.
  This sliding window captures late-arriving updates without rescanning the
  entire ledger.
* **Lineage**: Bronze metadata (`hash_payload`, `load_id`, `ingested_at`) is
  preserved for debugging and delete detection (future work toggles `is_deleted`
  when the API surfaces tombstones).

## Gold – Game review health mart

* **Model**: `gold.game_review_health_metrics` aggregates Silver into per-game
  metrics with `record_changed_at` and a derived daily `snapshot_date` for
  incremental rollups.
* **Metrics**:
  * **Hold-up score** – Change in positive review ratio between the first 180
    days of reviews and the most recent 180 days (configurable).
  * **Review decay ratio** – Ratio of review counts in the most recent 90 days
    versus the prior 90-day window. Values below 1 highlight faster decay.
  * **Cult popularity score** – Helpful-vote weighted signal adjusted for
    catalog reach (`avg helpful votes × lifetime positive ratio ÷ ln(total reviews + 2)`).
  * **General popularity score** – Broad reach proxy using
    `total reviews × lifetime positive ratio`.

## Semantic layer

`semantic_models/game_review_health.yml` defines a MetricFlow semantic model that
exposes the four key metrics directly from the Gold table with a daily time
dimension. BI tools can query `hold_up_score`, `review_decay_ratio`,
`cult_popularity_score`, and `general_popularity_score` without hand-writing SQL.

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
