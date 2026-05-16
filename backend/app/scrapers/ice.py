"""ICE end-of-day settlement scraper for London Cocoa (futures code 'C').

The ICE Report Center publishes a daily CSV per product with settle / volume /
open-interest per contract month. Public, no key needed.

The exact CSV URL pattern needs verification against a live request — ICE
periodically renames endpoints. The function `download_eod_csv` is structured
so the URL builder can be tweaked in one place.

For the first build pass we accept two strategies:
  1. Direct CSV download via httpx if the endpoint responds 200.
  2. Fallback: skip and log; intraday + yfinance still populate the DB.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

import httpx
from sqlmodel import select

from app.config import settings
from app.scrapers._base import scrape_run
from app.scrapers.contracts import upsert_contract
from app.storage.db import get_session
from app.storage.models import QuoteEod

log = logging.getLogger(__name__)


@dataclass
class EodRow:
    contract_month: str
    symbol: str
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    settle: Optional[float]
    volume: Optional[int]
    open_interest: Optional[int]


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if not s or s in {"-", "N/A", "."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v) -> Optional[int]:
    f = _to_float(v)
    return int(f) if f is not None else None


_MONTH_RE = re.compile(r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(?P<yr>\d{2,4})", re.I)


def _normalize_contract_month(text: str) -> str:
    if not text:
        return ""
    m = _MONTH_RE.search(text)
    if not m:
        return text.strip()
    yr = m.group("yr")
    if len(yr) == 2:
        yr = "20" + yr
    return f"{m.group('mon').title()} {yr}"


def _build_csv_url(for_date: date) -> str:
    """ICE Report Center CSV for London Cocoa daily settlement.

    Report id 180 = ICE Futures Europe end-of-day. Adjust if needed.
    """
    base = settings.ice_eod_report_base.rstrip("/")
    return f"{base}?selectionForm=&selectionDate={for_date.strftime('%m/%d/%Y')}&productCode=C&csv=true"


def download_eod_csv(for_date: Optional[date] = None) -> Optional[str]:
    target = for_date or _last_business_day()
    url = _build_csv_url(target)
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.text.strip():
            log.warning("ICE CSV non-200: %s url=%s", r.status_code, url)
            return None
        if "<html" in r.text[:200].lower():
            log.warning("ICE CSV returned HTML (likely auth wall) url=%s", url)
            return None
        return r.text
    except httpx.HTTPError as e:
        log.warning("ICE CSV fetch failed: %s", e)
        return None


def _last_business_day() -> date:
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def parse_csv(csv_text: str) -> List[EodRow]:
    rows: List[EodRow] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for raw in reader:
        norm = {k.strip().lower().replace(" ", "_"): v for k, v in raw.items() if k}
        month = (
            norm.get("contract")
            or norm.get("strip")
            or norm.get("month")
            or norm.get("contract_month")
            or ""
        )
        contract_month = _normalize_contract_month(month)
        if not contract_month:
            continue
        symbol = re.sub(r"\s+", "", contract_month).upper()
        rows.append(
            EodRow(
                contract_month=contract_month,
                symbol=symbol,
                open=_to_float(norm.get("open") or norm.get("op_int_(open)")),
                high=_to_float(norm.get("high")),
                low=_to_float(norm.get("low")),
                settle=_to_float(norm.get("settle") or norm.get("settlement_price")),
                volume=_to_int(norm.get("volume") or norm.get("tot_vol")),
                open_interest=_to_int(
                    norm.get("open_interest") or norm.get("op_int") or norm.get("oi")
                ),
            )
        )
    return rows


def run(for_date: Optional[date] = None) -> int:
    target = for_date or _last_business_day()
    with scrape_run("ice.eod") as handle:
        csv_text = download_eod_csv(target)
        if not csv_text:
            return 0
        rows = parse_csv(csv_text)
        if not rows:
            log.warning("ICE CSV parsed to 0 rows for %s", target)
            return 0
        with get_session() as session:
            for r in rows:
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
                row.open = r.open
                row.high = r.high
                row.low = r.low
                row.settle = r.settle
                row.volume = r.volume
                row.open_interest = r.open_interest
                row.source = "ice"
                session.add(row)
                handle.rows_written += 1
        log.info("ICE EOD for %s: %d rows", target, handle.rows_written)
        return handle.rows_written
