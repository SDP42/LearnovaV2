"""
Shared text normalisation for slide copy.

Several stages independently produced slide text and each stripped a slightly
different set of artifacts, so markdown emphasis and line-continuation escapes
leaked all the way onto rendered slides — real output read
``an **initial investment of ₹50,000**.\\ Expected **life = 5 years``.

Everything that puts words on a slide should normalise through here.
"""

from __future__ import annotations

import re
from typing import Optional

# ``**bold**``, ``__bold__``, ``*em*``, ``_em_``, ``` `code` ```
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.S)
_EM = re.compile(r"(?<!\w)[*_](?!\s)(.+?)(?<!\s)[*_](?!\w)", re.S)
_CODE = re.compile(r"`([^`]+)`")
# A backslash used as a line continuation by the markdown writers.
_ESCAPE = re.compile(r"\\+(?=\s|$)")
_LEADING_MARKER = re.compile(r"^\s*(?:[-*+•]|\d+[.)]|step\s*\d+\s*[:.\-])\s*", re.I)
_HEADING_HASH = re.compile(r"^\s*#{1,6}\s*")
# Figure-OCR wrapper (orchestrator) and its predecessors. Never belongs on a slide.
_OCR_BLOCK = re.compile(
    r"<<FIGURE_TEXT>>.*?<<END_FIGURE_TEXT>>"
    r"|\[+\s*(?:Extracted OCR|OCR Transcription|Image Diagram Content)[^\]]*\]*"
    r"|<<FIGURE_TEXT>>|<<END_FIGURE_TEXT>>",
    re.I | re.S,
)


_TOKEN = re.compile(r"[A-Za-z]+")
_WORDS: Optional[set] = None


def _english() -> set:
    """Lower-cased English words (the system dictionary), loaded once; empty when the machine has none."""
    global _WORDS
    if _WORDS is None:
        try:
            with open("/usr/share/dict/words", encoding="utf-8", errors="ignore") as fh:
                _WORDS = {w.strip().lower() for w in fh if w.strip()}
        except OSError:
            _WORDS = set()
    return _WORDS


def is_readable(text: str, min_ratio: float = 0.7) -> bool:
    """True when OCR'd text reads as language: most tokens of three or more letters are dictionary words (or, without a
    dictionary, word-like). Axis ticks and misread equations ("ara vane nnn ee M=1 tt") fail and are never shown as a caption."""
    toks = [t.lower() for t in _TOKEN.findall(text or "")]
    long_ = [t for t in toks if len(t) >= 3]
    if len(long_) < 3:
        return False
    words = _english()
    if words:
        good = sum(1 for t in long_ if t in words or t.rstrip("s") in words or t[:-2] in words and t.endswith(("ed", "ly")))
    else:
        good = sum(1 for t in long_ if re.search(r"[aeiouy]", t) and not re.search(r"(.)\1\1", t))
    noise = len(re.findall(r"[^\w\s.,;:()'\-%/]", text)) / max(1, len(text))
    short = sum(1 for t in toks if len(t) <= 2) / max(1, len(toks))
    return good / len(long_) >= min_ratio and noise <= 0.08 and short <= 0.45


def strip_ocr_block(text: str) -> str:
    """Remove any figure-OCR marker block from a chunk's text."""
    return re.sub(r"\n{3,}", "\n\n", _OCR_BLOCK.sub("", str(text or ""))).strip()


def strip_inline_markdown(text: str) -> str:
    """Remove markdown emphasis, code ticks and stray escapes from slide copy."""
    if not text:
        return ""
    out = _BOLD.sub(lambda m: m.group(1) or m.group(2) or "", str(text))
    out = _EM.sub(r"\1", out)
    out = _CODE.sub(r"\1", out)
    out = _ESCAPE.sub(" ", out)
    # Unbalanced markers survive the paired passes above, and extraction
    # routinely cuts a sentence between its opening and closing "**".
    out = re.sub(r"\*\*|__", "", out)
    # Orphan single markers, e.g. "Strategic Growth:* Helps achieve...". Only
    # strip one that touches a boundary or punctuation — an intra-word asterisk
    # is likely multiplication ("3*4") and must survive.
    out = re.sub(r"(?<![\w])[*_]+|[*_]+(?![\w])", "", out)
    return re.sub(r"\s+", " ", out).strip()


def clean_bullet(text: str) -> str:
    """Normalise one bullet: drop list markers, heading hashes and markdown."""
    if not text:
        return ""
    out = _HEADING_HASH.sub("", str(text))
    out = _LEADING_MARKER.sub("", out)
    return strip_inline_markdown(out)


def truncate_words(text: str, limit: int) -> str:
    """
    Cut to ``limit`` characters on a word boundary.

    Character-slicing produced slide text ending mid-word — "The cost of ca",
    "led to the development of Si" — which reads as a rendering fault.
    """
    clean = strip_inline_markdown(text)
    if len(clean) <= limit:
        return clean
    cut = clean[:limit]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:—–.") + "…"


def is_redundant(candidate: str, others: list[str]) -> bool:
    """
    True when ``candidate`` adds nothing beside ``others``.

    The planner emitted a title and its own fragments as sibling bullets
    ("Key Inputs for Capital Budgeting Decisions" / "Key Inputs" /
    "Capital Budgeting Decisions"), which filled a card grid with three
    restatements of the heading.
    """
    a = re.sub(r"[^a-z0-9 ]", "", (candidate or "").lower()).strip()
    if not a:
        return True
    a_words = len(a.split())
    for other in others:
        b = re.sub(r"[^a-z0-9 ]", "", (other or "").lower()).strip()
        if not b or a == b:
            return True
        contained = lambda s, t: (
            len(s) >= 4 and re.search(rf"(?:^|\s){re.escape(s)}(?:\s|$)", t)
        )
        if len(a) <= len(b):
            # Candidate is the shorter string. It is redundant only if it is a
            # bare fragment (few words, no real predicate) that the longer one
            # already contains — a title fragment, not a standalone point.
            if a_words <= 6 and contained(a, b):
                return True
        else:
            # Candidate is the LONGER string. It is redundant only if it barely
            # adds anything — a near-verbatim restatement of the shorter one.
            # A full explanatory sentence that merely *mentions* a short label
            # ("text categorization" inside "In email filtering, text
            # categorization is applied to …") is NOT redundant — it is the
            # explanation and must be kept (docs/MASTER_PROMPT.md).
            if len(a) <= len(b) + 14 and contained(b, a):
                return True
    return False


def dedupe_bullets(bullets: list[str]) -> list[str]:
    """Drop empties and restatements, preserving order."""
    kept: list[str] = []
    for raw in bullets or []:
        text = clean_bullet(raw)
        if text and not is_redundant(text, kept):
            kept.append(text)
    return kept


__all__ = [
    "strip_inline_markdown",
    "clean_bullet",
    "strip_ocr_block",
    "is_readable",
    "truncate_words",
    "is_redundant",
    "dedupe_bullets",
]
