"""Load and query the Gallery catalogue."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from learnova.config import DATA_DIR

GALLERY_USER = "__gallery__"

CATALOG_PATH = DATA_DIR.parent / "data" / "gallery" / "catalog.json"

_LOCK = threading.Lock()
_CACHE: Optional[List["CatalogEntry"]] = None
_MTIME: float = 0.0


@dataclass
class CatalogEntry:
    slug: str
    title: str
    subject: str
    category: str
    tags: List[str] = field(default_factory=list)
    level: str = "Introductory"
    minutes: int = 6
    status: str = "index"          # "outline" (deck buildable) | "index" (title only)
    outline: str = ""

    def to_dict(self, deck: Optional[dict] = None) -> dict:
        d: Dict[str, Any] = {
            "slug": self.slug,
            "title": self.title,
            "subject": self.subject,
            "category": self.category,
            "tags": list(self.tags),
            "level": self.level,
            "minutes": self.minutes,
            "status": "ready" if deck else self.status,
            "has_deck": bool(deck),
        }
        if deck:
            d["slide_count"] = deck.get("slide_count", 0)
            d["quiz_count"] = deck.get("quiz_count", 0)
            d["overall_score"] = deck.get("overall_score", 0)
        return d


def load_catalog(force: bool = False) -> List[CatalogEntry]:
    """Return the catalogue, reloading if the file changed on disk."""
    global _CACHE, _MTIME
    with _LOCK:
        try:
            mtime = CATALOG_PATH.stat().st_mtime
        except OSError:
            return []
        if _CACHE is not None and not force and mtime == _MTIME:
            return _CACHE
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        entries = [CatalogEntry(**{k: e.get(k) for k in CatalogEntry.__dataclass_fields__ if k in e})
                   for e in raw.get("entries", [])]
        _CACHE, _MTIME = entries, mtime
        return entries


def get_entry(slug: str) -> Optional[CatalogEntry]:
    for e in load_catalog():
        if e.slug == slug:
            return e
    return None


def subjects() -> List[Dict[str, Any]]:
    """Subjects with their entry counts, for the Gallery filter rail."""
    counts: Dict[str, Dict[str, Any]] = {}
    for e in load_catalog():
        row = counts.setdefault(e.subject, {"subject": e.subject, "category": e.category, "count": 0})
        row["count"] += 1
    return sorted(counts.values(), key=lambda r: (r["category"], r["subject"]))


def list_entries(
    subject: Optional[str] = None,
    category: Optional[str] = None,
    query: Optional[str] = None,
    ready_only: bool = False,
) -> List[CatalogEntry]:
    q = (query or "").strip().lower()
    out: List[CatalogEntry] = []
    for e in load_catalog():
        if subject and e.subject != subject:
            continue
        if category and e.category != category:
            continue
        if ready_only and e.status != "outline":
            continue
        if q and q not in e.title.lower() and q not in e.subject.lower() \
                and not any(q in t for t in e.tags):
            continue
        out.append(e)
    return out
