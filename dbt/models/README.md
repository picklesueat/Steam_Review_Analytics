# Models

The dbt project implements a medallion architecture to transform raw Steam
review payloads into analytics-ready marts.

* `bronze/steam_reviews_raw.sql` – view over the append-only DuckDB ledger
  populated by the ingestion pipeline. Mirrors every JSON payload with
  ingestion lineage.
* `bronze/steam_reviews_raw_compacted.sql` – latest payload per
  `(appid, recommendationid, hash_payload)` to provide a compacted feed for
  higher layers.
* `silver/steam_reviews_enriched.sql` – incremental MERGE that flattens JSON,
  normalizes timestamps, and processes only rows inside a two-day sliding window
  beyond the table watermark.
* `gold/game_review_health_metrics.sql` – game-level mart computing hold-up
  scores, decay ratios, and popularity heuristics for downstream analytics.
* `semantic_models/game_review_health.yml` – MetricFlow semantic model exposing
  hold-up, decay, cult, and general popularity metrics to BI tools.

Each subdirectory has an accompanying `schema.yml` to declare documentation and
quality tests. Extend the structure with additional models as new use cases are
introduced.
