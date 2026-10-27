"""Deck polish from the research pass: assertion-style titles, no stranded one-liners, richer speaker notes.

Rules (from how Gamma / Copilot / Gemini / assertion-evidence guidance build decks):
* a title says something, in sentence case, never a bare "Introduction" / "Overview";
* a thin slide is merged with its own continuation instead of being blown up with bigger type;
* detail that does not fit on the slide goes to the speaker notes.
"""

from __future__ import annotations

import re
from typing import Dict, List

_GENERIC = re.compile(r"^(?:introduction|intro|overview|summary|background|conclusion|key points|details|basics|basic concepts|notes|contents?)\s*:?$", re.I)
_PART = re.compile(r"\s*\((\d+)/(\d+)\)\s*$")
_DEFINES = re.compile(r"^(?:an?|the)?\s*([A-Z][\w\- ]{2,40}?)\s+(?:is|are|means|refers to)\s+(.{12,})$")


def _words(t: str) -> int:
    return len(str(t).split())


def _sentence_case(t: str) -> str:
    """ALL-CAPS titles become sentence case; short tokens (POS, HMM, CYK) stay as acronyms."""
    if not (t.isupper() and len(t) > 4):
        return t
    from learnova.parsers.slide_pdf import _vocab

    words = _vocab()
    toks = [w if not w.isalpha() or (len(w) <= 4 and w.lower() not in words) else w.lower() for w in t.split()]
    out = " ".join(toks)
    return out[:1].upper() + out[1:]


def _clean_title(t: str) -> str:
    t = re.sub(r"^[^\w(\[“\"']+", "", t).strip()
    t = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", t, flags=re.I)          # "Features Features" → "Features"
    return _sentence_case(t.strip(" .:;"))


def _first_claim(imp: dict) -> str:
    for b in imp.get("bullets") or []:
        b = re.sub(r"\s+", " ", str(b)).strip()
        if _words(b) >= 4:
            m = _DEFINES.match(b)
            claim = (m.group(0) if m else b)
            claim = re.split(r"(?<=[.!?;:])\s", claim)[0].rstrip(".;:")
            w = claim.split()
            return " ".join(w[:12]) + ("…" if len(w) > 12 else "")
    return ""


def retitle(entries: List[dict]) -> int:
    changed = 0
    for e in entries:
        imp = e.get("improved") or {}
        if str(imp.get("layout_type", "")).upper() == "QUIZ" or imp.get("is_agenda") or imp.get("is_summary") or imp.get("is_glossary") or imp.get("is_activity"):
            continue
        old = str(imp.get("title", ""))
        m = _PART.search(old)
        base = _PART.sub("", old)
        title = _clean_title(base)
        if _GENERIC.match(title):
            claim = _first_claim(imp)
            if claim:
                title = claim
        new = f"{title} ({m.group(1)}/{m.group(2)})" if m else title
        if new and new != old:
            imp["title"] = new
            changed += 1
    return changed


def _thin(entry: dict) -> bool:
    imp, orig = entry.get("improved") or {}, entry.get("original") or {}
    if str(imp.get("layout_type", "")).upper() not in {"MINIMAL_TEXT", "TEXT", "BULLETS", "CONTENT"}:
        return False
    if orig.get("image") or imp.get("table_rows") or imp.get("illustration") or imp.get("visual_data"):
        return False
    return 0 < _words(" ".join(map(str, imp.get("bullets") or []))) < 24


def merge_thin_parts(entries: List[dict]) -> int:
    """Consecutive thin slides of one topic ("X (1/3)", "X (2/3)") become one slide, up to 6 bullets."""
    merged, i = 0, 0
    while i < len(entries) - 1:
        a, b = entries[i], entries[i + 1]
        ta, tb = str((a.get("improved") or {}).get("title", "")), str((b.get("improved") or {}).get("title", ""))
        if _thin(a) and _thin(b) and _PART.sub("", ta).strip().lower() == _PART.sub("", tb).strip().lower():
            ia, ib = a["improved"], b["improved"]
            bullets = list(ia.get("bullets") or []) + [x for x in (ib.get("bullets") or []) if x not in (ia.get("bullets") or [])]
            if len(bullets) <= 6:
                ia["bullets"] = bullets
                a["original"] = {**(a.get("original") or {}), "text": "\n".join(map(str, bullets))}
                del entries[i + 1]
                merged += 1
                continue
        i += 1
    # renumber the parts that remain
    groups: Dict[str, List[dict]] = {}
    for e in entries:
        t = str((e.get("improved") or {}).get("title", ""))
        if _PART.search(t):
            groups.setdefault(_PART.sub("", t).strip().lower(), []).append(e)
    for g in groups.values():
        for k, e in enumerate(g, 1):
            base = _PART.sub("", e["improved"]["title"])
            e["improved"]["title"] = base if len(g) == 1 else f"{base} ({k}/{len(g)})"
    return merged


_STOPW = {"with", "from", "that", "this", "what", "which", "their", "there", "these", "those", "about", "into", "over", "under", "part",
          "slide", "lecture", "module", "introduction", "overview", "example", "examples", "types", "type", "using", "based"}


def _keywords(title: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", _PART.sub("", title)) if w.lower() not in _STOPW]


def _clean_sentence(sent: str) -> bool:
    """A sentence worth showing: prose, not OCR debris, code, a list of terms or a table row."""
    if not (9 <= _words(sent) <= 32) or not re.match(r"^[A-Z“\"(]", sent) or not re.search(r"[a-z][.!?]$", sent):
        return False
    if re.search(r"[⇒→←<>|{}=_]|--|\s/\s|\b(?:wf|pos|lemma|lexsn)\b", sent):
        return False
    letters = sum(ch.isalpha() for ch in sent)
    if letters < 0.75 * len(sent.replace(" ", "")):
        return False
    return bool(re.search(r"\b(?:is|are|was|were|has|have|can|will|uses?|means?|gives?|makes?|helps?|depends?|refers?|shows?|takes?|works?|needs?|allows?|produces?)\b", sent))


def _sig(sent: str) -> str:
    return re.sub(r"[^a-z]", "", sent.lower())[:70]


def add_context(entries: List[dict], max_words: int = 25) -> int:
    """A thin slide gets ONE sentence from elsewhere in the same source that explains its topic further.

    Nothing is invented: the sentence is the document's own, it names the slide's topic, it is clean prose, and it is not
    already on the slide. It is shown as an "Also in this lecture" callout — more substance, not bigger type."""
    pool: List[tuple] = []
    for i, e in enumerate(entries):
        imp = e.get("improved") or {}
        if str(imp.get("layout_type", "")).upper() == "QUIZ":
            continue
        text = " ".join(map(str, imp.get("bullets") or []))
        for sent in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text)):
            sent = sent.strip()
            if _clean_sentence(sent):
                pool.append((i, sent))
    used: set = set()
    added = 0
    for i, e in enumerate(entries):
        imp, orig = e.get("improved") or {}, e.get("original") or {}
        if (str(imp.get("layout_type", "")).upper() == "QUIZ" or imp.get("is_agenda") or imp.get("is_summary") or imp.get("is_glossary")
                or imp.get("is_activity") or orig.get("image") or orig.get("slide_kind") in {"title", "section", "figure"}):
            continue
        on_slide = " ".join(map(str, imp.get("bullets") or []))
        if _words(on_slide) >= max_words:
            continue
        keys = _keywords(str(imp.get("title", "")))
        if not keys:
            continue
        need = 2 if len(keys) >= 3 else 1                # a long title must share two of its words, not just one
        sig_slide = _sig(on_slide)
        for j, sent in sorted(pool, key=lambda js: abs(js[0] - i)):     # nearest slides first: the same part of the lecture
            sg = _sig(sent)
            if j == i or sg in used or sg[:40] in sig_slide:
                continue
            low = sent.lower()
            hits = sum(1 for k in keys if re.search(rf"\b{re.escape(k)}", low))
            if hits >= need and (len(keys[0]) >= 5 or hits >= 2):
                imp["context"] = [sent]
                used.add(sg)
                added += 1
                break
    return added


def polish_deck(entries: List[dict]) -> Dict[str, int]:
    merged = merge_thin_parts(entries)
    return {"retitled": retitle(entries), "merged_thin": merged, "context_added": add_context(entries)}
