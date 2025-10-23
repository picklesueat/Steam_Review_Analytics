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
from typing import Any, Optional

from prefect import flow, get_run_logger, task

from ingest_steam.client import SteamReviewsClient
from ingest_steam.config import SteamSettings

try:
    import duckdb
except ImportError:  # pragma: no cover - runtime dependency
    duckdb = None  # type: ignore[assignment]

def positive_int(value: str) -> int:
    """Validate that an argument value represents a positive integer."""
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
    • Silver (`silver.steam_reviews_enriched`): Table that flattens JSON, converts epochs
      to timestamps, and preserves Bronze lineage for each review. Soft delete flags are
      ready for future API tombstone support.
    • Gold (`gold.fct_steam_review_metrics_adaptive`): Aggregates Silver into adaptive
      review metrics covering lifetime positivity, exponentially decayed sentiment,
      popularity momentum, and a cult score while surfacing `record_changed_at` for lineage.
    • Semantic layer: MetricFlow semantic model exposes `avg_rating`, `edp_current`,
      `decay_ewrr`, and `cult_score` metrics for BI consumption directly from the Gold table.

    Orchestration steps:\n
    1. Ingest API → append JSON to disk and `bronze.steam_reviews_raw` with run-scoped
       `load_id`, advancing cursors and recording `(last_cursor, max(updated_at))` per
       app for replay watermarks.
    2. dbt Silver → materialize the enriched review table and keep Bronze lineage intact.
    3. dbt Gold/Semantic layer → recompute adaptive review metrics and refresh exposed
       semantic layer measures.
    """
)


@dataclass
class Watermark:
    app_id: str
    last_cursor: Optional[str]
    max_updated_at: Optional[datetime]
    load_id: str
    recorded_at: datetime


@dataclass
class PipelineConfig:
    """Serializable configuration passed into the Prefect flow."""

    app_ids: list[str]
    output_dir: Path
    max_pages: int
    language: str
    review_type: str
    purchase_type: str
    run_dbt: bool
    warehouse_path: Optional[Path]
    dbt_project_dir: Path
    dbt_profiles_dir: Optional[Path]
    document_modeling: bool


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Steam reviews ingestion utility."""
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
    """Raise an error if DuckDB is not available in the current environment."""
    if duckdb is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "duckdb Python package is required to persist the bronze table. Install it via `pip install duckdb`."
        )


def prepare_bronze_storage(database_path: Path) -> None:
    """Create DuckDB schemas and tables that back the bronze storage layer."""

    ensure_duckdb_available()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(database_path))
    try:
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
    finally:
        conn.close()


def compute_hash(payload: dict[str, object]) -> str:
    """Return a SHA-256 hash of a review payload for deduplication."""
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def parse_review_timestamp(value: object) -> Optional[datetime]:
    """Convert a Steam epoch timestamp to an aware ``datetime`` if possible."""
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
    """Persist an individual review record into the bronze ledger table."""
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
    """Store ingestion progress metadata for an app ID in DuckDB."""
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
    config: PipelineConfig,
    load_id: str,
    ingested_at: datetime,
    conn: Optional["duckdb.DuckDBPyConnection"],
    schema: object,
    logger: Any,
) -> Watermark:
    """Fetch reviews for a single app, persist results, and emit a watermark."""
    timestamp = ingested_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = config.output_dir / f"steam_reviews_{app_id}_{timestamp}.jsonl"
    review_iterable = client.iter_reviews(
        app_id,
        language=config.language,
        review_type=config.review_type,
        purchase_type=config.purchase_type,
        max_pages=config.max_pages,
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

    watermark = Watermark(
        app_id=str(app_id),
        last_cursor=last_cursor,
        max_updated_at=max_updated_at,
        load_id=load_id,
        recorded_at=ingested_at,
    )
    if conn is not None:
        record_watermark(conn, watermark)

    logger.info(
        "steam.reviews_written",
        app_id=str(app_id),
        output=str(output_path.resolve()),
        review_count=count,
        load_id=load_id,
    )
    return watermark


def run_dbt(
    project_dir: Path,
    profiles_dir: Path | None,
    *,
    logger: Any,
) -> None:
    """Invoke ``dbt build`` to materialize the medallion models."""
    command = ["dbt", "build", "--project-dir", str(project_dir)]
    if profiles_dir is not None:
        command += ["--profiles-dir", str(profiles_dir)]

    logger.info("steam.dbt_build.start", command=" ".join(command))
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "dbt executable not found. Ensure dbt-duckdb is installed in your environment."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("dbt build failed") from exc
    logger.info("steam.dbt_build.complete")


@task
def initialize_run(config: PipelineConfig) -> None:
    """Ensure local directories and warehouse tables exist before ingestion."""

    logger = get_run_logger()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "steam.output.prepared",
        output_dir=str(config.output_dir.resolve()),
    )
    if config.warehouse_path is not None:
        prepare_bronze_storage(config.warehouse_path)
        logger.info(
            "steam.warehouse.prepared",
            warehouse=str(config.warehouse_path.resolve()),
        )


@task
def ingest_app_reviews(
    app_id: str,
    config: PipelineConfig,
    load_id: str,
    ingested_at: datetime,
) -> Watermark:
    """Fetch reviews for a single app ID and persist them to disk and DuckDB."""

    logger = get_run_logger()
    settings = SteamSettings()
    conn: Optional["duckdb.DuckDBPyConnection"] = None
    try:
        if config.warehouse_path is not None:
            ensure_duckdb_available()
            conn = duckdb.connect(str(config.warehouse_path))

        with SteamReviewsClient(settings=settings) as client:
            schema = client.build_review_schema()
            watermark = ingest_reviews(
                client=client,
                app_id=str(app_id),
                config=config,
                load_id=load_id,
                ingested_at=ingested_at,
                conn=conn,
                schema=schema,
                logger=logger,
            )
        return watermark
    finally:
        if conn is not None:
            conn.close()


@task
def log_watermarks(watermarks: list[Watermark]) -> None:
    """Emit structured logs for recorded watermarks."""

    logger = get_run_logger()
    for watermark in watermarks:
        logger.info(
            "steam.ingest_watermark",
            app_id=watermark.app_id,
            load_id=watermark.load_id,
            last_cursor=watermark.last_cursor,
            max_updated_at=(
                watermark.max_updated_at.isoformat() if watermark.max_updated_at else None
            ),
        )


@task
def document_modeling_overview() -> None:
    """Log the medallion modeling overview."""

    logger = get_run_logger()
    logger.info("steam.medallion_overview", message=MEDALLION_MODELING_OVERVIEW)


@task
def trigger_dbt(project_dir: Path, profiles_dir: Path | None) -> None:
    """Kick off dbt build via a Prefect task."""

    logger = get_run_logger()
    run_dbt(project_dir, profiles_dir, logger=logger)


@flow(name="steam-reviews-poc")
def steam_reviews_flow(config: PipelineConfig) -> list[Watermark]:
    """Prefect flow that orchestrates the Steam review ingestion proof of concept."""

    logger = get_run_logger()
    initialize_run(config)

    ingested_at = datetime.now(tz=timezone.utc)
    load_id = ingested_at.strftime("%Y%m%dT%H%M%S")
    logger.info(
        "steam.flow.start",
        load_id=load_id,
        app_count=len(config.app_ids),
    )

    watermarks: list[Watermark] = []
    for app_id in config.app_ids:
        watermark = ingest_app_reviews(
            app_id=str(app_id),
            config=config,
            load_id=load_id,
            ingested_at=ingested_at,
        )
        watermarks.append(watermark)

    log_watermarks(watermarks)

    if config.document_modeling:
        document_modeling_overview()

    if config.run_dbt:
        trigger_dbt(config.dbt_project_dir, config.dbt_profiles_dir)

    logger.info("steam.flow.complete", load_id=load_id)
    return watermarks


def build_config(args: argparse.Namespace) -> PipelineConfig:
    """Translate parsed CLI arguments into a Prefect-friendly configuration."""

    return PipelineConfig(
        app_ids=[str(app_id) for app_id in args.app_ids],
        output_dir=args.output_dir,
        max_pages=args.max_pages,
        language=args.language,
        review_type=args.review_type,
        purchase_type=args.purchase_type,
        run_dbt=args.run_dbt,
        warehouse_path=args.warehouse_path,
        dbt_project_dir=args.dbt_project_dir,
        dbt_profiles_dir=args.dbt_profiles_dir,
        document_modeling=args.document_modeling,
    )


def run() -> None:
    """Execute the Prefect flow using CLI-sourced configuration."""

    args = parse_args()
    config = build_config(args)
    steam_reviews_flow(config)


if __name__ == "__main__":
    run()
