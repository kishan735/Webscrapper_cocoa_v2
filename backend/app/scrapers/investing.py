"""Investing.com — London Cocoa contracts table scraper.

Source page: https://www.investing.com/commodities/london-cocoa-contracts

Renders a table of all listed contract months with last/high/low/change/volume.
Open interest is not on this page — for OI we rely on the daily ICE EOD report
and the CFTC COT weekly release.

We use Scrapling's StealthyFetcher (Camoufox) to bypass the page's anti-bot
front. Selectors are kept loose because Investing.com changes its DOM
frequently — adjust during the first live run.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.config import settings
from app.scrapers._base import scrape_run
from app.scrapers.contracts import upsert_contract
from app.storage.db import get_session
from app.storage.models import QuoteIntraday

log = logging.getLogger(__name__)


@dataclass
class IntradayRow:
    symbol: str
    contract_month: str
    last: Optional[float]
    high: Optional[float]
    low: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    expiry_text: Optional[str]


def _parse_number(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    s = s.strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s in {"-", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(s: Optional[str]) -> Optional[int]:
    n = _parse_number(s)
    return int(n) if n is not None else None


_MONTH_RE = re.compile(r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(?P<yr>\d{2,4})", re.I)


def _normalize_contract_month(text: str) -> str:
    """Turn 'London Cocoa May 25' or 'C May 2025' into 'May 2025'."""
    m = _MONTH_RE.search(text or "")
    if not m:
        return text.strip()
    yr = m.group("yr")
    if len(yr) == 2:
        yr = "20" + yr
    return f"{m.group('mon').title()} {yr}"


def fetch_contract_rows() -> List[IntradayRow]:
    """Scrape the Investing.com contracts table.

    Returns a list of IntradayRow. Empty list on any failure (logged).
    """
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError:
        log.error("scrapling not installed; intraday scrape skipped")
        return []

    fetcher = StealthyFetcher(auto_match=True)
    response = fetcher.fetch(settings.london_cocoa_investing_url, headless=True, network_idle=True)
    if response.status != 200:
        log.warning("investing.com returned status %s", response.status)
        return []

    rows: List[IntradayRow] = []
    # Investing.com's contracts table uses a tbody with one tr per contract.
    # Columns (historically): Month | Last | High | Low | Chg. | Chg.% | Volume | Time
    for tr in response.css("table tbody tr"):
        tds = tr.css("td")
        if len(tds) < 6:
            continue
        cells = [td.text.clean() for td in tds]
        month_text = cells[0]
        contract_month = _normalize_contract_month(month_text)
        symbol = re.sub(r"\s+", "", contract_month).upper()  # e.g. MAY2025
        rows.append(
            IntradayRow(
                symbol=symbol,
                contract_month=contract_month,
                last=_parse_number(cells[1] if len(cells) > 1 else None),
                high=_parse_number(cells[2] if len(cells) > 2 else None),
                low=_parse_number(cells[3] if len(cells) > 3 else None),
                change=_parse_number(cells[4] if len(cells) > 4 else None),
                change_pct=_parse_number(cells[5] if len(cells) > 5 else None),
                volume=_parse_int(cells[6] if len(cells) > 6 else None),
                expiry_text=None,
            )
        )
    return rows


def run() -> int:
    """Fetch the Investing.com contracts table and persist intraday quotes.

    Returns the number of rows written.
    """
    with scrape_run("investing.intraday") as handle:
        rows = fetch_contract_rows()
        if not rows:
            return 0
        ts = datetime.utcnow()
        with get_session() as session:
            for r in rows:
                contract = upsert_contract(
                    session,
                    exchange="ICE_LIFFE",
                    symbol=r.symbol,
                    contract_month=r.contract_month,
                )
                session.add(
                    QuoteIntraday(
                        contract_id=contract.id,
                        ts=ts,
                        last=r.last,
                        volume_session=r.volume,
                        change=r.change,
                        change_pct=r.change_pct,
                    )
                )
                handle.rows_written += 1
        log.info("intraday scrape: %d rows", handle.rows_written)
        return handle.rows_written
