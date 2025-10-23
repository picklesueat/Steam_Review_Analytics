# Steam Review Analytics Pipeline (Proof of Concept)

This repository bootstraps a production-inspired analytics engineering and data
engineering project that ingests public review activity from the
[Steam Store](https://store.steampowered.com/), models it into reliable marts,
and publishes engagement metrics for PC games. The current milestone focuses on
a Prefect-orchestrated proof of concept that can grow into a showcase-quality
portfolio project.

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture Summary](#architecture-summary)
  - [Orchestration](#orchestration)
  - [Data Modeling](#data-modeling)
  - [Semantic Model](#semantic-model)
  - [API & Ingestion](#api--ingestion)
- [Repository layout](#repository-layout)
- [Quick setup](#quick-setup)
- [Getting started](#getting-started)
- [Development workflow](#development-workflow)
- [Detailed Design Notes](#detailed-design-notes)
  - [Orchestration Details](#orchestration-details)
  - [Data Modeling Details](#data-modeling-details)
  - [Semantic Model Details](#semantic-model-details)
  - [API & Ingestion Details](#api--ingestion-details)
- [Next steps](#next-steps)
- [Contributing](#contributing)
- [License](#license)

## Project Overview

The pipeline ingests reviews for one or more Steam app IDs, lands the payloads
in DuckDB bronze tables, and materializes analytics layers through dbt. The
workflow is intentionally lightweight so that it runs locally while still
demonstrating production-friendly patterns such as load watermarks, medallion
modeling, and a semantic metrics layer.

## Architecture Summary

Each subsection below highlights the technology choice and rationale, followed
by a link to a deeper technical breakdown for recruiters or collaborators who
want to understand the system.

### Orchestration

- **Choice:** Prefect 2.0 flow composed of discrete tasks.
- **Why:** Keeps orchestration simple for a single-machine proof of concept
  while providing retries, logging, and observability hooks out of the box.
- **Future:** Planned evolution toward Dagster for first-class assets, asset
  backfills, partitions, and richer testing as throughput grows.
- 👉 Dive deeper in [Orchestration Details](#orchestration-details).

### Data Modeling

- **Choice:** dbt-driven medallion architecture (bronze, silver, gold).
- **Why:** Encourages modular SQL transformations with version control,
  documentation, and data quality tests that mirror enterprise analytics stacks.
- 👉 See [Data Modeling Details](#data-modeling-details) for schemas and tests.

### Semantic Model

- **Choice:** MetricFlow semantic definitions layered on top of gold models.
- **Why:** Enables BI tools to consume consistent metrics such as `avg_rating`
  or `cult_score` without coupling dashboards directly to warehouse tables.
- 👉 Read [Semantic Model Details](#semantic-model-details) for metric coverage.

### API & Ingestion

- **Choice:** Python connector built with `httpx`, `pydantic`, and DuckDB for
  landing zone storage.
- **Why:** Provides typed validation, resilient pagination, and reproducible
  local development while remaining lightweight for a resume-ready demo.
- 👉 Explore [API & Ingestion Details](#api--ingestion-details) for internals.

## Repository layout

```
.
├── README.md                   # Project overview & quickstart
├── Makefile                    # Common developer tasks (lint, test, docs)
├── requirements.txt            # Python dependencies for the POC
├── ingest_steam/               # Connector package (API client, schemas, utils)
├── pipelines/                  # Prefect flow entry points
├── dbt/                        # dbt project (bronze/silver/gold models & metrics)
├── observability/              # Freshness/completeness dashboards, lineage cfg
├── docs/                       # Architecture, runbooks, roadmap, SLO strategy
└── data/                       # Local landing zone for ingested payloads
```

## Quick setup

The fastest way to (re)start working on the project is to run the automated
bootstrap target, then execute the proof-of-concept Prefect flow:

```bash
git clone https://github.com/<your-org>/movie_review_analytics_ETL.git
cd movie_review_analytics_ETL
make dev-install
source .venv/bin/activate
python -m pipelines.steam_reviews_poc 620 --max-pages 2 --run-dbt --document-modeling
```

`make dev-install` provisions/refreshes the `.venv` virtual environment and
installs Python dependencies so that returning contributors can jump back in
with a single command. Activate the environment with
`source .venv/bin/activate` whenever you resume work in a new shell.

## Getting started

1. **Install prerequisites**
   * Python 3.11+
   * `pip` for dependency management

2. **Create a virtual environment & install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   Alternatively, run `make dev-install` to automate the above steps.

3. **Configure optional environment overrides**
   * Copy `.env.example` (to be added) to `.env` to override defaults like
     `STEAM_PAGE_SIZE` or `STEAM_USER_AGENT`.
   * The Steam Store reviews endpoint does not require an API key.

4. **Run the Steam review ingestion POC**

   ```bash
   python -m pipelines.steam_reviews_poc 620 --max-pages 2 --run-dbt --document-modeling
   ```

   This command launches the Prefect flow, fetches up to two pages of reviews
   for the Steam app ID `620` (Portal 2), writes them to `data/bronze/` as
   newline-delimited JSON files, and appends the raw JSON into
   `bronze.steam_reviews_raw` inside the local DuckDB warehouse with per-run
   `load_id`s and watermarks. Passing `--run-dbt` materializes the
   bronze/silver/gold layers plus the semantic metrics overlay and logs a
   summary of the medallion modeling stack. Use `--warehouse-path` to point at
   an alternate DuckDB file if desired.

## Development workflow

* **Ingestion** lives under [`ingest_steam/`](ingest_steam/). The
  `SteamReviewsClient` class encapsulates pagination, retries, and schema
  validation for the Steam Store reviews API.
* **Prefect flows** are kept in [`pipelines/`](pipelines/). The
  `steam_reviews_poc.py` script wires the connector into Prefect tasks and a
  flow that can later be scheduled by Prefect Cloud or another orchestrator.
* **Modeling** lives in [`dbt/`](dbt/). The bronze view surfaces the
  append-only DuckDB ledger, silver materializes a table with normalized review
  attributes, and gold aggregates adaptive review metrics (`avg_rating`,
  `edp_current`, `decay_ewrr`, `cult_score`) that the semantic layer exposes.
* **Documentation & runbooks** are curated in [`docs/`](docs/). Update the
  architecture, SLO strategy, and incident templates as the system matures.

## Detailed Design Notes

### Orchestration Details

The proof-of-concept flow relies on Prefect 2.0 to break the ingestion process
into reusable tasks:

1. `initialize_run` prepares the landing zone and DuckDB warehouse.
2. `ingest_app_reviews` spins up a fresh `SteamReviewsClient` per app ID,
   writes JSONL drops, and records load watermarks.
3. `log_watermarks`, `document_modeling_overview`, and `trigger_dbt` provide
   post-ingestion instrumentation and transformations.

This structure keeps the local developer experience frictionless while paving
the way for richer orchestration. A future Dagster migration is on the roadmap
to unlock first-class asset management, partitions, backfills, asset checks,
and enhanced testability when the project needs to scale to higher review
volumes and stricter observability requirements.

### Data Modeling Details

The dbt project implements a medallion-style layout:

- **Bronze** (`bronze.steam_reviews_raw`): Append-only ledger that stores the
  untouched JSON payload and ingestion metadata such as `load_id`, `cursor`,
  and `ingested_at`.
- **Silver** (`silver.steam_reviews_enriched`): Flattens JSON into typed
  columns, converts epoch timestamps, and carries lineage fields for auditing.
- **Gold** (`gold.fct_steam_review_metrics_adaptive`): Aggregates sentiment,
  exponential decay metrics, popularity momentum, and a "cult score" signal.

All transformations live alongside automated tests and documentation so that
stakeholders can trust the derived metrics.

### Semantic Model Details

MetricFlow powers the semantic layer, surfacing measures such as `avg_rating`,
`edp_current`, `decay_ewrr`, and `cult_score`. Defining metrics in a semantic
model decouples BI tools from warehouse schemas, enforces shared definitions,
and enables flexible slicing without rewriting SQL.

### API & Ingestion Details

`SteamReviewsClient` is built on `httpx` with Pydantic-powered validation to
enforce response schemas. Review payloads are persisted both as timestamped
JSONL files and as rows in DuckDB so that engineers can replay loads or query
the bronze layer interactively. The Prefect tasks record watermarks per app ID,
supporting resumable ingestion strategies and downstream incremental builds.

## Next steps

1. Harden the Steam connector with richer validation, testing, and retry
   telemetry.
2. Land bronze tables (reviews, query summaries) using DuckDB for local
   development.
3. Build dbt staging models with tests and begin tracking metrics in the
   semantic layer.
4. Migrate orchestration to Dagster when asset partitions, backfills, and
   larger-scale observability become necessary.

## Contributing

Contributions should adhere to the following guidelines:

* **Code style**: Use `ruff` + `black` for Python; enable type hints checked by
  `mypy` or `pyright` once dependencies settle.
* **Testing**: Target ≥80% coverage on connector logic and dbt tests for every
  new model.
* **Docs first**: Update relevant documentation alongside features
  (architecture diagrams, runbooks, dashboards).
* **Reliability mindset**: Maintain idempotency, lineage, and SLO commitments
  across features.

## License

This project has not yet selected a license. Choose one (e.g., Apache 2.0 or
MIT) before public release.
