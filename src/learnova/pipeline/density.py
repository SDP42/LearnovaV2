"""
Text density profiles and slide pagination.

Two jobs:

1. **Density** — how much text belongs on one slide. The user picks
   ``low`` / ``medium`` / ``heavy`` and every downstream limit derives from
   that one choice.

2. **Continuity** — when content exceeds the chosen budget it is *carried
   over* to a continuation slide rather than truncated. Nothing is silently
   dropped, and a slide is never split mid-bullet.

Continuation slides are titled ``"Topic (2/3)"`` so a reader can see the run is
one continuous thought. Only the final part carries the takeaway bar, so the
conclusion lands once rather than repeating on every page.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from learnova.logging_config import logger
from learnova.textutils import clean_bullet, dedupe_bullets

# Opt-in: paginate text-ish slides with the research CLASS dynamic program
# (scoring/psf.py) — a load-optimal split — instead of the even _chunk split.
# Off by default so behaviour and the test suite are unchanged.
_USE_CLASS = os.getenv("LEARNOVA_USE_CLASS", "").lower() in {"1", "true", "yes", "on"}


def _segment(items: List[str], size: int, layout: str = "MINIMAL_TEXT") -> List[List[str]]:
    """Split a bullet/step list into slide-sized groups.

    Uses CLASS when ``LEARNOVA_USE_CLASS`` is set and the items are strings;
    otherwise the even ``_chunk`` rebalance. Both preserve every item and
    respect ``size`` as a hard cap.
    """
    if _USE_CLASS and items and all(isinstance(x, str) for x in items):
        try:
            from learnova.scoring.psf import segment_blocks

            groups = segment_blocks(items, max_per_slide=max(1, size), layout_type=layout)
            if groups and sum(len(g) for g in groups) == len(items):
                return groups
        except Exception:  # never let scoring math break pagination
            logger.debug("CLASS segmentation failed; falling back to _chunk", exc_info=True)
    return _chunk(items, size)

# ── Profiles ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DensityProfile:
    """Per-slide content budget for one density setting."""

    id: str
    label: str
    description: str

    max_bullets: int          # bullets before overflowing to a new slide
    max_words_per_bullet: int # a longer bullet is trimmed at a clause boundary
    max_chars_per_bullet: int # hard ceiling, protects the layout
    max_table_rows: int       # rows per table slide; header repeats on each
    max_flow_steps: int       # process cards per flowchart slide
    max_grid_cards: int       # cards in a CARD_GRID
    include_enhancement: bool # append pedagogical extras from enhancement/
    enhancement_items: int    # how many extras to append when included


PROFILES: Dict[str, DensityProfile] = {
    "low": DensityProfile(
        id="low",
        label="Low — headline only",
        description="Three short bullets per slide. Presenter-led decks where "
                    "the audience should listen, not read.",
        max_bullets=3,
        max_words_per_bullet=12,
        max_chars_per_bullet=90,
        max_table_rows=4,
        max_flow_steps=3,
        max_grid_cards=3,
        include_enhancement=False,
        enhancement_items=0,
    ),
    "medium": DensityProfile(
        id="medium",
        label="Medium — balanced (default)",
        description="Five bullets per slide with one supporting example. "
                    "Works for teaching and for self-study.",
        max_bullets=5,
        max_words_per_bullet=20,
        max_chars_per_bullet=140,
        max_table_rows=6,
        max_flow_steps=4,
        max_grid_cards=4,
        include_enhancement=True,
        enhancement_items=1,
    ),
    "heavy": DensityProfile(
        id="heavy",
        label="Heavy — study notes",
        description="Eight longer bullets plus examples, analogies and "
                    "revision points. Handouts meant to be read alone.",
        max_bullets=8,
        max_words_per_bullet=32,
        max_chars_per_bullet=220,
        max_table_rows=10,
        max_flow_steps=6,
        max_grid_cards=4,
        include_enhancement=True,
        enhancement_items=3,
    ),
}

DEFAULT_DENSITY = "medium"

# Layouts whose meaning breaks if they are split across slides.
_ATOMIC_LAYOUTS = {"METRIC", "QUIZ"}

_CLAUSE_BREAK = re.compile(r"[,;:—–]\s")


def get_profile(density: str) -> DensityProfile:
    return PROFILES.get((density or "").lower(), PROFILES[DEFAULT_DENSITY])


# ── Bullet shaping ────────────────────────────────────────────────────────────
def trim_bullet(text: str, profile: DensityProfile) -> str:
    """
    Shorten one bullet to the profile budget.

    Cuts at a clause boundary where possible so the result still reads as a
    sentence, rather than stopping mid-phrase with an ellipsis.
    """
    clean = clean_bullet(text)
    if not clean:
        return ""

    words = clean.split()
    if len(words) > profile.max_words_per_bullet:
        candidate = " ".join(words[: profile.max_words_per_bullet])
        # Prefer the last clause break inside the budget.
        breaks = list(_CLAUSE_BREAK.finditer(candidate))
        if breaks and breaks[-1].start() > len(candidate) * 0.5:
            candidate = candidate[: breaks[-1].start()]
        clean = candidate.rstrip(" ,;:—–")

    if len(clean) > profile.max_chars_per_bullet:
        cut = clean[: profile.max_chars_per_bullet]
        space = cut.rfind(" ")
        clean = (cut[:space] if space > profile.max_chars_per_bullet * 0.6 else cut).rstrip()

    return clean


def _chunk(items: List[Any], size: int) -> List[List[Any]]:
    """
    Split into pages, then rebalance so the last page is never a near-empty
    orphan.

    Strict chunking sent 5 bullets at a budget of 4 to a "(2/2)" slide holding
    one line — a whole slide, header and all, for a single sentence. Spreading
    the same items evenly gives 3+2 instead.
    """
    size = max(1, size)
    if len(items) <= size:
        return [list(items)] if items else []

    pages = -(-len(items) // size)                 # ceil
    base, extra = divmod(len(items), pages)
    out, start = [], 0
    for i in range(pages):
        take = base + (1 if i < extra else 0)
        out.append(items[start: start + take])
        start += take
    return out


def _restates(bullet: str, title: str) -> bool:
    """
    True when a bullet just repeats the slide title.

    Only fires on a near-exact match: a bullet that legitimately expands on the
    title shares words with it, and dropping those would lose real content.
    """
    strip = lambda s: re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()
    a, b = strip(bullet), strip(title)
    return bool(a) and bool(b) and (a == b or (len(a) >= 8 and a in b))


def _title_for_part(title: str, index: int, total: int) -> str:
    """Number continuation slides so the run reads as one continuous topic."""
    if total <= 1:
        return title
    base = re.sub(r"\s*\(\d+/\d+\)\s*$", "", title or "").strip()
    return f"{base} ({index + 1}/{total})"


# ── Enhancement folding ───────────────────────────────────────────────────────
def enhancement_bullets(enhanced: Any, profile: DensityProfile) -> List[str]:
    """
    Pick the most useful pedagogical extras for the chosen density.

    Ordered by teaching value: a concrete example beats an analogy, which beats
    an application, which beats a bare revision point.
    """
    if enhanced is None or not profile.include_enhancement:
        return []

    picks: List[str] = []
    for label, values in (
        ("Example", getattr(enhanced, "examples", None)),
        ("Analogy", getattr(enhanced, "analogies", None)),
        ("In practice", getattr(enhanced, "real_world_applications", None)),
        ("Watch out", getattr(enhanced, "common_mistakes", None)),
        ("Recall", getattr(enhanced, "revision_points", None)),
    ):
        for value in (values or []):
            text = str(value).strip()
            if text:
                picks.append(f"{label}: {text}")
                break                      # one per category, keeps variety
        if len(picks) >= profile.enhancement_items:
            break

    return picks[: profile.enhancement_items]


# ── Pagination ────────────────────────────────────────────────────────────────
def paginate_slide(entry: dict, profile: DensityProfile,
                   enhanced: Any = None) -> List[dict]:
    """
    Apply the density budget to one slide, splitting it if it overflows.

    Returns one or more slide entries. Every piece of content survives —
    overflow moves to a continuation slide instead of being cut.
    """
    improved = dict(entry.get("improved") or {})
    original = entry.get("original", {})
    layout = str(improved.get("layout_type", "MINIMAL_TEXT")).upper()
    title = improved.get("title", "Slide")
    takeaway = improved.get("takeaway", "")

    # Metrics and quizzes lose their meaning when split.
    if layout in _ATOMIC_LAYOUTS:
        if improved.get("bullets"):
            improved["bullets"] = [
                trim_bullet(b, profile) for b in improved["bullets"][: profile.max_bullets]
            ]
        return [{**entry, "improved": improved}]

    # ── Tables: split rows, repeat the header on every part ──────────────────
    if layout == "TABLE" and improved.get("table_rows"):
        row_pages = _chunk(list(improved["table_rows"]), profile.max_table_rows)

        # A table slide can also carry lead-in bullets. They are paginated
        # alongside the rows rather than capped — capping silently deleted
        # content, which the whole continuity contract forbids.
        lead = [trim_bullet(b, profile) for b in (improved.get("bullets") or [])]
        lead = [b for b in lead if b]
        lead_pages = _chunk(lead, profile.max_bullets) if lead else []

        total = max(len(row_pages), len(lead_pages), 1)
        out = []
        for i in range(total):
            rows = row_pages[i] if i < len(row_pages) else []
            page_bullets = lead_pages[i] if i < len(lead_pages) else []
            page = {
                **improved,
                "title": _title_for_part(title, i, total),
                "table_rows": rows,
                "bullets": page_bullets,
                "takeaway": takeaway if i == total - 1 else "",
                "continued": i > 0,
            }
            # A continuation page with no rows left is not a table. Leaving it
            # typed TABLE renders a blank slide, because the table branch has
            # nothing to draw and never falls through to the bullets.
            if not rows:
                page["layout_type"] = "MINIMAL_TEXT"
                page.pop("table_headers", None)
                page.pop("table_rows", None)
            out.append({
                **entry,
                "improved": page,
                # Only the first part keeps the figure, so it is not duplicated.
                "original": original if i == 0 else {**original, "image": None},
            })
        return out

    # ── Flowcharts: split into stages, never mid-step ────────────────────────
    if layout in {"FLOWCHART", "PROCESS_DIAGRAM"} and improved.get("bullets"):
        steps = [trim_bullet(b, profile) for b in improved["bullets"] if str(b).strip()]
        pages = _segment(steps, profile.max_flow_steps, "FLOWCHART")
        return [
            {
                **entry,
                "improved": {
                    **improved,
                    "title": _title_for_part(title, i, len(pages)),
                    "bullets": group,
                    "takeaway": takeaway if i == len(pages) - 1 else "",
                    "continued": i > 0,
                    # A partial flow must not reuse the whole-diagram mermaid.
                    **({} if len(pages) == 1 else {"mermaid_code": _partial_mermaid(group)}),
                },
                "original": original if i == 0 else {**original, "image": None},
            }
            for i, group in enumerate(pages)
        ]

    # ── Text-ish layouts: bullets, plus enhancement extras ───────────────────
    limit = profile.max_grid_cards if layout == "CARD_GRID" else profile.max_bullets

    # Dedupe before trimming: the planner sometimes emitted the slide title and
    # its own fragments as sibling bullets, which filled a card grid with three
    # restatements of the heading.
    source = dedupe_bullets(improved.get("bullets") or [])
    source = [b for b in source if not _restates(b, title)]
    bullets = [b for b in (trim_bullet(b, profile) for b in source) if b]

    for extra in enhancement_bullets(enhanced, profile):
        bullets.append(trim_bullet(extra, profile))

    if not bullets:
        return [{**entry, "improved": improved}]

    pages = _segment(bullets, limit, layout)
    return [
        {
            **entry,
            "improved": {
                **improved,
                "title": _title_for_part(title, i, len(pages)),
                "bullets": group,
                "takeaway": takeaway if i == len(pages) - 1 else "",
                "continued": i > 0,
            },
            "original": original if i == 0 else {**original, "image": None},
        }
        for i, group in enumerate(pages)
    ]


def _partial_mermaid(steps: List[str]) -> str:
    """Rebuild a mermaid chain for just the steps on this continuation slide."""
    if not steps:
        return ""
    nodes = [re.sub(r"[\[\]{}()\"|]", "", s)[:40] or "Step" for s in steps]
    chain = " --> ".join(f"P{i}[{label}]" for i, label in enumerate(nodes))
    return f"graph LR\n  {chain}"


def apply_density(deck: List[dict], density: str,
                  enhanced_by_index: Dict[int, Any] | None = None) -> List[dict]:
    """
    Apply the density profile across a whole deck.

    ``enhanced_by_index`` maps a slide's original position to its
    ``EnhancedSlide``, so pedagogical extras land on the right slide.
    """
    profile = get_profile(density)
    enhanced_by_index = enhanced_by_index or {}

    out: List[dict] = []
    for index, entry in enumerate(deck):
        out.extend(paginate_slide(entry, profile, enhanced_by_index.get(index)))

    if len(out) != len(deck):
        logger.info(
            "density '%s': %d slide(s) expanded to %d after overflow",
            profile.id, len(deck), len(out),
        )
    return out


__all__ = [
    "DensityProfile",
    "PROFILES",
    "DEFAULT_DENSITY",
    "get_profile",
    "trim_bullet",
    "paginate_slide",
    "apply_density",
    "enhancement_bullets",
]
