# AGENTS.md — Polymarket Arbitrage Spotter

> This file provides context for AI agents (Codex, Cursor, Copilot) working on this codebase.

## Quick Context

**What is this?** Python tool + Streamlit dashboard to **detect** potential arbitrage opportunities and related signals in Polymarket markets (**no trading is performed**).

**Tech Stack:** Python 3.8+, Streamlit, pandas/numpy, requests, sqlite, pytest

**Key Directories:**
- `app/core/` — Core logic (API client, arb detector, storage, alerts, replay, wallet tooling)
- `app/ui/` — Streamlit UI views (presentation layer)
- `scripts/` — Example scripts / entrypoints
- `docs/` — Feature docs (deployment, replay engine, notifications, etc.)
- `data/` — Local config/data/db files
- `tests/` — Pytest suite

## Architecture (Mental Model)

```
Streamlit UI / Scripts → app/core (domain logic) → External APIs / Local DB
```

**Key principle:** UI code should not contain business logic. Put logic in `app/core/` and call it from `app/ui/` or `scripts/`.

## Running Locally

```bash
# Dashboard
streamlit run run_live.py

# Mock speed test
python run_mock_speed.py --duration 120
```

## Testing

```bash
pytest -q
```

## Coding Standards

See `.cursorrules` for complete standards. Highlights:

1. **Separation of concerns** — `app/ui/` renders; `app/core/` computes/IOs
2. **Deterministic tests** — No network calls in unit tests; mock/stub
3. **No trading** — Detect/monitor only; do not add execution features
4. **Logging** — Use the project logger; avoid `print()`

## Do NOT

- Add auto-trading / execution features
- Scatter Polymarket API calls throughout the codebase (centralize in core client modules)
- Add heavy dependencies without a strong reason
- Hardcode secrets (use `.env` / environment variables)


