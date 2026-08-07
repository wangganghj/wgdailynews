from __future__ import annotations

import html
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT, SOURCES, USER_AGENT
from app.store import save_source, set_state

log = logging.getLogger(__name__)
update_lock = threading.Lock()


def _plain(value: str | None, limit: int = 320) -> str:
    soup = BeautifulSoup(html.unescape(value or ""), "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _image(entry) -> str | None:
    for item in entry.get("media_content", []) + entry.get("media_thumbnail", []):
        if item.get("url"):
            return item["url"]
    for enclosure in entry.get("enclosures", []):
        if enclosure.get("type", "").startswith("image/") and enclosure.get("href"):
            return enclosure["href"]
    soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
    img = soup.find("img")
    return img.get("src") if img else None


def _from_feed(client: httpx.Client, feed_url: str) -> list[dict]:
    response = client.get(feed_url)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(str(parsed.bozo_exception))
    results = []
    for entry in parsed.entries:
        url = entry.get("link")
        title = _plain(entry.get("title"), 180)
        if not url or not title:
            continue
        results.append({
            "title": title,
            "url": url,
            "image": _image(entry),
            "summary": _plain(entry.get("summary") or entry.get("description") or entry.get("content", [{}])[0].get("value")),
            "published": entry.get("published") or entry.get("updated") or "",
        })
    return results


def _from_homepage(client: httpx.Client, homepage: str) -> list[dict]:
    response = client.get(homepage)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results, seen = [], set()
    for node in soup.select("article, main h2, main h3"):
        link = node.find("a", href=True) if node.name == "article" else node.find("a", href=True)
        if not link and node.parent:
            link = node.parent if node.parent.name == "a" and node.parent.get("href") else None
        if not link:
            continue
        title = _plain(link.get_text(" ", strip=True), 180)
        url = urljoin(homepage, link["href"])
        if len(title) < 12 or url in seen or not url.startswith("http"):
            continue
        container = node if node.name == "article" else node.parent
        img = container.find("img") if container else None
        summary_node = container.find("p") if container else None
        results.append({"title": title, "url": url, "image": urljoin(homepage, img.get("src")) if img and img.get("src") else None, "summary": _plain(summary_node.get_text(" ") if summary_node else ""), "published": ""})
        seen.add(url)
        if len(results) >= 10:
            break
    return results


def fetch_source(source) -> tuple[list[dict], str | None]:
    errors = []
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9"}
    with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        articles = []
        for feed in source.feeds:
            try:
                articles.extend(_from_feed(client, feed))
            except Exception as exc:
                errors.append(f"{feed}: {exc}")
        deduped, seen = [], set()
        for article in articles:
            marker = article["url"].split("?")[0]
            if marker not in seen:
                deduped.append(article)
                seen.add(marker)
        if len(deduped) < 10:
            try:
                for article in _from_homepage(client, source.homepage):
                    marker = article["url"].split("?")[0]
                    if marker not in seen:
                        deduped.append(article)
                        seen.add(marker)
            except Exception as exc:
                errors.append(f"homepage: {exc}")
    error = "; ".join(errors) if not deduped and errors else None
    return deduped[:10], error


def update_all() -> bool:
    if not update_lock.acquire(blocking=False):
        return False
    started = datetime.now(timezone.utc).isoformat()
    set_state("update_status", "running")
    set_state("update_started_at", started)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(fetch_source, SOURCES))
        for source, (articles, error) in zip(SOURCES, results):
            now = datetime.now(timezone.utc).isoformat()
            try:
                save_source(source.key, source.name, source.homepage, articles, now, error)
            except Exception as exc:
                log.exception("Failed to update %s", source.name)
                save_source(source.key, source.name, source.homepage, [], now, str(exc))
        set_state("last_updated_at", datetime.now(timezone.utc).isoformat())
        set_state("update_status", "idle")
        return True
    finally:
        update_lock.release()
