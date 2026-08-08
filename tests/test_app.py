import asyncio
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
        assert "DAILY NEWS READER" in response.text
        assert "世界正在发生什么" not in response.text
        assert "Financial Times" in response.text
        assert "The New York Times" in response.text
        assert "The Globe and Mail" in response.text
        assert "The Vancouver Sun" in response.text
        assert 'id="progress-text"' in response.text
        assert 'class="back-to-top"' in response.text


def test_status_includes_progress():
    with TestClient(app) as client:
        payload = client.get("/api/status").json()
        assert payload["progress"]["total"] == 9
        assert "active" in payload["progress"]


def test_status_repairs_stale_running_flag(monkeypatch):
    saved = {}
    monkeypatch.setattr(main_module, "is_update_running", lambda: False)
    monkeypatch.setattr(main_module, "get_state", lambda key: "running" if key == "update_status" else None)
    monkeypatch.setattr(main_module, "set_state", lambda key, value: saved.update({key: value}))

    assert asyncio.run(main_module.status())["status"] == "idle"
    assert saved["update_status"] == "idle"


def test_source_modes_and_order():
    assert all(source.mode == "cover" for source in SOURCES[:7])
    assert all(source.feeds for source in SOURCES[:7])
    assert [source.key for source in SOURCES[-2:]] == ["bbc", "zaobao"]
    assert "wsj-cn" not in {source.key for source in SOURCES}
    assert SOURCES[0].cover_id == "wsj"
    assert SOURCES[1].cover_id == "dc_wp"
    assert SOURCES[4].cover_id == "ny_nyt"
    assert SOURCES[2].cover_provider == "homepage"
    assert SOURCES[3].cover_provider == "frontpages"
    assert SOURCES[5].cover_id == "can_tgam"
    assert SOURCES[6].cover_id == "can_vs"


def test_interrupted_update_is_reset(monkeypatch):
    saved = {}
    monkeypatch.setattr(main_module, "get_state", lambda key: "running" if key == "update_status" else None)
    monkeypatch.setattr(main_module, "set_state", lambda key, value: saved.update({key: value}))

    assert main_module._recover_interrupted_update() is True
    assert saved == {"update_status": "idle"}
