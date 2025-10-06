"""FastAPI app that replays recorded Trakt API responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Trakt Replay Service", version="0.1.0")

RECORDINGS_DIR = Path(__file__).parent / "fixtures"


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/movies/{title_id}/comments")
async def movie_comments(title_id: str, page: int = 1, limit: int = 10) -> Any:  # pragma: no cover - placeholder
    recording = RECORDINGS_DIR / f"movies_{title_id}_comments_{page}_{limit}.json"
    if not recording.exists():
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording.read_text()
