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
EDIT_FILE = "deck_edit.json"  # the editable improved-slide list (title/bullets/family), for re-renders
VERSIONS_DIR = "versions"
IMAGES_DIR = "images"         # per-slide figure bytes, so edits/crops survive a re-render

_IMG_EXT = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "webp": "webp", "gif": "gif"}


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
    version: int = 1
    versions: List[dict] = field(default_factory=list)  # [{v, at, note}]

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
    editable_slides: Optional[list] = None,
    deck_id: Optional[str] = None,
) -> DeckRecord:
    """Persist a ``PipelineResult`` for one user and return its record.

    ``deck_id`` lets the caller reuse the originating job id, so the same id
    opens the deck through both ``/api/jobs/{id}/*`` and ``/api/decks/{id}/*``
    (the editor, version history and figure routes are decks-only).
    """
    deck_id = _safe(deck_id, "deck id") if deck_id else uuid.uuid4().hex[:16]
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
    if editable_slides is not None:
        (target / EDIT_FILE).write_text(
            json.dumps({"slides": editable_slides}, ensure_ascii=False), encoding="utf-8"
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


def _img_path(d, slide_index: int):
    for ext in ("png", "jpg", "webp", "gif"):
        p = d / IMAGES_DIR / f"slide{int(slide_index)}.{ext}"
        if p.is_file():
            return p
    return None


def save_images(user_id: str, deck_id: str, images: Dict[int, tuple]) -> int:
    """images: {slide_index: (bytes, ext)}. Returns how many were written."""
    d = _deck_dir(user_id, deck_id)
    if not d.is_dir():
        return 0
    (d / IMAGES_DIR).mkdir(exist_ok=True)
    n = 0
    for idx, (data, ext) in (images or {}).items():
        if not data:
            continue
        ext = _IMG_EXT.get(str(ext or "png").lower().lstrip("."), "png")
        # Clear any prior extension for this slide, then write.
        for old in ("png", "jpg", "webp", "gif"):
            (d / IMAGES_DIR / f"slide{int(idx)}.{old}").unlink(missing_ok=True)
        (d / IMAGES_DIR / f"slide{int(idx)}.{ext}").write_bytes(data)
        n += 1
    return n


def read_image(user_id: str, deck_id: str, slide_index: int) -> Optional[tuple]:
    """Returns (bytes, ext) for a slide's stored figure, or None."""
    p = _img_path(_deck_dir(user_id, deck_id), slide_index)
    if not p:
        return None
    return p.read_bytes(), p.suffix.lstrip(".")


def save_one_image(user_id: str, deck_id: str, slide_index: int,
                   data: bytes, ext: str = "png") -> bool:
    return save_images(user_id, deck_id, {int(slide_index): (data, ext)}) == 1


def read_all_images(user_id: str, deck_id: str) -> Dict[int, tuple]:
    """{slide_index: (bytes, ext)} for every stored figure."""
    d = _deck_dir(user_id, deck_id) / IMAGES_DIR
    out: Dict[int, tuple] = {}
    if not d.is_dir():
        return out
    for p in d.iterdir():
        m = re.match(r"slide(\d+)\.(png|jpg|jpeg|webp|gif)$", p.name)
        if m:
            out[int(m.group(1))] = (p.read_bytes(), m.group(2))
    return out


def read_editable(user_id: str, deck_id: str) -> Optional[list]:
    """The editable improved-slide list, falling back to the display payload."""
    d = _deck_dir(user_id, deck_id)
    path = d / EDIT_FILE
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("slides")
        except (OSError, json.JSONDecodeError):
            pass
    # Fallback: reconstruct from the display payload (deck.json).
    from learnova.rendering.deck_payload import payload_to_editable

    stored = read_slides(user_id, deck_id) or {}
    out = payload_to_editable(stored.get("slides", []))
    return out or None


def save_edit(user_id: str, deck_id: str, *, editable_slides: list,
              slides_payload: list, html_bytes: Optional[bytes],
              pptx_bytes: Optional[bytes], scores: dict, quizzes: list,
              note: str = "edited") -> Optional[dict]:
    """
    Overwrite a deck's artifacts with an edited re-render, archiving the previous
    version under versions/v{n}/ first. Returns the updated meta dict.
    """
    d = _deck_dir(user_id, deck_id)
    if not (d / META_FILE).is_file():
        return None
    meta = json.loads((d / META_FILE).read_text(encoding="utf-8"))
    cur_v = int(meta.get("version", 1))

    # Archive current artifacts.
    vdir = d / VERSIONS_DIR / f"v{cur_v}"
    vdir.mkdir(parents=True, exist_ok=True)
    for name in (HTML_FILE, PPTX_FILE, SLIDES_FILE, EDIT_FILE):
        src = d / name
        if src.is_file():
            shutil.copy2(src, vdir / name)

    # Write the new version.
    if html_bytes:
        (d / HTML_FILE).write_bytes(html_bytes)
    if pptx_bytes:
        (d / PPTX_FILE).write_bytes(pptx_bytes)
    (d / SLIDES_FILE).write_text(
        json.dumps({"slides": slides_payload, "quizzes": quizzes, "scores": scores},
                   ensure_ascii=False), encoding="utf-8")
    (d / EDIT_FILE).write_text(
        json.dumps({"slides": editable_slides}, ensure_ascii=False), encoding="utf-8")

    versions = list(meta.get("versions") or [])
    versions.append({"v": cur_v, "at": time.time(), "note": meta.get("_last_note", "original" if cur_v == 1 else "edited")})
    meta.update({
        "version": cur_v + 1,
        "versions": versions,
        "_last_note": note,
        "slide_count": len(editable_slides),
        "quiz_count": len(quizzes),
        "overall_score": int((scores or {}).get("overall_score", meta.get("overall_score", 0)) or 0),
        "has_pptx": bool(pptx_bytes) or meta.get("has_pptx", False),
        "has_html": bool(html_bytes) or meta.get("has_html", False),
    })
    (d / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("saved edit v%d for deck %s", cur_v + 1, deck_id)
    return meta


def restore_version(user_id: str, deck_id: str, v: int) -> Optional[dict]:
    """Roll a deck's artifacts back to an archived version (itself archived first)."""
    d = _deck_dir(user_id, deck_id)
    vdir = d / VERSIONS_DIR / f"v{int(v)}"
    if not vdir.is_dir() or not (d / META_FILE).is_file():
        return None
    meta = json.loads((d / META_FILE).read_text(encoding="utf-8"))
    cur_v = int(meta.get("version", 1))
    keep = d / VERSIONS_DIR / f"v{cur_v}"
    keep.mkdir(parents=True, exist_ok=True)
    for name in (HTML_FILE, PPTX_FILE, SLIDES_FILE, EDIT_FILE):
        if (d / name).is_file():
            shutil.copy2(d / name, keep / name)
        if (vdir / name).is_file():
            shutil.copy2(vdir / name, d / name)

    slides = []
    try:
        slides = json.loads((d / EDIT_FILE).read_text(encoding="utf-8")).get("slides", [])
    except Exception:
        pass
    versions = list(meta.get("versions") or [])
    versions.append({"v": cur_v, "at": time.time(), "note": "before restore"})
    meta.update({"version": cur_v + 1, "versions": versions,
                 "_last_note": f"restored v{v}", "slide_count": len(slides)})
    (d / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("restored deck %s to v%d", deck_id, v)
    return meta


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
    "save_edit",
    "restore_version",
    "list_decks",
    "get_deck",
    "read_markdown",
    "read_slides",
    "read_editable",
    "read_artifact",
    "save_images",
    "save_one_image",
    "read_image",
    "read_all_images",
    "delete_deck",
]
