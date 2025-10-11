"""Manual proof-of-concept pipeline for ingesting Steam reviews."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import structlog

from ingest_steam.client import SteamReviewsClient
from ingest_steam.config import SteamSettings

LOGGER = structlog.get_logger()


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise argparse.ArgumentTypeError("max-pages must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("max-pages must be >= 1")
    return parsed


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
    return parser.parse_args()


def write_jsonl(path: Path, reviews: Iterable[dict[str, object]]) -> int:
    """Write an iterable of review dictionaries to a JSONL file."""

    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for review in reviews:
            fh.write(json.dumps(review, ensure_ascii=False) + "\n")
            count += 1
    return count


def run() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    settings = SteamSettings()
    with SteamReviewsClient(settings=settings) as client:
        schema = client.build_review_schema()
        for app_id in args.app_ids:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            output_path = args.output_dir / f"steam_reviews_{app_id}_{timestamp}.jsonl"
            reviews = client.iter_reviews(
                app_id,
                language=args.language,
                review_type=args.review_type,
                purchase_type=args.purchase_type,
                max_pages=args.max_pages,
                schema=schema,
            )
            count = write_jsonl(output_path, reviews)
            LOGGER.info(
                "steam.reviews_written",
                app_id=str(app_id),
                output=str(output_path),
                review_count=count,
            )


if __name__ == "__main__":
    run()
