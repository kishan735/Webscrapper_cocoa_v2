from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

from sqlmodel import select

from app.storage.db import get_session
from app.storage.models import ScrapeLog


@dataclass
class RunHandle:
    log_id: int
    rows_written: int = 0


@contextmanager
def scrape_run(source: str) -> Iterator[RunHandle]:
    """Record one scrape attempt in scrape_log.

    Callers can update handle.rows_written; on exit we persist
    finished_at / status / error / rows_written.
    """
    with get_session() as session:
        row = ScrapeLog(source=source)
        session.add(row)
        session.flush()
        log_id = row.id
        assert log_id is not None

    handle = RunHandle(log_id=log_id)
    error: Optional[str] = None
    try:
        yield handle
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        with get_session() as session:
            row = session.exec(select(ScrapeLog).where(ScrapeLog.id == log_id)).one()
            row.finished_at = datetime.utcnow()
            row.status = "error" if error else "ok"
            row.error = error
            row.rows_written = handle.rows_written
            session.add(row)
