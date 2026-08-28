"""
Extractive, LLM-free content structuring.

When no API key is configured the old fallback dumped raw sentences onto slides
(title mashed into the first bullet, most of the paragraph lost, prose wrongly
routed to FLOWCHART). This module does a real job without a model:

* clean the chunk (strip a leading heading line, normalise whitespace);
* segment into sentences;
* score sentences (content-word frequency à la TextRank-lite + position + title
  overlap), so the important ones survive;
* **decide whether to summarise at all** — a short definitional passage is kept
  almost verbatim; a long narrative one is compressed;
* compress each kept sentence into a tight bullet (drop discourse markers,
  unwrap "It is / This means", trim at a clause boundary);
* pick a high-yield takeaway.

Deterministic. No network. Used by ``ai/improver.py`` on the no-provider path.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple

_WORD = re.compile(r"[A-Za-z][A-Za-z\-']+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])[\"'”’)\]]?\s+(?=[A-Z0-9“\"'(])")

_STOP = frozenset("""
a an the this that these those there here it its it's they them their we our you your
he she his her him i me my mine ours yours theirs
and or but nor so yet for as if than then thus hence also too very
is are was were be been being am do does did doing done have has had having
will would shall should can could may might must ought
of to in on at by from with about against between into through during before after
above below up down out off over under again further once
not no only own same such just now which who whom whose what where when why how
each any all both few more most other some per via etc
""".split())

# Sentence-leading discourse markers to drop when compressing a bullet.
_LEAD_MARKERS = re.compile(
    r"^\s*(?:"
    r"it (?:is|was) (?:important to note|worth noting|clear|evident|also) that|"
    r"note that|"
    r"in other words|that is to say|"
    r"as (?:a|the) result|as such|consequently|therefore|thus|hence|"
    r"in addition|additionally|moreover|furthermore|"
    r"however|nevertheless|nonetheless|on the other hand|"
    r"for (?:instance|example)|for this reason|"
    r"in (?:fact|general|particular|essence|short|summary)|"
    r"basically|essentially|fundamentally|generally speaking|"
    r"this means (?:that)?|this (?:is|shows|implies|indicates) (?:that)?|"
    r"there(?:fore)? (?:is|are|exists?)"
    r")\b[\s,:-]*",
    re.I,
)

# "X is defined as / is the process of ... Y"  ->  keep from the head noun.
_COPULA_UNWRAP = re.compile(
    r"^\s*(?:the |a |an )?[\w \-]{1,40}? (?:is|are) (?:the |a |an )?"
    r"(?:process|study|measure|method|technique|approach|way|means|"
    r"type|kind|form|result|concept|idea|term|system) (?:of|for|by|that)\s+",
    re.I,
)

# Sentence-leading pronoun + light verb — drop it, keep the predicate.
_PRONOUN_LEAD = re.compile(
    r"^\s*(?:it|this|that|these|those|they|there)\s+"
    r"(?:is|are|was|were|consists? of|contains?|includes?|has|have|had|"
    r"means|refers to|allows?|enables?|involves?|requires?|provides?)\s+",
    re.I,
)

# Trailing / mid relative clause we can drop when over budget.
_REL_CLAUSE = re.compile(r",?\s+(?:which|who|where|that)\s+.*$", re.I)

_ORDINAL = re.compile(
    r"\b(?:step\s*\d|first(?:ly)?[,: ]|second(?:ly)?[,: ]|third(?:ly)?[,: ]|"
    r"fourth[,: ]|then\b|next\b|finally\b|stage\s*\d|phase\s*\d)", re.I)


def _clean_chunk(text: str, title: str) -> str:
    """Strip a leading line that just repeats the heading, then normalise."""
    t = (text or "").strip()
    title_norm = re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).strip()
    lines = t.splitlines()
    while lines:
        first = re.sub(r"[^a-z0-9 ]", "", lines[0].lower()).strip()
        if first and title_norm and (first == title_norm or first in title_norm):
            lines.pop(0)
        elif not lines[0].strip():
            lines.pop(0)
        else:
            break
    t = " ".join(lines)
    # A markdown list survives as newlines; keep those as sentence breaks.
    t = re.sub(r"\s*\n\s*[-*+]\s+", ". ", "\n".join(lines))
    t = re.sub(r"\s+", " ", t).strip()
    # OCR blocks the pipeline appends in [brackets] — drop the wrapper noise.
    t = re.sub(r"\[(?:Extracted OCR|OCR Transcription)[^\]]*\]", "", t)
    return t.strip()


def split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    out: List[str] = []
    for p in parts:
        p = p.strip(" .;:")
        if len(p.split()) >= 3:
            out.append(p if p.endswith((".", "!", "?")) else p + ".")
    return out


def _content_words(s: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(s) if w.lower() not in _STOP and len(w) > 2]


def _score_sentences(sentences: List[str], title: str) -> List[float]:
    freq: Counter = Counter()
    for s in sentences:
        freq.update(_content_words(s))
    if not freq:
        return [1.0] * len(sentences)
    peak = max(freq.values())
    norm = {w: c / peak for w, c in freq.items()}
    title_terms = set(_content_words(title))

    scores = []
    n = len(sentences)
    for i, s in enumerate(sentences):
        cw = _content_words(s)
        if not cw:
            scores.append(0.0)
            continue
        base = sum(norm.get(w, 0) for w in cw) / math.sqrt(len(cw))
        if i < 2:
            base *= 1.25                       # lead bias
        if i == n - 1 and n > 3:
            base *= 1.1                        # closing sentence often summarises
        if title_terms & set(cw):
            base *= 1.15
        wc = len(s.split())
        if wc > 34:
            base *= 0.85                       # very long sentences are unwieldy
        elif wc < 6:
            base *= 0.8
        scores.append(base)
    return scores


def compress_bullet(sentence: str, target_words: int = 16) -> str:
    s = sentence.strip()
    s = _LEAD_MARKERS.sub("", s, count=1)
    s = _PRONOUN_LEAD.sub("", s, count=1)
    s = _COPULA_UNWRAP.sub("", s, count=1)
    s = re.sub(r"\s+", " ", s).strip(" ,;:.")
    s = (s[:1].upper() + s[1:]) if s else s

    if len(s.split()) > target_words:
        # first, try dropping a relative clause
        trimmed = _REL_CLAUSE.sub("", s).strip(" ,;:")
        if target_words * 0.5 <= len(trimmed.split()) <= target_words + 4:
            s = trimmed

    words = s.split()
    if len(words) > target_words + 3:
        head = " ".join(words[: target_words + 3])
        m = list(re.finditer(r"[,;:]\s", head))
        if m and m[-1].start() > len(head) * 0.5:
            head = head[: m[-1].start()]
        s = head.rstrip(" ,;:")
    return s


def _should_summarise(sentences: List[str], text: str) -> bool:
    """Keep short definitional passages almost verbatim; summarise the rest."""
    wc = len(text.split())
    if len(sentences) <= 3 and wc <= 60:
        return False
    if re.search(r"\bis defined as\b|\brefers to\b|\bmeans that\b", text, re.I) and len(sentences) <= 4:
        return False
    return True


def heuristic_layout(text: str, bullets: List[str]) -> str:
    """Conservative: only route to a structure when the text really has one."""
    joined = " ".join(bullets) if bullets else text
    lower = joined.lower()
    ordinals = len(_ORDINAL.findall(lower))
    if ordinals >= 3 or re.search(r"step\s*1\b.*step\s*2\b", lower, re.S):
        return "FLOWCHART"
    if re.search(r"\bvs\.?\b|\bversus\b|\bcompared? (?:to|with)\b|\bwhereas\b", lower):
        return "TABLE"
    if len(re.findall(r"\b\d{1,3}(?:\.\d+)?\s?%|\b\d+\s?(?:percent)\b", lower)) >= 3:
        return "TABLE"
    if len(re.findall(r"\b\d{1,3}(?:\.\d+)?\s?%", lower)) == 1 and len(joined.split()) < 40:
        return "METRIC"
    labelled = sum(1 for b in bullets if re.match(r"^[A-Z][\w /&.\-]{1,32}:\s", b))
    if labelled >= 3:
        return "CARD_GRID"
    return "MINIMAL_TEXT"


_LIST_LINE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+\S")


def _list_items(text: str, title: str) -> List[str]:
    """
    If the chunk is already a list, return its items (never summarise those).

    Covers explicit markdown bullets AND the chunker's output, which strips the
    markers but keeps one item per line.
    """
    title_norm = re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).strip()
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 3:
        return []

    marked = [ln for ln in lines if _LIST_LINE.match(ln)]
    explicit = len(marked) >= 3 and len(marked) >= 0.6 * len(lines)

    # Implicit list: each line is one short statement (few sentence terminators,
    # not a flowing paragraph).
    def _one_statement(ln: str) -> bool:
        core = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", ln)
        return len(re.findall(r"[.!?](?:\s|$)", core)) <= 1 and 3 <= len(core.split()) <= 40

    implicit = sum(_one_statement(ln) for ln in lines) >= max(3, 0.7 * len(lines))

    if not (explicit or implicit):
        return []

    items = []
    for ln in lines:
        it = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", ln).strip(" .;:")
        it_norm = re.sub(r"[^a-z0-9 ]", "", it.lower()).strip()
        if it and it_norm != title_norm and len(it.split()) >= 3:
            items.append(it)
    return items


def structure_chunk(text: str, title: str = "", *,
                    max_bullets: int = 5, target_words: int = 16) -> dict:
    """The no-LLM replacement for a layout-router result."""
    # A chunk that is already a bulleted list is kept whole — the pipeline's
    # "content is never dropped" contract. We only lightly tidy each item.
    listed = _list_items(text, title)
    if listed:
        bullets = []
        seen: set = set()
        for it in listed:
            b = _LEAD_MARKERS.sub("", it, count=1).strip(" .;:") or it
            b = (b[:1].upper() + b[1:]) if b else b
            k = re.sub(r"[^a-z0-9 ]", "", b.lower())[:55]
            if k not in seen:
                seen.add(k)
                bullets.append(b)
        layout = heuristic_layout(" ".join(bullets), bullets)
        out = {
            "layout_type": layout,
            "title": (title or "Overview").strip(),
            "bullets": bullets,
            "takeaway": "",
            "verbatim": bullets,
            "visual_source": "extractive",
        }
        if layout == "FLOWCHART":
            nodes = [re.sub(r'[\[\]{}()"|]', "", b)[:34].strip() or "Step" for b in bullets[:6]]
            out["mermaid_code"] = "graph TD\n  " + " --> ".join(f"N{i}[{n}]" for i, n in enumerate(nodes))
        return out

    clean = _clean_chunk(text, title)
    sentences = split_sentences(clean)

    if not sentences:
        body = clean[:240].strip()
        return {
            "layout_type": "MINIMAL_TEXT",
            "title": (title or "Overview").strip(),
            "bullets": [body] if body else [],
            "takeaway": "",
        }

    scores = _score_sentences(sentences, title)
    summarise = _should_summarise(sentences, clean)

    top = max(range(len(sentences)), key=lambda i: scores[i])

    if summarise:
        n_keep = min(max_bullets, max(3, round(len(sentences) * 0.6)))
        ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
        # The single best sentence becomes the takeaway; the rest are bullets.
        keep = sorted(r for r in ranked[: n_keep + 1] if r != top)[:n_keep]
    else:
        keep = list(range(len(sentences)))

    seen: set = set()
    bullets: List[str] = []
    for i in keep:
        b = compress_bullet(sentences[i], target_words) if summarise else sentences[i].rstrip(".")
        key = re.sub(r"[^a-z0-9 ]", "", b.lower())[:55]
        if b and key not in seen and len(b.split()) >= 3:
            seen.add(key)
            bullets.append(b)

    takeaway = ""
    if summarise and len(bullets) >= 2:
        cand = compress_bullet(sentences[top], 22)
        if cand and re.sub(r"[^a-z0-9]", "", cand.lower())[:40] not in {
            re.sub(r"[^a-z0-9]", "", b.lower())[:40] for b in bullets
        }:
            takeaway = cand

    layout = heuristic_layout(clean, bullets)

    result = {
        "layout_type": layout,
        "title": (title or bullets[0][:60] if bullets else "Overview").strip(),
        "bullets": bullets or [clean[:240]],
        "takeaway": takeaway,
        "verbatim": [] if summarise else bullets,
        "visual_source": "extractive",
    }
    if layout == "FLOWCHART":
        nodes = [re.sub(r'[\[\]{}()"|]', "", b)[:34].strip() or "Step" for b in bullets[:6]]
        result["mermaid_code"] = "graph TD\n  " + " --> ".join(
            f"N{i}[{lbl}]" for i, lbl in enumerate(nodes)
        )
    return result


__all__ = ["structure_chunk", "compress_bullet", "split_sentences", "heuristic_layout"]
