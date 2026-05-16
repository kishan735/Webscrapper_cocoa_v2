"""ICE end-of-day scraper for ICE Futures Europe Cocoa No.7 (London Cocoa, 'C').

Source:
    https://www.ice.com/products/37089076/London-Cocoa-Futures/data

The legacy ``theice.com/marketdata/reports/180`` endpoint (and its CSV cousin)
now 404 — ICE rebranded ``theice.com`` to ``ice.com`` and rebuilt the report
center as a JS SPA whose data only loads after a form submission to
``/api/sites/ice/proxy``. The product spec ``/data`` page, however, still
renders a server-side HTML table with one row per listed contract
(`Contract`, `Last`, `Time(GMT)`, `% Change`, `Volume`). That's what we parse.

Open interest is no longer published per-contract on any free public ICE page
without the SPA dance, so this scraper records the curve without OI. The
front-month OI is recovered from Investing.com's keyMetrics in the
intraday scraper and merged into ``QuoteEod.open_interest`` at curve-build time.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlmodel import select

from app.config import settings
from app.scrapers._base import scrape_run
from app.scrapers.contracts import upsert_contract
from app.storage.db import get_session
from app.storage.models import QuoteEod

log = logging.getLogger(__name__)


@dataclass
class EodRow:
    contract_month: str  # e.g. "Jul 2026"
    symbol: str          # e.g. "JUL2026" (used as Contract.symbol)
    settle: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    open_interest: Optional[int]
    as_of: Optional[date]


_MONTH_CODE = {
    "JAN": "Jan", "FEB": "Feb", "MAR": "Mar", "APR": "Apr", "MAY": "May", "JUN": "Jun",
    "JUL": "Jul", "AUG": "Aug", "SEP": "Sep", "OCT": "Oct", "NOV": "Nov", "DEC": "Dec",
}
_MONTH_SHORT_RE = re.compile(r"^(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?P<yr>\d{2})$", re.I)


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s in {"-", "N/A", "."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v) -> Optional[int]:
    f = _to_float(v)
    return int(f) if f is not None else None


def _normalize_contract_month(short: str) -> Optional[str]:
    """``Jul26`` -> ``Jul 2026``. Returns None if no match."""
    m = _MONTH_SHORT_RE.match(short.strip())
    if not m:
        return None
    return f"{_MONTH_CODE[m.group('mon').upper()]} 20{m.group('yr')}"


_TIME_CELL_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _parse_as_of(time_cell_text: str) -> Optional[date]:
    """Extract trade date from ICE's Time(GMT) cell which embeds 'M/D/YYYY h:MM AM/PM'."""
    m = _TIME_CELL_DATE_RE.search(time_cell_text or "")
    if not m:
        return None
    mo, dy, yr = (int(x) for x in m.groups())
    try:
        return date(yr, mo, dy)
    except ValueError:
        return None


_CELL_RE = re.compile(r"<t[dh][^>]*>(?P<inner>.*?)</t[dh]>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip(html_fragment: str) -> str:
    txt = _TAG_RE.sub(" ", html_fragment)
    return re.sub(r"\s+", " ", txt).strip()


def parse_ice_data_html(html: str) -> List[EodRow]:
    """Extract contract rows from the ICE London Cocoa Futures data page HTML."""
    table_match = re.search(r"<table[^>]*>(.*?)</table>", html, re.S)
    if not table_match:
        return []
    table = table_match.group(0)
    rows: List[EodRow] = []
    for tr in re.finditer(r"<tr[^>]*>(?P<body>.*?)</tr>", table, re.S):
        cells = [_strip(m.group("inner")) for m in _CELL_RE.finditer(tr.group("body"))]
        if not cells:
            continue
        contract_month = _normalize_contract_month(cells[0]) if cells[0] else None
        if not contract_month:
            continue
        if len(cells) < 5:
            continue
        last = _to_float(cells[1])
        time_cell = cells[2] if len(cells) > 2 else ""
        change_pct = _to_float(cells[3])
        volume = _to_int(cells[4])
        if last is None and volume is None:
            continue
        change = round(last * change_pct / 100.0, 4) if (last is not None and change_pct is not None) else None
        symbol = re.sub(r"\s+", "", contract_month).upper()
        rows.append(EodRow(
            contract_month=contract_month,
            symbol=symbol,
            settle=last,
            change=change,
            change_pct=change_pct,
            volume=volume,
            open_interest=None,
            as_of=_parse_as_of(time_cell),
        ))
    return rows


def fetch_eod_rows() -> List[EodRow]:
    """Fetch and parse the ICE London Cocoa Futures data page."""
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError:
        log.error("scrapling not installed; ICE EOD scrape skipped")
        return []

    fetcher = StealthyFetcher(auto_match=True)
    try:
        response = fetcher.fetch(
            settings.ice_london_cocoa_data_url,
            headless=True,
            network_idle=True,
            timeout=60000,
        )
    except Exception as e:
        log.warning("ICE data page fetch failed: %s", e)
        return []
    if response.status != 200:
        log.warning("ICE data page returned status %s", response.status)
        return []
    return parse_ice_data_html(response.html_content)


def _last_business_day(today: Optional[date] = None) -> date:
    d = today or date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def run(for_date: Optional[date] = None) -> int:
    """Persist the latest curve from ICE into ``QuoteEod``.

    The ICE /data page always renders the most recent trading day's prices,
    so ``for_date`` only overrides the row date stamp; on weekends/holidays
    we still get the last trading day's data automatically.
    """
    with scrape_run("ice.eod") as handle:
        rows = fetch_eod_rows()
        if not rows:
            log.warning("ICE data page returned 0 parseable rows")
            return 0
        target = for_date or rows[0].as_of or _last_business_day()
        with get_session() as session:
            for r in rows:
                if not r.symbol or not r.contract_month:
                    continue
                contract = upsert_contract(
                    session,
                    exchange="ICE_LIFFE",
                    symbol=r.symbol,
                    contract_month=r.contract_month,
                )
                existing = session.exec(
                    select(QuoteEod).where(
                        QuoteEod.contract_id == contract.id,
                        QuoteEod.date == target,
                    )
                ).first()
                row = existing or QuoteEod(contract_id=contract.id, date=target)
                row.settle = r.settle
                row.volume = r.volume
                if r.open_interest is not None:
                    row.open_interest = r.open_interest
                row.source = "ice"
                session.add(row)
                handle.rows_written += 1
        log.info("ICE EOD for %s: %d rows", target, handle.rows_written)
        return handle.rows_written
