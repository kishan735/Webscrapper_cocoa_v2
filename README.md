# Cocoa Intelligence Terminal — v2

A Bloomberg-style intelligence terminal for the global cocoa market.

> v1 of this repo was a thin wrapper that fetched front-month spot for `CC=F` and ran a non-deterministic LLM call on every refresh. It has been removed in full. The new architecture is documented at `/root/.claude/plans/the-idea-reamins-the-smooth-wind.md`.

## What v2 does

**Phase 1 — Market data (this commit):**
- Full London Cocoa (ICE Liffe `C`) forward curve: every listed contract month, with settle / volume / open interest.
- Daily ICE end-of-day report ingest (canonical settle + OI per contract).
- 5-minute intraday quote polling from Investing.com via Scrapling (Camoufox stealth).
- Weekly CFTC Commitments of Traders positioning ingest (free Socrata API).
- 2-year history backfill via yfinance on cold start (continuous front-month series).
- Frontend: dark terminal-style forward-curve table, OHLC chart with OI overlay, and weekly COT panel.

**Phase 2 (not yet wired):** RSS news ingest + deterministic Anthropic Claude Haiku impact tagging with a hash-keyed SQLite cache.

**Phase 3 (not yet wired):** Adjacent feeds — weather (Open-Meteo), FX (Frankfurter), substitutes & equity proxies (EODHD ~$20/mo), Baltic Dry, ICCO bulletins, EUDR tracker.

**Phase 4 (stretch):** Live AIS shipment tracking from West African origin ports.

## Repo layout

```
backend/
  pyproject.toml
  app/
    main.py                  # FastAPI entry + lifespan
    config.py                # pydantic-settings
    scrapers/
      _base.py               # scrape_run context manager
      contracts.py           # upsert helper
      ice.py                 # ICE EOD report (settle/volume/OI per contract)
      investing.py           # Intraday quotes from Investing.com
      cftc.py                # CFTC COT weekly
      yfinance_backfill.py   # 2-year backfill on cold start
    storage/
      db.py                  # SQLite (WAL) + SQLModel engine
      models.py              # Contract, QuoteIntraday, QuoteEod, CotPositioning, ScrapeLog, AiCache
    services/
      curve.py               # Forward-curve snapshot assembly
    scheduler.py             # APScheduler jobs
    api/
      routes.py              # /api/curve, /api/contracts, /api/contract/{sym}/history, /api/positioning, /api/health, /api/admin/run/{src}
frontend/
  index.html
  app.js                     # Lightweight Charts curve + OHLC + OI + COT
  styles.css                 # Dark terminal theme
data/
  cocoa.db                   # SQLite (gitignored)
```

## Running locally

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .

# First-time Scrapling setup (downloads Camoufox browser)
python -m scrapling install

# Copy env template
cp ../.env.example ../.env

# Run
uvicorn app.main:app --reload --app-dir .
```

Then open <http://localhost:8000>.

### Trigger a scrape immediately (local debug)

The scheduler waits for its cron window. To pull data right away:

```bash
curl -X POST http://localhost:8000/api/admin/run/ice        # ICE EOD report (today / last business day)
curl -X POST http://localhost:8000/api/admin/run/intraday   # Investing.com contracts table
curl -X POST http://localhost:8000/api/admin/run/cftc       # CFTC COT latest 200 rows
```

## Verification

1. `curl http://localhost:8000/api/curve | jq '.rows | length'` returns ≥6 once ICE or Investing.com scrape has run.
2. Hit `http://localhost:8000` — forward-curve table populates, clicking a row loads OHLC into the chart.
3. `curl http://localhost:8000/api/health` shows last-run status per source.
4. Restart the server with an empty DB → `bootstrap.backfill` job runs and populates `quotes_eod` with the continuous series.

## Hosting

Deliberately undecided. The backend is a long-lived Python process with a local SQLite file — runs fine on any VPS, Fly.io, or Render. Vercel is **not** a fit (serverless timeouts, no persistent disk, shared CDN IPs blocked by ICE / Investing.com).

## Status

Phase 1 scaffold. Real-data verification of the ICE CSV URL pattern and the Investing.com selectors is still pending (URLs/selectors live in `backend/app/config.py` and `backend/app/scrapers/*.py` respectively — designed to be adjusted in one place).
