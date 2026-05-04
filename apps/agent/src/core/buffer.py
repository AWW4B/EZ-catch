from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from pydantic import BaseModel

def _find_root():
    curr = Path(__file__).resolve().parent
    for _ in range(10):
        if (curr / "apps").exists() or (curr / "packages").exists():
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent
    return curr

DB_PATH = _find_root() / "local_buffer.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS captured_events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                event_type TEXT   NOT NULL,
                raw_json  TEXT    NOT NULL
            )
            """
        )
        conn.commit()
        _local.conn = conn
    return _local.conn


class LocalSQLiteBuffer:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        global DB_PATH
        DB_PATH = db_path
        _get_conn()

    def push_event(self, event_model: BaseModel) -> None:
        data = event_model.model_dump(mode="json")
        timestamp = data.get("timestamp") or ""
        event_type = data.get("event_type") or type(event_model).__name__
        raw_json = event_model.model_dump_json()

        conn = _get_conn()
        conn.execute(
            "INSERT INTO captured_events (timestamp, event_type, raw_json) VALUES (?, ?, ?)",
            (str(timestamp), event_type, raw_json),
        )
        conn.commit()