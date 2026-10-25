"""
Phone-number + OTP authentication backed by SQLite.

Flow
----
1. ``request_otp(phone)``  — validates/normalises the number, rate-limits, stores
   an HMAC of a fresh 6-digit code (never the code itself) and hands the code to
   an SMS sender.
2. ``verify_otp(phone, code)`` — constant-time compare, max attempts, expiry,
   single use. On success it upserts the user and opens a session.
3. The session token is an opaque 256-bit random string. Only its SHA-256 is
   stored, so a leaked database cannot be replayed as live sessions.

SMS delivery is pluggable: ``OTP_SMS_PROVIDER=twilio`` (needs TWILIO_ACCOUNT_SID,
TWILIO_AUTH_TOKEN, TWILIO_FROM) or the default ``console`` sender, which logs the
code. With ``OTP_DEV_MODE=1`` the API also returns the code in its response so
the UI can be exercised without an SMS account. Never enable that in production.

Database location: ``LEARNOVA_DB_PATH`` (default ``<project>/.data/learnova.db``).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from learnova.config import DATA_DIR
from learnova.logging_config import logger

OTP_LENGTH = 6
OTP_TTL_S = 5 * 60
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_S = 30
OTP_MAX_PER_HOUR = 5
SESSION_TTL_S = 30 * 24 * 3600

_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")  # E.164

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    phone         TEXT NOT NULL UNIQUE,
    created_at    REAL NOT NULL,
    last_login_at REAL
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id       TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name     TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT '',
    organization  TEXT NOT NULL DEFAULT '',
    avatar_color  TEXT NOT NULL DEFAULT '',
    completed     INTEGER NOT NULL DEFAULT 0,
    updated_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS otp_codes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    phone      TEXT NOT NULL,
    code_hash  TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    consumed   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_otp_phone ON otp_codes(phone, created_at);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    user_agent TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    name       TEXT NOT NULL,
    path       TEXT NOT NULL DEFAULT '',
    props      TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_name ON events(name, created_at);
CREATE TABLE IF NOT EXISTS error_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    source     TEXT NOT NULL,
    message    TEXT NOT NULL,
    stack      TEXT NOT NULL DEFAULT '',
    path       TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
"""


class PhoneAuthError(Exception):
    """Raised with a user-safe message and an HTTP status hint."""

    def __init__(self, message: str, status: int = 400, retry_after: Optional[int] = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


# ── Database ──────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_ready_for: Optional[str] = None


def db_path() -> str:
    return os.getenv("LEARNOVA_DB_PATH") or str(DATA_DIR / "learnova.db")


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    global _ready_for
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        if _ready_for != path:
            with _lock:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(_SCHEMA)
                _ready_for = path
        yield conn
    finally:
        conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _secret() -> bytes:
    """HMAC key for OTP hashes. Set OTP_SECRET in production."""
    return (os.getenv("OTP_SECRET") or "learnova-dev-secret-change-me").encode()


def _hash_code(phone: str, code: str) -> str:
    return hmac.new(_secret(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_phone(raw: str) -> str:
    """Return an E.164 number or raise. A bare 10-digit number is read as +91."""
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+") and re.fullmatch(r"\d{10}", s):
        s = "+" + os.getenv("DEFAULT_COUNTRY_CODE", "91") + s
    if not _PHONE_RE.fullmatch(s):
        raise PhoneAuthError("Enter a valid mobile number with country code, e.g. +919876543210.")
    return s


def dev_mode() -> bool:
    return os.getenv("OTP_DEV_MODE", "1") == "1"


# ── SMS delivery ──────────────────────────────────────────────────────────────
def _send_sms(phone: str, code: str) -> None:
    provider = (os.getenv("OTP_SMS_PROVIDER") or "console").lower()
    message = f"{code} is your Learnova verification code. It expires in {OTP_TTL_S // 60} minutes."
    if provider == "twilio":
        import requests

        sid, token, sender = (os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"))
        if not (sid and token and sender):
            raise PhoneAuthError("SMS provider is not configured.", status=503)
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"To": phone, "From": sender, "Body": message},
            timeout=10,
        )
        if resp.status_code >= 300:
            logger.error("Twilio send failed: %s %s", resp.status_code, resp.text[:200])
            raise PhoneAuthError("Could not send the code. Try again shortly.", status=502)
        return
    # console sender: dev only
    logger.warning("[OTP console sender] %s -> %s", phone, code)


# ── OTP ───────────────────────────────────────────────────────────────────────
def request_otp(phone_raw: str) -> Dict[str, Any]:
    phone = normalize_phone(phone_raw)
    now = time.time()
    with _db() as conn:
        last = conn.execute(
            "SELECT created_at FROM otp_codes WHERE phone=? ORDER BY created_at DESC LIMIT 1",
            (phone,),
        ).fetchone()
        if last and now - last["created_at"] < OTP_RESEND_COOLDOWN_S:
            wait = int(OTP_RESEND_COOLDOWN_S - (now - last["created_at"])) + 1
            raise PhoneAuthError(f"Please wait {wait}s before requesting another code.", 429, wait)
        recent = conn.execute(
            "SELECT COUNT(*) AS n FROM otp_codes WHERE phone=? AND created_at>?",
            (phone, now - 3600),
        ).fetchone()["n"]
        if recent >= OTP_MAX_PER_HOUR:
            raise PhoneAuthError("Too many codes requested. Try again in an hour.", 429, 3600)

        code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
        # Invalidate any earlier live codes for this number.
        conn.execute("UPDATE otp_codes SET consumed=1 WHERE phone=? AND consumed=0", (phone,))
        conn.execute(
            "INSERT INTO otp_codes(phone, code_hash, created_at, expires_at) VALUES (?,?,?,?)",
            (phone, _hash_code(phone, code), now, now + OTP_TTL_S),
        )
    _send_sms(phone, code)
    out: Dict[str, Any] = {
        "phone": phone,
        "expires_in": OTP_TTL_S,
        "resend_in": OTP_RESEND_COOLDOWN_S,
        "length": OTP_LENGTH,
    }
    if dev_mode():
        out["dev_otp"] = code
    return out


def verify_otp(phone_raw: str, code: str, user_agent: str = "") -> Dict[str, Any]:
    phone = normalize_phone(phone_raw)
    code = re.sub(r"\D", "", code or "")
    now = time.time()
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM otp_codes WHERE phone=? AND consumed=0 ORDER BY created_at DESC LIMIT 1",
            (phone,),
        ).fetchone()
        if row is None or row["expires_at"] < now:
            raise PhoneAuthError("This code has expired. Request a new one.", 400)
        if row["attempts"] >= OTP_MAX_ATTEMPTS:
            conn.execute("UPDATE otp_codes SET consumed=1 WHERE id=?", (row["id"],))
            raise PhoneAuthError("Too many wrong attempts. Request a new code.", 429)
        if not hmac.compare_digest(row["code_hash"], _hash_code(phone, code)):
            conn.execute("UPDATE otp_codes SET attempts=attempts+1 WHERE id=?", (row["id"],))
            left = OTP_MAX_ATTEMPTS - row["attempts"] - 1
            raise PhoneAuthError(f"Incorrect code. {max(left, 0)} attempt(s) left.", 400)
        conn.execute("UPDATE otp_codes SET consumed=1 WHERE id=?", (row["id"],))

        user = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        is_new = user is None
        if is_new:
            uid = "u_" + secrets.token_hex(8)
            conn.execute("INSERT INTO users(id, phone, created_at, last_login_at) VALUES (?,?,?,?)", (uid, phone, now, now))
            conn.execute("INSERT INTO profiles(user_id, updated_at) VALUES (?,?)", (uid, now))
        else:
            uid = user["id"]
            conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now, uid))

        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions(token_hash, user_id, created_at, expires_at, user_agent) VALUES (?,?,?,?,?)",
            (_hash_token(token), uid, now, now + SESSION_TTL_S, user_agent[:200]),
        )
        conn.execute("DELETE FROM sessions WHERE expires_at<?", (now,))
        profile = get_user(uid, conn=conn)
    return {"token": token, "is_new": is_new, "user": profile}


# ── Sessions / users ──────────────────────────────────────────────────────────
def user_id_from_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token_hash=? AND expires_at>?",
            (_hash_token(token), time.time()),
        ).fetchone()
    return row["user_id"] if row else None


def logout(token: str) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (_hash_token(token),))


def get_user(user_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    def _q(c: sqlite3.Connection):
        return c.execute(
            "SELECT u.id, u.phone, u.created_at, p.full_name, p.email, p.role, p.organization, "
            "p.avatar_color, p.completed FROM users u JOIN profiles p ON p.user_id=u.id WHERE u.id=?",
            (user_id,),
        ).fetchone()

    if conn is not None:
        row = _q(conn)
    else:
        with _db() as c:
            row = _q(c)
    if row is None:
        return None
    d = dict(row)
    d["completed"] = bool(d["completed"])
    return d


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ROLES = {"educator", "student", "trainer", "researcher", "other"}


def update_profile(user_id: str, *, full_name: str, email: str = "", role: str = "",
                   organization: str = "", avatar_color: str = "") -> Dict[str, Any]:
    full_name = (full_name or "").strip()
    email = (email or "").strip()
    role = (role or "").strip().lower()
    if len(full_name) < 2 or len(full_name) > 80:
        raise PhoneAuthError("Please enter your name (2–80 characters).")
    if email and not _EMAIL_RE.fullmatch(email):
        raise PhoneAuthError("That email address doesn't look right.")
    if role and role not in _ROLES:
        raise PhoneAuthError("Unknown role.")
    with _db() as conn:
        conn.execute(
            "UPDATE profiles SET full_name=?, email=?, role=?, organization=?, avatar_color=?, "
            "completed=1, updated_at=? WHERE user_id=?",
            (full_name, email[:120], role, organization.strip()[:120], avatar_color[:20], time.time(), user_id),
        )
        user = get_user(user_id, conn=conn)
    if user is None:
        raise PhoneAuthError("Account not found.", 404)
    return user


# ── Account lifecycle, analytics, error tracking ─────────────────────────────
def logout_all(user_id: str) -> int:
    with _db() as conn:
        return conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,)).rowcount


def delete_account(user_id: str) -> None:
    """Erase the user, profile, sessions and their saved decks. Irreversible."""
    import shutil

    from learnova.config import DATA_DIR as _DATA

    with _db() as conn:
        row = conn.execute("SELECT phone FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise PhoneAuthError("Account not found.", 404)
        conn.execute("DELETE FROM otp_codes WHERE phone=?", (row["phone"],))
        conn.execute("UPDATE events SET user_id=NULL WHERE user_id=?", (user_id,))
        conn.execute("UPDATE error_logs SET user_id=NULL WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))  # profile + sessions cascade
    shutil.rmtree(_DATA / "users" / user_id, ignore_errors=True)
    logger.info("deleted account %s", user_id)


def record_event(name: str, path: str = "", props: Optional[dict] = None, user_id: Optional[str] = None) -> None:
    import json

    name = re.sub(r"[^\w.\-:]", "", name or "")[:60]
    if not name:
        raise PhoneAuthError("Event name required.")
    blob = json.dumps(props or {}, default=str)[:2000]
    with _db() as conn:
        conn.execute(
            "INSERT INTO events(user_id, name, path, props, created_at) VALUES (?,?,?,?,?)",
            (user_id, name, (path or "")[:200], blob, time.time()),
        )


def record_error(source: str, message: str, stack: str = "", path: str = "", user_id: Optional[str] = None) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO error_logs(user_id, source, message, stack, path, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, (source or "client")[:30], (message or "")[:1000], (stack or "")[:4000], (path or "")[:200], time.time()),
        )
    logger.error("[%s] %s (%s)", source, (message or "")[:200], path)


def backup(dest_dir: str, keep: int = 14) -> str:
    """Consistent online copy via SQLite's backup API; prunes to the newest ``keep``."""
    import glob

    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, time.strftime("learnova-%Y%m%d-%H%M%S.db"))
    with _db() as src:
        dst = sqlite3.connect(out)
        try:
            src.backup(dst)
        finally:
            dst.close()
    for old in sorted(glob.glob(os.path.join(dest_dir, "learnova-*.db")))[:-keep]:
        os.remove(old)
    return out
