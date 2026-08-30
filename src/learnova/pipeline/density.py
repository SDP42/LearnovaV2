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
one continuous thought. Every part carries the topic's takeaway bar — a reader
landing on part 2 in isolation still gets the key point.
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

# When set, a bullet is never shortened at all — the full sentence the source
# had is kept, and layout fitting is left to the renderer's auto-scaling. Useful
# for study handouts and worked examples where the reasoning IS the content.
_VERBOSE_BULLETS = os.getenv("LEARNOVA_VERBOSE_BULLETS", "").lower() in {"1", "true", "yes", "on"}


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
        label="Medium — teaching (default)",
        description="A study/lecture slide, not a keynote slide: every source "
                    "point kept near-verbatim as a full teaching sentence. The "
                    "web deck auto-fits the font and reveals one point per "
                    "click; a slide only splits past ~16 points / ~300 words.",
        # Research note: the '6x6' / 'few words' rules are for *narrated* talks
        # (Mayer's redundancy principle). A read-at-your-own-pace teaching deck
        # is governed by the coherence principle (cut extraneous, keep
        # essential) and by SEGMENTING + progressive disclosure — not deletion.
        # A teaching bullet is a whole sentence (~20-45 words); a slide holds as
        # many as the topic needs. So the budget is generous and the real
        # density lever is presentation (font fit, reveal, columns, a visual).
        max_bullets=16,
        max_words_per_bullet=55,     # only a genuine run-on is tightened
        max_chars_per_bullet=440,
        max_table_rows=14,
        max_flow_steps=10,
        max_grid_cards=8,
        include_enhancement=True,
        enhancement_items=1,
    ),
    "teaching": DensityProfile(
        id="teaching",
        label="Teaching — explain every step",
        description="Every point kept as a full sentence with its reasoning. "
                    "One idea revealed per click. Best for typed lesson notes "
                    "and worked examples.",
        max_bullets=14,
        max_words_per_bullet=60,
        max_chars_per_bullet=480,
        max_table_rows=12,
        max_flow_steps=12,
        max_grid_cards=8,
        include_enhancement=True,
        enhancement_items=2,
    ),
    "heavy": DensityProfile(
        id="heavy",
        label="Heavy — study notes",
        description="Full study handout: every sentence, plus examples, "
                    "analogies and revision points. Meant to be read alone.",
        max_bullets=22,
        max_words_per_bullet=70,
        max_chars_per_bullet=520,
        max_table_rows=18,
        max_flow_steps=14,
        max_grid_cards=8,
        include_enhancement=True,
        enhancement_items=3,
    ),
}

DEFAULT_DENSITY = "medium"

# Layouts whose meaning breaks if they are split across slides.
_ATOMIC_LAYOUTS = {"METRIC", "QUIZ"}

_CLAUSE_BREAK = re.compile(r"[,;:—–]\s")

# A bullet that carries its own reasoning ("... because ...", "first ... then ...")
# earns a wider budget before it is split — the connective clause is the point.
_REASONING_CUE = re.compile(
    r"\b(because|since|so that|in order to|which means|this means|as a result|"
    r"therefore|hence|thus|so the|the reason|this is why|note that|"
    r"first(?:ly)?|then|next|finally|step \d|begin by|start by)\b", re.I,
)


def get_profile(density: str) -> DensityProfile:
    return PROFILES.get((density or "").lower(), PROFILES[DEFAULT_DENSITY])


# ── Bullet shaping ────────────────────────────────────────────────────────────
def split_bullet(text: str, profile: DensityProfile,
                 preserve: bool = False) -> List[str]:
    """
    Shape one bullet to the profile budget **without ever discarding text**.

    A bullet within budget comes back as a single-item list. A longer one is
    split at clause boundaries into a head plus continuation fragments (each
    prefixed ``↳ `` so it reads as a sub-point) — so the tail of an explanation
    moves to its own line instead of being clipped off and lost.

    ``preserve`` (or ``LEARNOVA_VERBOSE_BULLETS``) returns the whole cleaned
    sentence untouched.
    """
    clean = clean_bullet(text)
    if not clean:
        return []
    if preserve or _VERBOSE_BULLETS:
        return [clean]

    # A reasoning bullet keeps 1.5x the word budget before it is worth splitting.
    slack = 1.5 if _REASONING_CUE.search(clean) else 1.0
    word_budget = int(profile.max_words_per_bullet * slack)
    char_budget = int(profile.max_chars_per_bullet * slack)

    within_words = len(clean.split()) <= word_budget
    within_chars = len(clean) <= char_budget
    if within_words and within_chars:
        return [clean]

    def _fits(s: str) -> bool:
        return (len(s.split()) <= word_budget and len(s) <= char_budget)

    # Break the sentence into clauses and regroup them into budget-sized pieces.
    parts = [p.strip(" ,;:—–") for p in _CLAUSE_BREAK.split(clean) if p.strip(" ,;:—–")]

    if len(parts) > 1:
        chunks: List[str] = []
        buf = ""
        for part in parts:
            candidate = f"{buf}, {part}" if buf else part
            if _fits(candidate):
                buf = candidate
            else:
                if buf:
                    chunks.append(buf)
                buf = part
        if buf:
            chunks.append(buf)
        parts = chunks or [clean]

    # Any piece still over budget (a long clause, or the no-clause case) is cut
    # by words/chars and its remainder kept as the next fragment — nothing is
    # dropped, it just moves to its own line.
    pieces: List[str] = []
    queue = list(parts)
    while queue:
        seg = queue.pop(0).strip()
        if not seg:
            continue
        if _fits(seg) or len(pieces) > 8:
            pieces.append(seg)
            continue
        words = seg.split()
        head = " ".join(words[: word_budget])
        if len(head) > char_budget:
            cut = head[: char_budget].rsplit(" ", 1)[0]
            head = cut or head[: char_budget]
        rest = seg[len(head):].strip(" ,;:—–")
        pieces.append(head)
        if rest:
            queue.insert(0, rest)

    if not pieces:
        return [clean[: char_budget]]
    return [pieces[0]] + [p if p.startswith("↳") else f"↳ {p}" for p in pieces[1:]]


def trim_bullet(text: str, profile: DensityProfile) -> str:
    """Back-compat single-string shaper: the head piece of :func:`split_bullet`."""
    pieces = split_bullet(text, profile)
    return pieces[0] if pieces else ""


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


def _should_preserve(improved: dict) -> bool:
    """
    True when this slide's wording must not be shortened — mirrors the Deck
    Director's PRESERVE directive (``rendering/deck_director.choose_summary_directive``)
    but computed here, before the director runs, so the density stage can honour
    it. Fires when a large share of the slide's sentences are precision-critical
    (definitions, laws, quotations, formulae).
    """
    try:
        from learnova.ai.text_policy import classify_sentences

        parts = [str(improved.get("title", ""))]
        parts += [str(b) for b in (improved.get("bullets") or [])]
        parts.append(str(improved.get("takeaway", "")))
        sents = classify_sentences(" ".join(p for p in parts if p))
        if not sents:
            return False
        # VERBATIM sentences count fully; KEEP_REASONING sentences count half —
        # a slide that is mostly either should not be shortened.
        weight = sum(
            1.0 if s.treatment == "VERBATIM"
            else 0.5 if s.treatment == "KEEP_REASONING"
            else 0.0
            for s in sents
        )
        return weight / len(sents) >= 0.4
    except Exception:
        return False


def _restates(bullet: str, title: str) -> bool:
    """
    True when a bullet just repeats the slide title.

    Only fires on a near-exact match: a bullet that legitimately expands on the
    title shares words with it, and dropping those would lose real content.
    """
    strip = lambda s: re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()
    a, b = strip(bullet), strip(title)
    return bool(a) and bool(b) and (a == b or (len(a) >= 8 and a in b))


def _base_title(title: str) -> str:
    return re.sub(r"\s*\(\d+/\d+\)\s*$", "", title or "").strip()


def _title_for_part(title: str, index: int, total: int) -> str:
    """Number continuation slides so the run reads as one continuous topic."""
    if total <= 1:
        return title
    return f"{_base_title(title)} ({index + 1}/{total})"


def _renumber_runs(deck: List[dict]) -> List[dict]:
    """After drops/folds/dedupe, re-number each run of consecutive same-base
    slides so the labels are contiguous ('(2/15)' with no '(1/15)' looks
    broken). A run of one loses its counter entirely."""
    i = 0
    n = len(deck)
    while i < n:
        base = _base_title(str((deck[i].get("improved") or {}).get("title", "")))
        j = i
        while j < n and _base_title(
            str((deck[j].get("improved") or {}).get("title", ""))
        ) == base and (j == i or (deck[j].get("improved") or {}).get("continued")):
            j += 1
        run = j - i
        for k in range(i, j):
            im = dict(deck[k].get("improved") or {})
            im["title"] = base if run == 1 else f"{base} ({k - i + 1}/{run})"
            deck[k] = {**deck[k], "improved": im}
        i = j
    return deck


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

    # MASTER_PROMPT: a sentence is never trimmed for length. For every teaching
    # profile we keep bullets whole (the renderer wraps / auto-fits / paginates)
    # — only "low" (deliberate headline mode) may split a run-on into ↳ lines.
    preserve = profile.id != "low" or _should_preserve(improved)

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
        lead = [p for b in (improved.get("bullets") or [])
                for p in split_bullet(b, profile, preserve)]
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
                "takeaway": takeaway,  # every part keeps the topic's key point
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
        steps = [p for b in improved["bullets"] if str(b).strip()
                 for p in split_bullet(b, profile, preserve)]
        pages = _segment(steps, profile.max_flow_steps, "FLOWCHART")
        return [
            {
                **entry,
                "improved": {
                    **improved,
                    "title": _title_for_part(title, i, len(pages)),
                    "bullets": group,
                    "takeaway": takeaway,  # repeated on every continuation, not just the last
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
    bullets = [p for b in source for p in split_bullet(b, profile, preserve) if p]

    for extra in enhancement_bullets(enhanced, profile):
        bullets.extend(split_bullet(extra, profile, preserve))

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
                "takeaway": takeaway,  # repeated on every continuation, not just the last
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


def _real_bullets(im: dict) -> list:
    out = []
    for b in (im.get("bullets") or []):
        s = str(b).strip()
        # a lone title echo or a stray page number is not content
        if len(s.split()) >= 3 and not re.fullmatch(r"\d+\s.*", s):
            out.append(s)
    return out


def _echoes_title(bullet: str, title: str) -> bool:
    bw = set(re.findall(r"[a-z]{3,}", (bullet or "").lower()))
    tw = set(re.findall(r"[a-z]{3,}", (title or "").lower()))
    if not bw:
        return True
    return len(bw & tw) / len(bw) >= 0.6


def _has_content(improved: dict, original: dict) -> bool:
    """True when a slide has something to show — real bullets, a table, a
    metric, a diagram, a quiz, or a figure with a meaningful caption. A bare
    heading (even one with a mis-anchored decorative image) is not a slide."""
    im = improved or {}
    rb = _real_bullets(im)
    # A single bullet that is really the title again is not content.
    if len(rb) == 1 and _echoes_title(rb[0], str(im.get("title", ""))):
        rb = []
    if rb:
        return True
    if im.get("table_rows") or str(im.get("metric_value", "")).strip():
        return True
    if im.get("mermaid_code") or im.get("question") or im.get("flowchart_spec"):
        return True
    if str(im.get("takeaway", "")).strip():
        return True
    # An image-only slide survives only if its title is a real topic name, not a
    # generic label ("Course Contents:", "Section 4", "Overview").
    img = (original or {}).get("image")
    title = str(im.get("title", "")).strip().rstrip(":")
    generic = re.fullmatch(
        r"(section|page|slide|overview|contents?|course contents?|agenda|outline|index)\s*\d*",
        title, re.I,
    )
    return bool(img) and not generic


def _fold_thin_slides(deck: List[dict]) -> List[dict]:
    """Merge a slide that carries only one real point (and no visual) into the
    next slide of the same run. A lone-bullet slide scores badly and reads as
    filler; its point is better shown as the first bullet of the next slide."""
    if len(deck) < 4:  # a short deck needs every slide it has
        return deck
    out: List[dict] = []
    pending: List[str] = []
    for i, entry in enumerate(deck):
        im = entry.get("improved") or {}
        rb = _real_bullets(im)
        has_visual = bool(
            im.get("table_rows") or str(im.get("metric_value", "")).strip()
            or im.get("mermaid_code") or im.get("flowchart_spec") or im.get("question")
        )
        is_last = i == len(deck) - 1
        # Fold forward only a genuinely empty fragment. A real one-point slide
        # is kept — the web deck grows its font and gives it a visual.
        if not is_last and not rb and not has_visual:
            pending.extend(str(b) for b in (im.get("bullets") or []))
            continue
        if pending:
            merged_bullets = pending + [str(b) for b in (im.get("bullets") or [])]
            im = {**im, "bullets": merged_bullets}
            entry = {**entry, "improved": im}
            pending = []
        out.append(entry)
    if pending and out:  # trailing thin slide — attach to the last real one
        last = out[-1].get("improved") or {}
        last = {**last, "bullets": [str(b) for b in (last.get("bullets") or [])] + pending}
        out[-1] = {**out[-1], "improved": last}
    return out or deck


def _bullet_key_set(im: dict) -> set:
    out = set()
    for b in (im.get("bullets") or []):
        k = re.sub(r"[^a-z0-9]", "", str(b).lower())[:60]
        if len(k) >= 6:
            out.add(k)
    return out


def _dedupe_slides(deck: List[dict]) -> List[dict]:
    """Drop a slide whose content is already shown on an earlier one.

    The chunker merges same-heading source sections, but the LLM can still
    re-title two different sections identically, or a figure-only page can echo
    the slide before it. A slide is a duplicate when >=70% of its bullet set is
    already covered by an earlier slide. Continuation parts ("(2/4)") are never
    treated as duplicates of each other — they share a title by design.
    """
    kept: List[dict] = []
    seen: List[tuple[str, set]] = []  # (title_key, bullet_key_set) of non-continuation slides
    dropped = 0
    for entry in deck:
        im = entry.get("improved") or {}
        if im.get("continued"):
            kept.append(entry)
            continue
        bk = _bullet_key_set(im)
        tk = re.sub(r"[^a-z0-9 ]", " ", str(im.get("title", "")).lower())
        tk = re.sub(r"\s+", " ", tk).strip()
        is_dup = False
        if bk:
            for _, prev_bk in seen:
                if prev_bk and len(bk & prev_bk) >= 0.7 * len(bk):
                    is_dup = True
                    break
        if is_dup and not (im.get("table_rows") or im.get("mermaid_code") or im.get("question")):
            dropped += 1
            continue
        seen.append((tk, bk))
        kept.append(entry)
    if dropped:
        logger.info("density: dropped %d duplicate slide(s)", dropped)
    return kept


def _drop_empty_and_fold_titles(deck: List[dict]) -> List[dict]:
    """
    Drop content-less slides. If a dropped slide had a distinct heading, carry
    that heading onto the next slide as a lead line so the topic name is not
    lost. Keeps a single deliberate section divider if it is followed by real
    content under a *different* title.
    """
    out: List[dict] = []
    carried_title = None
    for entry in deck:
        im = entry.get("improved") or {}
        orig = entry.get("original") or {}
        if _has_content(im, orig):
            if carried_title and not str(im.get("title", "")).strip():
                im = {**im, "title": carried_title}
                entry = {**entry, "improved": im}
            carried_title = None
            out.append(entry)
        else:
            t = str(im.get("title", "")).strip()
            if t and not re.fullmatch(r"(section|page|slide)\s*\d+", t, re.I):
                carried_title = t
    return out


def apply_density(deck: List[dict], density: str,
                  enhanced_by_index: Dict[int, Any] | None = None) -> List[dict]:
    """
    Apply the density profile across a whole deck.

    ``enhanced_by_index`` maps a slide's original position to its
    ``EnhancedSlide``, so pedagogical extras land on the right slide.
    """
    profile = get_profile(density)
    enhanced_by_index = enhanced_by_index or {}

    # Drop whole-slide duplicates *before* pagination, so a re-titled repeat
    # can't spawn its own "(1/3)…(3/3)" run.
    deck = _dedupe_slides(deck)

    out: List[dict] = []
    for index, entry in enumerate(deck):
        out.extend(paginate_slide(entry, profile, enhanced_by_index.get(index)))

    before_drop = len(out)
    out = _drop_empty_and_fold_titles(out)
    if before_drop != len(out):
        logger.info("density: dropped %d empty slide(s)", before_drop - len(out))

    before_fold = len(out)
    out = _fold_thin_slides(out)
    if before_fold != len(out):
        logger.info("density: folded %d lone-point slide(s) forward", before_fold - len(out))

    out = _renumber_runs(out)

    if len(out) != len(deck):
        logger.info(
            "density '%s': %d slide(s) -> %d after overflow/cleanup",
            profile.id, len(deck), len(out),
        )
    return out


__all__ = [
    "DensityProfile",
    "PROFILES",
    "DEFAULT_DENSITY",
    "get_profile",
    "trim_bullet",
    "split_bullet",
    "paginate_slide",
    "apply_density",
    "enhancement_bullets",
]
