from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    homepage: str


SOURCES = (
    Source("wsj", "The Wall Street Journal", "https://www.wsj.com/"),
    Source("wsj-cn", "华尔街日报中文网", "https://cn.wsj.com/"),
    Source("washington-post", "The Washington Post", "https://www.washingtonpost.com/"),
    Source("bbc", "BBC", "https://www.bbc.com/"),
    Source("economist", "The Economist", "https://www.economist.com/"),
    Source("zaobao", "联合早报", "https://www.zaobao.com.sg/global"),
    Source("ft", "Financial Times", "https://www.ft.com/"),
    Source("nytimes", "The New York Times", "https://www.nytimes.com/"),
)

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/news.db")
TIMEZONE = os.getenv("TIMEZONE", "America/Vancouver")
UPDATE_HOUR = int(os.getenv("UPDATE_HOUR", "8"))
UPDATE_MINUTE = int(os.getenv("UPDATE_MINUTE", "0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
USER_AGENT = os.getenv("USER_AGENT", "DailyNewsReader/1.0 (+personal news dashboard; respects publisher access controls)")
