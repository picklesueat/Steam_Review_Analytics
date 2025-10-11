# SLO strategy

The Steam reviews pipeline emphasizes freshness, completeness, and reliability
as it graduates from a manual POC into an automated platform.

## Service Level Objectives

| SLO                        | Target              | Measurement                                      |
| -------------------------- | ------------------- | ------------------------------------------------- |
| Bronze freshness           | 99% by 09:00 CT     | Time since last successful Steam review landing   |
| Page completeness          | 99% daily           | Pages ingested ÷ expected pages per app           |
| Incident response MTTR     | < 30 minutes        | Time from alert to mitigation for Sev1 issues     |
| Gold query performance p95 | < 300 ms            | DuckDB/Spark query execution time post-tuning     |

## Service Level Indicators

* Freshness lag (minutes)
* 429 error rate (per hour)
* Retry success ratio
* Late arrival rate (reviews arriving >7 days late)
* Row-level duplicate rate (per incremental run)

## Alerting philosophy

* **S1** – Immediate pager if freshness or completeness SLO breaches.
* **S2** – Slack notification when lag >75% of error budget or sustained 429 storm.
* **S3** – Weekly digest summarizing latency trends and schema drift events.

## Error budget policy

* Allocate 2 hours of error budget per 28-day window for freshness/completeness.
* Spending >50% of budget triggers a change freeze until mitigations are deployed.
* Document all spends in the incident postmortem template.

## Tooling (future state)

* Orchestration platform (Dagster/Prefect/Airflow) will emit metrics to
  Prometheus/Grafana dashboards.
* Elementary monitors dbt model freshness and test results.
* OpenLineage captures lineage for traceability during incidents.
