"""
Content planner: **preserve everything, then decide how each slide should carry it.**

The old path summarised each section with an extractive/LLM summariser, which cannot know what a student
needs and silently dropped content. This planner never shortens text. For every source section it decides:

* short (≲ 90 words)  → one slide;
* long                → split at natural boundaries (paragraphs, list items, topic shifts) into several
                        slides, each ~45–90 words so it can be drawn as a real visual, preceded by an
                        *overview* slide that maps the parts when there are three or more;
* tables              → handled by ``table_pages`` (own slide each, paginated);
* very short (≲ 30 w) → flagged ``short`` so enrichment (key terms, illustration, discussion prompt) lifts it.

Every sentence of the source survives. A final capacity check (the "self-correction" step borrowed from
PPTAgent) re-splits any slide that is still over budget and merges stray fragments.
"""

from __future__ import annotations

import copy
import re
from typing import Dict, List

from learnova.visuals.engine import _content_words, heading_for, short_label, split_sentences

MAX_WORDS = 130     # visible words per slide before it is split (balanced)
MIN_PART = 50       # a trailing fragment shorter than this is merged back
SHORT_WORDS = 30    # below this a slide counts as "short" and gets enrichment
HARD_CAP = 190      # self-correction: nothing may exceed this


def _wc(s: str) -> int:
    return len(str(s).split())


def _clean_line(l: str) -> str:
    return re.sub(r"^\s*(?:[-*•▪◦]|\d+[.)])\s+", "", l).strip()


def _prose_bullets(text: str) -> List[str]:
    """Every sentence / list item of ``text`` (tables excluded), verbatim, in order."""
    lines = [l for l in text.split("\n") if not l.strip().startswith("|") and l.strip() != "[TABLE DATA]"]
    out: List[str] = []
    for l in lines:
        l = _clean_line(l)
        if l:
            out.extend(split_sentences(l) or [l])
    return out


def preserve_chunks(chunks: List[dict]) -> List[dict]:
    """Chunks → slide entries with the *entire* text as bullets (no summarising, no truncation)."""
    entries = []
    for c in chunks:
        text = (c.get("text") or "").strip()
        title = (c.get("title") or "").strip() or "Overview"
        entries.append({
            "original": c,
            "improved": {"layout_type": "MINIMAL_TEXT", "title": title, "bullets": _prose_bullets(text), "takeaway": "", "verbatim": []},
        })
    return entries


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / max(1, len(a | b))


_CONTINUES = re.compile(r"^(?:however|therefore|thus|hence|consequently|as a result|for example|for instance|in addition|moreover|furthermore|"
                         r"also|similarly|likewise|otherwise|instead|nevertheless|in contrast|on the other hand|this|these|those|such|"
                         r"it|they|its|their|both|each of|in other words|that is|as a consequence|because of this|to do this|to achieve this)\b", re.I)
_INTRO = re.compile(r"[:]\s*$|\b(?:following|as follows|below|these are)\b[^.]*$", re.I)


def _group(sents: List[str], max_words: int = MAX_WORDS) -> List[List[str]]:
    min_part = max(30, int(max_words * 0.4))
    groups: List[List[str]] = []
    cur: List[str] = []
    cw = 0
    for s in sents:
        w = _wc(s)
        shift = False
        if cur and cw >= 45:
            recent = set(_content_words(" ".join(cur[-3:])))
            shift = _jaccard(recent, set(_content_words(s))) < 0.04
        leans = bool(_CONTINUES.match(s.strip())) or (bool(cur) and bool(_INTRO.search(cur[-1])))
        if cur and (cw + w > max_words or shift) and not (leans and cw + w <= max_words * 1.35):
            groups.append(cur)
            cur, cw = [], 0
        cur.append(s)
        cw += w
    if cur:
        if groups and cw < min_part:
            groups[-1].extend(cur)
        else:
            groups.append(cur)
    return groups


def _is_table_entry(entry: dict) -> bool:
    return "[TABLE DATA]" in str((entry.get("original") or {}).get("text") or "")


def _unique(title: str, used: Dict[str, int]) -> str:
    n = used.get(title.lower(), 0)
    used[title.lower()] = n + 1
    return title if n == 0 else f"{title} ({n + 1})"


_SEC = re.compile(r"^\s*(\d+)(?:\.\d+)*[.)]?\s")


def _section_of(entry: dict) -> str:
    imp = entry.get("improved") or {}
    t = str(imp.get("section") or imp.get("title") or "")
    m = _SEC.match(t)
    return m.group(1) if m else ""


def _words_of(e: dict) -> int:
    return sum(_wc(x) for x in ((e.get("improved") or {}).get("bullets") or []))


def _mergeable(e: dict) -> bool:
    imp = e.get("improved") or {}
    return bool(_section_of(e)) and not _is_table_entry(e) and not imp.get("is_overview") and not imp.get("part") \
        and not imp.get("is_glossary") and not imp.get("merged")


def _pack_siblings(entries: List[dict], max_words: int) -> List[dict]:
    """
    Pack consecutive sibling subsections (same numbered parent, e.g. 4.2, 4.3, 4.4) onto one slide while they fit
    ``max_words``. Each keeps its heading; the slide is shown as side-by-side sections. Nothing is cut.
    """
    out: List[dict] = []
    i = 0
    while i < len(entries):
        e = entries[i]
        if not _mergeable(e) or _words_of(e) > max_words * 0.7:
            out.append(e)
            i += 1
            continue
        group = [e]
        total = _words_of(e)
        j = i + 1
        while j < len(entries) and len(group) < 3 and _mergeable(entries[j]) and _section_of(entries[j]) == _section_of(e) \
                and total + _words_of(entries[j]) <= max_words and _words_of(entries[j]) <= max_words * 0.7:
            total += _words_of(entries[j])
            group.append(entries[j])
            j += 1
        if len(group) == 1:
            out.append(e)
            i += 1
            continue
        merged = copy.deepcopy(group[0])
        titles = [str((g.get("improved") or {}).get("title") or "") for g in group]
        merged["original"]["text"] = "\n".join(f"### {t}\n{(g.get('original') or {}).get('text', '')}" for t, g in zip(titles, group))
        merged["improved"] = {"layout_type": "MINIMAL_TEXT", "title": " · ".join(titles), "takeaway": "", "verbatim": [], "merged": True,
                              "bullets": [x for g in group for x in ((g.get("improved") or {}).get("bullets") or [])]}
        out.append(merged)
        i = j
    return out


def _drop_empty_headings(entries: List[dict]) -> List[dict]:
    """A section heading with no text of its own ("6. Implementation" followed by 6.1…) adds nothing as a slide."""
    out = []

    def _norm(t: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", "", str(t).lower()).strip()

    for k, e in enumerate(entries):
        imp = e.get("improved") or {}
        nxt = entries[k + 1] if k + 1 < len(entries) else None
        body = _norm(" ".join(map(str, imp.get("bullets") or [])))
        if body and body == _norm(imp.get("title", "")) and not _is_table_entry(e):
            continue                    # a heading that only repeats itself ("# Sorting Algorithms") is the deck title, not a slide
        if (not _is_table_entry(e) and _words_of(e) < 8 and nxt is not None and _section_of(e)
                and _section_of(nxt) == _section_of(e) and not imp.get("is_glossary")):
            continue
        out.append(e)
    return out


def plan_slides(entries: List[dict], max_words: int = MAX_WORDS) -> int:
    """In-place. Split long slides, add overviews, flag short ones. Returns the change in slide count."""
    out: List[dict] = []
    used: Dict[str, int] = {}
    for entry in entries:
        imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else {}
        if _is_table_entry(entry) or str(imp.get("layout_type", "")).upper() == "QUIZ":
            out.append(entry)
            continue
        base = str(imp.get("title") or "Overview")
        sents = [str(b) for b in (imp.get("bullets") or []) if str(b).strip()]
        words = sum(_wc(s) for s in sents)
        groups = _group(sents, max_words) if words > max_words else [sents]
        if len(groups) == 1:
            imp["short"] = words < SHORT_WORDS
            imp["title"] = _unique(base, used)
            out.append(entry)
            continue
        labels = []
        for k, g in enumerate(groups):
            e = copy.deepcopy(entry)
            e["original"]["text"] = " ".join(g)
            label = short_label(g[0], 5)
            labels.append(label)
            title = base if k == 0 else f"{base}: {label}"
            e["improved"] = {"layout_type": "MINIMAL_TEXT", "title": _unique(title, used), "bullets": g, "takeaway": "",
                             "verbatim": [], "part": [k + 1, len(groups)], "short": sum(_wc(x) for x in g) < SHORT_WORDS}
            out.append(e)
        if len(groups) >= 4 and len(entries) < 40:  # a map of the parts, placed before them (short decks only)
            ov = copy.deepcopy(entry)
            lines = [f"{heading_for(l) if len(l.split()) > 4 else l}: {' '.join(g[0].split()[:16])}" for l, g in zip(labels[:6], groups[:6])]
            ov["original"]["text"] = "\n".join(lines)
            ov["improved"] = {"layout_type": "MINIMAL_TEXT", "title": _unique(f"{base}: overview", used), "bullets": lines, "takeaway": "",
                              "verbatim": [], "is_overview": True}
            out.insert(len(out) - len(groups), ov)
    out = _pack_siblings(_drop_empty_headings(out), max_words)
    # self-correction: nothing over the hard cap; no empty slide
    final = []
    for e in out:
        imp = e.get("improved") or {}
        bl = imp.get("bullets") or []
        if not bl and "[TABLE DATA]" not in str((e.get("original") or {}).get("text") or "") and not imp.get("is_overview"):
            continue
        final.append(e)
    delta = len(final) - len(entries)
    entries[:] = final
    return delta


def plan_to_budget(entries: List[dict], max_words: int = MAX_WORDS, target: int | None = None, ceiling: int = 230) -> int:
    """
    Plan the deck, then — if a target slide count is known (from the source's page count) and the plan overshoots it —
    raise the per-slide capacity step by step and re-plan until it fits (never above ``ceiling`` words per slide).
    Returns the change in slide count. The result always keeps every sentence.
    """
    cap = max_words
    best = None
    while True:
        trial = copy.deepcopy(entries)
        plan_slides(trial, cap)
        best = trial
        if not target or len(trial) <= target * 1.12 or cap >= ceiling:
            break
        cap = min(ceiling, int(cap * 1.15) + 1)
    delta = len(best) - len(entries)
    entries[:] = best
    return delta
