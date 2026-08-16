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
    cover_provider: str = "freedom_forum"


SOURCES = (
    Source(
        "wsj",
        "The Wall Street Journal",
        "https://www.wsj.com/",
        (
            "https://feeds.content.dowjones.io/public/rss/wsj_world_news",
            "https://feeds.content.dowjones.io/public/rss/mw_topstories",
            "https://news.google.com/rss/search?q=site:wsj.com&hl=en-US&gl=US&ceid=US:en",
        ),
        mode="cover",
        cover_page="https://frontpages.freedomforum.org/newspapers/wsj-The_Wall_Street_Journal",
        cover_id="wsj",
    ),
    Source(
        "washington-post",
        "The Washington Post",
        "https://www.washingtonpost.com/",
        (
            "https://feeds.washingtonpost.com/rss/world",
            "https://feeds.washingtonpost.com/rss/national",
        ),
        mode="cover",
        cover_page="https://www.frontpages.com/the-washington-post/",
        cover_provider="frontpages",
    ),
    Source(
        "economist",
        "The Economist",
        "https://www.economist.com/",
        (
            "https://www.economist.com/the-world-this-week/rss.xml",
            "https://www.economist.com/international/rss.xml",
        ),
        mode="cover",
        cover_page="https://www.economist.com/",
        cover_provider="homepage",
    ),
    Source(
        "ft",
        "Financial Times",
        "https://www.ft.com/",
        (
            "https://www.ft.com/world?format=rss",
            "https://www.ft.com/global-economy?format=rss",
        ),
        mode="cover",
        cover_page="https://www.frontpages.com/financial-times/",
        cover_provider="frontpages",
    ),
    Source(
        "nytimes",
        "The New York Times",
        "https://www.nytimes.com/",
        ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml",),
        mode="cover",
        cover_page="https://frontpages.freedomforum.org/newspapers/ny_nyt-The_New_York_Times",
        cover_id="ny_nyt",
    ),
    Source(
        "globe-and-mail",
        "The Globe and Mail",
        "https://www.theglobeandmail.com/",
        (
            "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/canada/",
            "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/world/",
        ),
        mode="cover",
        cover_page="https://frontpages.freedomforum.org/newspapers/can_tgam-The_Globe_and_Mail",
        cover_id="can_tgam",
    ),
    Source(
        "vancouver-sun",
        "The Vancouver Sun",
        "https://vancouversun.com/",
        (
            "https://vancouversun.com/category/news/feed/",
            "https://vancouversun.com/feed/",
        ),
        mode="cover",
        cover_page="https://frontpages.freedomforum.org/newspapers/can_vs-The_Vancouver_Sun",
        cover_id="can_vs",
    ),
    Source(
        "bbc",
        "BBC",
        "https://www.bbc.com/",
        (
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.bbci.co.uk/news/rss.xml",
        ),
    ),
    Source(
        "zaobao",
        "联合早报",
        "https://www.zaobao.com.sg/global",
        mode="web",
    ),
    Source(
        "reuters",
        "Reuters",
        "https://www.reuters.com/",
        ("https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",),
    ),
    Source(
        "bloomberg",
        "Bloomberg",
        "https://www.bloomberg.com/",
        ("https://news.google.com/rss/search?q=site:bloomberg.com&hl=en-US&gl=US&ceid=US:en",),
    ),
    Source(
        "nikkei",
        "Nikkei Asia",
        "https://asia.nikkei.com/",
        ("https://asia.nikkei.com/rss/feed/nar",),
    ),
    Source(
        "techcrunch",
        "TechCrunch",
        "https://techcrunch.com/",
        ("https://techcrunch.com/feed/",),
    ),
    Source(
        "hackernews",
        "Hacker News",
        "https://news.ycombinator.com/",
        ("https://news.ycombinator.com/rss",),
    ),
)

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/news.db")
TIMEZONE = os.getenv("TIMEZONE", "America/Vancouver")
UPDATE_HOUR = int(os.getenv("UPDATE_HOUR", "8"))
UPDATE_MINUTE = int(os.getenv("UPDATE_MINUTE", "0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
USER_AGENT = os.getenv("USER_AGENT", "DailyNewsReader/1.0 (+personal news dashboard; respects publisher access controls)")

# Translation configuration (google | openai | gemini | deepl)
TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "google").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")

SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "/data/screenshots")
