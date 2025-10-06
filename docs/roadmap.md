# Milestone roadmap

The following plan covers ~6 weeks of focused development, aligned with the project specification.

## Week 0.5 – Scaffold & contracts (current)

* [x] Initialize repository structure and documentation scaffolding.
* [ ] Define JSON Schemas for Trakt comments and rating distribution payloads.
* [ ] Configure Dagster/dbt skeletons and CI placeholders.

## Week 1 – Ingestion & bronze

* Implement resilient Trakt connector with pagination, retries, and rate-limit handling.
* Land bronze tables for comments and ratings distribution (DuckDB/Delta).
* Add unit tests (≥15) covering connector logic, schema validation, and failure modes.

## Week 2 – Silver facts/dims + semantics

* Build staging models (`stg_trakt__comment_event`, `stg_trakt__rating_dist`, `dim_title`).
* Add dbt tests (unique/not_null/relationships) and semantic layer metric definitions.
* Document data contracts and schema drift handling.

## Week 3 – Gold marts + dashboard

* Implement gold fact tables and marts (Breadth vs Intensity quadrants, hold-up metrics).
* Publish dashboard prototype (Hex/Mode) referencing semantic metrics.
* Capture screenshots and document AE value.

## Week 4 – Reliability & performance

* Add Dagster sensors, alerts, and SLO dashboards.
* Implement compaction + clustering; record before/after p95 + bytes scanned.
* Publish incident postmortem template and run reliability drill.

## Week 5 – Stress & backfills

* Finalize synthetic API replayer with replay fixtures.
* Execute 10–50× load tests; document throughput and recovery metrics.
* Demonstrate idempotent backfill strategy with resume tokens.

## Week 6 – Platform polish (optional)

* Dockerize workers and replayer; define Terraform modules for storage/secrets.
* Add FastAPI read-only endpoints for product-style data serving.
* Summarize outcomes in portfolio docs (STAR stories, lessons learned).
