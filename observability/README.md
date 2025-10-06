# Observability & SLO dashboards

This directory stores configuration for monitoring freshness, completeness, and reliability of the Trakt pipeline.

Planned assets:

* **Elementary** configuration and saved reports for dbt model health.
* **OpenLineage** settings for Dagster and dbt to emit lineage metadata.
* **Grafana/Prometheus** dashboards tracking SLOs (freshness, completeness, error budget burn).
* **Incident response** templates, including alert routing and postmortem integration.

When implementing monitoring:

1. Wire Dagster sensors to emit metrics via OpenTelemetry exporters.
2. Configure Elementary to publish `dbt docs` and freshness dashboards nightly.
3. Capture performance metrics before/after compaction & clustering exercises.
4. Provide screenshots in `docs/` to showcase observability outcomes.
