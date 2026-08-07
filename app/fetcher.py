from __future__ import annotations

import html
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin

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
            articles = _from_homepage(client, source.homepage)[:10]
            with ThreadPoolExecutor(max_workers=4) as pool:
                articles = list(pool.map(lambda item: _enrich_article(client, item), articles))
            return articles, None if articles else "首页未找到可识别的新闻链接"
        except Exception as exc:
            return [], f"homepage: {exc}"


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
