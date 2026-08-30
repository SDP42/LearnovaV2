"""
Enumeration detection and extraction.

The single biggest faithfulness failure in the pipeline was *content selection*:
a passage that lists "the five phases of NLP" or "seven applications" would come
out with one or two of them because the summariser scored the short list items
low and dropped them, or a 2-word item ("Machine Translation") fell below a
minimum-length filter.

Summarisation research (Maynez et al. 2020; Kryściński et al. 2020) calls this
under-generation / content-selection error, and the practical fix is the same
everywhere: treat a list-bearing span as **atomic** — pull out the complete
item set deterministically, and never let scoring, length filters or the LLM
touch its membership. This module does the pulling; callers do the enforcing.

`extract_enumerations(text)` returns a list of `Enumeration`:

    Enumeration(lead="The five phases of NLP", items=[...], kind="phases",
                claimed_count=5, style="numbered")

with `items` verbatim and de-duplicated, order preserved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ── number words, for "the five phases …" ────────────────────────────────────
_NUM_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

# Plural head nouns that introduce a teaching enumeration.
_KIND_RE = (
    r"phases?|stages?|steps?|levels?|types?|kinds?|categories|category|classes|"
    r"components?|elements?|parts?|layers?|methods?|techniques?|approaches?|"
    r"applications?|advantages?|benefits?|disadvantages?|limitations?|"
    r"drawbacks?|features?|properties|principles?|rules?|factors?|"
    r"characteristics?|examples?|kinds?|forms?|models?|algorithms?|tasks?"
)

# "There are five phases:"  /  "NLP has 5 stages -"  /  "The 4 types of X are:"
_CLAIM_RE = re.compile(
    r"(?P<lead>(?:there\s+are|there\s+exist|has|have|the|following)\s+"
    r"(?:are\s+)?(?P<count>\d{1,2}|" + "|".join(_NUM_WORDS) + r")\s+"
    r"(?:main\s+|key\s+|basic\s+|core\s+|primary\s+|major\s+)?"
    r"(?P<kind>" + _KIND_RE + r")\b[^.:\n]*)[:.]?",
    re.IGNORECASE,
)

# "Types:" / "Applications of NLP:" style header that precedes a list.
_HEADER_RE = re.compile(
    r"^\s*(?P<lead>(?:the\s+)?(?:main\s+|key\s+|core\s+)?"
    r"(?:[\w /&'-]+\s+)?(?P<kind>" + _KIND_RE + r")(?:\s+(?:of|in|for)\s+[\w /&'-]+)?)"
    r"\s*[:：]\s*$",
    re.IGNORECASE,
)

_NUM_ITEM_RE = re.compile(r"^\s*(?:\(?(\d{1,2})[.)]\s+|([a-hA-H])[.)]\s+|[-*+•▪◦‣]\s+)(.+)$")
_INLINE_SPLIT_RE = re.compile(r"\s*(?:,|;| and | or |&)\s*")

# "X involves / includes / consists of / comprises  A, B and C"
_INLINE_LEAD_RE = re.compile(
    r"\b(?P<lead>[\w /&'-]{2,50}?\s+(?:involves?|includes?|consists?\s+of|"
    r"comprises?|contains?|covers?|are|namely|such\s+as|like)\s*[:—-]?)\s+"
    r"(?P<body>[A-Z][\w()'’./&\- ]+(?:\s*(?:,|;| and | or )\s*[A-Za-z(][\w()'’./&\- ]+){2,})",
)


@dataclass
class Enumeration:
    items: List[str]
    lead: str = ""
    kind: str = ""
    claimed_count: Optional[int] = None
    style: str = "list"  # numbered | bulleted | inline | header

    def is_reliable(self) -> bool:
        n = len(self.items)
        if n < 3:
            return False
        if self.claimed_count and abs(self.claimed_count - n) > 1:
            return False
        return True


def _clean_item(s: str) -> str:
    s = re.sub(r"^\s*(?:\(?\d{1,2}[.)]\s*|[a-hA-H][.)]\s*|[-*+•▪◦‣]\s*)+", "", s)
    s = re.sub(r"^\s*(?:and|or)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+(?:etc\.?|and\s+so\s+on)\s*$", "", s, flags=re.IGNORECASE)
    s = s.strip(" \t.;:-–—•")
    # Keep only the label when an item is "Label - long explanation" or
    # "Label: explanation" AND the label is short (a real enumeration item).
    m = re.match(r"^([A-Z][\w()/&'’.\- ]{1,44}?)\s*[-–—:]\s+\S", s)
    if m and len(m.group(1).split()) <= 6:
        return m.group(1).strip()
    return s


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        k = re.sub(r"[^a-z0-9]", "", it.lower())
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _numbered_run(lines: List[str], start: int) -> tuple[List[str], int]:
    """Collect a contiguous run of numbered / bulleted lines from ``start``."""
    items: List[str] = []
    i = start
    while i < len(lines):
        m = _NUM_ITEM_RE.match(lines[i])
        if not m:
            # allow a wrapped continuation line to attach to the last item
            if items and lines[i].strip() and not lines[i].startswith("#"):
                items[-1] = f"{items[-1]} {lines[i].strip()}"
                i += 1
                continue
            break
        items.append(_clean_item(m.group(3)))
        i += 1
    return items, i


def extract_enumerations(text: str) -> List[Enumeration]:
    """Find every enumeration in a text block. Order-preserving, verbatim items."""
    if not text or not text.strip():
        return []
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: List[Enumeration] = []

    # ── 1. numbered / bulleted runs (≥3 lines) ──────────────────────────────
    i = 0
    while i < len(lines):
        m = _NUM_ITEM_RE.match(lines[i])
        if m:
            items, j = _numbered_run(lines, i)
            items = _dedupe([it for it in (x.strip() for x in items) if len(it) >= 2])
            if len(items) >= 3:
                lead = ""
                for k in range(i - 1, max(-1, i - 4), -1):
                    if lines[k].strip():
                        lead = lines[k].strip().rstrip(":.")
                        break
                style = "numbered" if re.match(r"^\s*\(?\d", lines[i]) else "bulleted"
                out.append(Enumeration(items=items, lead=lead, style=style,
                                       kind=_kind_from(lead)))
            i = max(j, i + 1)
            continue
        i += 1

    # ── 2. "N <kind>" claim sentences (inline or followed by a list) ────────
    for cm in _CLAIM_RE.finditer(text):
        count = cm.group("count").lower()
        n = _NUM_WORDS.get(count, None) or (int(count) if count.isdigit() else None)
        kind = cm.group("kind").lower()
        tail = text[cm.end(): cm.end() + 400]
        # items right after the claim: "X, Y, Z and W" on the same/next lines
        inline = tail.split(".")[0]
        cand = [_clean_item(c) for c in _INLINE_SPLIT_RE.split(inline)]
        cand = [c for c in cand if 1 <= len(c.split()) <= 8 and c[:1].isalpha()]
        cand = _dedupe(cand)
        if n and len(cand) >= max(3, n - 1):
            out.append(Enumeration(items=cand[:n + 1] if n else cand,
                                   lead=cm.group("lead").strip(), kind=kind,
                                   claimed_count=n, style="inline"))

    # ── 2b. "X involves A, B and C" inline lists (no count claim) ───────────
    for lm in _INLINE_LEAD_RE.finditer(text):
        parts = [_clean_item(p) for p in _INLINE_SPLIT_RE.split(lm.group("body"))]
        parts = _dedupe([p for p in parts
                         if p and p[:1].isalpha() and 1 <= len(p.split()) <= 6])
        if len(parts) >= 3:
            out.append(Enumeration(items=parts, lead=lm.group("lead").strip(" :—-"),
                                   kind=_kind_from(lm.group("lead")), style="inline"))

    # ── 2c. plain block of short Title-Case lines (markers stripped by the
    #        chunker) — a bare list like the "Applications of NLP" slide ─────
    run: List[str] = []

    def _flush_run():
        cand = _dedupe([_clean_item(x) for x in run])
        cand = [c for c in cand if 1 <= len(c.split()) <= 7 and c[:1].isalpha()]
        titleish = sum(1 for c in cand if c[:1].isupper())
        if len(cand) >= 3 and titleish >= 0.7 * len(cand):
            out.append(Enumeration(items=cand, style="list", kind=""))

    for ln in lines:
        s = re.sub(r"\s+(?:etc\.?|and\s+so\s+on\.?)\s*$", "", ln.strip(), flags=re.IGNORECASE)
        looks_item = bool(s) and 1 <= len(s.split()) <= 8 and not s.endswith((".", "!", "?")) \
            and not s.startswith("#") and len(s) <= 60
        if looks_item:
            run.append(s)
        else:
            if len(run) >= 3:
                _flush_run()
            run = []
    if len(run) >= 3:
        _flush_run()

    # ── 3. "Kind:" header immediately followed by short lines ───────────────
    for idx, ln in enumerate(lines):
        hm = _HEADER_RE.match(ln)
        if not hm:
            continue
        block: List[str] = []
        for nxt in lines[idx + 1: idx + 14]:
            s = nxt.strip()
            if not s or s.startswith("#"):
                if block:
                    break
                continue
            block.append(_clean_item(s))
        block = _dedupe([b for b in block if 2 <= len(b) and len(b.split()) <= 12])
        if len(block) >= 3:
            out.append(Enumeration(items=block, lead=hm.group("lead").strip(),
                                   kind=hm.group("kind").lower(), style="header"))

    # de-duplicate whole enumerations (same item set)
    uniq: List[Enumeration] = []
    seen_sets = []
    for e in out:
        key = frozenset(re.sub(r"[^a-z0-9]", "", x.lower()) for x in e.items)
        if key in seen_sets or not key:
            continue
        seen_sets.append(key)
        uniq.append(e)
    return uniq


def _kind_from(lead: str) -> str:
    m = re.search(_KIND_RE, lead or "", re.IGNORECASE)
    return m.group(0).lower() if m else ""


def missing_items(enum: Enumeration, covered_text: str) -> List[str]:
    """Enumeration items whose content words are not already in ``covered_text``."""
    blob = re.sub(r"[^a-z0-9 ]", " ", (covered_text or "").lower())
    blob_words = set(blob.split())
    out = []
    for it in enum.items:
        w = {x for x in re.sub(r"[^a-z0-9 ]", " ", it.lower()).split() if len(x) > 2}
        if not w or len(w & blob_words) < max(1, 0.6 * len(w)):
            out.append(it)
    return out


__all__ = ["Enumeration", "extract_enumerations", "missing_items"]
