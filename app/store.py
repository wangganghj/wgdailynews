from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DATABASE_PATH


def _path() -> str:
    path = Path(DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def connect():
    conn = sqlite3.connect(_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_cache (
                source_key TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                homepage TEXT NOT NULL,
                articles_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_briefing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                summary_points_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def save_source(source_key: str, source_name: str, homepage: str, articles: list[dict], updated_at: str, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO source_cache VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_key) DO UPDATE SET
               source_name=excluded.source_name, homepage=excluded.homepage,
               articles_json=CASE WHEN excluded.articles_json='[]' THEN source_cache.articles_json ELSE excluded.articles_json END,
               updated_at=excluded.updated_at,
               error=excluded.error""",
            (source_key, source_name, homepage, json.dumps(articles, ensure_ascii=False), updated_at, error),
        )


def set_state(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO app_state VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_state(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def load_sources() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM source_cache ORDER BY source_name").fetchall()
    return [
        {
            "key": row["source_key"], "name": row["source_name"], "homepage": row["homepage"],
            "articles": json.loads(row["articles_json"]), "updated_at": row["updated_at"], "error": row["error"],
        }
        for row in rows
    ]


def save_briefing(date_str: str, content: str, summary_points: list[str] | list[dict], created_at: str) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO ai_briefing (date, content, summary_points_json, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
               content=excluded.content,
               summary_points_json=excluded.summary_points_json,
               created_at=excluded.created_at""",
            (date_str, content, json.dumps(summary_points, ensure_ascii=False), created_at),
        )


def get_latest_briefing() -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM ai_briefing ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    try:
        points = json.loads(row["summary_points_json"])
    except Exception:
        points = []
    return {
        "id": row["id"],
        "date": row["date"],
        "content": row["content"],
        "summary_points": points,
        "created_at": row["created_at"],
    }
