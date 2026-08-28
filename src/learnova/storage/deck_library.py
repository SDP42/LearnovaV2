"""
Per-user deck library.

Every generated deck is written under ``.data/users/<user_id>/<deck_id>/`` with
its markdown, PPTX, HTML and a metadata record. Users only ever see their own
decks: the user id comes from a verified Clerk token, never from the client.

Disk rather than a database because a deck is mostly two large binaries; a
directory per deck keeps them streamable and makes deletion trivial. Swap in a
real database when decks need sharing or search.
"""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from learnova.config import DATA_DIR
from learnova.logging_config import logger

_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")

MARKDOWN_FILE = "deck.md"
PPTX_FILE = "deck.pptx"
HTML_FILE = "deck.html"
META_FILE = "meta.json"
SLIDES_FILE = "deck.json"   # the slides payload, so a saved deck opens without a live job


@dataclass
class DeckRecord:
    id: str
    user_id: str
    title: str
    created_at: float
    slide_count: int = 0
    quiz_count: int = 0
    overall_score: int = 0
    converter: str = ""
    theme_id: str = "auto"
    theme_spec: Optional[Dict[str, Any]] = None
    has_pptx: bool = False
    has_html: bool = False
    source_type: str = ""
    stages: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _safe(component: str, label: str) -> str:
    """Reject anything that could escape the storage root via path traversal."""
    if not _SAFE_ID.match(component or ""):
        raise ValueError(f"invalid {label}")
    return component


def _user_dir(user_id: str):
    return DATA_DIR / "users" / _safe(user_id, "user id")


def _deck_dir(user_id: str, deck_id: str):
    return _user_dir(user_id) / _safe(deck_id, "deck id")


def save_deck(
    user_id: str,
    result,
    theme_id: str = "auto",
    theme_spec: Optional[dict] = None,
    title: Optional[str] = None,
    slides_payload: Optional[list] = None,
) -> DeckRecord:
    """Persist a ``PipelineResult`` for one user and return its record."""
    deck_id = uuid.uuid4().hex[:16]
    target = _deck_dir(user_id, deck_id)
    target.mkdir(parents=True, exist_ok=True)

    if result.markdown:
        (target / MARKDOWN_FILE).write_text(result.markdown, encoding="utf-8")
    if result.pptx_bytes:
        (target / PPTX_FILE).write_bytes(result.pptx_bytes)
    if result.html_bytes:
        (target / HTML_FILE).write_bytes(result.html_bytes)
    if slides_payload is not None:
        (target / SLIDES_FILE).write_text(
            json.dumps(
                {
                    "slides": slides_payload,
                    "quizzes": list(getattr(result, "quizzes", []) or []),
                    "scores": dict(getattr(result, "scores", {}) or {}),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    record = DeckRecord(
        id=deck_id,
        user_id=user_id,
        title=title or result.source_name or "Untitled deck",
        created_at=time.time(),
        slide_count=len(result.final_deck),
        quiz_count=len(result.quizzes),
        overall_score=int(result.scores.get("overall_score", 0) or 0),
        converter=result.converter,
        theme_id=theme_id,
        theme_spec=theme_spec,
        has_pptx=bool(result.pptx_bytes),
        has_html=bool(result.html_bytes),
        stages=[
            {"name": s.name, "status": s.status, "seconds": round(s.seconds, 2)}
            for s in result.stages
        ],
    )
    (target / META_FILE).write_text(
        json.dumps(record.to_dict(), indent=2), encoding="utf-8"
    )
    logger.info("saved deck %s for user %s (%d slides)", deck_id, user_id, record.slide_count)
    return record


def list_decks(user_id: str) -> List[dict]:
    """All of one user's decks, newest first."""
    root = _user_dir(user_id)
    if not root.exists():
        return []

    records = []
    for entry in root.iterdir():
        meta = entry / META_FILE
        if not meta.is_file():
            continue
        try:
            records.append(json.loads(meta.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("skipping unreadable deck record %s: %s", meta, exc)

    records.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return records


def get_deck(user_id: str, deck_id: str) -> Optional[dict]:
    meta = _deck_dir(user_id, deck_id) / META_FILE
    if not meta.is_file():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_markdown(user_id: str, deck_id: str) -> Optional[str]:
    path = _deck_dir(user_id, deck_id) / MARKDOWN_FILE
    return path.read_text(encoding="utf-8") if path.is_file() else None


def read_slides(user_id: str, deck_id: str) -> Optional[dict]:
    """The stored slides payload ({slides, quizzes, scores}), or None."""
    path = _deck_dir(user_id, deck_id) / SLIDES_FILE
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_artifact(user_id: str, deck_id: str, artifact: str) -> Optional[bytes]:
    """Read the stored ``pptx`` or ``html`` bytes for a deck."""
    filename = {"pptx": PPTX_FILE, "html": HTML_FILE}.get(artifact)
    if not filename:
        return None
    path = _deck_dir(user_id, deck_id) / filename
    return path.read_bytes() if path.is_file() else None


def delete_deck(user_id: str, deck_id: str) -> bool:
    target = _deck_dir(user_id, deck_id)
    if not target.is_dir():
        return False
    shutil.rmtree(target, ignore_errors=True)
    logger.info("deleted deck %s for user %s", deck_id, user_id)
    return True


__all__ = [
    "DeckRecord",
    "save_deck",
    "list_decks",
    "get_deck",
    "read_markdown",
    "read_slides",
    "read_artifact",
    "delete_deck",
]
