from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    CATEGORIES,
    SCREENSHOT_DIR,
    SOURCES,
    TIMEZONE,
    UPDATE_HOUR,
    UPDATE_MINUTE,
)
from app.fetcher import (
    generate_ai_briefing,
    get_progress,
    is_update_running,
    send_notifications,
    update_all,
)
from app.store import (
    get_latest_briefing,
    get_state,
    init_db,
    load_sources,
    set_state,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
templates = Jinja2Templates(directory="app/templates")


def _recover_interrupted_update() -> bool:
    interrupted = get_state("update_status") == "running"
    if interrupted:
        set_state("update_status", "idle")
    return interrupted


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    interrupted_update = _recover_interrupted_update()
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        update_all,
        CronTrigger(hour=UPDATE_HOUR, minute=UPDATE_MINUTE, timezone=TIMEZONE),
        id="daily-update",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    if interrupted_update or not load_sources():
        threading.Thread(target=update_all, daemon=True).start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Daily News", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/screenshots", StaticFiles(directory=SCREENSHOT_DIR, check_dir=False), name="screenshots")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    by_key = {item["key"]: item for item in load_sources()}
    sources = []
    for source in SOURCES:
        item = by_key.get(
            source.key,
            {
                "key": source.key,
                "name": source.name,
                "homepage": source.homepage,
                "articles": [],
                "updated_at": "",
                "error": None,
            },
        )
        item["mode"] = source.mode
        item["category"] = getattr(source, "category", "general")
        item["has_cover"] = source.mode == "cover" and os.path.exists(os.path.join(SCREENSHOT_DIR, f"{source.key}.jpg"))
        item["cover_page"] = source.cover_page
        item["cover_provider"] = source.cover_provider
        sources.append(item)
    
    briefing = get_latest_briefing()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "sources": sources,
            "categories": CATEGORIES,
            "briefing": briefing,
            "status": get_state("update_status") or "idle",
            "last_updated": get_state("last_updated_at"),
            "timezone": TIMEZONE,
            "hour": UPDATE_HOUR,
        },
    )


@app.post("/api/update")
async def manual_update():
    if is_update_running():
        return JSONResponse({"started": False, "message": "更新正在进行"}, status_code=409)
    threading.Thread(target=update_all, daemon=True).start()
    return JSONResponse({"started": True, "message": "已开始更新"}, status_code=202)


@app.get("/api/status")
async def status():
    actual_status = "running" if is_update_running() else "idle"
    if get_state("update_status") != actual_status:
        set_state("update_status", actual_status)
    return {"status": actual_status, "last_updated_at": get_state("last_updated_at"), "progress": get_progress()}


@app.get("/api/briefing")
async def get_briefing_api():
    briefing = get_latest_briefing()
    return {"briefing": briefing}


@app.post("/api/briefing/generate")
async def generate_briefing_api():
    sources = load_sources()
    sources_map = {s["key"]: s.get("articles", []) for s in sources}
    briefing = generate_ai_briefing(sources_map)
    return {"success": True, "briefing": briefing}


@app.post("/api/notify")
async def test_notify_api():
    briefing = get_latest_briefing()
    if not briefing:
        return JSONResponse({"success": False, "message": "暂无可用简报"}, status_code=400)
    send_notifications(briefing)
    return {"success": True, "message": "已触发推送通知"}


@app.get("/health")
async def health():
    return {"status": "ok"}
