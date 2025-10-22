# Models

The dbt project implements a medallion architecture to transform raw Steam
review payloads into analytics-ready marts.

* `bronze/steam_reviews_raw.sql` – view over the append-only DuckDB ledger
  populated by the ingestion pipeline. Mirrors every JSON payload with
  ingestion lineage.
* `bronze/steam_reviews_raw_compacted.sql` – latest payload per
  `(appid, recommendationid, hash_payload)` to provide a compacted feed for
  higher layers.
* `silver/steam_reviews_enriched.sql` – table that flattens JSON, normalizes
  timestamps, and preserves Bronze lineage for each review.
* `gold/fct_steam_review_metrics_adaptive.sql` – adaptive review metrics table
  with lifetime positivity, exponentially decayed sentiment, momentum, and
  cult-score signals.
* `semantic_models/steam_review_metrics_adaptive.yml` – MetricFlow semantic
  model exposing the adaptive review metrics to BI tools.

Each subdirectory has an accompanying `schema.yml` to declare documentation and
quality tests. Extend the structure with additional models as new use cases are
introduced.
