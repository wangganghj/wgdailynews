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
    cover_page: str | None = None
    cover_id: str | None = None


SOURCES = (
    Source("wsj", "The Wall Street Journal", "https://www.wsj.com/", ("https://feeds.a.dj.com/rss/RSSWorldNews.xml", "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"), mode="cover", cover_page="https://frontpages.freedomforum.org/newspapers/wsj-The_Wall_Street_Journal", cover_id="wsj"),
    Source("washington-post", "The Washington Post", "https://www.washingtonpost.com/", ("https://feeds.washingtonpost.com/rss/world", "https://feeds.washingtonpost.com/rss/national"), mode="cover", cover_page="https://frontpages.freedomforum.org/newspapers/dc_wp-The_Washington_Post", cover_id="dc_wp"),
    Source("economist", "The Economist", "https://www.economist.com/", ("https://www.economist.com/the-world-this-week/rss.xml", "https://www.economist.com/international/rss.xml"), mode="cover"),
    Source("ft", "Financial Times", "https://www.ft.com/", ("https://www.ft.com/world?format=rss", "https://www.ft.com/global-economy?format=rss"), mode="cover"),
    Source("nytimes", "The New York Times", "https://www.nytimes.com/", ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml",), mode="cover", cover_page="https://frontpages.freedomforum.org/newspapers/ny_nyt-The_New_York_Times", cover_id="ny_nyt"),
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
