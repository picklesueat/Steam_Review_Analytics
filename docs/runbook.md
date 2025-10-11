# Operations runbook

## Manual ingestion procedure

1. Activate the virtual environment and export any overrides from `.env`.
2. Execute the manual pipeline for each target app ID:
   ```bash
   python -m pipelines.steam_reviews_poc 620 1121560 --max-pages 2
   ```
   Add flags such as `--filter recent` or `--review-type positive` to mirror
   the Steam UI filters when needed.
3. Confirm that JSONL files appear under `data/bronze/` with the current UTC
   timestamp.
4. Inspect the most recent file and spot-check `fetched_at`, `cursor`, and
   `recommendationid` fields for plausibility.
5. Log completion and anomalies in the team journal or ticketing system.

## Backfill procedure

1. Determine the missing window (e.g., specific app IDs or date ranges).
2. Re-run the manual pipeline with a higher `--max-pages` value or adjusted
   filters to cover the gap.
3. If duplicate reviews appear, rely on downstream deduplication by
   `recommendationid` and `timestamp_updated`.
4. After ingestion, trigger the appropriate dbt models once they are available:
   ```bash
   dbt run --select tag:steam_reviews
   ```

## Synthetic load testing (future)

1. Launch the FastAPI replayer (`uvicorn replayer.app:app --reload`).
2. Set `STEAM_BASE_URL=http://localhost:8000` and `IS_SYNTHETIC=true` in the
   environment.
3. Execute the manual pipeline against the synthetic dataset with elevated
   `--max-pages` to stress pagination.
4. Record metrics: rows/sec, retry/backoff behavior, time-to-recover from
   induced 429 storms.
5. Store observations in `docs/perf_report.md` (to be created) for portfolio
   storytelling.

## Incident management

* Severity levels align with SLO impact (S1 = SLO breach, S2 = approaching error
  budget, S3 = informational).
* Log every incident in the postmortem template within 24 hours of detection.
* Track action items and owners; review progress during weekly reliability
  reviews.

## Secrets rotation

* The Steam reviews endpoint does not require credentials, but any future API
  keys or secrets should be rotated quarterly or upon suspected compromise.
* Store secrets in the chosen Secret Manager; never commit them to the repo.
* Update deployment automation immediately after rotation.
