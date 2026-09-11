from types import SimpleNamespace

from app.fetcher import _from_feed


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
