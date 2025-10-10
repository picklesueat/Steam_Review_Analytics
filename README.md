# Trakt Review/Comment Analytics Pipeline

This repository scaffolds a production-inspired analytics engineering and data engineering project that ingests public comment activity from [Trakt](https://trakt.tv/), models it into reliable dimensional marts, and publishes metrics that quantify engagement breadth, intensity, and durability for film and television titles.

The project is intentionally designed to exercise real-world DE/AE responsibilities:

* **Custom ingestion** with pagination, rate limiting, and schema contracts.
* **Lakehouse-friendly modeling** using a bronze → silver → gold layering strategy managed by dbt.
* **Dagster orchestration** with backfill/resume workflows, SLO monitoring, and incident response playbooks.
* **Governed semantic metrics** that can be reused across BI experiences.
* **Observability, performance, and reliability** artifacts that translate into portfolio-ready STAR stories.

> ℹ️  The repository currently ships with a structured scaffold so you can iterate feature-by-feature without reworking foundations. Each directory includes documentation stubs that explain intended responsibilities, dependencies, and next steps.

## Repository layout

```
.
├── README.md                   # Project overview & quickstart
├── Makefile                    # Common developer tasks (lint, test, docs)
├── requirements.txt            # Python dependencies (split by extras later)
├── ingest_trakt/               # Connector package (API client, schemas, utils)
├── orchestration/              # Dagster assets, jobs, and sensors
├── dbt/                        # dbt project (bronze/silver/gold models & metrics)
├── infra/                      # Infrastructure & IaC notes (Terraform, Docker)
├── observability/              # Freshness/completeness dashboards, OpenLineage cfg
├── dash/                       # Analytics experience (Hex/Mode/Looker notebooks)
├── replayer/                   # Synthetic API replayer for stress/perf testing
├── notebooks/                  # Exploratory analyses & scratchpads
└── docs/                       # Architecture, runbooks, SLO strategy, postmortems
```

Each subtree includes a README or design document describing ownership and integration points. Follow the roadmap in [`docs/roadmap.md`](docs/roadmap.md) to progress through the recommended milestones.

## Getting started

1. **Install prerequisites**
   * Python 3.11+
      `pip` for dependency management

2. **Clone & bootstrap**

   ```bash
   git clone https://github.com/<you>/movie_review_analytics_ETL.git
   cd movie_review_analytics_ETL
   make dev-install
   ```

3. **Configure secrets & environment**
   * Copy `.env.example` (to be added) to `.env` with Trakt/TMDb credentials.
   * Export `TRAKT_CLIENT_ID`, `TRAKT_CLIENT_SECRET`, and Dagster-related settings.
   * For the synthetic replayer, set `TRAKT_BASE_URL=http://localhost:8000` to toggle replay mode.

4. **Run initial checks**

   ```bash
   make lint
   make test
   make dbt-compile
   ```

   These commands currently act as placeholders; implement them as functionality lands.

## Development workflow

* **Ingestion** lives under [`ingest_trakt/`](ingest_trakt/). The `TraktClient` class encapsulates pagination, retries, and schema validation. Add JSON Schema definitions under `ingest_trakt/schemas/` and keep bronze landings append-only.
* **Orchestration** assets under [`orchestration/`](orchestration/) define Dagster jobs for daily ingests, backfills, and sensors. Use asset dependencies to wire dbt run steps and set SLO monitors.
* **Modeling** is managed by [`dbt/`](dbt/). Follow the bronze/silver/gold folder structure and declare metrics in YAML. Enable incremental models with idempotent merge strategies and `on_schema_change: append_new_columns`.
* **Documentation & runbooks** are curated in [`docs/`](docs/). Update the architecture, SLO strategy, and incident templates as the system matures. These artifacts underpin portfolio storytelling.

## Next steps

1. Implement the Trakt connector with resilient pagination and rate-limit handling.
2. Land bronze tables (comments, ratings distribution, optional TMDb metadata) using Delta/Iceberg or DuckDB for local development.
3. Build dbt staging models with tests and begin tracking metrics in the semantic layer.
4. Stand up Dagster orchestration with freshness sensors and incident alerting.
5. Deliver observability dashboards, SLO reporting, and performance benchmarks.

## Contributing

Contributions should adhere to the following guidelines:

* **Code style**: Use `ruff` + `black` for Python; enable type hints checked by `mypy` or `pyright` once dependencies settle.
* **Testing**: Target ≥80% coverage on connector logic and dbt tests for every new model.
* **Docs first**: Update relevant documentation alongside features (architecture diagrams, runbooks, dashboards).
* **Reliability mindset**: Maintain idempotency, lineage, and SLO commitments across features.

## License

This project has not yet selected a license. Choose one (e.g., Apache 2.0 or MIT) before public release.
