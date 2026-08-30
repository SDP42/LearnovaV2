"""
Stable identifiers for Learnova presentations and slides.

The deck library keys decks by a random ``uuid.hex[:16]`` (== the originating
job id). That is stable, but not human-facing and not what the assistant spec
wants. This module layers a **permanent, readable id** on top:

    LRN-PRES-0001            a presentation
    LRN-PRES-0001-S03        slide 3 of that presentation

``display_number`` (1, 2, 3 …) is a per-user convenience that may change as
decks are added/removed — the assistant always resolves it to the permanent
``pres_id`` before doing anything (spec §3, §5, §40).
"""

from __future__ import annotations

import re

_PRES_RE = re.compile(r"^LRN-PRES-(\d{4,})$")
_SLIDE_RE = re.compile(r"^LRN-PRES-(\d{4,})-S(\d{2,})$")


def pres_id(n: int) -> str:
    """Permanent id for the n-th presentation ever created (1-indexed)."""
    return f"LRN-PRES-{int(n):04d}"


def slide_id(presentation_id: str, slide_index: int) -> str:
    """Permanent id for a slide. ``slide_index`` is 1-indexed."""
    m = _PRES_RE.match(presentation_id or "")
    core = m.group(1) if m else str(presentation_id or "0")
    return f"LRN-PRES-{core}-S{int(slide_index):02d}"


def is_pres_id(value: str) -> bool:
    return bool(_PRES_RE.match((value or "").strip().upper()))


def is_slide_id(value: str) -> bool:
    return bool(_SLIDE_RE.match((value or "").strip().upper()))


def parse_slide_id(value: str) -> tuple[str, int] | None:
    """``LRN-PRES-0001-S03`` -> (``LRN-PRES-0001``, 3), else None."""
    m = _SLIDE_RE.match((value or "").strip().upper())
    if not m:
        return None
    return f"LRN-PRES-{m.group(1)}", int(m.group(2))


def pres_seq(value: str) -> int | None:
    """The sequence number inside a permanent id, or None."""
    m = _PRES_RE.match((value or "").strip().upper())
    return int(m.group(1)) if m else None


__all__ = [
    "pres_id", "slide_id", "is_pres_id", "is_slide_id",
    "parse_slide_id", "pres_seq",
]
