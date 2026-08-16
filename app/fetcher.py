from __future__ import annotations

import copy
import html
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config import (
    DEEPL_API_KEY,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REQUEST_TIMEOUT,
    SCREENSHOT_DIR,
    SOURCES,
    TRANSLATION_PROVIDER,
    USER_AGENT,
)
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


def is_update_running() -> bool:
    return update_lock.locked()


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
        try:
            response = client.get(feed_url)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                continue
            for entry in parsed.entries:
                url = entry.get("link")
                title = _plain(entry.get("title"), 180)
                if url and title:
                    results.append({
                        "title": title,
                        "url": url,
                        "image": _feed_image(entry),
                        "summary": _plain(
                            entry.get("summary")
                            or entry.get("description")
                            or (entry.get("content", [{}])[0].get("value") if entry.get("content") else "")
                        ),
                        "published": entry.get("published") or entry.get("updated") or "",
                    })
            if len(results) >= 10:
                break
        except Exception as exc:
            log.warning("Feed fetch error for %s (%s): %s", source.name, feed_url, exc)
            continue
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
        article["summary"] = article.get("summary") or _plain(
            _meta(soup, ("property", "og:description"), ("name", "description"), ("name", "twitter:description"))
        )
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
    response = client.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text[:4500]},
    )
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


def _gemini_translate(client: httpx.Client, title: str, summary: str) -> tuple[str, str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""你是专业新闻翻译。请将以下新闻标题和摘要翻译为简体中文：
标题: {title}
摘要: {summary}

请严格按如下 JSON 格式输出：
{{"title_zh": "中文标题", "summary_zh": "中文摘要"}}"""
    response = client.post(
        url,
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}},
    )
    response.raise_for_status()
    result_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(result_text)
    return data.get("title_zh", ""), data.get("summary_zh", "")


def _deepl_translate(client: httpx.Client, text: str) -> str:
    if not text or _mostly_chinese(text):
        return text
    api_url = "https://api-free.deepl.com/v2/translate" if ":fx" in DEEPL_API_KEY else "https://api.deepl.com/v2/translate"
    response = client.post(
        api_url,
        headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
        data={"text": text[:4000], "target_lang": "ZH"},
    )
    response.raise_for_status()
    translations = response.json().get("translations", [])
    return translations[0]["text"] if translations else text


def _translate_article(client: httpx.Client, article: dict) -> dict:
    title, summary = article.get("title", ""), article.get("summary", "")
    try:
        if TRANSLATION_PROVIDER == "gemini" and GEMINI_API_KEY:
            article["title_zh"], article["summary_zh"] = _gemini_translate(client, title, summary)
        elif TRANSLATION_PROVIDER == "openai" and OPENAI_API_KEY:
            article["title_zh"], article["summary_zh"] = _openai_translate(client, title, summary)
        elif TRANSLATION_PROVIDER == "deepl" and DEEPL_API_KEY:
            article["title_zh"] = _deepl_translate(client, title)
            article["summary_zh"] = _deepl_translate(client, summary)
        else:
            article["title_zh"] = _google_translate(client, title)
            article["summary_zh"] = _google_translate(client, summary)
    except Exception as exc:
        log.warning("Primary translation failed for %s (%s), trying fallback: %s", article.get("url"), TRANSLATION_PROVIDER, exc)
        try:
            article["title_zh"] = _google_translate(client, title)
            article["summary_zh"] = _google_translate(client, summary)
        except Exception:
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
        results.append({
            "title": title,
            "url": url,
            "image": _image_url(img, homepage),
            "summary": _plain(summary_node.get_text(" ") if summary_node else ""),
            "published": "",
        })
        seen.add(url)
        if len(results) >= 10:
            break
    return results


def _fetch_freedom_forum_cover(client: httpx.Client, source) -> None:
    if not source.cover_id:
        raise ValueError("Freedom Forum 暂未收录该报纸")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    final_path = os.path.join(SCREENSHOT_DIR, f"{source.key}.jpg")
    temp_path = os.path.join(SCREENSHOT_DIR, f".{source.key}.tmp.jpg")
    image_response = None
    for days_ago in range(15):
        issue_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()
        image_url = f"https://d2dr22b2lm4tvw.cloudfront.net/{source.cover_id}/{issue_date}/front-page-medium.jpg"
        try:
            candidate = client.get(image_url)
            if candidate.status_code == 200 and candidate.headers.get("content-type", "").startswith("image/") and len(candidate.content) >= 10_000:
                image_response = candidate
                break
        except Exception:
            continue
    if image_response is None:
        raise ValueError("Freedom Forum 最近 15 天没有可用封面")
    try:
        with open(temp_path, "wb") as image_file:
            image_file.write(image_response.content)
        os.replace(temp_path, final_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _save_cover(content: bytes, source) -> None:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    final_path = os.path.join(SCREENSHOT_DIR, f"{source.key}.jpg")
    temp_path = os.path.join(SCREENSHOT_DIR, f".{source.key}.tmp.jpg")
    try:
        with open(temp_path, "wb") as image_file:
            image_file.write(content)
        os.replace(temp_path, final_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _fetch_frontpages_cover(client: httpx.Client, source) -> None:
    headers = {"Referer": "https://www.frontpages.com/"}
    response = client.get(source.cover_page, headers=headers)
    response.raise_for_status()
    html_text = response.text
    candidates = []

    # Extract og:image
    og = re.search(r'<meta property=[\"\']og:image[\"\'] content=[\"\']([^\"\']+)[\"\']', html_text)
    if og:
        raw_url = og.group(1)
        cleaned = re.sub(r'\.jpg$', '', raw_url).replace('/g/', '/t/').replace('/share/', '/t/')
        if cleaned.endswith('.webp'):
            candidates.append(cleaned.replace('.webp', '@2x.webp'))
            candidates.append(cleaned)
        else:
            candidates.append(cleaned + '@2x.webp')
            candidates.append(cleaned)

    # Extract any /t/ date images from HTML
    for m in re.finditer(r'(/t/\d{4}/\d{2}/\d{2}/[^\"\'\s]+\.webp)', html_text):
        path = "https://www.frontpages.com" + m.group(1)
        if "@2x" not in path:
            candidates.append(path.replace(".webp", "@2x.webp"))
        candidates.append(path)

    candidates = list(dict.fromkeys(candidates))
    image = None
    for image_url in candidates:
        try:
            candidate = client.get(image_url, headers=headers)
            if candidate.status_code == 200 and candidate.headers.get("content-type", "").startswith("image/") and len(candidate.content) >= 10_000:
                image = candidate
                break
        except Exception:
            continue

    if image is None:
        raise ValueError("FrontPages.com 返回的封面图片无效")
    _save_cover(image.content, source)


def _capture_homepage(source) -> None:
    os.environ.setdefault("PW_TEST_SCREENSHOT_NO_FONTS_READY", "1")
    from playwright.sync_api import sync_playwright

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    temp_path = os.path.join(SCREENSHOT_DIR, f".{source.key}.tmp.jpg")
    final_path = os.path.join(SCREENSHOT_DIR, f"{source.key}.jpg")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
            context = browser.new_context(viewport={"width": 1440, "height": 1600}, locale="en-GB")
            page = context.new_page()
            page.goto(source.homepage, wait_until="domcontentloaded", timeout=45_000)
            challenge_text = (page.title() + " " + page.locator("body").inner_text(timeout=3000)).lower()
            if any(marker in challenge_text for marker in ("performing security verification", "verify you are human", "unusual activity", "access denied")):
                raise ValueError("The Economist 返回安全验证页面，已保留上一次有效截图")
            for label in ("Accept all", "Accept All", "I agree", "Agree", "Continue", "Close"):
                try:
                    page.get_by_role("button", name=re.compile(f"^{re.escape(label)}$", re.I)).first.click(timeout=1200)
                except Exception:
                    pass
            page.evaluate("""() => {
              const selectors = ['#onetrust-banner-sdk', '#onetrust-consent-sdk', '[class*="cookie-banner"]', '[class*="CookieBanner"]', '[aria-label*="cookie" i]', '[role="dialog"]'];
              for (const selector of selectors) for (const node of document.querySelectorAll(selector)) node.remove();
              document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';
            }""")
            page.wait_for_timeout(1200)
            page.screenshot(path=temp_path, type="jpeg", quality=82, full_page=False, timeout=20_000)
            browser.close()
        os.replace(temp_path, final_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _fetch_cover(client: httpx.Client, source) -> None:
    if source.cover_provider == "frontpages":
        _fetch_frontpages_cover(client, source)
    elif source.cover_provider == "homepage":
        _capture_homepage(source)
    else:
        _fetch_freedom_forum_cover(client, source)


def fetch_source(source) -> tuple[list[dict], str | None]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.6",
    }
    with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        try:
            cover_error = None
            if source.mode == "cover":
                provider = {"frontpages": "FrontPages.com", "homepage": "媒体首页"}.get(source.cover_provider, "Freedom Forum")
                _progress(source, f"从 {provider} 获取封面")
                try:
                    _fetch_cover(client, source)
                except Exception as exc:
                    cover_error = str(exc)
                    log.warning("Cover failed for %s: %s", source.name, exc)
                _progress(source, "读取 RSS")
                try:
                    articles = _from_feed(client, source)
                except Exception as exc:
                    log.warning("RSS failed for %s, trying homepage: %s", source.name, exc)
                    _progress(source, "读取媒体首页")
                    articles = _from_homepage(client, source.homepage)[:10]
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
            if source.key != "zaobao":
                _progress(source, "翻译为中文")
                with ThreadPoolExecutor(max_workers=4) as pool:
                    articles = list(pool.map(lambda item: _translate_article(client, item), articles))
            empty_message = "页面未找到可识别的新闻链接" if source.mode == "web" else "RSS 未返回可识别的新闻"
            errors = []
            if cover_error:
                errors.append(f"封面：{cover_error}")
            if not articles:
                errors.append(empty_message)
            return articles, "；".join(errors) or None
        except Exception as exc:
            label = "cover" if source.mode == "cover" else ("homepage" if source.mode == "web" else "rss")
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
        set_state("update_status", "idle")
        update_lock.release()
