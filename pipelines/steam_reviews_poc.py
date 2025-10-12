"""Manual proof-of-concept pipeline for ingesting Steam reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from ingest_steam.client import SteamReviewsClient
from ingest_steam.config import SteamSettings

try:
    import duckdb
except ImportError:  # pragma: no cover - runtime dependency
    duckdb = None  # type: ignore[assignment]

LOGGER = structlog.get_logger()


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise argparse.ArgumentTypeError("max-pages must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("max-pages must be >= 1")
    return parsed


MEDALLION_MODELING_OVERVIEW = textwrap.dedent(
    """
    Medallion modeling overview:\n
    • Bronze (`bronze.steam_reviews_raw`): Append-only review ledger backed by DuckDB.
      Each row stores the untouched JSON payload alongside ingestion lineage columns
      (`load_id`, `ingested_at`, `cursor`, and a `hash_payload`). Raw JSONL drops are
      retained on disk for replay while the warehouse table mirrors one row per fetch.
      A compacted view (`bronze.steam_reviews_raw_compacted`) keeps the latest copy of
      each `(appid, recommendationid, hash_payload)` trio for downstream normalization.
    • Silver (`silver.steam_reviews_enriched`): Incremental MERGE that flattens JSON,
      converts epochs to timestamps, and processes only reviews whose `updated_at`
      values fall inside a two-day sliding window beyond the table watermark. Changes
      overwrite prior versions, optional columns track Bronze lineage, and soft delete
      flags are ready for future API tombstone support.
    • Gold (`gold.game_review_health_metrics`): Aggregates Silver into per-game health
      metrics, capturing hold-up deltas, review decay, and popularity heuristics while
      surfacing `record_changed_at` for incremental rollups.
    • Semantic layer: MetricFlow semantic model exposes `hold_up_score`,
      `review_decay_ratio`, `cult_popularity_score`, and `general_popularity_score`
      metrics for BI consumption directly from the Gold table.

    Orchestration steps:\n
    1. Ingest API → append JSON to disk and `bronze.steam_reviews_raw` with run-scoped
       `load_id`, advancing cursors and recording `(last_cursor, max(updated_at))` per
       app for replay watermarks.
    2. dbt Silver → incremental MERGE across the sliding window using Bronze
       `updated_at` (fallback to `ingested_at`) so only new or edited reviews are
       processed.
    3. dbt Gold/Semantic layer → recompute review-health rollups and refresh exposed
       metrics.
    """
)


@dataclass
class Watermark:
    app_id: str
    last_cursor: Optional[str]
    max_updated_at: Optional[datetime]
    load_id: str
    recorded_at: datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Steam Store reviews for one or more app IDs and write them to JSONL files.",
    )
    parser.add_argument(
        "app_ids",
        nargs="+",
        help="Steam app IDs to ingest reviews for (e.g. 620 for Portal 2).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/bronze"),
        help="Directory where JSONL files will be written.",
    )
    parser.add_argument(
        "--max-pages",
        type=positive_int,
        default=1,
        help="Maximum number of review pages to fetch per app ID.",
    )
    parser.add_argument(
        "--language",
        default="all",
        help="Steam language filter (default: all languages).",
    )
    parser.add_argument(
        "--review-type",
        default="all",
        help="Steam review_type filter (all, positive, negative).",
    )
    parser.add_argument(
        "--purchase-type",
        default="all",
        help="Steam purchase_type filter (all, steam, non_steam).",
    )
    parser.add_argument(
        "--run-dbt",
        action="store_true",
        help="After ingestion, run dbt build to materialize bronze/silver/gold models.",
    )
    parser.add_argument(
        "--warehouse-path",
        type=Path,
        default=Path("data/warehouse/steam_reviews.duckdb"),
        help="DuckDB warehouse file used to persist the bronze ledger (default: data/warehouse/steam_reviews.duckdb).",
    )
    parser.add_argument(
        "--dbt-project-dir",
        type=Path,
        default=Path("dbt"),
        help="Directory containing the dbt project (default: dbt).",
    )
    parser.add_argument(
        "--dbt-profiles-dir",
        type=Path,
        default=None,
        help="Optional directory that houses dbt profiles.yml (defaults to ~/.dbt).",
    )
    parser.add_argument(
        "--document-modeling",
        action="store_true",
        help="Log a summary of the medallion modeling stack after the run.",
    )
    return parser.parse_args()


def ensure_duckdb_available() -> None:
    if duckdb is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "duckdb Python package is required to persist the bronze table. Install it via `pip install duckdb`."
        )


def prepare_bronze_storage(database_path: Path) -> "duckdb.DuckDBPyConnection":
    """Open DuckDB and ensure bronze tables exist."""

    ensure_duckdb_available()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(database_path))
    conn.execute("create schema if not exists bronze")
    conn.execute(
        """
        create table if not exists bronze.steam_reviews_raw (
            appid text,
            recommendationid text,
            updated_at timestamp,
            ingested_at timestamp,
            load_id text,
            hash_payload text,
            cursor text,
            payload json
        )
        """
    )
    conn.execute(
        """
        create table if not exists bronze.load_watermarks (
            appid text,
            load_id text,
            cursor text,
            max_updated_at timestamp,
            recorded_at timestamp
        )
        """
    )
    return conn


def compute_hash(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def parse_review_timestamp(value: object) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def insert_into_bronze(
    conn: "duckdb.DuckDBPyConnection",
    *,
    review: dict[str, object],
    load_id: str,
    ingested_at: datetime,
) -> None:
    updated_at = parse_review_timestamp(review.get("timestamp_updated"))
    app_id = str(review.get("app_id")) if review.get("app_id") is not None else None
    recommendation_id = review.get("recommendationid")
    cursor = review.get("cursor")
    if app_id is None or recommendation_id is None:
        return
    hash_payload = compute_hash(review)
    conn.execute(
        """
        insert into bronze.steam_reviews_raw as target
        (appid, recommendationid, updated_at, ingested_at, load_id, hash_payload, cursor, payload)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            app_id,
            str(recommendation_id),
            updated_at.replace(tzinfo=None) if updated_at else None,
            ingested_at.replace(tzinfo=None),
            load_id,
            hash_payload,
            str(cursor) if cursor is not None else None,
            json.dumps(review, ensure_ascii=False),
        ],
    )


def record_watermark(
    conn: "duckdb.DuckDBPyConnection",
    watermark: Watermark,
) -> None:
    conn.execute(
        """
        insert into bronze.load_watermarks (appid, load_id, cursor, max_updated_at, recorded_at)
        values (?, ?, ?, ?, ?)
        """,
        [
            watermark.app_id,
            watermark.load_id,
            watermark.last_cursor,
            watermark.max_updated_at.replace(tzinfo=None) if watermark.max_updated_at else None,
            watermark.recorded_at.replace(tzinfo=None),
        ],
    )


def ingest_reviews(
    *,
    client: SteamReviewsClient,
    app_id: str,
    args: argparse.Namespace,
    load_id: str,
    ingested_at: datetime,
    conn: Optional["duckdb.DuckDBPyConnection"],
    schema: object,
) -> Watermark:
    timestamp = ingested_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = args.output_dir / f"steam_reviews_{app_id}_{timestamp}.jsonl"
    review_iterable = client.iter_reviews(
        app_id,
        language=args.language,
        review_type=args.review_type,
        purchase_type=args.purchase_type,
        max_pages=args.max_pages,
        schema=schema,
    )

    count = 0
    last_cursor: Optional[str] = None
    max_updated_at: Optional[datetime] = None
    with output_path.open("w", encoding="utf-8") as fh:
        for review in review_iterable:
            fh.write(json.dumps(review, ensure_ascii=False) + "\n")
            count += 1
            last_cursor = str(review.get("cursor")) if review.get("cursor") else last_cursor
            updated_at = parse_review_timestamp(review.get("timestamp_updated"))
            if updated_at and (max_updated_at is None or updated_at > max_updated_at):
                max_updated_at = updated_at
            if conn is not None:
                insert_into_bronze(conn, review=review, load_id=load_id, ingested_at=ingested_at)

    LOGGER.info(
        "steam.reviews_written",
        app_id=str(app_id),
        output=str(output_path),
        review_count=count,
        load_id=load_id,
    )

    watermark = Watermark(
        app_id=str(app_id),
        last_cursor=last_cursor,
        max_updated_at=max_updated_at,
        load_id=load_id,
        recorded_at=ingested_at,
    )
    if conn is not None:
        record_watermark(conn, watermark)
    return watermark


def run() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ingested_at = datetime.now(tz=timezone.utc)
    load_id = ingested_at.strftime("%Y%m%dT%H%M%S")
    conn: Optional["duckdb.DuckDBPyConnection"] = None
    if args.warehouse_path:
        conn = prepare_bronze_storage(args.warehouse_path)

    settings = SteamSettings()
    watermarks: list[Watermark] = []
    with SteamReviewsClient(settings=settings) as client:
        schema = client.build_review_schema()
        for app_id in args.app_ids:
            watermark = ingest_reviews(
                client=client,
                app_id=str(app_id),
                args=args,
                load_id=load_id,
                ingested_at=ingested_at,
                conn=conn,
                schema=schema,
            )
            watermarks.append(watermark)

    for watermark in watermarks:
        LOGGER.info(
            "steam.ingest_watermark",
            app_id=watermark.app_id,
            load_id=watermark.load_id,
            last_cursor=watermark.last_cursor,
            max_updated_at=(
                watermark.max_updated_at.isoformat() if watermark.max_updated_at else None
            ),
        )

    if conn is not None:
        conn.close()

    if args.document_modeling:
        LOGGER.info("steam.medallion_overview", message=MEDALLION_MODELING_OVERVIEW)

    if args.run_dbt:
        run_dbt(args.dbt_project_dir, args.dbt_profiles_dir)


def run_dbt(project_dir: Path, profiles_dir: Path | None) -> None:
    command = ["dbt", "build", "--project-dir", str(project_dir)]
    if profiles_dir is not None:
        command += ["--profiles-dir", str(profiles_dir)]

    LOGGER.info("steam.dbt_build.start", command=" ".join(command))
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "dbt executable not found. Ensure dbt-duckdb is installed in your environment."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("dbt build failed") from exc
    LOGGER.info("steam.dbt_build.complete")


if __name__ == "__main__":
    run()
