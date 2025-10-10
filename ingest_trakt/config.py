"""Configuration helpers for the Trakt connector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings


class TraktSettings(BaseSettings):
    """Environment-driven settings for the Trakt API."""

    client_id: str = Field(..., alias="TRAKT_CLIENT_ID")
    client_secret: str = Field(..., alias="TRAKT_CLIENT_SECRET")
    base_url: HttpUrl = Field("https://api.trakt.tv", alias="TRAKT_BASE_URL")
    user_agent: str = Field(
        "movie-review-analytics-etl/0.1 (+https://github.com/yourname)",
        alias="TRAKT_USER_AGENT",
    )
    max_retries: int = Field(5, alias="TRAKT_MAX_RETRIES")
    backoff_seconds: float = Field(1.0, alias="TRAKT_BACKOFF_SECONDS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@dataclass(frozen=True)
class PaginationState:
    """Track pagination progress for idempotent backfills."""

    title_id: str
    resource: str
    page: int
    fetched_at: Optional[str] = None
