"""yfinance backfill of cocoa front-month continuous OHLCV.

Yahoo's ``CC=F`` is the NYBOT (now ICE US) cocoa continuous front-month series
priced in USD/tonne. It's the closest free historical proxy for cocoa futures
levels. We persist 2 years of daily bars under a single Contract row with
``symbol="CC-CONTINUOUS"`` so the existing forward-curve filter (which
excludes ``%-CONTINUOUS`` rows) keeps the proxy out of the curve UI while
still letting the history endpoint reach it via the standard
``QuoteEod[contract_id]`` join.

This is **not** London Cocoa (LCCcN). London cocoa has no free continuous
ticker on Yahoo. The proxy is labelled ``CC=F NYBOT continuous`` in the UI
so users aren't misled about the source.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import select

from app.scrapers._base import scrape_run
from app.scrapers.contracts import upsert_contract
from app.storage.db import get_session
from app.storage.models import QuoteEod

log = logging.getLogger(__name__)

CONTINUOUS_SYMBOL = "CC-CONTINUOUS"
CONTINUOUS_EXCHANGE = "NYBOT"
CONTINUOUS_LABEL = "CC=F NYBOT continuous"
YF_TICKER = "CC=F"


def _to_float(v) -> Optional[float]:
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _to_int(v) -> Optional[int]:
    f = _to_float(v)
    return int(f) if f is not None else None


def run(years: int = 2) -> int:
    """Pull `years` years of daily OHLCV for CC=F and upsert into QuoteEod.

    Returns the number of rows written (inserts + updates).
    """
    with scrape_run("yfinance.backfill") as handle:
        try:
            import yfinance as yf
        except ImportError:
            log.error("yfinance not installed; backfill skipped")
            return 0

        end = datetime.utcnow().date()
        start = end - timedelta(days=int(years * 366))
        log.info("yfinance backfill %s: %s → %s", YF_TICKER, start, end)
        try:
            df = yf.download(
                YF_TICKER,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as e:
            log.warning("yfinance download failed: %s", e)
            return 0

        if df is None or df.empty:
            log.warning("yfinance returned empty dataframe for %s", YF_TICKER)
            return 0

        # yfinance returns columns either as a flat Index ['Open','High',...]
        # or as a 2-level MultiIndex when threads is True / multi-ticker.
        # Flatten if needed.
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = [c[0] for c in df.columns]

        with get_session() as session:
            contract = upsert_contract(
                session,
                exchange=CONTINUOUS_EXCHANGE,
                symbol=CONTINUOUS_SYMBOL,
                contract_month="Continuous",
            )
            for ts, row in df.iterrows():
                bar_date = ts.date() if hasattr(ts, "date") else ts
                close = _to_float(row.get("Close"))
                if close is None:
                    continue
                existing = session.exec(
                    select(QuoteEod).where(
                        QuoteEod.contract_id == contract.id,
                        QuoteEod.date == bar_date,
                    )
                ).first()
                target = existing or QuoteEod(contract_id=contract.id, date=bar_date)
                target.open = _to_float(row.get("Open"))
                target.high = _to_float(row.get("High"))
                target.low = _to_float(row.get("Low"))
                target.settle = close
                target.volume = _to_int(row.get("Volume"))
                target.source = "yfinance"
                session.add(target)
                handle.rows_written += 1
        log.info("yfinance backfill: %d rows written", handle.rows_written)
        return handle.rows_written


def backfill_if_empty() -> int:
    """Run backfill only if QuoteEod has no rows for the continuous contract.

    Called on startup from scheduler.start(). Returns rows written (0 if a
    backfill already exists).
    """
    with get_session() as session:
        from app.storage.models import Contract  # local import to avoid cycle

        contract = session.exec(
            select(Contract).where(Contract.symbol == CONTINUOUS_SYMBOL)
        ).first()
        if contract is not None:
            existing_count = len(session.exec(
                select(QuoteEod).where(QuoteEod.contract_id == contract.id).limit(1)
            ).all())
            if existing_count > 0:
                log.info("yfinance backfill already populated, skipping")
                return 0
    return run()
