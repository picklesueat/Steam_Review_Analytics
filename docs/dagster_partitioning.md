# Dagster movie partitions cheat sheet

The Dagster definitions under `orchestration/` expose the `bronze_trakt_comments` asset as a
**static-partitioned asset**. Each partition key corresponds to a single Trakt movie slug
(e.g. `inception-2010`). Dagster treats every partition key as an independent slice of the
asset, so orchestration tooling can materialize them separately, in bulk, or in parallel.

## How runs can execute in parallel

Partitioned assets delegate run-level concurrency to the active run launcher. When you
submit a backfill from Dagster Cloud or Dagit, the launcher will queue one run per selected
partition. The default `QueuedRunCoordinator` ships with local Dagster, so by default you
get one run at a time. To fan out into parallel execution you can:

1. Enable the [Dagster daemon's `dagster-daemon run_worker`](https://docs.dagster.io/guides/deploying/running-dagster-locally#running-the-dagster-daemon)
   process and configure `max_concurrent_runs` in `dagster.yaml`.
2. Use a distributed run launcher (Kubernetes, Celery, or Dask) that spins up workers per
   run. Each movie partition becomes its own run, so multiple slugs can ingest at once.

No application code changes are required—Dagster fans out partitions based on the launcher
capacity.

## Targeted reloads versus full reruns

Because the asset is partitioned, you can materialize just the movie slugs you care about.
In Dagit you can:

* Open the asset, choose **Materialize**, and pick a single partition key to re-run.
* Kick off the `bronze_trakt_comments_backfill` job but select only the subset of partition
  keys you want refreshed.

Downstream assets can inherit the same partition keys using partition mappings. For example,
if a silver-layer asset references `bronze_trakt_comments`, declaring it with
`partitions_def=MOVIE_ID_PARTITIONS` and the default mapping lets Dagster request only the
bronze partitions that correspond to the silver partition currently materializing. That
means you can reprocess one movie end-to-end without forcing a full backfill.

If you intentionally want a full rerun (e.g. for a schema change), just start a backfill
with **all** partitions selected.

## Mental model

Think of partitions as a coordinate system: `(asset, partition_key)`. Dagster stores run
history at that granularity and schedules work accordingly. Whenever you see
`context.partition_key` in the code, it is retrieving the partition currently being
materialized so that the ingestion writes data to a movie-specific folder
(`movie_id=<slug>`). 【F:orchestration/assets/__init__.py†L47-L92】

By scoping file paths, metadata, and logging to the partition key, you get isolated storage
per movie and clear observability for individual reruns.
