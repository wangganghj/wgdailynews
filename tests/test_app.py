import os

os.environ["DATABASE_PATH"] = "/tmp/daily-news-test.db"

from fastapi.testclient import TestClient
from app.main import app
import app.main as main_module
from app.config import SOURCES


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
    assert all(source.mode == "cover" for source in SOURCES[:5])
    assert [source.key for source in SOURCES[-2:]] == ["bbc", "zaobao"]
    assert "wsj-cn" not in {source.key for source in SOURCES}
    assert SOURCES[0].cover_page.endswith("/wsj.html")
    assert SOURCES[3].cover_page is None


def test_interrupted_update_is_reset(monkeypatch):
    saved = {}
    monkeypatch.setattr(main_module, "get_state", lambda key: "running" if key == "update_status" else None)
    monkeypatch.setattr(main_module, "set_state", lambda key, value: saved.update({key: value}))

    assert main_module._recover_interrupted_update() is True
    assert saved == {"update_status": "idle"}
