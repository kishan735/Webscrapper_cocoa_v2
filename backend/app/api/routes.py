from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlmodel import select

from app.scrapers import cftc, ice, investing, yfinance_backfill
from app.scrapers.yfinance_backfill import CONTINUOUS_SYMBOL, CONTINUOUS_LABEL
from app.services import curve as curve_service
from app.services.resample import resample_ohlc
from app.storage.db import get_session
from app.storage.models import Contract, CotPositioning, QuoteEod, ScrapeLog

router = APIRouter(prefix="/api")

ACTIVE_SCRAPE_SOURCES = {"investing.intraday", "ice.eod", "cftc.cot"}


@router.get("/curve")
def get_curve() -> Dict[str, Any]:
    rows = curve_service.snapshot()
    return {"as_of": datetime.utcnow().isoformat(), "rows": rows}


@router.get("/contracts")
def get_contracts() -> List[Dict[str, Any]]:
    with get_session() as session:
        contracts = session.exec(
            select(Contract)
            .where(Contract.active == True)  # noqa: E712
            .where(Contract.exchange == "ICE_LIFFE")
            .where(~Contract.symbol.like("%-CONTINUOUS"))
            .where(~Contract.symbol.like("LCCc%"))
        ).all()
        contracts = sorted(contracts, key=lambda c: curve_service.sort_key(c.contract_month))
        return [
            {
                "symbol": c.symbol,
                "contract_month": c.contract_month,
                "expiry": c.expiry_date.isoformat() if c.expiry_date else None,
            }
            for c in contracts
        ]


@router.get("/contract/{symbol}/history")
def get_contract_history(
    symbol: str,
    limit: int = 730,
    tf: str = "D",
    series: str = "this",
) -> Dict[str, Any]:
    tf_upper = tf.upper()
    series_lower = series.lower()
    if tf_upper not in ("D", "W", "M"):
        raise HTTPException(400, "tf must be one of D, W, M")
    if series_lower not in ("this", "continuous"):
        raise HTTPException(400, "series must be one of this, continuous")

    with get_session() as session:
        contract = session.exec(select(Contract).where(Contract.symbol == symbol)).first()
        if not contract:
            raise HTTPException(404, f"unknown contract {symbol}")

        if series_lower == "continuous":
            data_contract = session.exec(
                select(Contract).where(Contract.symbol == CONTINUOUS_SYMBOL)
            ).first()
            if data_contract is None:
                return {
                    "symbol": contract.symbol,
                    "contract_month": contract.contract_month,
                    "series": series_lower,
                    "series_label": CONTINUOUS_LABEL,
                    "tf": tf_upper,
                    "ohlc": [],
                    "note": "Continuous series not backfilled yet. POST /api/admin/run/backfill.",
                }
            series_label = CONTINUOUS_LABEL
        else:
            data_contract = contract
            series_label = contract.contract_month

        rows = session.exec(
            select(QuoteEod)
            .where(QuoteEod.contract_id == data_contract.id)
            .order_by(QuoteEod.date.asc())
        ).all()

        ohlc = resample_ohlc(rows, tf_upper)
        if tf_upper == "D" and limit and len(ohlc) > limit:
            ohlc = ohlc[-limit:]

        note: Optional[str] = None
        if series_lower == "this" and len(ohlc) < 2:
            note = "Selected contract has < 2 observations. Switch to 'continuous' for historical context."

        return {
            "symbol": contract.symbol,
            "contract_month": contract.contract_month,
            "series": series_lower,
            "series_label": series_label,
            "tf": tf_upper,
            "ohlc": ohlc,
            "note": note,
        }


@router.get("/positioning")
def get_positioning(limit: int = 52) -> Dict[str, Any]:
    with get_session() as session:
        rows = session.exec(
            select(CotPositioning).order_by(CotPositioning.report_date.desc()).limit(limit)
        ).all()
        return {
            "rows": [
                {
                    "report_date": r.report_date.isoformat(),
                    "market": r.market,
                    "commercial_long": r.commercial_long,
                    "commercial_short": r.commercial_short,
                    "mm_long": r.mm_long,
                    "mm_short": r.mm_short,
                    "other_long": r.other_long,
                    "other_short": r.other_short,
                    "nonreportable_long": r.nonreportable_long,
                    "nonreportable_short": r.nonreportable_short,
                    "open_interest_all": r.open_interest_all,
                }
                for r in reversed(rows)
            ]
        }


_CSV_COLUMNS = [
    "report_date",
    "market",
    "commercial_long",
    "commercial_short",
    "mm_long",
    "mm_short",
    "other_long",
    "other_short",
    "nonreportable_long",
    "nonreportable_short",
    "open_interest_all",
]


@router.get("/positioning.csv")
def get_positioning_csv() -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_COLUMNS)
    with get_session() as session:
        rows = session.exec(
            select(CotPositioning).order_by(CotPositioning.report_date.desc())
        ).all()
        for r in rows:
            writer.writerow([
                r.report_date.isoformat(),
                r.market,
                r.commercial_long,
                r.commercial_short,
                r.mm_long,
                r.mm_short,
                r.other_long,
                r.other_short,
                r.nonreportable_long,
                r.nonreportable_short,
                r.open_interest_all,
            ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cocoa-cftc.csv"'},
    )


@router.get("/health")
def get_health() -> Dict[str, Any]:
    with get_session() as session:
        recent = session.exec(
            select(ScrapeLog)
            .where(ScrapeLog.source.in_(ACTIVE_SCRAPE_SOURCES))
            .order_by(ScrapeLog.started_at.desc())
            .limit(20)
        ).all()
        by_source: Dict[str, Dict[str, Any]] = {}
        for log_row in recent:
            if log_row.source in by_source:
                continue
            by_source[log_row.source] = {
                "started_at": log_row.started_at.isoformat(),
                "finished_at": log_row.finished_at.isoformat() if log_row.finished_at else None,
                "status": log_row.status,
                "rows_written": log_row.rows_written,
                "error": log_row.error,
            }
        return {"ok": True, "sources": by_source}


@router.post("/admin/run/{source}")
def admin_run(source: str) -> Dict[str, Any]:
    """Trigger a scrape immediately. For local debugging only."""
    runners = {
        "intraday": investing.run,
        "ice": ice.run,
        "cftc": cftc.run,
        "backfill": yfinance_backfill.run,
    }
    runner = runners.get(source)
    if not runner:
        raise HTTPException(404, f"unknown source {source}; choose from {list(runners)}")
    rows = runner()
    return {"source": source, "rows_written": rows}
