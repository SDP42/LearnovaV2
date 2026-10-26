"""
Durable job records (SQLite, same file as the accounts).

Jobs are executed in memory, but their *state* is mirrored here so a server restart does not make a user's
upload vanish: a deck that was awaiting review comes back, and a deck that was mid-build is reported as
interrupted (with its markdown intact, so one click regenerates it) instead of "job not found".
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from learnova.config import DATA_DIR

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL DEFAULT '', source_name TEXT NOT NULL DEFAULT '',
  source_type TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, stage TEXT NOT NULL DEFAULT '',
  progress REAL NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '', error TEXT,
  markdown TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_user ON jobs(user_id, created_at DESC);
"""
_lock = threading.Lock()
_ready_for: Optional[str] = None


def _path() -> str:
    return os.getenv("LEARNOVA_DB_PATH") or str(DATA_DIR / "learnova.db")


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    global _ready_for
    path = _path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        if _ready_for != path:
            with _lock:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(_SCHEMA)
                _ready_for = path
        yield conn
    finally:
        conn.close()


def save(job: Any, source_type: str = "") -> None:
    """Upsert a job's state. Never raises: persistence must not break a running job."""
    try:
        with _db() as c:
            c.execute(
                "INSERT INTO jobs(id,user_id,source_name,source_type,status,stage,progress,detail,error,markdown,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, stage=excluded.stage,"
                " progress=excluded.progress, detail=excluded.detail, error=excluded.error, markdown=excluded.markdown,"
                " source_type=CASE WHEN excluded.source_type='' THEN jobs.source_type ELSE excluded.source_type END, updated_at=excluded.updated_at",
                (job.id, job.user_id or "", job.source_name, source_type, job.status, job.stage, float(job.progress or 0),
                 job.detail or "", job.error, job.markdown or "", job.created_at, time.time()),
            )
    except Exception:
        from learnova.logging_config import logger

        logger.warning("could not persist job %s", getattr(job, "id", "?"), exc_info=True)


def load(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        with _db() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def delete(job_id: str) -> None:
    try:
        with _db() as c:
            c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    except Exception:
        pass


def list_for_user(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    try:
        with _db() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id or "", limit))]
    except Exception:
        return []


def recover_interrupted(message: str) -> int:
    """At start-up: anything that was queued or running when the process died is marked failed, markdown kept."""
    try:
        with _db() as c:
            cur = c.execute("UPDATE jobs SET status='failed', error=?, updated_at=? WHERE status='running'", (message, time.time()))
            return cur.rowcount or 0
    except Exception:
        return 0


def prune(older_than_days: int = 30) -> int:
    try:
        with _db() as c:
            cur = c.execute("DELETE FROM jobs WHERE updated_at < ?", (time.time() - older_than_days * 86400,))
            return cur.rowcount or 0
    except Exception:
        return 0
