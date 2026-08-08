import os

os.environ["DATABASE_PATH"] = "/tmp/daily-news-test.db"

from fastapi.testclient import TestClient
from app.main import app
from app.config import SOURCES
from app.fetcher import _access_block_message


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_home():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "世界正在发生什么" in response.text
        assert "Financial Times" in response.text
        assert "The New York Times" in response.text
        assert 'id="progress-text"' in response.text


def test_status_includes_progress():
    with TestClient(app) as client:
        payload = client.get("/api/status").json()
        assert payload["progress"]["total"] == 7
        assert "active" in payload["progress"]


def test_source_modes_and_order():
    assert all(source.mode == "screenshot" for source in SOURCES[:5])
    assert [source.key for source in SOURCES[-2:]] == ["bbc", "zaobao"]
    assert "wsj-cn" not in {source.key for source in SOURCES}


def test_access_block_message_detects_bot_challenge():
    class BlockedPage:
        def evaluate(self, _script):
            return "Access is temporarily restricted. We detected automated (bot) activity on your network."

    assert "保留" in _access_block_message(BlockedPage())
