# Milestone roadmap

The following plan covers ~6 weeks of focused development, aligned with the
Steam reviews analytics specification.

## Week 0.5 – Scaffold & contracts (current)

* [x] Initialize repository structure and documentation scaffolding.
* [ ] Define JSON Schemas for Steam review payloads.
* [ ] Ship a manually-triggered ingestion POC that writes JSONL landings.

## Week 1 – Ingestion & bronze

* Harden the Steam connector with pagination resume tokens and retry telemetry.
* Land bronze tables for reviews and query summaries (DuckDB/Delta).
* Add unit tests covering connector logic, schema validation, and failure modes.

## Week 2 – Silver facts/dims + semantics

* Build staging models (`stg_steam__review`, `dim_app`).
* Add dbt tests (unique/not_null/relationships) and semantic layer metric
  definitions.
* Document data contracts and schema drift handling.

## Week 3 – Gold marts + dashboard

* Implement gold fact tables and marts (engagement funnels, retention metrics).
* Publish dashboard prototype (Hex/Mode) referencing semantic metrics.
* Capture screenshots and document analytics value.

## Week 4 – Reliability & performance

* Introduce orchestration (e.g., Dagster/Prefect) with freshness monitoring.
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
