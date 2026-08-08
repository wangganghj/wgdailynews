from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    homepage: str
    feeds: tuple[str, ...] = ()
    mode: str = "rss"


SOURCES = (
    Source("wsj", "The Wall Street Journal", "https://www.wsj.com/", mode="screenshot"),
    Source("washington-post", "The Washington Post", "https://www.washingtonpost.com/", mode="screenshot"),
    Source("economist", "The Economist", "https://www.economist.com/", mode="screenshot"),
    Source("ft", "Financial Times", "https://www.ft.com/", mode="screenshot"),
    Source("nytimes", "The New York Times", "https://www.nytimes.com/", mode="screenshot"),
    Source("bbc", "BBC", "https://www.bbc.com/", ("https://feeds.bbci.co.uk/news/world/rss.xml", "https://feeds.bbci.co.uk/news/rss.xml")),
    Source("zaobao", "联合早报", "https://www.zaobao.com.sg/global", mode="web"),
)

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/news.db")
TIMEZONE = os.getenv("TIMEZONE", "America/Vancouver")
UPDATE_HOUR = int(os.getenv("UPDATE_HOUR", "8"))
UPDATE_MINUTE = int(os.getenv("UPDATE_MINUTE", "0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
USER_AGENT = os.getenv("USER_AGENT", "DailyNewsReader/1.0 (+personal news dashboard; respects publisher access controls)")
TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "google").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "/data/screenshots")
