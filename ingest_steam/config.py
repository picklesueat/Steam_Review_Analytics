"""Configuration helpers for the Steam reviews connector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class SteamSettings(BaseSettings):
    """Environment-driven settings for the Steam Store API."""

    base_url: HttpUrl = Field("https://store.steampowered.com", alias="STEAM_BASE_URL")
    user_agent: str = Field(
        "steam-review-analytics-etl/0.1 (+https://github.com/yourname)",
        alias="STEAM_USER_AGENT",
    )
    max_retries: int = Field(5, alias="STEAM_MAX_RETRIES")
    backoff_seconds: float = Field(1.0, alias="STEAM_BACKOFF_SECONDS")
    page_size: int = Field(100, alias="STEAM_PAGE_SIZE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@dataclass(frozen=True)
class SteamPaginationState:
    """Track pagination progress for idempotent backfills."""

    app_id: str
    cursor: str
    page: int
    fetched_at: Optional[str] = None
