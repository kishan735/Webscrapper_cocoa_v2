from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import settings
from app.scheduler import shutdown as stop_scheduler, start as start_scheduler
from app.storage.db import init_db

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    log.info("startup complete (env=%s, db=%s)", settings.environment, settings.db_path)
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="Cocoa Intelligence Terminal", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)

if settings.frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")
