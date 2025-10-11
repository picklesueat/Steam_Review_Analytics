# Synthetic API replayer

The synthetic replayer mirrors Steam Store review endpoints using recorded JSON
responses. It enables reproducible load tests without hitting public APIs.

Components:

* `app.py` – FastAPI application serving recorded payloads with controllable
  latency, error rates, and 429 storms.
* `tests/` – Unit tests that validate pagination, backoff, and labeling logic.
* `fixtures/` (planned) – Gzipped recordings captured from real API
  interactions.

Usage outline:

```bash
uvicorn replayer.app:app --reload
```

Configure the connector with `STEAM_BASE_URL=http://localhost:8000` and
`SOURCE_SYSTEM=replay` to route traffic through the replayer during stress
scenarios.
