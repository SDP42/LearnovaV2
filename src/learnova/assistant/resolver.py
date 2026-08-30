"""
Reference resolution (spec §4, §5, §21, §38).

``resolve_presentation_reference`` turns any of

    "LRN-PRES-0002"                direct id
    "presentation 2" / "deck 2"    display number
    "the second presentation"      ordinal position
    "the RSA presentation"         title / partial title
    "the one about social eng…"    description / tags
    "the second one"               index into the last result list (context)
    "the one we looked at earlier" current / previous presentation (context)

into a :class:`Resolution` — either a single confident match, several
candidates needing a clarification question, or nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from learnova.assistant.ids import is_pres_id
from learnova.assistant.registry import PresentationEntry, _tokens

_ORDINALS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "last": -1, "latest": -1,
    "newest": -1, "most recent": -1, "final": -1,
}


@dataclass
class Resolution:
    status: str                       # "resolved" | "ambiguous" | "not_found" | "empty"
    entry: Optional[PresentationEntry] = None
    candidates: List[PresentationEntry] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"


def _score(entry: PresentationEntry, q_tokens: set, phrase: str) -> float:
    hay = " ".join([entry.title.lower(), entry.subject.lower(),
                    entry.topic.lower(), " ".join(entry.tags),
                    " ".join(entry.aliases)])
    if phrase and phrase in hay:
        return 1.0
    e_tokens = set(_tokens(entry.title) + _tokens(entry.subject)
                   + _tokens(entry.topic) + entry.tags
                   + [t for a in entry.aliases for t in _tokens(a)])
    if not q_tokens or not e_tokens:
        return 0.0
    overlap = len(q_tokens & e_tokens)
    return overlap / len(q_tokens)


def resolve_presentation_reference(
    reference: str,
    entries: List[PresentationEntry],
    *,
    result_list: Optional[List[PresentationEntry]] = None,
    current: Optional[PresentationEntry] = None,
    previous: Optional[PresentationEntry] = None,
) -> Resolution:
    ref = (reference or "").strip()
    low = ref.lower()
    if not entries:
        return Resolution("empty", reason="no presentations exist yet")
    if not ref:
        if current:
            return Resolution("resolved", current, confidence=0.7,
                              reason="current presentation (no reference given)")
        return Resolution("not_found", reason="no reference and no active presentation")

    # 1. direct permanent id
    if is_pres_id(ref):
        for e in entries:
            if e.pres_id == ref.upper():
                return Resolution("resolved", e, confidence=1.0, reason="pres_id")
        return Resolution("not_found", reason=f"{ref} does not exist")

    # 2. context words
    if re.search(r"\b(earlier|before|previous|last one|that one|it)\b", low) \
            and not re.search(r"\bslide\b", low):
        if current:
            return Resolution("resolved", current, confidence=0.75, reason="context: current")
        if previous:
            return Resolution("resolved", previous, confidence=0.7, reason="context: previous")

    # 3. "the Nth one" against the last result list
    m = re.search(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|"
                  r"ninth|tenth|last|latest|newest|\d+)(?:\s+one)?\b", low)
    ord_word = m.group(1) if m else None
    if ord_word and result_list:
        idx = _ORDINALS.get(ord_word, None)
        if idx is None and ord_word.isdigit():
            idx = int(ord_word)
        if idx is not None:
            pick = result_list[-1] if idx == -1 else (
                result_list[idx - 1] if 1 <= idx <= len(result_list) else None)
            if pick:
                return Resolution("resolved", pick, confidence=0.85,
                                  reason="ordinal into last result list")

    by_num = sorted(entries, key=lambda e: e.display_number)

    # 4. explicit display number ("presentation 2", "deck no. 2", "number two")
    num = None
    m = re.search(r"\b(?:presentation|deck|slide\s*deck|ppt|number|no\.?|#)\s*"
                  r"(\d{1,3})\b", low) or re.search(r"^\s*(\d{1,3})\s*$", low)
    if m:
        num = int(m.group(1))
    else:
        m = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b", low)
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        if m and re.search(r"\b(presentation|deck|number|open|show|launch|start|"
                           r"go to|goto)\b", low):
            num = words[m.group(1)]
    if num is not None:
        for e in by_num:
            if e.display_number == num:
                return Resolution("resolved", e, confidence=0.95, reason="display number")
        return Resolution("not_found",
                          reason=f"there is no presentation {num} (you have {len(entries)})")

    # 5. ordinal position ("the second presentation", "the last one")
    if ord_word and re.search(r"\b(presentation|deck|one)\b", low):
        idx = _ORDINALS.get(ord_word)
        if idx is None and ord_word.isdigit():
            idx = int(ord_word)
        if idx is not None:
            pick = by_num[-1] if idx == -1 else (
                by_num[idx - 1] if 1 <= idx <= len(by_num) else None)
            if pick:
                return Resolution("resolved", pick, confidence=0.8, reason="ordinal position")

    # 6. title / description / tag match
    phrase = re.sub(
        r"\b(open|show|launch|start|get|give me|take me to|go to|the|please|"
        r"can you|could you|i want|bring up|web deck|deck|presentation|slides?"
        r"|interactive|version|about|on|for)\b", " ", low).strip()
    q_tokens = set(_tokens(phrase or low))
    scored = sorted(((_score(e, q_tokens, phrase), e) for e in entries),
                    key=lambda x: x[0], reverse=True)
    top = [(s, e) for s, e in scored if s >= 0.5]
    if len(top) == 1:
        return Resolution("resolved", top[0][1], confidence=min(0.95, 0.6 + top[0][0] * 0.35),
                          reason="title/description match")
    if len(top) >= 2 and top[0][0] - top[1][0] >= 0.34:
        return Resolution("resolved", top[0][1], confidence=0.8,
                          reason="best of several title matches")
    if len(top) >= 2:
        return Resolution("ambiguous", candidates=[e for _, e in top[:5]],
                          confidence=0.4,
                          reason=f"{len(top)} presentations match {phrase!r}")
    # weak single hit
    if scored and scored[0][0] >= 0.34:
        return Resolution("resolved", scored[0][1], confidence=0.55,
                          reason="weak title match")
    return Resolution("not_found", reason=f"nothing matches {reference!r}")


__all__ = ["Resolution", "resolve_presentation_reference"]
