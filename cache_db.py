"""SQLite TTLキャッシュ（全外部データの一元管理）"""
import json
import sqlite3
import time
from pathlib import Path
from threading import Lock

_DB  = Path(__file__).parent / "data" / "cache.db"
_lock = Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB, check_same_thread=False, timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS cache(
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        expires_at REAL NOT NULL
    )""")
    conn.commit()
    return conn


def get(key: str):
    try:
        with _lock:
            with _conn() as c:
                row = c.execute(
                    "SELECT value FROM cache WHERE key=? AND expires_at>?",
                    (key, time.time())
                ).fetchone()
                return json.loads(row[0]) if row else None
    except Exception:
        return None


def set(key: str, value, ttl: int = 300):
    try:
        with _lock:
            with _conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO cache(key,value,expires_at) VALUES(?,?,?)",
                    (key, json.dumps(value, ensure_ascii=False, default=str),
                     time.time() + ttl)
                )
    except Exception:
        pass


def delete(key: str):
    try:
        with _lock:
            with _conn() as c:
                c.execute("DELETE FROM cache WHERE key=?", (key,))
    except Exception:
        pass


def cleanup():
    try:
        with _lock:
            with _conn() as c:
                c.execute("DELETE FROM cache WHERE expires_at<?", (time.time(),))
    except Exception:
        pass
