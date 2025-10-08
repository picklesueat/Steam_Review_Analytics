"""Dagster job definitions for scheduled runs and backfills."""

from dagster import Definitions, define_asset_job

from ..assets import MOVIE_ID_PARTITIONS, bronze_trakt_comments
from ..sensors import bronze_freshness_sensor


def build_jobs() -> Definitions:
    """Create Dagster job definitions for bronze backfills."""

    bronze_backfill = define_asset_job(
        name="bronze_trakt_comments_backfill",
        selection=[bronze_trakt_comments],
        partitions_def=MOVIE_ID_PARTITIONS,
        description=(
            "Backfill Trakt comment payloads by movie id into local bronze storage."
        ),
    )

    return Definitions(
        assets=[bronze_trakt_comments],
        jobs=[bronze_backfill],
        sensors=[bronze_freshness_sensor],
    )


__all__ = ["build_jobs"]
