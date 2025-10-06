# Operations runbook

## Daily ingestion

1. Ensure Dagster's `daily_trakt_ingestion` job completes by 07:30 CT.
2. Verify Elementary freshness dashboard for `bronze_trakt_comments` shows ≤120 minute lag.
3. If freshness breach occurs:
   * Check Dagster logs for rate-limit (429) storms.
   * Trigger `make orchestration/backfill_comments` (to be implemented) with the impacted date range.
   * Document incident in [`docs/postmortem_template.md`](postmortem_template.md).

## Backfill procedure

1. Pause scheduled jobs for the affected resource.
2. Use Dagster backfill CLI or API with `resume_state` from the latest successful page.
3. Monitor throughput (target ≥1M comment rows in ≤30 minutes on dev hardware).
4. Once complete, run `dbt run --select state:modified+` to recompute downstream models.

## Synthetic load testing

1. Launch the FastAPI replayer (`uvicorn replayer.app:app --reload`).
2. Set `TRAKT_BASE_URL=http://localhost:8000` and `IS_SYNTHETIC=true` in the environment.
3. Execute backfill job targeting the replayer dataset.
4. Record metrics: rows/sec, retry/backoff behavior, time-to-recover from induced 429 storms.
5. Store observations in `docs/perf_report.md` (to be created) for portfolio storytelling.

## Incident management

* Severity levels align with SLO impact (S1 = SLO breach, S2 = approaching error budget, S3 = informational).
* Log every incident in the postmortem template within 24 hours of detection.
* Track action items and owners; review progress during weekly reliability reviews.

## Secrets rotation

* Rotate Trakt and TMDb credentials quarterly or upon suspected compromise.
* Store secrets in the chosen Secret Manager; never commit them to the repo.
* Update Dagster deployments and CI/CD pipelines immediately after rotation.
