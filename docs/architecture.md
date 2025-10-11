# Architecture overview

This project implements a Steam-focused review analytics pipeline with an
opinionated architecture that can grow from a local proof of concept into a
production-grade stack.

## Data flow

1. **Ingestion (bronze)**
   * A manual Python pipeline calls the Steam Store reviews endpoint via
     `ingest_steam.SteamReviewsClient`.
   * Responses are validated against JSON Schema before being persisted as
     append-only JSONL files in `data/bronze/`.
   * Bronze payloads capture metadata such as `app_id`, `page`, `cursor`, and
     `fetched_at` to enable deterministic resume behaviour.

2. **Modeling (silver)**
   * dbt will transform bronze landings into typed staging models
     (`stg_steam__review`, `dim_app`).
   * Incremental merges rely on `recommendationid` idempotency keys and watermarks
     on `GREATEST(timestamp_created, timestamp_updated)`.
   * Optional enrichment can join against Steam store metadata or third-party
     catalogs.

3. **Analytics (gold)**
   * Future gold marts will compute engagement funnels, sentiment trends, and
     retention indicators per title, region, and release cohort.
   * Semantic layer definitions will expose governed metrics for BI tools.

4. **Serving & observability**
   * Dashboards in Hex/Mode/Looker will visualize sentiment drift and player
     retention.
   * Observability hooks (Elementary, OpenLineage) will be added once orchestration
     is introduced.

## Reliability principles

* Idempotent incrementals with resume tokens support deterministic backfills.
* Schema drift is managed through JSON Schema contracts and staged promotion of
  new fields.
* Future SLOs will target ≥99% freshness by 09:00 CT and page completeness per
  app per day.
* A synthetic replayer will reproduce quota storms and load scenarios without
  live API traffic.

## Technology stack

| Layer            | Primary tooling                     | Notes |
| ---------------- | ----------------------------------- | ----- |
| Ingestion        | Python (`httpx`, `structlog`)       | Manual trigger via CLI script |
| Orchestration    | _TBD_                               | To be introduced after POC |
| Storage/Compute  | DuckDB / Delta (future)             | JSONL landings for local dev |
| Modeling         | dbt (DuckDB adapter)                | Bronze → Silver → Gold |
| Observability    | _TBD_                               | Wire in after orchestration |
| Serving          | Hex/Mode/Looker                     | Sentiment & engagement dashboards |

For a milestone-by-milestone plan, see [`docs/roadmap.md`](roadmap.md).
