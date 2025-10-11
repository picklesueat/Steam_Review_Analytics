"""HTTP client abstractions for interacting with the Steam reviews API."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional
from urllib.parse import quote

import httpx
import structlog
from jsonschema import Draft7Validator

from .config import SteamPaginationState, SteamSettings

LOGGER = structlog.get_logger()
SCHEMA_DIR = Path(__file__).parent / "schemas"


class SteamReviewsClient:
    """Thin wrapper around the Steam Store reviews endpoint with pagination & retry handling."""

    def __init__(
        self,
        settings: Optional[SteamSettings] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.settings = settings or SteamSettings()
        self._client = http_client or httpx.Client(
            base_url=str(self.settings.base_url),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.settings.user_agent,
            },
            timeout=httpx.Timeout(10.0, read=30.0),
        )

    def __enter__(self) -> "SteamReviewsClient":  # pragma: no cover - syntactic sugar
        return self

    def __exit__(self, *exc_info: Any) -> None:  # pragma: no cover
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def _get(self, path: str, params: Dict[str, Any]) -> httpx.Response:
        """Perform an HTTP GET with retry/backoff for 429 handling."""

        attempt = 0
        while True:
            attempt += 1
            response = self._client.get(path, params=params)
            if response.status_code == 429 and attempt <= self.settings.max_retries:
                retry_after = response.headers.get("Retry-After")
                sleep_seconds = float(retry_after or (self.settings.backoff_seconds * attempt))
                LOGGER.warning(
                    "steam.rate_limited",
                    path=path,
                    params=params,
                    attempt=attempt,
                    sleep_seconds=sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue
            response.raise_for_status()
            return response

    def iter_reviews(
        self,
        app_id: str | int,
        *,
        language: str = "all",
        filter_type: str = "recent",
        review_type: str = "all",
        purchase_type: str = "all",
        max_pages: Optional[int] = None,
        schema: Optional[Draft7Validator] = None,
        resume_state: Optional[SteamPaginationState] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate through review pages, yielding validated payloads."""

        cursor = resume_state.cursor if resume_state else "*"
        page = resume_state.page if resume_state else 1
        while True:
            encoded_cursor = self._encode_cursor(cursor)
            params = {
                "json": 1,
                "cursor": encoded_cursor,
                "language": language,
                "filter": filter_type,
                "review_type": review_type,
                "purchase_type": purchase_type,
                "num_per_page": self.settings.page_size,
            }
            response = self._get(f"/appreviews/{app_id}", params)
            payload = response.json()
            if payload.get("success") != 1:
                LOGGER.warning(
                    "steam.unexpected_response",
                    app_id=str(app_id),
                    success=payload.get("success"),
                    status=payload.get("status"),
                )
                break

            reviews = payload.get("reviews", [])
            if schema:
                for review in reviews:
                    schema.validate(review)
            if not reviews:
                break
            for review in reviews:
                review["app_id"] = str(app_id)
                review["page"] = page
                review["cursor"] = cursor
                review["fetched_at"] = datetime.utcnow().isoformat()
                yield review
            next_cursor = payload.get("cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
            page += 1
            if max_pages is not None and page > max_pages:
                break

    @staticmethod
    def _encode_cursor(cursor: str) -> str:
        """Prepare a cursor string for use in query parameters."""

        if cursor == "*":
            return cursor
        return quote(cursor, safe="")

    @staticmethod
    def _load_schema(schema_name: str) -> Draft7Validator:
        schema_path = SCHEMA_DIR / schema_name
        with schema_path.open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
        return Draft7Validator(schema)

    def build_review_schema(self) -> Draft7Validator:
        """Load the JSON schema for review payloads."""

        return self._load_schema("reviews.schema.json")


def chunk(iterable: Iterable[Any], size: int) -> Iterable[list[Any]]:
    """Yield chunks from an iterable.

    Useful for batching inserts to storage layers or warehouses.
    """

    batch: list[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
