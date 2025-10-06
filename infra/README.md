# Infrastructure & platform notes

This folder will contain optional infrastructure-as-code and deployment assets.

Planned contents:

* `terraform/` – modules for object storage buckets, secrets, and Dagster deployment.
* `docker/` – container definitions for the ingestion workers and synthetic replayer.
* `kubernetes/` (optional) – manifests for running Dagster and dbt jobs on a cluster.

Before committing infrastructure code:

1. Document required cloud providers and IAM policies.
2. Capture secrets management strategy (e.g., AWS Secrets Manager, GCP Secret Manager).
3. Provide cost estimates and guardrails (resource monitors, budgets).
4. Align with observability stack (logs, metrics, traces).
