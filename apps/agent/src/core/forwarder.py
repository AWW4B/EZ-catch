from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional
from urllib import request as urllib_request
from urllib.error import URLError

from apps.agent.src.core.buffer import DB_PATH

# Default backend endpoint that receives forwarded events
DEFAULT_BACKEND_URL = "http://localhost:8000/api/v1/ingest"

BATCH_SIZE = 50          # events per HTTP POST
FLUSH_INTERVAL = 3.0     # seconds between flush attempts
MAX_RETRIES = 3


class BufferForwarder:
    """
    Reads captured events from the local SQLite WAL buffer and forwards them
    to the backend API in batches. Runs in a background daemon thread so it
    never blocks the interceptors.

    Forwarded rows are deleted from the buffer on success; on failure they are
    retried up to MAX_RETRIES times before being dropped to prevent a
    runaway buffer.
    """

    def __init__(
        self,
        backend_url: str = DEFAULT_BACKEND_URL,
        db_path: Path = DB_PATH,
        flush_interval: float = FLUSH_INTERVAL,
    ) -> None:
        self._backend_url = backend_url
        self._db_path = db_path
        self._flush_interval = flush_interval
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> threading.Thread:
        """Start the forwarder in a daemon thread and return it."""
        t = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="buffer-forwarder",
        )
        t.start()
        return t

    def stop(self) -> None:
        """Signal the background thread to stop after its current flush."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_batch(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        cur = conn.execute(
            "SELECT id, timestamp, event_type, raw_json FROM captured_events "
            "ORDER BY id ASC LIMIT ?",
            (BATCH_SIZE,),
        )
        return cur.fetchall()

    def _delete_batch(self, conn: sqlite3.Connection, ids: list[int]) -> None:
        conn.execute(
            f"DELETE FROM captured_events WHERE id IN ({','.join('?' * len(ids))})",
            ids,
        )
        conn.commit()

    def _post_batch(self, rows: list[sqlite3.Row]) -> bool:
        """
        POST a JSON array of event objects to the backend.
        Returns True on HTTP 2xx, False otherwise.
        """
        payload = [json.loads(row["raw_json"]) for row in rows]
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            self._backend_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with urllib_request.urlopen(req, timeout=5) as resp:
                    if 200 <= resp.status < 300:
                        return True
                    print(
                        f"[FORWARDER] Backend returned {resp.status} "
                        f"(attempt {attempt}/{MAX_RETRIES})"
                    )
            except URLError as exc:
                print(
                    f"[FORWARDER] POST failed ({exc}) "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )
            time.sleep(0.5 * attempt)
        return False

    def _flush_once(self) -> None:
        try:
            conn = self._get_conn()
            rows = self._fetch_batch(conn)
            if not rows:
                conn.close()
                return
            success = self._post_batch(rows)
            if success:
                self._delete_batch(conn, [row["id"] for row in rows])
                print(f"[FORWARDER] Forwarded {len(rows)} event(s) to backend.")
            else:
                print(
                    f"[FORWARDER] Could not forward batch of {len(rows)} — "
                    "will retry next cycle."
                )
            conn.close()
        except Exception as exc:
            print(f"[FORWARDER] Unexpected error during flush: {exc}")

    def _run_loop(self) -> None:
        print(f"[FORWARDER] Started — forwarding to {self._backend_url} "
              f"every {self._flush_interval}s")
        while not self._stop_event.is_set():
            self._flush_once()
            self._stop_event.wait(self._flush_interval)
        # Final flush on exit
        self._flush_once()
        print("[FORWARDER] Stopped.")


def start_forwarder(
    backend_url: str = DEFAULT_BACKEND_URL,
    db_path: Optional[Path] = None,
) -> BufferForwarder:
    """Convenience factory — creates and starts a BufferForwarder."""
    fwd = BufferForwarder(
        backend_url=backend_url,
        db_path=db_path or DB_PATH,
    )
    fwd.start()
    return fwd
