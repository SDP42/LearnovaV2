"""
Discourse relations from cue phrases — how each sentence relates to the one before it.

Rhetorical-structure work (RST; slide generation from discourse structure, Shibata & Kurohashi 2005) shows that
connectives such as *however*, *because*, *for example* signal how sentences relate, and that slides should keep
related sentences together and show the relationship. Detection here is deliberately simple and deterministic: a
cue phrase at the start of a sentence (or a strong one inside it) assigns a relation.

Relations: contrast · cause · result · example · addition · sequence · purpose · concession · elaboration · none
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

_CUES: List[Tuple[str, re.Pattern]] = [
    ("contrast", re.compile(r"\b(however|but|whereas|while|unlike|in contrast|on the other hand|instead|rather than|conversely|yet)\b", re.I)),
    ("concession", re.compile(r"\b(although|though|even though|despite|in spite of|nevertheless|nonetheless|still)\b", re.I)),
    ("result", re.compile(r"\b(therefore|thus|hence|consequently|as a result|so that|which means|for this reason|accordingly)\b", re.I)),
    ("cause", re.compile(r"\b(because|since|due to|owing to|as it|as they|this is why|which is why|given that)\b", re.I)),
    ("example", re.compile(r"\b(for example|for instance|e\.g\.|such as|like|including|in particular|namely)\b", re.I)),
    ("sequence", re.compile(r"\b(first(?:ly)?|second(?:ly)?|third(?:ly)?|next|then|after that|afterwards|finally|lastly|subsequently|before)\b", re.I)),
    ("purpose", re.compile(r"\b(in order to|so as to|to ensure|to allow|to enable|to avoid|aims? to|designed to|intended to)\b", re.I)),
    ("addition", re.compile(r"\b(also|moreover|furthermore|in addition|additionally|as well as|besides|similarly|likewise)\b", re.I)),
    ("elaboration", re.compile(r"^(this|these|those|such|it|they|its|their|that is|in other words|specifically|more precisely)\b", re.I)),
]
# at the *start* of a sentence these are decisive; elsewhere only the strongest cues count
_STRONG_INSIDE = {"contrast": r"\b(whereas|while|unlike|however)\b", "cause": r"\b(because|due to)\b", "result": r"\b(therefore|thus|hence|so that)\b",
                  "example": r"\b(for example|for instance|such as|e\.g\.)\b", "purpose": r"\b(in order to|so as to)\b",
                  "concession": r"\b(although|though|despite)\b"}


def relation(sentence: str) -> Tuple[str, str]:
    """(relation, connective) for one sentence; ('none', '') when no cue is found."""
    s = sentence.strip()
    head = s[:48]
    for name, rx in _CUES:
        m = rx.match(head) or (rx.search(head) if name != "elaboration" else None)
        if m and m.start() <= 14:
            return name, m.group(0)
    for name, pat in _STRONG_INSIDE.items():
        m = re.search(pat, s, re.I)
        if m:
            return name, m.group(0)
    return "none", ""


def analyze(sentences: List[str]) -> List[Dict[str, str]]:
    """One {rel, cue} per sentence; the first sentence is the topic (no relation to a previous one)."""
    out = []
    for i, s in enumerate(sentences):
        rel, cue = ("none", "") if i == 0 else relation(s)
        out.append({"rel": rel, "cue": cue})
    return out


def cue_spans(sentence: str) -> List[Tuple[int, int, str]]:
    """Character spans of connectives inside a sentence, for highlighting: [(start, end, relation)]."""
    spans: List[Tuple[int, int, str]] = []
    for name, rx in _CUES:
        if name == "elaboration":
            continue
        for m in rx.finditer(sentence):
            if len(m.group(0)) >= 3 and not any(a <= m.start() < b for a, b, _ in spans):
                spans.append((m.start(), m.end(), name))
    return sorted(spans)
