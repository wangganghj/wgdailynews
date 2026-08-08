from __future__ import annotations

import html
import copy
import base64
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config import OPENAI_API_KEY, OPENAI_MODEL, REQUEST_TIMEOUT, SCREENSHOT_DIR, SOURCES, TRANSLATION_PROVIDER, USER_AGENT
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
        if len(results) >= 10:
            break
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


def _mostly_chinese(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    return bool(compact) and sum("\u4e00" <= char <= "\u9fff" for char in compact) / len(compact) > 0.25


def _google_translate(client: httpx.Client, text: str) -> str:
    if not text or _mostly_chinese(text):
        return text
    response = client.get("https://translate.googleapis.com/translate_a/single", params={"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text[:4500]})
    response.raise_for_status()
    payload = response.json()
    return "".join(segment[0] for segment in payload[0] if segment and segment[0]).strip()


def _openai_translate(client: httpx.Client, title: str, summary: str) -> tuple[str, str]:
    response = client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": OPENAI_MODEL,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "你是严谨的新闻翻译。将输入准确翻译为简体中文，保留人名、机构、数字和语气，不添加解释。只返回 JSON：title_zh 和 summary_zh。"},
                {"role": "user", "content": f"Title: {title}\nSummary: {summary}"},
            ],
        },
    )
    response.raise_for_status()
    data = json.loads(response.json()["choices"][0]["message"]["content"])
    return data.get("title_zh", ""), data.get("summary_zh", "")


def _translate_article(client: httpx.Client, article: dict) -> dict:
    title, summary = article.get("title", ""), article.get("summary", "")
    try:
        if TRANSLATION_PROVIDER == "openai" and OPENAI_API_KEY:
            article["title_zh"], article["summary_zh"] = _openai_translate(client, title, summary)
        else:
            article["title_zh"] = _google_translate(client, title)
            article["summary_zh"] = _google_translate(client, summary)
    except Exception as exc:
        log.warning("Translation failed for %s: %s", article.get("url"), exc)
        article["title_zh"], article["summary_zh"] = "", ""
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


def _from_screenshot_page(source) -> list[dict]:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    final_path = os.path.join(SCREENSHOT_DIR, f"{source.key}.jpg")
    temp_path = os.path.join(SCREENSHOT_DIR, f".{source.key}.tmp.jpg")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-http2"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=1, user_agent=USER_AGENT)
        page = context.new_page()
        page.set_default_timeout(10000)
        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9", "Upgrade-Insecure-Requests": "1"})
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in {"font", "media"} else route.continue_())
        navigation_ok = True
        try:
            page.goto(source.homepage, wait_until="commit", timeout=15000)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            navigation_ok = False
            log.warning("Navigation failed for %s; using RSS title fallback: %s", source.name, exc)
        if not navigation_ok:
            browser.close()
            return []
        try:
            page.wait_for_timeout(5000)
        except Exception as exc:
            log.warning("Post-navigation wait failed for %s: %s", source.name, exc)
        _progress(source, "生成首页截图")
        try:
            cdp = context.new_cdp_session(page)
            captured = cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 78, "captureBeyondViewport": False})
            with open(temp_path, "wb") as image_file:
                image_file.write(base64.b64decode(captured["data"]))
            os.replace(temp_path, final_path)
        except Exception as exc:
            log.warning("Screenshot failed for %s; keeping previous screenshot: %s", source.name, exc)
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        _progress(source, "提取新闻标题")
        try:
            links = page.evaluate("""
                () => Array.from(document.querySelectorAll('main a[href], article a[href], h2 a[href], h3 a[href]'))
                    .slice(0, 250).map(a => ({
                        title: (a.querySelector('h1,h2,h3,h4')?.innerText || a.getAttribute('aria-label') || a.innerText || '').trim(),
                        url: a.href
                    }))
            """)
        except Exception as exc:
            log.warning("Title extraction failed for %s: %s", source.name, exc)
            links = []
        browser.close()
    results, seen = [], set()
    for item in links:
        title = _plain(item.get("title"), 180)
        url = item.get("url", "")
        marker = url.split("?")[0]
        if len(title) < 12 or marker in seen or not url.startswith("http") or marker.rstrip("/") == source.homepage.rstrip("/"):
            continue
        results.append({"title": title, "url": url, "image": None, "summary": "", "published": ""})
        seen.add(marker)
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
            if source.mode == "screenshot":
                _progress(source, "打开首页并截图")
                articles = _from_screenshot_page(source)
                if not articles and source.feeds:
                    _progress(source, "首页标题不可用，读取 RSS")
                    articles = _from_feed(client, source)
            elif source.mode == "web":
                _progress(source, "打开首页")
                articles = _from_homepage(client, source.homepage)[:10]
            else:
                _progress(source, "读取 RSS")
                articles = _from_feed(client, source)
            if source.mode != "screenshot":
                _progress(source, "补全图片与摘要")
                with ThreadPoolExecutor(max_workers=4) as pool:
                    articles = list(pool.map(lambda item: _enrich_article(client, item), articles))
            _progress(source, "翻译为中文")
            with ThreadPoolExecutor(max_workers=4) as pool:
                articles = list(pool.map(lambda item: _translate_article(client, item), articles))
            empty_message = "页面未找到可识别的新闻链接" if source.mode in {"web", "screenshot"} else "RSS 未返回可识别的新闻"
            return articles, None if articles else empty_message
        except Exception as exc:
            label = "homepage" if source.mode in {"web", "screenshot"} else "rss"
            return [], f"{label}: {exc}"


def update_all() -> bool:
    if not update_lock.acquire(blocking=False):
        return False
    started = datetime.now(timezone.utc).isoformat()
    _reset_progress()
    set_state("update_status", "running")
    set_state("update_started_at", started)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
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
