"""APScheduler jobs for Phase 1.

- Intraday quotes: every N minutes during London session
- ICE EOD report: ~19:30 London on weekdays
- CFTC COT: Fridays 21:00 London (CFTC publishes ~15:30 ET Friday)
- Backfill: once at startup, if EOD table is empty
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import select

from app.config import settings
from app.scrapers import cftc, ice, investing, yfinance_backfill
from app.storage.db import get_session
from app.storage.models import QuoteEod

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _backfill_if_empty() -> None:
    with get_session() as session:
        any_row = session.exec(select(QuoteEod).limit(1)).first()
    if any_row:
        log.info("backfill skipped: quotes_eod already populated")
        return
    log.info("backfill: pulling %d years of history", settings.backfill_years)
    yfinance_backfill.run()


def start() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sch = BackgroundScheduler(timezone=settings.scheduler_timezone)

    sch.add_job(
        investing.run,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="9-17",
            minute=f"*/{settings.intraday_poll_minutes}",
        ),
        id="intraday.investing",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    sch.add_job(
        ice.run,
        trigger=CronTrigger(day_of_week="mon-fri", hour=19, minute=30),
        id="eod.ice",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    sch.add_job(
        cftc.run,
        trigger=CronTrigger(day_of_week="fri", hour=21, minute=0),
        id="cot.cftc",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    sch.add_job(
        _backfill_if_empty,
        trigger="date",
        id="bootstrap.backfill",
    )

    sch.start()
    _scheduler = sch
    log.info("scheduler started")
    return sch


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler stopped")
