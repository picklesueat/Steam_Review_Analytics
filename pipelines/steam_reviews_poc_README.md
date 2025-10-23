# Steam Reviews Proof-of-Concept Pipeline

The `steam_reviews_poc.py` script now leverages a Prefect flow composed of discrete
tasks to pull Steam Store review data, persist the raw payloads for replay, and
optionally kick off analytics transformations with dbt. It is intended as a manual
entry point for understanding the larger Movie Review Analytics stack without requiring
the full production deployment.

## High-level workflow

1. **Argument parsing** – Validates CLI options such as the app IDs to fetch, output
directories, pagination limits, and whether dbt should run after ingestion.
2. **Bronze storage preparation** – Ensures a DuckDB warehouse exists with two tables:
   `bronze.steam_reviews_raw` for the review ledger and `bronze.load_watermarks` for load
   metadata. Both tables are created on-demand.
3. **Prefect flow orchestration** – Each app ID is handled by the
   `ingest_app_reviews` task, which streams reviews through `SteamReviewsClient`, writes
   payloads to timestamped JSONL files, mirrors them into DuckDB, and records load
   metadata.
4. **Watermark persistence** – After fetching an app's reviews, the most recent cursor and
   `updated_at` timestamp observed are stored so that downstream jobs can resume from the
   correct point in time.
5. **Optional post-processing** – When invoked with `--run-dbt`, the script executes `dbt
   build` against the configured project to materialize bronze, silver, and gold models.
   Enabling `--document-modeling` also logs a short primer describing how the medallion
   layers relate to each other.

## Key outputs

- Timestamped JSONL drops under `data/bronze/` (configurable via `--output-dir`).
- Inserted records in DuckDB, allowing interactive exploration of the bronze tables.
- Structured logs emitted through Prefect's task logger, detailing ingestion counts and
  watermarks.

## Running the script

```bash
python pipelines/steam_reviews_poc.py 620 400 --max-pages 2 --run-dbt
```

The example above ingests two Steam app IDs, fetches up to two pages of reviews each,
persists results locally, and then rebuilds the dbt project using the default settings.
Provide `--dbt-project-dir` or `--dbt-profiles-dir` if your dbt configuration lives in a
non-standard location.
