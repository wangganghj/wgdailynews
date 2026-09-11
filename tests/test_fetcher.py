from types import SimpleNamespace

import app.fetcher as fetcher_module
from app.fetcher import _fetch_economist_cover, _from_feed


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class _FeedClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return _Response(self.responses[url])


def _rss(items):
    body = "".join(
        f"<item><title>{title}</title><link>{url}</link><pubDate>{published}</pubDate></item>"
        for title, url, published in items
    )
    return f"<?xml version='1.0'?><rss version='2.0'><channel>{body}</channel></rss>".encode()


def test_from_feed_merges_all_feeds_and_returns_freshest_articles():
    stale_items = [
        (f"Old story {index}", f"https://www.wsj.com/articles/old-{index}", "Mon, 01 Sep 2026 12:00:00 GMT")
        for index in range(10)
    ]
    fresh_item = [
        ("Fresh story", "https://www.wsj.com/articles/fresh", "Thu, 10 Sep 2026 12:00:00 GMT")
    ]
    client = _FeedClient({"stale": _rss(stale_items), "fresh": _rss(fresh_item)})
    source = SimpleNamespace(name="The Wall Street Journal", feeds=("stale", "fresh"))

    articles = _from_feed(client, source)

    assert client.calls == ["stale", "fresh"]
    assert articles[0]["title"] == "Fresh story"
    assert len(articles) == 10
    assert all("_published_ts" not in article and "_feed_index" not in article for article in articles)


def test_wsj_uses_current_official_feeds():
    from app.config import SOURCES

    wsj = next(source for source in SOURCES if source.key == "wsj")
    assert "https://feeds.content.dowjones.io/public/rss/RSSWorldNews" in wsj.feeds
    assert "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain" in wsj.feeds
    assert not any("wsj_world_news" in feed or "mw_topstories" in feed for feed in wsj.feeds)


def test_economist_cover_checks_upcoming_saturday_and_skips_article_images(monkeypatch):
    real_datetime = fetcher_module.datetime

    class CoverResponse:
        def __init__(self, found=False):
            self.status_code = 200 if found else 403
            self.headers = {"content-type": "image/jpeg" if found else "text/plain"}
            self.content = b"x" * 10_001 if found else b"not found"

    class CoverClient:
        def __init__(self):
            self.urls = []

        def get(self, url, headers=None):
            self.urls.append(url)
            return CoverResponse(url.endswith("20260912_DE_US.jpg"))

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return real_datetime(2026, 9, 11, tzinfo=tz)

    saved = []
    monkeypatch.setattr(fetcher_module, "datetime", FixedDateTime)
    monkeypatch.setattr(fetcher_module, "_save_cover", lambda content, source: saved.append(content))
    client = CoverClient()
    source = SimpleNamespace(key="economist")

    _fetch_economist_cover(client, source)

    assert client.urls == [
        "https://www.economist.com/img/b/1000/1333/90/media-assets/image/20260912_DE_US.jpg"
    ]
    assert all("CUD001" not in url for url in client.urls)
    assert saved == [b"x" * 10_001]
