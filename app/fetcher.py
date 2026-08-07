from __future__ import annotations

import html
import copy
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT, SOURCES, USER_AGENT
from app.store import save_source, set_state

log = logging.getLogger(__name__)
update_lock = threading.Lock()
progress_lock = threading.Lock()
progress_state = {"total": len(SOURCES), "completed": 0, "active": {}, "phase": "等待更新"}


def _progress(source=None, phase: str | None = None, completed: int | None = None) -> None:
    with progress_lock:
        if source and phase:
            progress_state["active"][source.key] = {"name": source.name, "phase": phase}
        if completed is not None:
            progress_state["completed"] = completed
        if phase:
            progress_state["phase"] = phase


def get_progress() -> dict:
    with progress_lock:
        return copy.deepcopy(progress_state)


def _reset_progress() -> None:
    with progress_lock:
        progress_state.update({"total": len(SOURCES), "completed": 0, "active": {}, "phase": "准备更新"})


def _plain(value: str | None, limit: int = 320) -> str:
    soup = BeautifulSoup(html.unescape(value or ""), "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _image_url(img, base_url: str) -> str | None:
    if not img:
        return None
    candidate = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
    if not candidate and img.get("srcset"):
        candidate = img["srcset"].split(",")[-1].strip().split(" ")[0]
    return urljoin(base_url, candidate) if candidate else None


def _meta(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str | None:
    for attr, value in selectors:
        node = soup.find("meta", attrs={attr: value})
        if node and node.get("content"):
            return node["content"].strip()
    return None


def _feed_image(entry) -> str | None:
    for item in entry.get("media_content", []) + entry.get("media_thumbnail", []):
        if item.get("url"):
            return item["url"]
    for enclosure in entry.get("enclosures", []):
        if enclosure.get("type", "").startswith("image/") and enclosure.get("href"):
            return enclosure["href"]
    img = BeautifulSoup(entry.get("summary", ""), "html.parser").find("img")
    return img.get("src") if img else None


def _from_feed(client: httpx.Client, source) -> list[dict]:
    results = []
    for feed_url in source.feeds:
        response = client.get(feed_url)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(str(parsed.bozo_exception))
        for entry in parsed.entries:
            url, title = entry.get("link"), _plain(entry.get("title"), 180)
            if url and title:
                results.append({"title": title, "url": url, "image": _feed_image(entry), "summary": _plain(entry.get("summary") or entry.get("description") or entry.get("content", [{}])[0].get("value")), "published": entry.get("published") or entry.get("updated") or ""})
    deduped, seen = [], set()
    for article in results:
        marker = article["url"].split("?")[0]
        if marker not in seen:
            deduped.append(article)
            seen.add(marker)
    return deduped[:10]


def _enrich_article(client: httpx.Client, article: dict) -> dict:
    if article.get("image") and article.get("summary"):
        return article
    try:
        response = client.get(article["url"])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        article["image"] = article.get("image") or _meta(
            soup, ("property", "og:image"), ("name", "twitter:image"), ("name", "twitter:image:src")
        )
        article["summary"] = article.get("summary") or _plain(_meta(
            soup, ("property", "og:description"), ("name", "description"), ("name", "twitter:description")
        ))
        published = _meta(soup, ("property", "article:published_time"), ("name", "date"))
        if published:
            article["published"] = published
    except Exception as exc:
        log.debug("Could not enrich %s: %s", article["url"], exc)
    return article


def _from_homepage(client: httpx.Client, homepage: str) -> list[dict]:
    response = client.get(homepage)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results, seen = [], set()
    candidates = soup.select("article, main h2, main h3, [data-testid*='card'], main a[href]")
    if len(candidates) < 10:
        candidates.extend(soup.select("a[href]"))
    for node in candidates:
        link = node if node.name == "a" and node.get("href") else node.find("a", href=True)
        if not link and node.parent:
            link = node.parent if node.parent.name == "a" and node.parent.get("href") else None
        if not link:
            continue
        heading = link.find(["h1", "h2", "h3", "h4"])
        title = _plain((heading or link).get_text(" ", strip=True) or link.get("aria-label"), 180)
        url = urljoin(homepage, link["href"])
        if len(title) < 12 or url in seen or not url.startswith("http") or url.rstrip("/") == homepage.rstrip("/"):
            continue
        container = node if node.name == "article" else link.find_parent("article") or node.parent
        img = container.find("img") if container else None
        summary_node = container.find("p") if container else None
        results.append({"title": title, "url": url, "image": _image_url(img, homepage), "summary": _plain(summary_node.get_text(" ") if summary_node else ""), "published": ""})
        seen.add(url)
        if len(results) >= 10:
            break
    return results


def fetch_source(source) -> tuple[list[dict], str | None]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.6",
    }
    with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        try:
            if source.mode == "web":
                _progress(source, "打开首页")
                articles = _from_homepage(client, source.homepage)[:10]
            else:
                _progress(source, "读取 RSS")
                articles = _from_feed(client, source)
            _progress(source, "补全图片与摘要")
            with ThreadPoolExecutor(max_workers=4) as pool:
                articles = list(pool.map(lambda item: _enrich_article(client, item), articles))
            empty_message = "首页未找到可识别的新闻链接" if source.mode == "web" else "RSS 未返回可识别的新闻"
            return articles, None if articles else empty_message
        except Exception as exc:
            return [], f"{'homepage' if source.mode == 'web' else 'rss'}: {exc}"


def update_all() -> bool:
    if not update_lock.acquire(blocking=False):
        return False
    started = datetime.now(timezone.utc).isoformat()
    _reset_progress()
    set_state("update_status", "running")
    set_state("update_started_at", started)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fetch_source, source): source for source in SOURCES}
            for completed, future in enumerate(as_completed(futures), start=1):
                source = futures[future]
                now = datetime.now(timezone.utc).isoformat()
                try:
                    articles, error = future.result()
                    _progress(source, "保存缓存", completed - 1)
                    save_source(source.key, source.name, source.homepage, articles, now, error)
                except Exception as exc:
                    log.exception("Failed to update %s", source.name)
                    save_source(source.key, source.name, source.homepage, [], now, str(exc))
                with progress_lock:
                    progress_state["active"].pop(source.key, None)
                _progress(completed=completed, phase="保存缓存")
        set_state("last_updated_at", datetime.now(timezone.utc).isoformat())
        set_state("update_status", "idle")
        _progress(phase="更新完成", completed=len(SOURCES))
        return True
    finally:
        update_lock.release()
