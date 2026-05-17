"""Investing.com — London Cocoa intraday scraper.

Source page: https://www.investing.com/commodities/london-cocoa
(The historical /london-cocoa-contracts URL now 302s to the overview page and
no longer renders a separate contracts table.)

Selectors: the page is a Next.js app and embeds its full server state in a
``<script id="__NEXT_DATA__">`` blob. That blob is the only stable selector
across DOM redesigns — the visible markup changes every few weeks, the JSON
shape does not. We extract:

  - props.pageProps.state.commodityStore.instrument.price   (front-month rich fields)
  - props.pageProps.state.commodityStore.instrument.relatives.relatives[]  (LCCc1..LCCc6 + LCC1!)
  - props.pageProps.state.commodityStore.keyMetrics         (front-month label + trading_months)

Contract month labels are derived by combining ``keyMetrics.month`` (front-month
label, e.g. ``"May 25"``) with ``keyMetrics.trading_months`` (e.g. ``"HKNUZ"`` =
Mar/May/Jul/Sep/Dec) and the LCCcN index — Investing.com only spells out the
front month, the rest are relative.
"""
from __future__ import annotations

import json
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
    open: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    open_interest: Optional[int]


_MONTH_RE = re.compile(r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(?P<yr>\d{2,4})", re.I)

_MONTH_CODE_TO_NAME = {
    "F": "Jan", "G": "Feb", "H": "Mar", "J": "Apr", "K": "May", "M": "Jun",
    "N": "Jul", "Q": "Aug", "U": "Sep", "V": "Oct", "X": "Nov", "Z": "Dec",
}
_NAME_TO_CODE = {v: k for k, v in _MONTH_CODE_TO_NAME.items()}


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s in {"-", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v) -> Optional[int]:
    f = _to_float(v)
    return int(f) if f is not None else None


def _normalize_year(yr: str) -> int:
    return int("20" + yr) if len(yr) == 2 else int(yr)


def _front_month_components(front_label: str) -> Optional[tuple[str, int]]:
    m = _MONTH_RE.search(front_label or "")
    if not m:
        return None
    return m.group("mon").title(), _normalize_year(m.group("yr"))


def _derive_contract_month(front_label: str, trading_months: str, offset: int) -> str:
    """Roll forward `offset` positions through `trading_months` (e.g. 'HKNUZ').

    Returns ``"Mon YYYY"``. Falls back to the raw front label if it can't parse.
    """
    parts = _front_month_components(front_label)
    if not parts or not trading_months:
        return (front_label or "").strip()
    name, year = parts
    front_code = _NAME_TO_CODE.get(name)
    codes = [c for c in trading_months if c in _MONTH_CODE_TO_NAME]
    if not front_code or front_code not in codes:
        return f"{name} {year}"
    idx = codes.index(front_code)
    rolled = idx + offset
    target_code = codes[rolled % len(codes)]
    target_year = year + rolled // len(codes)
    return f"{_MONTH_CODE_TO_NAME[target_code]} {target_year}"


def _extract_next_data(html: str) -> Optional[dict]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        log.warning("__NEXT_DATA__ JSON did not decode")
        return None


def parse_investing_html(html: str) -> List[IntradayRow]:
    """Parse Investing.com London Cocoa HTML into IntradayRow per contract.

    Returns rows for LCCc1..LCCcN; the continuous symbol (``LCC1!``) is
    excluded because it is just a duplicate of LCCc1 with no incremental info.
    """
    data = _extract_next_data(html)
    if not data:
        return []
    try:
        store = data["props"]["pageProps"]["state"]["commodityStore"]
    except (KeyError, TypeError):
        return []
    price = store.get("instrument", {}).get("price", {}) or {}
    relatives = store.get("instrument", {}).get("relatives", {}).get("relatives", []) or []
    metrics = store.get("keyMetrics", {}) or {}

    front_label = metrics.get("month", "")
    trading_months = metrics.get("trading_months", "")
    front_oi = _to_int(metrics.get("open_interest"))

    rows: List[IntradayRow] = []
    front_seen = False
    for i, r in enumerate(relatives):
        symbol = (r.get("symbol") or "").strip()
        if not symbol or "!" in symbol:
            continue
        is_front = symbol.endswith("c1") and not front_seen
        contract_month = _derive_contract_month(front_label, trading_months, i)
        if is_front:
            front_seen = True
            rows.append(IntradayRow(
                symbol=symbol,
                contract_month=contract_month,
                last=_to_float(price.get("last") or r.get("last")),
                high=_to_float(price.get("high")),
                low=_to_float(price.get("low")),
                open=_to_float(price.get("open")),
                change=_to_float(price.get("change")),
                change_pct=_to_float(price.get("changePcr") or r.get("changeOneDayPercent")),
                volume=_to_int(price.get("volume") or r.get("volumeOneDay")),
                open_interest=front_oi,
            ))
            continue
        pct = _to_float(r.get("changeOneDayPercent"))
        last = _to_float(r.get("last"))
        change = round(last * pct / 100.0, 4) if (last is not None and pct is not None) else None
        rows.append(IntradayRow(
            symbol=symbol,
            contract_month=contract_month,
            last=last,
            high=None,
            low=None,
            open=None,
            change=change,
            change_pct=pct,
            volume=_to_int(r.get("volumeOneDay")),
            open_interest=None,
        ))
    return rows


def fetch_contract_rows() -> List[IntradayRow]:
    """Fetch and parse the Investing.com page. Empty list on failure."""
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError as e:
        # The legacy message said "scrapling not installed" which was wrong
        # when scrapling was installed but a sub-dependency (patchright,
        # playwright browsers) was missing. Surface the real cause.
        log.error(
            "scrapling.fetchers import failed: %s. Try: "
            "pip install 'scrapling[fetchers]' && scrapling install",
            e,
        )
        return []

    fetcher = StealthyFetcher(auto_match=True)
    try:
        response = fetcher.fetch(
            settings.london_cocoa_investing_url,
            headless=True,
            network_idle=True,
            timeout=60000,
        )
    except Exception as e:
        log.warning("investing.com fetch failed: %s", e)
        return []
    if response.status != 200:
        log.warning("investing.com returned status %s", response.status)
        return []
    return parse_investing_html(response.html_content)


def run() -> int:
    """Fetch intraday quotes from Investing.com and persist them."""
    with scrape_run("investing.intraday") as handle:
        rows = fetch_contract_rows()
        if not rows:
            log.warning("intraday: fetch returned 0 parseable rows (page format may have changed or browser not installed)")
            return 0
        log.info("intraday: %d rows fetched, persisting…", len(rows))
        ts = datetime.utcnow()
        with get_session() as session:
            for r in rows:
                if not r.symbol or not r.contract_month:
                    log.debug("intraday: skipping row with empty symbol/month: %r", r)
                    continue
                contract = upsert_contract(
                    session,
                    exchange="ICE_LIFFE",
                    symbol=r.symbol,
                    contract_month=r.contract_month,
                )
                assert contract.id is not None, f"upsert_contract returned a row without id: {contract!r}"
                session.add(QuoteIntraday(
                    contract_id=contract.id,
                    ts=ts,
                    last=r.last,
                    volume_session=r.volume,
                    change=r.change,
                    change_pct=r.change_pct,
                ))
                handle.rows_written += 1
            session.flush()  # surface any IntegrityError before the context manager commits silently
        log.info("intraday scrape: %d rows persisted (fetched %d)", handle.rows_written, len(rows))
        return handle.rows_written
