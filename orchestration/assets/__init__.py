"""Dagster software-defined assets for ingestion and modeling."""

from dagster import AssetIn, AssetOut, asset


@asset(group_name="bronze", io_manager_key="delta_io_manager")
def bronze_trakt_comments() -> None:  # pragma: no cover - placeholder
    """Placeholder asset description for bronze comment landings."""

    raise NotImplementedError("Implement ingestion asset for Trakt comments")


@asset(ins={"comments": AssetIn("bronze_trakt_comments")}, outs={"staging": AssetOut()})
def stg_trakt__comment_event(comments):  # pragma: no cover - placeholder
    """Transform bronze comments into typed staging rows."""

    raise NotImplementedError("Implement dbt or PySpark transformation asset")
