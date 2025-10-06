# dbt project structure

This directory houses the dbt assets for the Trakt Review/Comment pipeline. The project intentionally mirrors a lakehouse layering strategy:

* `models/bronze` – raw, append-only tables preserving Trakt payloads and metadata.
* `models/silver` – typed staging models with minimal business logic and drift-tolerant columns.
* `models/gold` – analytics-ready marts powering breadth/intensity/hold-up metrics.
* `macros/` – shared macros for incremental merges, SCD helpers, and quality checks.

Future milestones:

1. Configure `profiles.yml` (DuckDB or Spark) and reference it from CI workflows.
2. Declare metrics in the dbt Semantic Layer for reuse across dashboards.
3. Integrate [Elementary](https://www.elementary-data.com/) or Great Expectations for extended monitoring.
4. Document exposures for Hex/Mode dashboards and Dagster asset lineage.
