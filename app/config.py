from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    homepage: str
    feeds: tuple[str, ...]


SOURCES = (
    Source("wsj", "The Wall Street Journal", "https://www.wsj.com/", ("https://feeds.a.dj.com/rss/RSSWorldNews.xml", "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml")),
    Source("wsj-cn", "华尔街日报中文网", "https://cn.wsj.com/", ("https://cn.wsj.com/zh-hans/rss",)),
    Source("washington-post", "The Washington Post", "https://www.washingtonpost.com/", ("https://feeds.washingtonpost.com/rss/world", "https://feeds.washingtonpost.com/rss/national")),
    Source("bbc", "BBC", "https://www.bbc.com/", ("https://feeds.bbci.co.uk/news/world/rss.xml", "https://feeds.bbci.co.uk/news/rss.xml")),
    Source("economist", "The Economist", "https://www.economist.com/", ("https://www.economist.com/the-world-this-week/rss.xml", "https://www.economist.com/international/rss.xml")),
    Source("zaobao", "联合早报", "https://www.zaobao.com.sg/global", ("https://www.zaobao.com.sg/rss.xml",)),
    Source("ft", "Financial Times", "https://www.ft.com/", ("https://www.ft.com/world?format=rss", "https://www.ft.com/global-economy?format=rss")),
    Source("nytimes", "The New York Times", "https://www.nytimes.com/", ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml",)),
)

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/news.db")
TIMEZONE = os.getenv("TIMEZONE", "America/Vancouver")
UPDATE_HOUR = int(os.getenv("UPDATE_HOUR", "8"))
UPDATE_MINUTE = int(os.getenv("UPDATE_MINUTE", "0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
USER_AGENT = os.getenv("USER_AGENT", "DailyNewsReader/1.0 (+personal news dashboard; respects publisher access controls)")

