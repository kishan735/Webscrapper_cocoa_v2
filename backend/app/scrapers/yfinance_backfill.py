"""Historical OHLCV backfill via yfinance.

Used on cold start to populate `quotes_eod` with up to N years of daily bars
for the front-month London cocoa continuous series. Per-contract series for
London cocoa are not reliably exposed by Yahoo, so this backfill targets the
continuous front-month symbol and writes rows under a synthetic
"CC2.L-CONTINUOUS" contract.

The intent is to give the OHLC chart something to show before the first ICE
EOD scrape lands. Once ICE EOD writes start landing per contract month, this
synthetic series can be hidden in the UI.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Tuple

from sqlmodel import select

from app.config import settings
from app.scrapers._base import scrape_run
from app.scrapers.contracts import upsert_contract
from app.storage.db import get_session
from app.storage.models import QuoteEod

log = logging.getLogger(__name__)


CANDIDATE_SYMBOLS = ["CC2.L", "C-LON", "C=F"]  # try in order; first to return rows wins


def _try_download(symbol: str, start: date, end: date):
    try:
        import yfinance as yf
    except ImportError:
        log.error("yfinance not installed")
        return None
    try:
        df = yf.Ticker(symbol).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:  # broad — yfinance raises a zoo of exceptions
        log.warning("yfinance fetch %s failed: %s", symbol, e)
        return None


def pick_symbol(start: date, end: date) -> Tuple[str, object] | Tuple[None, None]:
    for sym in CANDIDATE_SYMBOLS:
        df = _try_download(sym, start, end)
        if df is not None and not df.empty:
            return sym, df
    return None, None


def run(years: int | None = None) -> int:
    yrs = years or settings.backfill_years
    end = date.today()
    start = end - timedelta(days=365 * yrs)

    with scrape_run("yfinance.backfill") as handle:
        symbol, df = pick_symbol(start, end)
        if symbol is None:
            log.warning("yfinance: no candidate symbol returned data")
            return 0

        with get_session() as session:
            contract = upsert_contract(
                session,
                exchange="ICE_LIFFE",
                symbol=f"{symbol}-CONTINUOUS",
                contract_month="Continuous (front month)",
            )
            contract_id = contract.id

            existing_dates = {
                d for (d,) in session.exec(
                    select(QuoteEod.date).where(QuoteEod.contract_id == contract_id)
                ).all()
            }

            written = 0
            for idx, row in df.iterrows():
                day = idx.date() if hasattr(idx, "date") else idx
                if day in existing_dates:
                    continue
                session.add(
                    QuoteEod(
                        contract_id=contract_id,
                        date=day,
                        open=float(row.get("Open")) if row.get("Open") == row.get("Open") else None,
                        high=float(row.get("High")) if row.get("High") == row.get("High") else None,
                        low=float(row.get("Low")) if row.get("Low") == row.get("Low") else None,
                        settle=float(row.get("Close")) if row.get("Close") == row.get("Close") else None,
                        volume=int(row.get("Volume")) if row.get("Volume") == row.get("Volume") else None,
                        open_interest=None,
                        source=f"yfinance:{symbol}",
                    )
                )
                written += 1
            handle.rows_written = written
        log.info("yfinance backfill via %s: %d rows", symbol, handle.rows_written)
        return handle.rows_written
