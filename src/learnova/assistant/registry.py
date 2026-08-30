"""
Presentation registry (spec §3, §39, §40).

Wraps ``learnova.storage.deck_library`` with a stable, human-facing identity
layer. Every deck gets:

    pres_id         "LRN-PRES-0007"  — permanent, assigned once
    display_number  7                — per-user ordinal (newest = highest),
                                       may change; never used for actions
    aliases         ["rsa deck", "cryptography presentation", …]

``pres_id`` is derived from a per-user monotonic counter stored in
``.data/users/<uid>/_assistant/seq.json`` and pinned into each deck's
``meta.json`` the first time the registry sees it (backfill-safe).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from learnova.assistant.ids import pres_id as _mk_pres_id
from learnova.assistant.ids import slide_id as _mk_slide_id
from learnova.logging_config import logger

_STOP = {"the", "a", "an", "of", "on", "in", "to", "for", "and", "presentation",
         "deck", "slides", "slide", "ppt", "pptx", "web", "interactive",
         "learnova", "about", "regarding", "covering"}


def _tokens(s: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower())
            if w not in _STOP and len(w) > 1]


@dataclass
class PresentationEntry:
    pres_id: str
    deck_id: str            # the deck_library key (== originating job id)
    user_id: str
    display_number: int
    title: str
    subject: str = ""
    topic: str = ""
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    slide_count: int = 0
    quiz_count: int = 0
    overall_score: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    has_web_deck: bool = False
    has_pptx: bool = False

    @property
    def web_deck_url(self) -> str:
        return f"/api/decks/{self.deck_id}/download/html"

    @property
    def presentation_url(self) -> str:
        return f"/app/preview/{self.deck_id}"

    def slide_ref(self, index_1based: int) -> str:
        return _mk_slide_id(self.pres_id, index_1based)

    def to_dict(self) -> dict:
        d = {
            "pres_id": self.pres_id,
            "deck_id": self.deck_id,
            "display_number": self.display_number,
            "title": self.title,
            "subject": self.subject,
            "topic": self.topic,
            "tags": self.tags,
            "aliases": self.aliases,
            "slide_count": self.slide_count,
            "quiz_count": self.quiz_count,
            "overall_score": self.overall_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "web_deck_url": self.web_deck_url,
            "presentation_url": self.presentation_url,
            "has_web_deck": self.has_web_deck,
            "has_pptx": self.has_pptx,
        }
        return d


# ── per-user pres_id sequence ───────────────────────────────────────────────
def _seq_path(user_id: str):
    from learnova.config import DATA_DIR
    from learnova.storage.deck_library import _safe

    d = DATA_DIR / "users" / _safe(user_id, "user id") / "_assistant"
    d.mkdir(parents=True, exist_ok=True)
    return d / "seq.json"


def _load_seq(user_id: str) -> Dict[str, Any]:
    p = _seq_path(user_id)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"next": 1, "map": {}}   # map: deck_id -> seq int


def _save_seq(user_id: str, data: Dict[str, Any]) -> None:
    try:
        _seq_path(user_id).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("assistant registry: could not persist seq for %s: %s", user_id, exc)


def _assign_pres_id(user_id: str, deck_id: str) -> str:
    data = _load_seq(user_id)
    if deck_id in data["map"]:
        return _mk_pres_id(data["map"][deck_id])
    n = int(data.get("next", 1))
    data["map"][deck_id] = n
    data["next"] = n + 1
    _save_seq(user_id, data)
    return _mk_pres_id(n)


# ── alias / metadata derivation ────────────────────────────────────────────
_SUBJECT_HINTS = {
    "cybersecurity": ["security", "cyber", "phishing", "malware", "attack",
                      "encryption", "cryptography", "firewall", "vulnerability"],
    "networking": ["network", "tcp", "ip", "router", "packet", "osi", "dns"],
    "machine learning": ["machine learning", "neural", "model", "training",
                         "regression", "classifier", "deep learning"],
    "nlp": ["nlp", "natural language", "tokeniz", "lexical", "semantic",
            "syntactic", "language processing"],
    "operating systems": ["operating system", "process", "thread", "scheduler",
                          "kernel", "deadlock", "paging"],
    "databases": ["database", "sql", "normalization", "transaction", "index"],
}


def _derive(title: str, subject_meta: str, topic_meta: str,
            source_text: str = "") -> tuple[str, str, List[str], List[str]]:
    blob = f"{title} {subject_meta} {topic_meta} {source_text[:2000]}".lower()
    subject = subject_meta or ""
    if not subject:
        for name, hints in _SUBJECT_HINTS.items():
            if any(h in blob for h in hints):
                subject = name
                break
    topic = topic_meta or title.strip()
    ttok = _tokens(title)
    tags = sorted(set(ttok + _tokens(subject)))[:12]

    aliases: List[str] = []
    tl = title.strip().lower()
    if tl:
        aliases.append(tl)
        aliases.append(f"{tl} presentation")
        aliases.append(f"{tl} deck")
    if subject:
        aliases.append(f"{subject} presentation")
        aliases.append(f"{subject} deck")
    # "the X presentation" where X is the salient noun
    if ttok:
        aliases.append(f"{ttok[0]} presentation")
        aliases.append(" ".join(ttok[:3]))
    seen, out = set(), []
    for a in aliases:
        a = a.strip()
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return subject, topic, tags, out


# ── build the registry from the deck library ───────────────────────────────
def build_registry(user_id: str) -> List[PresentationEntry]:
    """All of a user's decks as :class:`PresentationEntry`, oldest first so
    ``display_number`` is stable-ish (1 = first created)."""
    from learnova.storage import deck_library

    raw = deck_library.list_decks(user_id)
    raw.sort(key=lambda r: r.get("created_at", 0))  # oldest first
    entries: List[PresentationEntry] = []
    for i, rec in enumerate(raw, start=1):
        deck_id = rec.get("id") or rec.get("deck_id") or ""
        if not deck_id:
            continue
        pid = rec.get("pres_id") or _assign_pres_id(user_id, deck_id)
        title = rec.get("title") or "Untitled deck"
        src = ""
        try:
            src = (deck_library.read_markdown(user_id, deck_id) or "")[:2000]
        except Exception:
            pass
        subject, topic, tags, aliases = _derive(
            title, rec.get("subject", ""), rec.get("topic", ""), src)
        entries.append(PresentationEntry(
            pres_id=pid, deck_id=deck_id, user_id=user_id, display_number=i,
            title=title, subject=subject, topic=topic, tags=tags, aliases=aliases,
            slide_count=int(rec.get("slide_count", 0) or 0),
            quiz_count=int(rec.get("quiz_count", 0) or 0),
            overall_score=int(rec.get("overall_score", 0) or 0),
            created_at=float(rec.get("created_at", 0) or 0),
            updated_at=float(rec.get("updated_at", rec.get("created_at", 0)) or 0),
            has_web_deck=bool(rec.get("has_html")),
            has_pptx=bool(rec.get("has_pptx")),
        ))
        # Backfill pres_id / derived metadata into meta.json once.
        if rec.get("pres_id") != pid or "aliases" not in rec:
            _pin_metadata(user_id, deck_id, pid, subject, topic, tags, aliases)
    return entries


def _pin_metadata(user_id, deck_id, pid, subject, topic, tags, aliases) -> None:
    from learnova.storage.deck_library import META_FILE, _deck_dir

    p = _deck_dir(user_id, deck_id) / META_FILE
    if not p.is_file():
        return
    try:
        meta = json.loads(p.read_text(encoding="utf-8"))
        meta.update({"pres_id": pid, "subject": subject, "topic": topic,
                     "tags": tags, "aliases": aliases})
        p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("assistant registry: backfill failed for %s: %s", deck_id, exc)


def registry_payload(user_id: str) -> dict:
    entries = build_registry(user_id)
    return {"count": len(entries), "presentations": [e.to_dict() for e in entries]}


def get_entry(user_id: str, ref) -> Optional[PresentationEntry]:
    """Fetch by pres_id, deck_id or display_number — no fuzzy matching here
    (that is ``resolver.resolve_presentation_reference``)."""
    entries = build_registry(user_id)
    s = str(ref).strip()
    for e in entries:
        if s.upper() == e.pres_id or s == e.deck_id or s == str(e.display_number):
            return e
    return None


__all__ = ["PresentationEntry", "build_registry", "registry_payload",
           "get_entry", "_tokens"]
