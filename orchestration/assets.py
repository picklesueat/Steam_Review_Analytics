"""Dagster software-defined assets for ingestion and modeling."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import structlog
from dagster import (
    AssetExecutionContext,
    MetadataValue,
    Output,
    StaticPartitionsDefinition,
    asset,
)

from ingest_trakt.client import TraktClient
from ingest_trakt.config import TraktSettings


LOGGER = structlog.get_logger()


def _load_movie_partitions() -> Sequence[str]:
    """Resolve the set of movie IDs that should be partitioned."""

    env_value = os.getenv("TRAKT_MOVIE_IDS", "")
    if env_value:
        partitions = [value.strip() for value in env_value.split(",") if value.strip()]
        if partitions:
            return partitions
    # Provide a small default list so local development works out-of-the-box.
    return ["inception-2010", "dune-2021", "blade-runner-2049"]


MOVIE_ID_PARTITIONS = StaticPartitionsDefinition(_load_movie_partitions())


def _resolve_bronze_root() -> Path:
    """Determine where bronze payloads are written on disk."""

    base_path = os.getenv("BRONZE_STORAGE_ROOT", "data/bronze/trakt_comments")
    return Path(base_path)


def _resolve_comment_resource(movie_id: str) -> str:
    """Construct the Trakt resource path for movie comment ingestion."""

    # Trakt exposes comments at /movies/{slug}/comments. Consumers can adjust this
    # helper if they prefer the /newest or /likes sub-resources.
    return f"/movies/{movie_id}/comments"


def _write_jsonl(path: Path, payload: Iterable[dict]) -> int:
    """Persist payloads to newline-delimited JSON and return the row count."""

    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for record in payload:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
            count += 1
    return count


@asset(
    group_name="bronze",
    partitions_def=MOVIE_ID_PARTITIONS,
)
def bronze_trakt_comments(context) -> str:
    """Ingest Trakt comments for a single movie into local bronze storage."""

    partition_key = context.partition_key
    if not partition_key:  # pragma: no cover - safety guard
        raise ValueError("bronze_trakt_comments requires a partitioned movie id")

    resource_path = _resolve_comment_resource(partition_key)
    storage_root = _resolve_bronze_root()
    movie_root = storage_root / f"movie_id={partition_key}"
    movie_root.mkdir(parents=True, exist_ok=True)
    load_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_path = movie_root / f"load_ts={load_ts}.jsonl"

    LOGGER.info(
        "bronze_trakt_comments.start",
        movie_id=partition_key,
        resource_path=resource_path,
        output_path=str(output_path),
    )

    settings = TraktSettings()
    client = TraktClient(settings=settings)
    schema = client.build_comment_schema()
    try:
        payload = list(
            client.iter_comments(
                resource_path=resource_path,
                params={"extended": "full"},
                schema=schema,
            )
        )
    finally:
        client.close()

    row_count = _write_jsonl(output_path, payload)

    LOGGER.info(
        "bronze_trakt_comments.complete",
        movie_id=partition_key,
        resource_path=resource_path,
        row_count=row_count,
        output_path=str(output_path),
    )

    return Output(
        str(output_path),
        metadata={
            "movie_id": partition_key,
            "resource_path": resource_path,
            "rows": row_count,
            "output_path": MetadataValue.path(str(output_path)),
        },
    )


__all__ = ["bronze_trakt_comments", "MOVIE_ID_PARTITIONS"]
