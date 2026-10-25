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

MAX_WORDS = 90      # visible words per slide before it is split
MIN_PART = 35       # a trailing fragment shorter than this is merged back
SHORT_WORDS = 30    # below this a slide counts as "short" and gets enrichment
HARD_CAP = 130      # self-correction: nothing may exceed this


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


def _group(sents: List[str]) -> List[List[str]]:
    groups: List[List[str]] = []
    cur: List[str] = []
    cw = 0
    for s in sents:
        w = _wc(s)
        shift = False
        if cur and cw >= 45:
            recent = set(_content_words(" ".join(cur[-3:])))
            shift = _jaccard(recent, set(_content_words(s))) < 0.06
        if cur and (cw + w > MAX_WORDS or shift):
            groups.append(cur)
            cur, cw = [], 0
        cur.append(s)
        cw += w
    if cur:
        if groups and cw < MIN_PART:
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


def plan_slides(entries: List[dict]) -> int:
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
        groups = _group(sents) if words > MAX_WORDS else [sents]
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
        if len(groups) >= 3:  # a map of the parts, placed before them
            ov = copy.deepcopy(entry)
            lines = [f"{heading_for(l) if len(l.split()) > 4 else l}: {' '.join(g[0].split()[:16])}" for l, g in zip(labels[:6], groups[:6])]
            ov["original"]["text"] = "\n".join(lines)
            ov["improved"] = {"layout_type": "MINIMAL_TEXT", "title": _unique(f"{base}: overview", used), "bullets": lines, "takeaway": "",
                              "verbatim": [], "is_overview": True}
            out.insert(len(out) - len(groups), ov)
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
