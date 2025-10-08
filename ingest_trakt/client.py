"""HTTP client abstractions for interacting with the Trakt API."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

import httpx
import structlog
from jsonschema import Draft7Validator

from .config import PaginationState, TraktSettings

LOGGER = structlog.get_logger()
SCHEMA_DIR = Path(__file__).parent / "schemas"


class TraktClient:
    """Thin wrapper around the Trakt API with pagination & retry handling."""

    def __init__(
        self,
        settings: Optional[TraktSettings] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.settings = settings or TraktSettings()
        self._client = http_client or httpx.Client(
            base_url=str(self.settings.base_url),
            headers={
                "Content-Type": "application/json",
                "trakt-api-version": "2",
                "trakt-api-key": self.settings.client_id,
                "User-Agent": self.settings.user_agent,
            },
            timeout=httpx.Timeout(10.0, read=30.0),
        )

    def __enter__(self) -> "TraktClient":  # pragma: no cover - syntactic sugar
        return self

    def __exit__(self, *exc_info: Any) -> None:  # pragma: no cover
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        """Perform an HTTP GET with retry/backoff for 429 handling."""

        params = params or {}
        attempt = 0
        while True:
            attempt += 1
            response = self._client.get(path, params=params)
            if response.status_code == 429 and attempt <= self.settings.max_retries:
                retry_after = response.headers.get("Retry-After")
                sleep_seconds = float(retry_after or (self.settings.backoff_seconds * attempt))
                LOGGER.warning(
                    "trakt.rate_limited",
                    path=path,
                    params=params,
                    attempt=attempt,
                    sleep_seconds=sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue
            response.raise_for_status()
            return response

    def iter_comments(
        self,
        resource_path: str,
        params: Optional[Dict[str, Any]] = None,
        schema: Optional[Draft7Validator] = None,
        resume_state: Optional[PaginationState] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate through comment pages, yielding validated payloads."""

        params = params or {}
        page = resume_state.page if resume_state else 1
        while True:
            response = self._get(resource_path, {**params, "page": page})
            payload = response.json()
            if schema:
                for item in payload:
                    schema.validate(item)
            if not payload:
                break
            for comment in payload:
                comment["fetched_at"] = datetime.utcnow().isoformat()
                yield comment
            page += 1

    def iter_ratings_distribution(
        self,
        resource_path: str,
        schema: Optional[Draft7Validator] = None,
    ) -> Dict[str, Any]:
        """Return a ratings distribution snapshot for a title."""

        response = self._get(resource_path)
        payload = response.json()
        if schema:
            schema.validate(payload)
        payload["fetched_at"] = datetime.utcnow().isoformat()
        return payload

    @staticmethod
    def _load_schema(schema_name: str) -> Draft7Validator:
        schema_path = SCHEMA_DIR / schema_name
        with schema_path.open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
        return Draft7Validator(schema)

    def build_comment_schema(self) -> Draft7Validator:
        """Load the JSON schema for comment payloads."""

        return self._load_schema("comments.schema.json")

    def build_ratings_schema(self) -> Draft7Validator:
        """Load the JSON schema for ratings distributions."""

        return self._load_schema("ratings.schema.json")


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
