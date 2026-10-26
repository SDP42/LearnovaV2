"""
Slide geometry and text fitting.

Every position in the deck used to be a hardcoded inch value, so a card held
the same box whether it carried three words or forty — short text floated in
a mostly empty rectangle, long text overflowed its edges.

This module computes geometry from the content instead:

* ``fit_font_size`` picks the largest point size at which the text still fits.
* ``grid_cells`` lays N cards out in a wrapping grid, sized to the area.
* ``content_band`` shrinks the body area when a takeaway or an inline quiz
  band is present, so nothing is drawn on top of anything else.

The measurement is an estimate, not a real text engine — PowerPoint does the
final shaping. It is deliberately conservative (assumes slightly wider glyphs
than average) so the error lands on "a bit small" rather than "overflowing".
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

# ── Canvas ────────────────────────────────────────────────────────────────────
SLIDE_W = 13.33
SLIDE_H = 7.5

MARGIN_X = 0.5
HEADER_H = 1.1
CONTENT_TOP = 1.42          # header (1.1) + accent strip (0.07) + 0.25 breathing room
BOTTOM_MARGIN = 0.5         # content stops here; the footer band sits below it
FOOTER_Y = 7.08             # footer text box top (height FOOTER_H) — identical on every slide
FOOTER_H = 0.3

# One grid for the whole deck: every card, box and text inset uses these.
PAD = 0.22                  # internal padding of every card / box
GUTTER = 0.22               # gap between neighbouring cards
ICON_D = 0.62               # icon disc diameter
BADGE_D = 0.5               # number / letter badge diameter

TAKEAWAY_H = 1.0
QUIZ_BAND_H = 2.05          # question line + a row of four options
GAP = 0.22

# Typography bounds. Below MIN_PT text stops being readable from the back of a
# room, so we paginate instead of shrinking further.
MAX_BODY_PT = 22.0
MIN_BODY_PT = 11.0
MAX_CARD_PT = 18.0
MIN_CARD_PT = 9.0

# Average glyph width as a fraction of point size, and line height multiplier.
_GLYPH_RATIO = 0.52
_BOLD_RATIO = 0.575
_LINE_HEIGHT = 1.26


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float


def content_band(has_takeaway: bool = True, has_quiz: bool = False) -> Box:
    """The usable body area, after the header, takeaway and quiz bands."""
    top = CONTENT_TOP
    bottom = SLIDE_H - BOTTOM_MARGIN
    if has_quiz:
        bottom -= QUIZ_BAND_H + GAP
    if has_takeaway:
        bottom -= TAKEAWAY_H + GAP
    return Box(MARGIN_X, top, SLIDE_W - 2 * MARGIN_X, max(1.0, bottom - top))


def quiz_band(has_takeaway: bool = True) -> Box:
    """Where the inline quiz sits: directly above the takeaway bar."""
    bottom = SLIDE_H - BOTTOM_MARGIN
    if has_takeaway:
        bottom -= TAKEAWAY_H + GAP
    return Box(MARGIN_X, bottom - QUIZ_BAND_H, SLIDE_W - 2 * MARGIN_X, QUIZ_BAND_H)


def takeaway_band() -> Box:
    bottom = SLIDE_H - BOTTOM_MARGIN
    return Box(MARGIN_X, bottom - TAKEAWAY_H, SLIDE_W - 2 * MARGIN_X, TAKEAWAY_H)


# ── Measurement ───────────────────────────────────────────────────────────────
def estimate_lines(text: str, width_in: float, font_pt: float, bold: bool = False) -> int:
    """How many wrapped lines a string needs in a box of the given width (word-aware)."""
    if not text:
        return 0
    ratio = _BOLD_RATIO if bold else _GLYPH_RATIO
    cpl = max(1, int((width_in * 72.0) / (font_pt * ratio)))
    lines = 0
    for paragraph in str(text).splitlines() or [""]:
        cur, n = 0, 1
        for word in paragraph.split():
            wl = len(word)
            if wl > cpl:                      # an over-long word breaks across lines
                if cur:
                    n += 1
                n += (wl - 1) // cpl
                cur = wl % cpl or cpl
            elif cur == 0:
                cur = wl
            elif cur + 1 + wl <= cpl:
                cur += 1 + wl
            else:
                n += 1
                cur = wl
        lines += n
    return max(1, lines)


def block_height(texts: Sequence[str], width_in: float, font_pt: float,
                 spacing_pt: float = 8.0, bold: bool = False) -> float:
    """Height in inches needed to render these paragraphs at this size."""
    total_lines = sum(estimate_lines(t, width_in, font_pt, bold) for t in texts)
    line_in = (font_pt * _LINE_HEIGHT) / 72.0
    gaps_in = (max(0, len(texts) - 1) * spacing_pt) / 72.0
    return total_lines * line_in + gaps_in


def paras_height(paras: Sequence[Tuple[str, float, bool, float]], width_in: float) -> float:
    """Height of mixed paragraphs given as ``(text, size_pt, bold, space_before_pt)``."""
    total = 0.0
    for i, (text, size, bold, before) in enumerate(paras):
        if not str(text).strip():
            continue
        total += estimate_lines(str(text), width_in, size, bold) * size * _LINE_HEIGHT / 72.0
        if i:
            total += before / 72.0
    return total


# Advance widths (em) of printable ASCII (32–126) in DejaVu Sans — a deliberately wide sans, so a word that fits here (with the margin
# below) fits in Poppins, Inter, Calibri or whichever face the viewer's machine substitutes.
_W_REG = (
    0.318, 0.401, 0.460, 0.838, 0.636, 0.950, 0.780, 0.275, 0.390, 0.390, 0.500, 0.838,
    0.318, 0.361, 0.318, 0.337, 0.636, 0.636, 0.636, 0.636, 0.636, 0.636, 0.636, 0.636,
    0.636, 0.636, 0.337, 0.337, 0.838, 0.838, 0.838, 0.531, 1.000, 0.684, 0.686, 0.698,
    0.770, 0.632, 0.575, 0.775, 0.752, 0.295, 0.295, 0.656, 0.557, 0.863, 0.748, 0.787,
    0.603, 0.787, 0.695, 0.635, 0.611, 0.732, 0.684, 0.989, 0.685, 0.611, 0.685, 0.390,
    0.337, 0.390, 0.838, 0.500, 0.500, 0.613, 0.635, 0.550, 0.635, 0.615, 0.352, 0.635,
    0.634, 0.278, 0.278, 0.579, 0.278, 0.974, 0.634, 0.612, 0.635, 0.635, 0.411, 0.521,
    0.392, 0.634, 0.592, 0.818, 0.592, 0.592, 0.525, 0.636, 0.337, 0.636, 0.838,
)
_W_BOLD = (
    0.348, 0.456, 0.521, 0.838, 0.696, 1.002, 0.872, 0.306, 0.457, 0.457, 0.523, 0.838,
    0.380, 0.415, 0.380, 0.365, 0.696, 0.696, 0.696, 0.696, 0.696, 0.696, 0.696, 0.696,
    0.696, 0.696, 0.400, 0.400, 0.838, 0.838, 0.838, 0.580, 1.000, 0.774, 0.762, 0.734,
    0.830, 0.683, 0.683, 0.821, 0.837, 0.372, 0.372, 0.775, 0.637, 0.995, 0.837, 0.850,
    0.733, 0.850, 0.770, 0.720, 0.682, 0.812, 0.774, 1.103, 0.771, 0.724, 0.725, 0.457,
    0.365, 0.457, 0.838, 0.500, 0.500, 0.675, 0.716, 0.593, 0.716, 0.678, 0.435, 0.716,
    0.712, 0.343, 0.343, 0.665, 0.343, 1.042, 0.712, 0.687, 0.716, 0.716, 0.493, 0.595,
    0.478, 0.712, 0.652, 0.924, 0.645, 0.652, 0.582, 0.712, 0.365, 0.712, 0.838,
)

_WORD_FIT = 1.06                      # Verdana (what LibreOffice and many viewers substitute for a missing face) runs ~4% wider than DejaVu
_SOFT_BREAK = re.compile(r"(?<=[-\u2010-\u2014/])")          # PowerPoint wraps after a hyphen or slash


def _pieces(text: str) -> List[str]:
    """Unbreakable runs of characters: words, further split where a hyphen or slash allows a line break."""
    return [piece for word in str(text).split() for piece in _SOFT_BREAK.split(word) if piece]


def word_width_in(piece: str, font_pt: float, bold: bool = False) -> float:
    """Width of one unbreakable word in inches, measured glyph by glyph (so "Homonyms" is wider than "illicit" of equal length)."""
    table = _W_BOLD if bold else _W_REG
    em = sum(table[ord(ch) - 32] if 32 <= ord(ch) <= 126 else (0.78 if bold else 0.70) for ch in piece)
    return em * font_pt * _WORD_FIT / 72.0


def longest_word_fits(texts: Sequence[str], width_in: float, font_pt: float, bold: bool = False) -> bool:
    return all(word_width_in(w, font_pt, bold) <= width_in for t in texts for w in _pieces(t))


def word_scale(paras: Sequence[Tuple[str, float, bool]], width_in: float, floor: float = 0.62) -> float:
    """Factor (≤1) by which every paragraph must shrink so no unbreakable word is wider than the box."""
    scale = 1.0
    for text, size, bold in paras:
        for piece in _pieces(text):
            need = word_width_in(piece, size, bold)
            if need > width_in > 0:
                scale = min(scale, width_in / need)
    return max(floor, scale)


def fit_font_size(texts: Sequence[str], width_in: float, height_in: float,
                  max_pt: float = MAX_BODY_PT, min_pt: float = MIN_BODY_PT,
                  spacing_pt: float = 8.0, bold: bool = False) -> float:
    """
    Largest point size at which ``texts`` fit inside the given box.

    Steps down in half points and stops at ``min_pt`` — the caller has already
    decided this much content belongs on one slide, so we never go smaller
    than legible.
    """
    items = [t for t in texts if str(t).strip()]
    if not items:
        return max_pt

    size = max_pt
    while size > min_pt:
        if block_height(items, width_in, size, spacing_pt, bold) <= height_in and \
                longest_word_fits(items, width_in, size, bold):
            return round(size, 1)
        size -= 0.5
    return min_pt


# ── Card grids ────────────────────────────────────────────────────────────────
def grid_cells(count: int, area: Box, gap: float = 0.22,
               max_per_row: int = 4) -> List[Box]:
    """
    Lay out ``count`` cards inside ``area``, wrapping into rows.

    A single row of six cards leaves each one too narrow to read, so past
    ``max_per_row`` the grid wraps and uses the vertical space instead.
    """
    if count <= 0:
        return []

    columns = min(count, max_per_row)
    rows = math.ceil(count / columns)
    # Balance the last row: 5 items become 3+2, not 4+1.
    if rows > 1:
        columns = math.ceil(count / rows)

    cell_w = (area.width - gap * (columns - 1)) / columns
    cell_h = (area.height - gap * (rows - 1)) / rows

    cells: List[Box] = []
    for index in range(count):
        row, col = divmod(index, columns)
        cells.append(Box(
            left=area.left + col * (cell_w + gap),
            top=area.top + row * (cell_h + gap),
            width=cell_w,
            height=cell_h,
        ))
    return cells


def split_text_image(area: Box, has_image: bool,
                     image_fraction: float = 0.38) -> Tuple[Box, Box]:
    """Split the body into a text column and an image column."""
    if not has_image:
        return area, Box(0, 0, 0, 0)
    image_w = area.width * image_fraction
    text_w = area.width - image_w - GAP
    return (
        Box(area.left, area.top, text_w, area.height),
        Box(area.left + text_w + GAP, area.top, image_w, area.height),
    )


__all__ = [
    "SLIDE_W", "SLIDE_H", "MARGIN_X", "HEADER_H", "CONTENT_TOP",
    "TAKEAWAY_H", "QUIZ_BAND_H", "GAP", "BOTTOM_MARGIN", "FOOTER_Y", "FOOTER_H",
    "PAD", "GUTTER", "ICON_D", "BADGE_D", "paras_height", "longest_word_fits",
    "MAX_BODY_PT", "MIN_BODY_PT", "MAX_CARD_PT", "MIN_CARD_PT",
    "Box", "content_band", "quiz_band", "takeaway_band",
    "estimate_lines", "block_height", "fit_font_size",
    "grid_cells", "split_text_image",
]
