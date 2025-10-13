# Steam Review Analytics Pipeline (Proof of Concept)

This repository bootstraps a production-inspired analytics engineering and data
engineering project that ingests public review activity from the
[Steam Store](https://store.steampowered.com/), models it into reliable
marts, and publishes engagement metrics for PC games.

The current milestone focuses on a **manual proof of concept** for fetching
Steam reviews. Future iterations will layer in dbt models, automated
orchestration, observability, and serving patterns.

## Repository layout

```
.
├── README.md                   # Project overview & quickstart
├── Makefile                    # Common developer tasks (lint, test, docs)
├── requirements.txt            # Python dependencies for the POC
├── ingest_steam/               # Connector package (API client, schemas, utils)
├── pipelines/                  # Manually-triggered ingestion scripts
├── dbt/                        # dbt project (bronze/silver/gold models & metrics)
├── infra/                      # Infrastructure & IaC notes (Terraform, Docker)
├── observability/              # Freshness/completeness dashboards, lineage cfg
├── dash/                       # Analytics experience (Hex/Mode/Looker notebooks)
├── replayer/                   # Synthetic API replayer for stress/perf testing
├── notebooks/                  # Exploratory analyses & scratchpads
├── docs/                       # Architecture, runbooks, roadmap, SLO strategy
└── data/                       # Local landing zone for ingested payloads
```

## Quick setup

The fastest way to (re)start working on the project is to run the automated
bootstrap target, then execute the proof-of-concept pipeline:

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

   This command fetches up to two pages of reviews for the Steam app ID `620`
   (Portal 2), writes them to `data/bronze/` as newline-delimited JSON files,
   and appends the raw JSON into `bronze.steam_reviews_raw` inside the local
   DuckDB warehouse with per-run `load_id`s and watermarks. Passing `--run-dbt`
   materializes the bronze/silver/gold layers plus the semantic metrics overlay
   and logs a summary of the medallion modeling stack.
   Use `--warehouse-path` to point at an alternate DuckDB file if desired.

## Development workflow

* **Ingestion** lives under [`ingest_steam/`](ingest_steam/). The
  `SteamReviewsClient` class encapsulates pagination, retries, and schema
  validation for the Steam Store reviews API.
* **Manual pipelines** are kept in [`pipelines/`](pipelines/). The
  `steam_reviews_poc.py` script demonstrates how to run the connector without a
  scheduler. Future work will port this into an orchestrated workflow.
* **Modeling** lives in [`dbt/`](dbt/). The bronze view surfaces the append-only
  DuckDB ledger, silver performs incremental MERGEs across a sliding window, and
  gold aggregates review health metrics that feed the semantic layer metrics
  (`hold_up_score`, `review_decay_ratio`, `cult_popularity_score`,
  `general_popularity_score`).
* **Documentation & runbooks** are curated in [`docs/`](docs/). Update the
  architecture, SLO strategy, and incident templates as the system matures.

## Next steps

1. Harden the Steam connector with richer validation, testing, and retry
   telemetry.
2. Land bronze tables (reviews, query summaries) using DuckDB for local
   development.
3. Build dbt staging models with tests and begin tracking metrics in the
   semantic layer.
4. Introduce orchestration once the connector and models stabilize.

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
