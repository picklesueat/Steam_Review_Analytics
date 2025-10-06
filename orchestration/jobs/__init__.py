"""Dagster job definitions for scheduled runs and backfills."""

from dagster import Definitions, JobDefinition, ScheduleDefinition

from ..assets import bronze_trakt_comments, stg_trakt__comment_event


def build_jobs() -> Definitions:  # pragma: no cover - placeholder
    """Create Dagster job and schedule definitions."""

    daily_job = JobDefinition.from_graph(  # type: ignore[arg-type]
        name="daily_trakt_ingestion",
        graph_def=bronze_trakt_comments,
    )
    schedule = ScheduleDefinition(
        name="daily_trakt_ingestion_schedule",
        cron_schedule="0 7 * * *",
        job=daily_job,
    )
    return Definitions(jobs=[daily_job], schedules=[schedule], assets=[stg_trakt__comment_event])
