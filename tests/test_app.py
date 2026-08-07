import os

os.environ["DATABASE_PATH"] = "/tmp/daily-news-test.db"

from fastapi.testclient import TestClient
from app.main import app


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


def test_status_includes_progress():
    with TestClient(app) as client:
        payload = client.get("/api/status").json()
        assert payload["progress"]["total"] == 8
        assert "active" in payload["progress"]
