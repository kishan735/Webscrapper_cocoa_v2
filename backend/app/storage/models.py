from datetime import date as _date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class Contract(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_contract_symbol"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    exchange: str
    symbol: str
    contract_month: str
    expiry_date: Optional[_date] = None
    active: bool = True
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class QuoteIntraday(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: int = Field(foreign_key="contract.id", index=True)
    ts: datetime = Field(index=True)
    last: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_session: Optional[int] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None


class QuoteEod(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("contract_id", "date", name="uq_eod_contract_date"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: int = Field(foreign_key="contract.id", index=True)
    date: _date = Field(index=True)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    settle: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    source: str = "ice"


class CotPositioning(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("report_date", "market", name="uq_cot_report"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    report_date: _date = Field(index=True)
    market: str = Field(index=True)
    commercial_long: Optional[int] = None
    commercial_short: Optional[int] = None
    mm_long: Optional[int] = None
    mm_short: Optional[int] = None
    other_long: Optional[int] = None
    other_short: Optional[int] = None
    nonreportable_long: Optional[int] = None
    nonreportable_short: Optional[int] = None
    open_interest_all: Optional[int] = None


class ScrapeLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    status: str = "running"
    rows_written: int = 0
    error: Optional[str] = None


class AiCache(SQLModel, table=True):
    input_hash: str = Field(primary_key=True)
    output_json: str
    model: str
    prompt_version: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
