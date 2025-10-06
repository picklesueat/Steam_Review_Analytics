# Architecture overview

This project implements a Trakt-focused review/comment analytics pipeline with the following opinionated architecture:

## Data flow

1. **Ingestion (bronze)**
   * Dagster orchestrates HTTP ingestion via `ingest_trakt.TraktClient`.
   * Responses are validated against JSON Schema before being persisted as append-only Delta/Iceberg tables (or DuckDB during dev).
   * Bronze tables capture payload JSON and metadata (`resource_kind`, `title_kind`, `title_id_trakt`, `page`, `fetched_at`).

2. **Modeling (silver)**
   * dbt transforms bronze tables into typed staging models (`stg_trakt__comment_event`, `stg_trakt__rating_dist`).
   * Incremental merges rely on `comment_id` idempotency keys and watermarks on `GREATEST(created_at, updated_at)`.
   * Optional TMDb metadata enriches a `dim_title` dimension.

3. **Analytics (gold)**
   * Gold marts compute per-title daily engagement metrics, Breadth vs Intensity quadrants, and hold-up indicators.
   * Semantic layer definitions expose governed metrics for BI tools.

4. **Serving & observability**
   * Hex/Mode/Looker dashboards visualize quadrants and half-life trends.
   * Elementary + OpenLineage provide lineage, freshness, and testing coverage.
   * Grafana/Prometheus dashboards monitor SLOs and incident response workflows.

## Reliability principles

* Idempotent incrementals with resume tokens support deterministic backfills.
* Schema drift is managed through JSON Schema contracts and staged promotion of new fields.
* SLOs: 99% freshness by 09:00 CT and ≥99% page completeness per title per day.
* Synthetic replayer reproduces quota storms and load scenarios without live API traffic.

## Technology stack

| Layer            | Primary tooling                     | Notes |
| ---------------- | ----------------------------------- | ----- |
| Ingestion        | Python (`httpx`, `structlog`)       | Async client with retry/backoff |
| Orchestration    | Dagster                            | Assets, schedules, sensors |
| Storage/Compute  | Delta/Iceberg on object store       | DuckDB for local dev |
| Modeling         | dbt (DuckDB adapter)                | Bronze → Silver → Gold |
| Observability    | Elementary, Grafana, OpenLineage    | Freshness, completeness, lineage |
| Serving          | Hex/Mode/Looker                     | Quadrant explorer dashboards |

For a milestone-by-milestone plan, see [`docs/roadmap.md`](roadmap.md).
