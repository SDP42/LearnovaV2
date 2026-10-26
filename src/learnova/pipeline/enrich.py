"""
Student-oriented enrichment — adds understanding without removing or inventing content.

* **Glossary** — terms the document itself defines ("X is …", "X refers to …", "Machine Learning (ML)") are
  collected across the whole deck. Every slide that *uses* a term defined elsewhere gets a "Key terms" strip with
  that definition, so a student never meets an unexplained word. A Glossary slide closes the deck.
* **Discussion prompt** — a "think about it" question chosen from the slide's visual (a process asks which step
  matters most, a comparison asks when you would pick each side…), shown in speaker notes and the web deck.
* **Optional LLM enrichment** (``ai/assist.enrich_slides``) — a worked example and extra term definitions for
  short slides, in one batched request. Nothing here needs a model.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from learnova.visuals.engine import decide, split_sentences

_DEF = [
    re.compile(r"^(?:The\s+)?([A-Z][\w\-/]*(?:\s+[\w\-/]+){0,3}?)\s+(?:is|are)\s+(?:a|an|the)\s+(.{14,170}?)[.;]?$"),
    re.compile(r"^(?:The\s+)?([A-Za-z][\w\-/]*(?:\s+[\w\-/]+){0,3}?)\s+(?:refers to|means|denotes|is defined as|is known as|is called|stands for)\s+(.{8,170}?)[.;]?$"),
]
_ACR = re.compile(r"\b([A-Z][A-Za-z\-]+(?:\s+[A-Za-z\-]+){1,4})\s+\(([A-Z]{2,8}s?)\)")
_BAD_START = {"this", "it", "there", "they", "these", "those", "we", "you", "he", "she", "that", "which", "what", "one"}


def _clip(text: str, n: int = 20) -> str:
    w = text.split()
    return " ".join(w[:n]).rstrip(",;:") + ("…" if len(w) > n else "")


def build_glossary(entries: List[dict]) -> Dict[str, Tuple[str, int]]:
    """term(lower) → (definition, slide index where it is defined)."""
    gl: Dict[str, Tuple[str, int]] = {}
    for i, e in enumerate(entries):
        imp = e.get("improved") or {}
        if str(imp.get("layout_type", "")).upper() == "QUIZ" or imp.get("is_overview"):
            continue
        text = str((e.get("original") or {}).get("text") or "")
        if "[TABLE DATA]" in text:
            continue
        for s in split_sentences(text):
            for rx in _DEF:
                m = rx.match(s.strip())
                if m:
                    term, d = m.group(1).strip(), m.group(2).strip()
                    if term.split()[0].lower() in _BAD_START or len(term) < 3 or len(term.split()) > 4:
                        continue
                    gl.setdefault(term.lower(), (f"{term}: " and _clip(d), i))
                    break
            for m in _ACR.finditer(s):
                gl.setdefault(m.group(2).lower(), (f"{m.group(1)}", i))
        if len(gl) >= 80:
            break
    return gl


def attach_key_terms(entries: List[dict], gl: Dict[str, Tuple[str, int]], per_slide: int = 2, regap: int = 12) -> int:
    """
    A term is explained where a student first meets it after its definition, then only again after ``regap`` slides —
    and a term that runs through most of the deck (its central topic) is explained once, not on every slide.
    """
    texts = [str((e.get("original") or {}).get("text") or "") for e in entries]
    n_slides = max(1, len(entries))
    freq = {t: sum(1 for x in texts if re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", x, re.I)) for t in gl}
    last_shown: Dict[str, int] = {}
    n = 0
    for i, e in enumerate(entries):
        imp = e.get("improved") or {}
        if str(imp.get("layout_type", "")).upper() == "QUIZ" or imp.get("is_glossary"):
            continue
        text = texts[i]
        if "[TABLE DATA]" in text:
            continue
        hits = []
        for term, (d, src) in gl.items():
            if src == i:  # the slide that defines it already explains it
                continue
            central = freq.get(term, 0) > 0.3 * n_slides and n_slides >= 10
            if term in last_shown and (central or i - last_shown[term] < regap):
                continue
            if re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", text, re.I):
                hits.append((len(term), term, d))
        hits.sort(reverse=True)
        chosen = hits[:per_slide]
        kt = [{"term": t if t.isupper() or len(t) < 4 else t[:1].upper() + t[1:], "definition": d} for _, t, d in chosen]
        for _, t, _ in chosen:
            last_shown[t] = i
        if kt:
            imp["key_terms"] = kt
            n += 1
    return n


def glossary_slides(entries: List[dict], gl: Dict[str, Tuple[str, int]], per_slide: int = 6, minimum: int = 4, max_terms: int = 12) -> int:
    import re as _re

    if any(_re.search(r"key terms|glossary|terminology|vocabulary|key concepts|definitions", str((e.get("improved") or {}).get("title", "")), _re.I) for e in entries):
        return 0               # the source already has its own glossary section; a second one would only repeat it
    corpus = " ".join(str((e.get("original") or {}).get("text") or "") for e in entries).lower()
    ranked = sorted(((corpus.count(t), t, d) for t, (d, _) in gl.items() if len(d.split()) >= 3), reverse=True)
    items = [(t, d) for _, t, d in ranked[:max_terms]]
    if len(items) < minimum:
        return 0
    base = entries[0] if entries else None
    if base is None:
        return 0
    import copy

    pages = [items[i:i + per_slide] for i in range(0, len(items), per_slide)]
    added = 0
    for k, page in enumerate(pages, 1):
        e = copy.deepcopy(base)
        lines = [f"{(t[:1].upper() + t[1:]) if len(t) < 30 else t[:30]}: {d}" for t, d in page]
        e["original"] = {**(e.get("original") or {}), "text": "\n".join(lines), "title": "Glossary"}
        e.get("original", {}).pop("image", None)
        e["improved"] = {"layout_type": "MINIMAL_TEXT", "title": "Glossary" if len(pages) == 1 else f"Glossary ({k}/{len(pages)})",
                         "bullets": lines, "takeaway": "", "verbatim": [], "is_glossary": True}
        entries.append(e)
        added += 1
    return added


_THINK = {
    "PROCESS_LINEAR": "Which step would break the whole process if it failed — and why?",
    "PROCESS_CYCLIC": "What would happen if the cycle stopped after the second step?",
    "TIMELINE": "Which of these events changed things the most, and why?",
    "COMPARE_TABLE": "In what situation would you choose one side over the other?",
    "COMPARE_VISUAL": "Do the advantages outweigh the trade-offs? Argue both sides.",
    "MATRIX_GRID": "Place a real example of your own in each quadrant.",
    "LAYERS": "How does each level depend on the one beneath it?",
    "FUNNEL": "Where do you lose the most — and what could you change there?",
    "STAT_TILES": "What might explain these numbers?",
    "DEFINITION": "Give one real-life example of this idea.",
    "FORMULA_CALLOUT": "What happens to the result if one of the inputs doubles?",
    "CAUSE_EFFECT": "Where could you break this chain of events?",
    "CHECKLIST": "Which of these would you do first, and why?",
    "SET_DIAGRAM": "Name one more thing that belongs in the overlap.",
    "REFERENCES": "",
}


def attach_prompts(entries: List[dict]) -> int:
    n = 0
    for e in entries:
        imp = e.get("improved") or {}
        if str(imp.get("layout_type", "")).upper() == "QUIZ" or imp.get("is_glossary"):
            continue
        text = str((e.get("original") or {}).get("text") or "")
        try:
            fam = decide(str(imp.get("title", "")), text, [str(b) for b in (imp.get("bullets") or [])]).family
        except Exception:
            fam = ""
        q = _THINK.get(fam, "Explain this slide in your own words, in one sentence.") if fam != "REFERENCES" else ""
        if q:
            imp["think"] = q
            n += 1
    return n


def enrich_deck(entries: List[dict]) -> Dict[str, int]:
    gl = build_glossary(entries)
    kt = attach_key_terms(entries, gl)
    pr = attach_prompts(entries)
    gs = glossary_slides(entries, gl)
    return {"glossary_terms": len(gl), "slides_with_terms": kt, "prompts": pr, "glossary_slides": gs}
