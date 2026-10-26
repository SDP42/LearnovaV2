"""
Share links: a read-only, unlisted web deck anyone with the link can open (no account needed).

A link is an unguessable token (128 bits) mapped to one deck. It can expire and be revoked at any time; the owner
sees who has not been given anything beyond the slideshow — no editing, no download of the source, no account data.
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Dict, List, Optional

from learnova.pipeline.job_db import _db


def _ensure() -> None:
    with _db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS shares (token TEXT PRIMARY KEY, deck_id TEXT NOT NULL, user_id TEXT NOT NULL, created_at REAL NOT NULL,"
                  " expires_at REAL, revoked INTEGER NOT NULL DEFAULT 0, views INTEGER NOT NULL DEFAULT 0)")
        c.execute("CREATE INDEX IF NOT EXISTS shares_deck ON shares(deck_id, user_id)")


def create(user_id: str, deck_id: str, days: Optional[int] = 30) -> Dict[str, Any]:
    _ensure()
    token = secrets.token_urlsafe(16)
    now = time.time()
    exp = now + days * 86400 if days else None
    with _db() as c:
        c.execute("INSERT INTO shares(token, deck_id, user_id, created_at, expires_at) VALUES(?,?,?,?,?)", (token, deck_id, user_id, now, exp))
    return {"token": token, "deck_id": deck_id, "expires_at": exp}


def resolve(token: str) -> Optional[Dict[str, Any]]:
    """The share if it is live (and counts the view); None when unknown, revoked or expired."""
    _ensure()
    with _db() as c:
        row = c.execute("SELECT * FROM shares WHERE token=?", (token,)).fetchone()
        if not row or row["revoked"] or (row["expires_at"] and row["expires_at"] < time.time()):
            return None
        c.execute("UPDATE shares SET views = views + 1 WHERE token=?", (token,))
        return dict(row)


def list_for_deck(user_id: str, deck_id: str) -> List[Dict[str, Any]]:
    _ensure()
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT token, created_at, expires_at, revoked, views FROM shares WHERE user_id=? AND deck_id=? ORDER BY created_at DESC", (user_id, deck_id))]


def revoke(user_id: str, deck_id: str, token: str) -> bool:
    _ensure()
    with _db() as c:
        cur = c.execute("UPDATE shares SET revoked=1 WHERE token=? AND user_id=? AND deck_id=?", (token, user_id, deck_id))
        return bool(cur.rowcount)
