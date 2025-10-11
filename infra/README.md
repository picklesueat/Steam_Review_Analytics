# Infrastructure & platform notes

This folder will contain optional infrastructure-as-code and deployment assets
once the Steam reviews pipeline moves beyond the local POC stage.

Planned contents:

* `terraform/` – modules for object storage buckets, secrets, and the future
  orchestration deployment.
* `docker/` – container definitions for ingestion workers and the synthetic
  replayer.
* `kubernetes/` (optional) – manifests for running orchestrated jobs and dbt
  tasks on a cluster.

Before committing infrastructure code:

1. Document required cloud providers and IAM policies.
2. Capture secrets management strategy (e.g., AWS Secrets Manager, GCP Secret
   Manager).
3. Provide cost estimates and guardrails (resource monitors, budgets).
4. Align with the observability stack (logs, metrics, traces).
