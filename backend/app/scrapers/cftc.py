"""CFTC Commitments of Traders — weekly positioning for cocoa.

Public Socrata REST API. No key required (rate-limited unbounded for low
volume). Disaggregated Futures-Only report (dataset id: 72hh-3qpy).

The legacy dataset (jun7-fc8e) only carried combined commercial / non-
commercial / nonreportable columns, so m_money / other_rept were always
null. Switched to the disaggregated dataset which breaks "commercial" into
producer/merchant + swap dealers and exposes managed money + other
reportables separately. We sum producer/merchant + swap dealers back into
the existing commercial_long/short columns to keep the schema stable.

We pull all rows whose market name matches the configured cocoa market
(default 'COCOA - ICE FUTURES U.S.'). The market name is configurable via
settings so we can switch between Liffe London cocoa and ICE US cocoa
without code changes.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import List, Optional

import httpx
from sqlmodel import select

from app.config import settings
from app.scrapers._base import scrape_run
from app.storage.db import get_session
from app.storage.models import CotPositioning

log = logging.getLogger(__name__)


def _to_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _sum_opt(a: Optional[int], b: Optional[int]) -> Optional[int]:
    """Sum two optional ints, returning None only if both are None."""
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


def _parse_report_date(s: str) -> Optional[date]:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fetch_cot(limit: int = 200) -> List[dict]:
    """Fetch recent COT rows for the configured cocoa market."""
    params = {
        "$where": f"market_and_exchange_names = '{settings.cftc_london_cocoa_market_name}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": str(limit),
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(settings.cftc_socrata_endpoint, params=params)
        if r.status_code != 200:
            log.warning("CFTC API non-200: %s", r.status_code)
            return []
        return r.json()
    except httpx.HTTPError as e:
        log.warning("CFTC API fetch failed: %s", e)
        return []


def run(limit: int = 200) -> int:
    with scrape_run("cftc.cot") as handle:
        rows = fetch_cot(limit=limit)
        if not rows:
            return 0
        market = settings.cftc_london_cocoa_market_name
        with get_session() as session:
            for raw in rows:
                report_date = _parse_report_date(raw.get("report_date_as_yyyy_mm_dd") or "")
                if not report_date:
                    continue
                existing = session.exec(
                    select(CotPositioning).where(
                        CotPositioning.report_date == report_date,
                        CotPositioning.market == market,
                    )
                ).first()
                target = existing or CotPositioning(report_date=report_date, market=market)
                # Disaggregated dataset splits the legacy "commercial" bucket
                # into producer/merchant (PROD_MERC) + swap dealers (SWAP).
                # Sum them back into commercial_long/short so the existing
                # schema and chart series stay stable.
                prod_long = _to_int(raw.get("prod_merc_positions_long"))
                swap_long = _to_int(raw.get("swap_positions_long_all"))
                prod_short = _to_int(raw.get("prod_merc_positions_short"))
                # NOTE: the disaggregated dataset stores swap_short under a
                # field with a double underscore ('swap__positions_short_all').
                swap_short = _to_int(raw.get("swap__positions_short_all"))
                target.commercial_long = _sum_opt(prod_long, swap_long)
                target.commercial_short = _sum_opt(prod_short, swap_short)
                target.mm_long = _to_int(raw.get("m_money_positions_long_all"))
                target.mm_short = _to_int(raw.get("m_money_positions_short_all"))
                target.other_long = _to_int(raw.get("other_rept_positions_long"))
                target.other_short = _to_int(raw.get("other_rept_positions_short"))
                target.nonreportable_long = _to_int(raw.get("nonrept_positions_long_all"))
                target.nonreportable_short = _to_int(raw.get("nonrept_positions_short_all"))
                target.open_interest_all = _to_int(raw.get("open_interest_all"))
                session.add(target)
                handle.rows_written += 1
        log.info("CFTC COT: %d rows", handle.rows_written)
        return handle.rows_written
