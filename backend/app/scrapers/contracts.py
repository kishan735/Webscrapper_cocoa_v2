"""Helpers for upserting Contract rows."""
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.storage.models import Contract


MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}


def upsert_contract(
    session: Session,
    exchange: str,
    symbol: str,
    contract_month: str,
    expiry_date: Optional[datetime] = None,
) -> Contract:
    existing = session.exec(
        select(Contract).where(Contract.exchange == exchange, Contract.symbol == symbol)
    ).first()
    now = datetime.utcnow()
    if existing:
        existing.last_seen = now
        existing.active = True
        if expiry_date and not existing.expiry_date:
            existing.expiry_date = expiry_date.date() if hasattr(expiry_date, "date") else expiry_date
        session.add(existing)
        return existing

    contract = Contract(
        exchange=exchange,
        symbol=symbol,
        contract_month=contract_month,
        expiry_date=expiry_date.date() if expiry_date and hasattr(expiry_date, "date") else expiry_date,
        active=True,
        first_seen=now,
        last_seen=now,
    )
    session.add(contract)
    session.flush()
    return contract
