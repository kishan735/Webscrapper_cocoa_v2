"""Assemble the forward-curve snapshot.

Combines the latest intraday quote (if any) with the most recent EOD row for
each active contract, producing one row per contract month with last, settle,
change, volume, and open interest.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import select

from app.storage.db import get_session
from app.storage.models import Contract, QuoteEod, QuoteIntraday


def _latest_intraday(session, contract_id: int) -> Optional[QuoteIntraday]:
    return session.exec(
        select(QuoteIntraday)
        .where(QuoteIntraday.contract_id == contract_id)
        .order_by(QuoteIntraday.ts.desc())
        .limit(1)
    ).first()


def _latest_eod(session, contract_id: int) -> Optional[QuoteEod]:
    return session.exec(
        select(QuoteEod)
        .where(QuoteEod.contract_id == contract_id)
        .order_by(QuoteEod.date.desc())
        .limit(1)
    ).first()


def _prev_eod(session, contract_id: int) -> Optional[QuoteEod]:
    rows = session.exec(
        select(QuoteEod)
        .where(QuoteEod.contract_id == contract_id)
        .order_by(QuoteEod.date.desc())
        .limit(2)
    ).all()
    return rows[1] if len(rows) >= 2 else None


def snapshot() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with get_session() as session:
        contracts = session.exec(
            select(Contract).where(Contract.active == True).order_by(Contract.contract_month)  # noqa: E712
        ).all()
        for c in contracts:
            intra = _latest_intraday(session, c.id)
            eod = _latest_eod(session, c.id)
            prev_eod = _prev_eod(session, c.id)

            last = intra.last if intra and intra.last is not None else (eod.settle if eod else None)
            settle = eod.settle if eod else None
            change = None
            change_pct = None
            if eod and prev_eod and eod.settle is not None and prev_eod.settle:
                change = round(eod.settle - prev_eod.settle, 4)
                change_pct = round((change / prev_eod.settle) * 100, 4)
            elif intra and intra.change is not None:
                change = intra.change
                change_pct = intra.change_pct

            updated = None
            if intra:
                updated = intra.ts
            elif eod:
                updated = datetime.combine(eod.date, datetime.min.time())

            out.append({
                "symbol": c.symbol,
                "contract_month": c.contract_month,
                "expiry": c.expiry_date.isoformat() if c.expiry_date else None,
                "last": last,
                "settle": settle,
                "change": change,
                "change_pct": change_pct,
                "volume": eod.volume if eod else (intra.volume_session if intra else None),
                "open_interest": eod.open_interest if eod else None,
                "updated_at": updated.isoformat() if updated else None,
            })
    return out
