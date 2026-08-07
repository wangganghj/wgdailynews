from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import SOURCES, TIMEZONE, UPDATE_HOUR, UPDATE_MINUTE
from app.fetcher import get_progress, update_all
from app.store import get_state, init_db, load_sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(update_all, CronTrigger(hour=UPDATE_HOUR, minute=UPDATE_MINUTE, timezone=TIMEZONE), id="daily-update", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    if not load_sources():
        threading.Thread(target=update_all, daemon=True).start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Daily News", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    by_key = {item["key"]: item for item in load_sources()}
    sources = [by_key.get(source.key, {"key": source.key, "name": source.name, "homepage": source.homepage, "articles": [], "updated_at": "", "error": None}) for source in SOURCES]
    return templates.TemplateResponse(request=request, name="index.html", context={"sources": sources, "status": get_state("update_status") or "idle", "last_updated": get_state("last_updated_at"), "timezone": TIMEZONE, "hour": UPDATE_HOUR})


@app.post("/api/update")
async def manual_update():
    if get_state("update_status") == "running":
        return JSONResponse({"started": False, "message": "更新正在进行"}, status_code=409)
    threading.Thread(target=update_all, daemon=True).start()
    return JSONResponse({"started": True, "message": "已开始更新"}, status_code=202)


@app.get("/api/status")
async def status():
    return {"status": get_state("update_status") or "idle", "last_updated_at": get_state("last_updated_at"), "progress": get_progress()}


@app.get("/health")
async def health():
    return {"status": "ok"}
