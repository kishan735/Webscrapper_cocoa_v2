"""APScheduler jobs for Phase 1.

- Intraday quotes: every N minutes during London session
- ICE EOD report: ~19:30 London on weekdays
- CFTC COT: Fridays 21:00 London (CFTC publishes ~15:30 ET Friday)
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.scrapers import cftc, ice, investing, yfinance_backfill

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


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

    sch.start()
    _scheduler = sch
    log.info("scheduler started")

    try:
        written = yfinance_backfill.backfill_if_empty()
        if written:
            log.info("startup yfinance backfill: %d rows", written)
    except Exception as e:  # noqa: BLE001
        log.warning("startup yfinance backfill failed: %s", e)

    return sch


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler stopped")
