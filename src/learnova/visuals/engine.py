"""
Content Decision Engine.

Reads a slide's content and decides **what visual it should be** and **what data
that visual needs** — deterministically, with no model and no network, so the
whole deck is decided in milliseconds and never waits on an API.

Every detector returns ``(family, variant, confidence, data, reason)`` or None.
The strongest detection wins; if nothing structural is found the slide still
gets a *lossless* visual (``KEY_POINTS``), so no slide is ever plain text.

Design rules
------------
* Lossless by default — structured visuals carry the full sentence as detail
  text, so choosing a visual never silently drops a fact.
* STEM families (plots, algorithm traces, worked examples…) are left to the
  Visual Modality Selector, which already extracts their payloads.
* "When NOT to visualise" is explicit: verbatim definitions / laws / formulae
  keep their exact wording, shown in a callout rather than a diagram.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "at", "for", "by", "with", "is", "are", "was",
         "were", "be", "been", "it", "its", "this", "that", "these", "those", "as", "from", "which", "who"}
_LEAD_CUE = re.compile(
    r"^(?:(?:step|stage|phase)\s*\d+\s*[:.\-)]?\s*|(?:first(?:ly)?|second(?:ly)?|third(?:ly)?|next|then|"
    r"finally|lastly|after that|afterwards|meanwhile|however|in addition|also|therefore|thus|hence|"
    r"as a result|consequently|furthermore|moreover)\b[,:]?\s*)", re.I)
_VERBISH = re.compile(
    r"\b(?:is|are|was|were|has|have|had|holds?|reach(?:ed|es)?|grew|grow(?:s|n)?|fell|rose|accounts?|"
    r"added|adds?|became|become|improved?|reduced?|increased?|decreased?|totall?ed|stands?|makes?|gives?|"
    r"uses?|needs?|requires?|produces?|contains?|includes?)\b", re.I)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def split_sentences(text: str) -> List[str]:
    out: List[str] = []
    for block in re.split(r"\n+", text or ""):
        block = re.sub(r"^\s*(?:[-*•▪◦]|\d+[.)])\s+", "", block.strip())
        if not block:
            continue
        out.extend(s.strip() for s in _SENT.split(block) if s.strip())
    # "A has 4, B has 7, and C has 9." → one item per clause when each carries a figure
    expanded: List[str] = []
    for s in out:
        parts = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+(?=[A-Z]\w*\s+(?:has|have|holds?|is|are)\b)", s) if p.strip()]
        if len(parts) >= 3 and sum(1 for p in parts if re.search(r"\d", p)) == len(parts) and all(_VERBISH.search(p) for p in parts):
            expanded.extend(_cap(_strip_end(p)) + "." for p in parts)
        else:
            expanded.append(s)
    # the pipeline passes the section text AND its bullets: keep each sentence once
    seen, uniq = set(), []
    for s in expanded:
        k = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


def _strip_end(s: str) -> str:
    return re.sub(r"[\s.;:,]+$", "", s.strip())


def _cap(s: str) -> str:
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def short_label(text: str, max_words: int = 6) -> str:
    """A compact heading for a sentence: leading cue and filler removed, cut at a clause break."""
    t = _LEAD_CUE.sub("", _strip_end(text))
    t = re.split(r"[;:,]| — | - |\bwhich\b|\bwhile\b|\bwhereas\b|\bbecause\b", t)[0]
    words = t.split()
    if len(words) > max_words:
        words = words[:max_words]
        while words and words[-1].lower() in _STOP:
            words.pop()
    return _cap(" ".join(words)) or _cap(_strip_end(text)[:40])


_PRON = re.compile(r"^(?:it|they|this|these|those|he|she|we|you|there)\s+(?:can|will|may|should|must|also|often|usually)?\s*", re.I)


def heading_for(sentence: str) -> str:
    """A 2–3 word heading that does not just repeat the sentence's opening words."""
    t = _PRON.sub("", _LEAD_CUE.sub("", _strip_end(sentence)))
    words = [w for w in t.split() if w]
    # prefer the first verb/noun pair: drop leading determiners
    while words and words[0].lower() in _STOP:
        words.pop(0)
    out = words[:3]
    while out and out[-1].lower() in _STOP:
        out.pop()
    return _cap(" ".join(out)) or short_label(sentence, 3)


def _content_words(s: str) -> List[str]:
    return [w for w in _WORD.findall(s.lower()) if w not in _STOP]


@dataclass
class Decision:
    family: str
    variant: str
    confidence: float
    data: Dict[str, Any]
    reason: str
    alternatives: List[Tuple[str, float]] = field(default_factory=list)
    lossless: bool = True
    takeaway: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"family": self.family, "variant": self.variant, "confidence": round(self.confidence, 2),
                "reason": self.reason, "alternatives": [(f, round(c, 2)) for f, c in self.alternatives],
                "lossless": self.lossless}


Det = Optional[Tuple[str, str, float, Dict[str, Any], str]]


# ─────────────────────────────────────────────────────────────────────────────
# Detectors
# ─────────────────────────────────────────────────────────────────────────────
_NUM = r"[$₹€£]?\s?\d[\d,]*(?:\.\d+)?\s?(?:%|percent|billion|million|thousand|trillion|bn|mn|k|m|x|×)?"
_NUM_RE = re.compile(_NUM, re.I)
_YEAR_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


_REF_NUM = re.compile(r"\b(?:tables?|figures?|fig\.?|sections?|pages?|steps?|chapters?|appendix|eq\.?|equations?|slides?)\s*\d+(?:\.\d+)*|\[\d+(?:[,\u2013-]\s*\d+)*\]|\(\d+\)", re.I)


def _numbers(s: str) -> List[str]:
    out = []
    s = _REF_NUM.sub(" ", s)  # cross-references are not quantities
    for m in _NUM_RE.finditer(s):
        t = m.group(0).strip()
        if re.fullmatch(r"\d{4}", t) and _YEAR_RE.fullmatch(t):  # a year, not a quantity
            continue
        if re.search(r"\d", t):
            out.append(t)
    return out


def _to_float(tok: str) -> Optional[float]:
    t = tok.lower().replace(",", "").replace("$", "").replace("₹", "").replace("€", "").replace("£", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group(0))
    for w, mul in (("trillion", 1e12), ("billion", 1e9), ("bn", 1e9), ("million", 1e6), ("mn", 1e6), ("thousand", 1e3)):
        if w in t:
            return v * mul
    return v


def _split_steps(sents: List[str]) -> List[str]:
    return [_strip_end(_LEAD_CUE.sub("", s)) for s in sents]


_STEP_CUES = re.compile(
    r"\b(step\s*\d|first(?:ly)?|second(?:ly)?|third(?:ly)?|next|then|finally|lastly|after that|stage\s*\d|phase\s*\d)\b", re.I)
_LOOP_CUES = re.compile(r"\b(cycle|loop|repeat(?:s|ing)?|iterat\w+|continuous(?:ly)?|recurr\w+|feedback|again and again|returns?)\b", re.I)


def det_process(title: str, sents: List[str]) -> Det:
    cued = [s for s in sents if _STEP_CUES.search(s)]
    # A procedure: ≥3 sentences with sequence cues, OR ≥4 short imperative-ish sentences that each start with a cue.
    starts = sum(1 for s in sents if _LEAD_CUE.match(s))
    body = [s for s in sents if len(s.split()) >= 3]
    # "…then X. Finally Y." with no "first": a closing cue plus ≥4 short action sentences is still a procedure
    closing = any(re.match(r"^(?:finally|lastly|in the end)\b", s, re.I) for s in sents)
    sparse_ok = closing and len(cued) >= 2 and len(body) >= 4
    if len(cued) < 3 and starts < 3 and not sparse_ok:
        return None
    if len(body) < 3:
        return None
    # Skip an intro line like "Photosynthesis happens in stages." when it has no cue and others do.
    steps = [s for s in body if _STEP_CUES.search(s) or _LEAD_CUE.match(s)] if len(cued) >= 3 and not sparse_ok else body
    if len(steps) < 3:
        return None
    blob = " ".join(sents)
    loop = bool(re.search(r"\b(cycle|loop)\b", title, re.I)) or bool(re.search(
        r"\b(cycle|loop|process|it) (?:repeats|continues|begins again|starts again)|back to the (?:start|beginning)|"
        r"repeats? (?:continuously|again|indefinitely)|the cycle continues", blob, re.I))
    stages = [{"label": short_label(s, 5), "detail": _strip_end(_LEAD_CUE.sub("", s))} for s in steps[:8]]
    conf = 0.82 + min(len(cued), 5) * 0.02
    fam = "PROCESS_CYCLIC" if loop else "PROCESS_LINEAR"
    return fam, "cycle" if fam.endswith("CYCLIC") else "flowchart", conf, {"stages": stages}, \
        f"{len(steps)} sequenced steps" + (" that repeat" if fam.endswith("CYCLIC") else "")


_PROC_TITLE = re.compile(r"\b(how|steps?|process|procedure|mak(?:e|es|ing)|work(?:s|ing)?|method|workflow|recipe|install\w*|set ?up|lifecycle|stages|guide|instructions)\b", re.I)


def det_process_implicit(title: str, sents: List[str]) -> Det:
    """A procedure told without sequence words: the title says 'how / process / steps' and the lines are short actions."""
    body = [x for x in sents if len(x.split()) >= 3]
    if not _PROC_TITLE.search(title) or not (4 <= len(body) <= 8):
        return None
    if sum(len(x.split()) for x in body) / len(body) > 20:
        return None
    stages = [{"label": short_label(x, 5), "detail": _strip_end(_LEAD_CUE.sub("", x))} for x in body[:8]]
    return "PROCESS_LINEAR", "flowchart", 0.7, {"stages": stages}, "a procedure (title + short action lines)"


def det_cycle(title: str, sents: List[str]) -> Det:
    blob = " ".join(sents) + " " + title
    if not (re.search(r"\b(cycle|loop)\b", title, re.I) or re.search(
            r"\b(?:the )?(?:cycle|loop|process) (?:repeats|continues|begins again|starts again)|back to the (?:start|beginning)|"
            r"repeats? (?:continuously|again|indefinitely)", blob, re.I)):
        return None
    items = [s for s in sents if len(s.split()) >= 3]
    # "Plan the change, do it..., check..., and act..." → one sentence enumerating a loop
    if len(items) < 3 and len(sents) >= 1:
        m = re.search(r"([A-Za-z][^.]*?(?:,\s*[^,.]+){2,}(?:,?\s*and\s+[^.]+)?)\.", sents[0])
        if m:
            parts = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1)) if p.strip()]
            parts = [p for p in parts if len(p.split()) >= 2]
            if 3 <= len(parts) <= 6:
                items = parts
    if len(items) < 3:
        return None
    stages = [{"label": short_label(s, 4), "detail": _strip_end(_LEAD_CUE.sub("", s))} for s in items[:6]]
    return "PROCESS_CYCLIC", "cycle", 0.8, {"stages": stages}, "a process that repeats"


_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE_TOK = re.compile(rf"\b(?:{_MONTH}\s+\d{{1,2}},?\s+\d{{4}}|{_MONTH}\s+\d{{4}}|1[0-9]{{3}}|20[0-9]{{2}}|\d{{1,2}}(?:st|nd|rd|th)\s+century)\b")


_CITATION = re.compile(r"\b(?:edition|ed\.|press|publications?|publisher|isbn|wiley|mcgraw|springer|pearson|elsevier|oxford|cambridge|"
                       r"o'reilly|tata|phi learning|et al|pp\.|vol\.|journal|proceedings|ieee|acm)\b", re.I)


def is_citation(line: str) -> bool:
    if re.match(r"^\s*\[\d{1,3}\]\s+\S", line) and re.search(r"\b(?:1[89]\d{2}|20\d{2})\b", line):
        return True
    return bool(_CITATION.search(line)) and bool(re.search(r"\b(?:1[89]\d{2}|20\d{2})\b|\bed(?:ition)?\b", line, re.I))


def det_timeline(title: str, sents: List[str]) -> Det:
    events = []
    if sum(1 for x in sents if is_citation(x)) >= max(2, len(sents) // 2):
        return None  # a reference list, not a history
    for s in sents:
        if is_citation(s):
            continue
        m = _DATE_TOK.search(s)
        if not m:
            continue
        date = m.group(0)
        rest = (s[:m.start()] + s[m.end():])
        rest = re.sub(r"^\s*(?:in|on|by|since|during|from|until|around|circa|c\.)\s*,?\s*", "", rest, flags=re.I)
        rest = re.sub(r"\b(?:in|on|by|since)\s*$", "", _strip_end(rest), flags=re.I)
        rest = _strip_end(re.sub(r"\s{2,}", " ", rest).strip(" ,"))
        events.append({"date": date, "title": _cap(rest) or _cap(_strip_end(s))})
    if len(events) < 3:
        return None
    return "TIMELINE", "dated", 0.9, {"events": events[:8]}, f"{len(events)} dated events"


_PRO = re.compile(r"\b(advantages?|benefits?|pros?|upsides?|strengths?|merits?|gives?|improves?|boosts?|widens?|"
                  r"saves?|increases?|enables?|reduces? (?:cost|risk)|flexib\w+|efficien\w+|low(?:er)? (?:cost|carbon))\b", re.I)
_CON = re.compile(r"\b(disadvantages?|drawbacks?|cons?|downsides?|weakness(?:es)?|limitations?|risks?|harder|isolation|"
                  r"waste|expensive|cost(?:ly)?|difficult|challenges?|blurred|accidents?|however|but)\b", re.I)


_CON_MARK = re.compile(r"^(?:however|but|unfortunately|on the (?:other hand|downside|flip side)|in contrast|the (?:main |major )?(?:drawbacks?|downsides?|disadvantages?|cons|limitations?|challenges?) (?:is|are)|(?:drawbacks?|downsides?|disadvantages?|cons)\b)", re.I)


def _con_marker_index(sents: List[str]) -> Optional[int]:
    for i, x in enumerate(sents):
        if i > 0 and _CON_MARK.search(x.strip()):
            return i
    return None


def det_pros_cons(title: str, sents: List[str]) -> Det:
    blob = " ".join(sents)
    labelled_a = re.search(r"advantages?\s*[:\-]\s*(.+?)(?=disadvantages?\s*[:\-]|drawbacks?\s*[:\-]|cons?\s*[:\-]|$)", blob, re.I | re.S)
    labelled_d = re.search(r"(?:disadvantages?|drawbacks?|cons?)\s*[:\-]\s*(.+)$", blob, re.I | re.S)
    pros: List[str] = []
    cons: List[str] = []
    if labelled_a and labelled_d:
        def items(t: str) -> List[str]:
            t = re.split(r"\.\s+(?=[A-Z])", t.strip())  # sentences
            out: List[str] = []
            for x in t:
                out += [p.strip(" .") for p in re.split(r",\s*(?:and\s+)?|\s+and\s+(?=[a-z]{3,}\s)", x) if len(p.strip(" .").split()) >= 2]
            return [_cap(p) for p in out]
        pros, cons = items(labelled_a.group(1)), items(labelled_d.group(1))
    elif _con_marker_index(sents) is not None and 1 <= _con_marker_index(sents) <= len(sents) - 1:
        k = _con_marker_index(sents)
        pros = [_cap(_strip_end(_LEAD_CUE.sub("", x))) for x in sents[:k]]
        cons = [_cap(_strip_end(_LEAD_CUE.sub("", x))) for x in sents[k:]]
        if len(sents) < 3:
            return None
    else:
        mode = "pro"
        for s in sents:
            has_pro, has_con = bool(_PRO.search(s)), bool(_CON.search(s))
            if re.search(r"^(?:however|but|on the other hand|in contrast)\b|disadvantage|drawback|downside|\bcons?\b", s, re.I):
                mode = "con"
            elif re.search(r"advantage|benefit|\bpros?\b|upside", s, re.I):
                mode = "pro"
            side = mode
            if has_con and not has_pro:
                side = "con"
            elif has_pro and not has_con:
                side = "pro"
            (pros if side == "pro" else cons).append(_cap(_strip_end(_LEAD_CUE.sub("", s))))
        # need genuine signal on both sides
        if sum(1 for s in sents if _PRO.search(s)) < 1 or sum(1 for s in sents if _CON.search(s)) < 2:
            return None
    if len(pros) < 1 or len(cons) < 1 or len(pros) + len(cons) < 3:
        return None
    return "COMPARE_VISUAL", "pros_cons", 0.84, {"pros": pros[:6], "cons": cons[:6]}, "advantages vs drawbacks of one thing"


def _subjects_from_title(title: str) -> Optional[Tuple[str, str]]:
    m = re.split(r"\s+(?:vs\.?|versus|compared (?:to|with)|and|or|v)\s+", title.strip(), maxsplit=1, flags=re.I)
    if len(m) != 2:
        return None
    a, b = m[0].strip(), m[1].strip()
    return (a.split()[0], b.split()[0]) if a and b else None


def det_compare(title: str, sents: List[str]) -> Det:
    subj = _subjects_from_title(title)
    blob = " ".join(sents)
    if not subj:
        m = re.search(r"\b([A-Z][\w+#.-]*(?: [A-Z][\w+#.-]*)?)\s+(?:vs\.?|versus)\s+([A-Z][\w+#.-]*(?: [A-Z][\w+#.-]*)?)", blob)
        subj = (m.group(1), m.group(2)) if m else None
    if not subj:
        return None
    a, b = subj
    pa = re.compile(rf"(?<![\w-]){re.escape(a)}(?![\w-])", re.I)     # not inside "bias-variance"
    pb = re.compile(rf"(?<![\w-]){re.escape(b)}(?![\w-])", re.I)
    left: List[str] = []
    right: List[str] = []

    def clean(x: str, subj_re) -> str:
        x = _LEAD_CUE.sub("", x)
        x = re.sub(r"^(?:while|whereas|but|and|,|;)\s+", "", x.strip(" ,;"), flags=re.I)
        if subj_re.match(x):                         # drop the subject only when it opens the clause ("Bias is…"), never mid-sentence
            x = subj_re.sub("", x, count=1).strip(" ,;")
            x = re.sub(r"^(?:is|are|was|were|means|refers to)\s+", "", x, flags=re.I)
        x = re.sub(r"[,;]?\s*(?:while|whereas|but|and)\s*$", "", x, flags=re.I).strip(" ,;")
        x = re.sub(r"^(?:learning|models?|databases?|systems?|methods?|approach(?:es)?)\b\s*", "", x, flags=re.I)
        return _cap(_strip_end(x))

    for s in sents:
        ma, mb = pa.search(s), pb.search(s)
        if ma and mb:
            first, second = (ma, mb) if ma.start() < mb.start() else (mb, ma)
            l, r = s[:second.start()], s[second.start():]
            if first is ma:
                left.append(clean(l, pa)); right.append(clean(r, pb))
            else:
                right.append(clean(l, pb)); left.append(clean(r, pa))
        elif ma:
            left.append(clean(s, pa))
        elif mb:
            right.append(clean(s, pb))
    left = [x for x in left if x]
    right = [x for x in right if x]
    n = min(len(left), len(right))
    if n < 2:
        return None
    rows = [[left[i], right[i]] for i in range(n)]
    rows += [[left[i], ""] for i in range(n, len(left))] + [["", right[i]] for i in range(n, len(right))]
    return "COMPARE_TABLE", "comparison", 0.88, {"headers": [_cap(a), _cap(b)], "rows": rows[:7]}, f"{a} compared with {b}"


def det_matrix(title: str, sents: List[str]) -> Det:
    blob = " ".join(sents)
    if not re.search(r"\b(axes|axis|matrix|quadrant|2\s?x\s?2)\b", blob + title, re.I):
        return None
    m = re.search(r"axes?:?\s*([\w ]+?)\s+and\s+([\w ]+?)(?:\.|,|$)", blob, re.I)
    quads = []
    for s in sents:
        mm = re.match(r"^(.*?\b(?:and|but|not|neither)\b.*?)\s+(?:tasks|items|things|ideas|projects|cases)?\s*(?:are|is|should be)\s+(.+?)\.?$", s, re.I)
        if mm and not re.search(r"axes|axis", s, re.I):
            quads.append({"title": _cap(re.sub(r"\s+(tasks|items|things|ideas|projects|cases)$", "", mm.group(1).strip(), flags=re.I)),
                          "items": [_cap(_strip_end(mm.group(2)))]})
    if len(quads) < 3:
        return None
    x = [_cap(m.group(1).strip()), _cap(m.group(2).strip())] if m else ["Low", "High"]
    return "MATRIX_GRID", "quadrant_2x2", 0.93, {"quadrants": quads[:4], "x_axis": ["Not " + x[0].lower(), x[0]] if m else x,
                                                  "y_axis": ["Not " + x[1].lower(), x[1]] if m else x}, "two independent axes"


_LEVEL_WORD = re.compile(r"\b(layers?|levels?|tiers?|stages? of|base|foundation|beneath|below|above|top|apex|outer|inner|deepest|hierarch\w+)\b", re.I)


def _entity(s: str) -> Tuple[str, str]:
    m = re.search(r"\b(?:lies|lie|comes?|sits?|follows?|forms?|is found|rests?)\s+(?:the\s+|a\s+|an\s+)?([A-Za-z\- ]{3,28}?)(?=[,.;]|\s+(?:which|that|is|are|and)\b)", s)
    if m and re.match(r"^(?:beneath|below|above|under|inside|next|then|finally|at)\b", s, re.I):
        return _cap(m.group(1).strip()), _strip_end(s)
    m = re.match(r"^(?:The|A|An)?\s*([A-Za-z\-]+(?: [A-Za-z\-]+)?)\s+(?:is|are|was|were|form|forms|has|have|come|comes|include|includes)\b", s)
    if m:
        return _cap(m.group(1).strip()), _strip_end(s)
    m = re.match(r"^(?:Physiological|[A-Z][a-z]+)\s+needs?\b", s)
    if m:
        return _cap(m.group(0)), _strip_end(s)
    return short_label(s, 3), _strip_end(s)


def det_layers(title: str, sents: List[str]) -> Det:
    blob = " ".join(sents) + " " + title
    if len(_LEVEL_WORD.findall(blob)) < 2:
        return None
    ents = [(a, d) for a, d in (_entity(s) for s in sents[1:] if len(s.split()) >= 4)] if len(sents) > 3 else []
    if len(ents) < 3:
        ents = [(a, d) for a, d in (_entity(s) for s in sents if len(s.split()) >= 4)]
    # ordered build-up like Maslow: "...X form the base. Y build on them. Then come ..."
    if len(ents) < 3:
        return None
    seen = set()
    levels = []
    for a, d in ents[:6]:
        if a.lower() in seen:
            continue
        seen.add(a.lower())
        levels.append({"label": a, "detail": d})
    if len(levels) < 3:
        return None
    return "LAYERS", "stack", 0.84, {"levels": levels}, f"{len(levels)} nested / stacked levels"


def det_funnel(title: str, sents: List[str]) -> Det:
    vals = []
    for s in sents:
        nums = _numbers(s)
        if not nums:
            continue
        v = _to_float(nums[0])
        label = _strip_end(s.replace(nums[0], "", 1))
        label = re.sub(r"^\s*(?:the|a|an)\s+", "", label, flags=re.I)
        if v is not None:
            vals.append((v, short_label(label, 5), _strip_end(s)))
    steep = vals and vals[0][0] > vals[-1][0] * 4
    cue = bool(re.search(r"funnel|pipeline|conversion|stages|admission|hiring|recruit|sales", title, re.I))
    if len(vals) >= 3 and all(vals[i][0] >= vals[i + 1][0] for i in range(len(vals) - 1)) and (steep or (cue and vals[0][0] > vals[-1][0] * 1.5)):
        return "FUNNEL", "funnel", 0.86, {"stages": [{"label": l, "value": _fmt(v), "detail": d} for v, l, d in vals[:6]]}, "a narrowing sequence of counts"
    return None


def _fmt(v: float) -> str:
    if v >= 1e9:
        return f"{v / 1e9:.1f}B".replace(".0B", "B")
    if v >= 1e6:
        return f"{v / 1e6:.1f}M".replace(".0M", "M")
    if v >= 1e4:
        return f"{v / 1e3:.0f}K"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:g}"


def _subject_before_verb(s: str) -> str:
    s = _LEAD_CUE.sub("", s)
    m = _VERBISH.search(s)
    head = s[:m.start()] if m else re.split(_NUM, s)[0]
    head = re.sub(r"^(?:the|a|an)\s+", "", head.strip(), flags=re.I)
    return _cap(head.strip(" ,;")[:40])


def det_chart(title: str, sents: List[str]) -> Det:
    blob = " ".join(sents)
    # percentage shares of a whole
    pct = []
    for s in sents:
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s?(?:%|percent)", s)
        if m:
            pct.append((_subject_before_verb(s) or short_label(s, 3), float(m.group(1))))
    if len(pct) >= 3 and 95 <= sum(v for _, v in pct) <= 105:
        return "CHART_PART_TO_WHOLE", "pie", 0.9, {"points": [{"label": l, "value": v} for l, v in pct[:8]]}, "shares that sum to ~100%"
    # "value in PERIOD" pairs → trend
    pairs = re.findall(rf"({_NUM})\s*(?:[A-Za-z]+\s+){{0,2}}in\s+((?:Q[1-4](?:\s+\d{{4}})?)|(?:{_MONTH}(?:\s+\d{{4}})?)|(?:19|20)\d{{2}})", blob, re.I)
    if len(pairs) >= 3:
        pts = [{"label": p[1].strip(), "value": _to_float(p[0])} for p in pairs if _to_float(p[0]) is not None]
        if len(pts) >= 3:
            return "CHART_TREND", "line", 0.88, {"points": pts[:10]}, "a value across ordered periods"
    # label → value per sentence (only when every figure shares one unit — otherwise they are separate statistics)
    def _unit(tok: str) -> str:
        t = tok.lower()
        if "%" in t or "percent" in t:
            return "pct"
        if re.search(r"[$₹€£]", t):
            return "cur"
        m = re.search(r"(trillion|billion|million|thousand|bn|mn|k)\b", t)
        return m.group(1) if m else "plain"

    lab = []
    for s in sents:
        nums = _numbers(s)
        if len(nums) == 1 and _to_float(nums[0]) is not None:
            subj = _subject_before_verb(s)
            if subj and len(subj.split()) <= 4:
                lab.append((subj, _to_float(nums[0]), _unit(nums[0])))
    if len(lab) >= 3 and len({l for l, _, _ in lab}) == len(lab) and len({u for _, _, u in lab}) == 1:
        lab = [(l, v) for l, v, _ in lab]
        return "CHART_CATEGORICAL", "bar", 0.84, {"points": [{"label": l, "value": v} for l, v in lab[:8]]}, "one quantity compared across categories"
    return None


_UNITS = {"seconds", "second", "secs", "sec", "minutes", "minute", "mins", "hours", "hour", "days", "day", "weeks", "week", "months", "month",
          "years", "year", "ms", "milliseconds", "kg", "km", "m", "cm", "mm", "mb", "gb", "kb", "tb", "gw", "mw", "kw", "kwh", "hz", "mhz", "ghz",
          "users", "people", "students", "patients", "countries", "cities", "points", "degrees", "tons", "tonnes", "miles", "litres", "liters"}
_LABEL_STOP = {"a", "an", "the", "and", "or", "but", "to", "from", "that", "which", "while", "in", "on", "at", "for", "with", "by", "than", "as",
               "is", "are", "was", "were", "be", "of", "about", "around", "roughly", "approximately", "nearly", "almost", "over", "under", "reached",
               "grew", "fell", "rose", "added", "reduced", "increased", "decreased", "pass", "passes", "total", "totalling", "totaling", "only", "just", "up", "down"}


def _words_after(text: str, limit: int = 4) -> List[str]:
    out: List[str] = []
    for tok in re.findall(r"[\w'’+#./-]+|[,;:.()]", text):
        if tok in ",;:.()" or tok.lower() in _LABEL_STOP:
            break
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def _words_before(text: str, limit: int = 4) -> List[str]:
    toks = re.findall(r"[\w'’+#./-]+|[,;:.()]", text)
    while toks and toks[-1].lower() in _LABEL_STOP:          # "from about" / "to"
        toks.pop()
    out: List[str] = []
    for tok in reversed(toks):
        if tok in ",;:.()" or re.search(r"\d", tok) or tok.lower() in _UNITS:     # another figure ends the phrase
            break
        out.append(tok)
        if len(out) >= limit:
            break
    out.reverse()
    while out and out[0].lower() in _LABEL_STOP:
        out.pop(0)
    return out


def _local_stats(sentence: str) -> List[Tuple[str, str]]:
    """(value, label) per figure, where the label is the phrase *next to* the figure ("37" -> "backend checks"), not the sentence opening."""
    s = _REF_NUM.sub(lambda m: " " * len(m.group(0)), sentence)
    found: List[Tuple[str, str]] = []
    for m in _NUM_RE.finditer(s):
        tok = m.group(0).strip().rstrip(",. ")
        if not re.search(r"\d", tok) or (re.fullmatch(r"\d{4}", tok) and _YEAR_RE.fullmatch(tok)):
            continue
        after_txt = s[m.end():]
        value = tok
        unit = re.match(r"\s*([A-Za-z]+)", after_txt)
        if unit and unit.group(1).lower() in _UNITS:
            value = f"{tok} {unit.group(1).lower()}"
            after_txt = after_txt[unit.end():]
        after = _words_after(after_txt)
        before = _words_before(s[:m.start()])
        words = after if after else before
        label = _cap(" ".join(words)) if words else (found[-1][1] if found else short_label(s, 6))   # "from 12 to 2": same subject
        found.append((value, label))
    # "from X to Y" with one shared label reads as before / after
    if len(found) == 2 and found[0][1] == found[1][1] and re.search(r"\bfrom\b.+\bto\b", s, re.I):
        found = [(found[0][0], found[0][1] + " (before)"), (found[1][0], found[1][1] + " (after)")]
    return found


def det_stats(title: str, sents: List[str]) -> Det:
    if sum(1 for s in sents if re.search(r"[A-Za-z0-9)]\s*=\s*[A-Za-z0-9(]", s)) >= 1:
        return None  # equations are not statistics
    # sentences that are really table rows (many bare numbers, pipes, marks/hours columns) are not statistics
    sents = [x for x in sents if len(_numbers(x)) <= 3 and "|" not in x and not re.search(r"\b(?:marks|term test|hrs?\.?|duration|credits?)\b.*\d.*\d.*\d", x, re.I)]
    if not sents:
        return None
    tiles = []
    for s in sents:
        for k, (value, label) in enumerate(_local_stats(s)[:2]):
            tiles.append({"value": value, "label": label, "detail": _strip_end(s) if k == 0 else ""})
    # de-duplicate by value
    seen, uniq = set(), []
    for t in tiles:
        if t["value"] in seen:
            continue
        seen.add(t["value"])
        uniq.append(t)
    if not uniq:
        return None
    n_words = sum(len(s.split()) for s in sents)
    with_num = sum(1 for s in sents if _numbers(s))
    if with_num / max(1, len(sents)) < (0.6 if n_words >= 45 else 0.5) and n_words >= 30:
        return None  # a number in passing is not a statistic slide
    if len(uniq) >= 3 or (len(uniq) >= 2 and n_words < 60) or (len(uniq) >= 1 and n_words < 30):
        conf = 0.8 if len(uniq) >= 3 else 0.74
        return "STAT_TILES", "tiles", conf, {"tiles": uniq[:4], "context": [_strip_end(s) for s in sents[:3]]}, f"{len(uniq)} headline figures"
    return None


_DEF_CUE = re.compile(r"\b(is defined as|refers to|is a measure of|is a term|is known as|means|denotes|is the (?:process|study|science|ability|measure|degree)(?: of| by which)|is a (?:type|kind|form|method|technique|set|branch|subfield|field|process|general))\b", re.I)
_FORMULA = re.compile(r"(?<![\w])((?:[A-Za-z][A-Za-z0-9_]{0,3}|[A-Za-z]\([a-z]\))\s*=\s*[-+\w().*/^\s×÷∑Σ]+?(?:\([^)]*\))?[\w)]*)(?=[.;,]\s|[.;,]?$)")


def _formula(text: str) -> str:
    m = re.search(r"\b((?:[A-Z]|[A-Za-z]{1,3})\s*=\s*[^.;\n]{2,60})", text)
    if m:
        f = re.split(r"\s+(?:gives|is|are|where|which|and|so|for|when|represents?|denotes?|means|that|if)\b|,\s", m.group(1))[0]
        return re.sub(r"\s+", " ", _strip_end(f))
    m = re.search(r"\b([A-Z][a-z]+(?: [a-z]+)?)\s+equals\s+([a-z]+(?: [a-z]+)?)\s+(times|plus|minus|divided by|over)\s+([a-z]+(?: [a-z]+)?)", text)
    if m:
        op = {"times": "×", "plus": "+", "minus": "−", "divided by": "÷", "over": "÷"}[m.group(3)]
        return f"{m.group(1)} = {m.group(2)} {op} {m.group(4)}"
    m = re.search(r"\b([a-z]+(?: [a-z]+)?)\s+squared plus\s+([a-z]+(?: [a-z]+)?)\s+squared equals\s+([a-z]+(?: [a-z]+)?)\s+squared", text, re.I)
    if m:
        return f"{m.group(1)}² + {m.group(2)}² = {m.group(3)}²"
    return ""


def det_definition(title: str, sents: List[str]) -> Det:
    first = sents[0] if sents else ""
    law = re.search(r"\b(law|theorem|principle|rule|equation|formula|postulate|axiom|identity|inequality)\b", title, re.I)
    formula = _formula(" ".join(sents))
    title_def = bool(re.match(r"^\s*(?:what (?:is|are)|definition of|defining|meaning of|understanding)\b|\bdefined\b|\bdefinition\b", title, re.I)) and bool(re.search(r"\b(is|are|refers?|means)\b", first))
    if (_DEF_CUE.search(first) or title_def) and len(sents) <= 4:
        m = re.match(r"^(?:The\s+)?(.{2,40}?)\s+(?:is defined as|refers to|is a measure of|is known as|means|denotes|is)\s+(.+)$", _strip_end(first), re.I)
        term = _cap(m.group(1)) if m else short_label(first, 3)
        meaning = _cap(m.group(2)) if m else _strip_end(first)
        if formula:
            return "FORMULA_CALLOUT", "card", 0.86, {"term": term, "statement": _cap(_strip_end(first)), "formula": formula,
                                                     "notes": [_strip_end(s) for s in sents[1:]]}, "a definition with its formula"
        return "DEFINITION", "term", 0.85, {"term": term, "definition": meaning, "notes": [_strip_end(s) for s in sents[1:]]}, "a term being defined"
    if (law or formula) and len(sents) <= 5 and formula:
        return "FORMULA_CALLOUT", "card", 0.86, {"term": re.sub(r"\s+\(.*?\)", "", title).strip(), "statement": _cap(_strip_end(sents[0])),
                                                 "formula": formula, "notes": [_strip_end(s) for s in sents[1:]]}, "a law / theorem with a formula"
    if law and len(sents) <= 3:
        return "QUOTE", "statement", 0.78, {"text": _strip_end(sents[0]), "attribution": title}, "a principle stated once"
    return None


_CAUSE = re.compile(r"\b(leads? to|causes?|results? in|as a result|therefore|thus|which in turn|pushes?|raises?|drives?|triggers?|"
                    r"so that|consequently|because|due to|reduces?|increases?|breaks?|turns? into|then)\b", re.I)


def det_cause_effect(title: str, sents: List[str]) -> Det:
    cued = [s for s in sents if _CAUSE.search(s)]
    strong = [s for s in sents if re.search(r"\b(as a result|therefore|thus|leads? to|causes?|results? in|consequently|which in turn|so that)\b", s, re.I)]
    if (len(cued) < 2 and not strong) or len(sents) < 3 or len(sents) > 7:
        return None
    loop = bool(re.search(r"\b(again|in turn|repeat|loop|spiral|vicious|feedback)\b", " ".join(sents), re.I))
    nodes = [{"label": short_label(s, 5), "detail": _strip_end(_LEAD_CUE.sub("", s))} for s in sents[:6]]
    return "CAUSE_EFFECT", "loop" if loop else "chain", 0.76, {"nodes": nodes, "loop": loop}, "a chain of causes and effects"


def det_labelled(title: str, sents: List[str], raw: str) -> Det:
    items, seen = [], set()
    for ln in re.split(r"\n|(?<=[.!?])\s+", raw):
        m = re.match(r"^\s*(?:[-*•]\s*)?([A-Z][\w /&-]{1,32}?):\s+(.{8,})$", ln.strip())
        if m:
            key = (m.group(1).strip().lower(), re.sub(r"\W+", "", m.group(2).lower())[:60])
            if key in seen:  # the director passes the text and its bullets together
                continue
            seen.add(key)
            items.append({"heading": _cap(m.group(1)), "body": _strip_end(m.group(2))})
    if len(items) >= 3 and not re.match(r"(?i)^(advantages?|disadvantages?|pros?|cons?)$", items[0]["heading"]):
        return "LIST_STRUCTURED", "cards", 0.86, {"cards": items[:6]}, f"{len(items)} labelled pillars"
    return None


def det_venn(title: str, sents: List[str]) -> Det:
    blob = " ".join(sents)
    if not re.search(r"\b(both|shared|in common|overlap)\b", blob, re.I) or not re.search(r"\bonly\b", blob, re.I):
        return None
    items = [_strip_end(s) for s in sents]
    if len(items) < 3:
        return None
    return "SET_DIAGRAM", "venn2", 0.84, {"items": items[:8]}, "shared vs unique members"


def det_checklist_or_points(title: str, sents: List[str], bullets: List[str]) -> Det:
    src = bullets if len(bullets) >= 3 else sents
    src = [s for s in src if len(s.split()) >= 2]
    if len(src) < 2:
        return None
    imperative = sum(1 for s in src if re.match(r"^(?:review|use|teach|practice|sleep|keep|avoid|make|ensure|check|always|never|try|start|stop|write|read|set|plan|build|test|drink|eat|take|run|add|remove|define|choose|ask|learn|focus)\b", s.strip(), re.I))
    if imperative >= max(3, int(len(src) * 0.6)):
        return "CHECKLIST", "ticks", 0.8, {"items": [{"text": _strip_end(s)} for s in src[:8]]}, "actionable tips"
    # Connected prose — long sentences that lean on each other ("however", "because", "for example") — reads best as
    # plain flowing text with its relationships marked, not as separate boxes. Boxes are for short parallel items.
    from learnova.visuals.discourse import analyze

    avg = sum(len(s.split()) for s in src) / len(src)
    linked = sum(1 for r in analyze(src) if r["rel"] != "none")
    if avg >= 13 or linked >= 2 or len(src) < 3:
        return det_prose(title, src)
    heads = [{"heading": heading_for(s), "body": _strip_end(s)} for s in src[:6]]
    return "KEY_POINTS", "grid" if len(heads) <= 6 else "list", 0.55, {"cards": heads}, "discrete key points (lossless cards)"


def det_prose(title: str, sents: List[str]) -> Det:
    """Narrative text: a lead sentence, then the rest as flowing prose with each sentence's relation to the previous one."""
    from learnova.visuals.discourse import analyze

    sents = [_strip_end(s) + "." if not re.search(r"[.!?:]$", _strip_end(s)) else s.strip() for s in sents if s.strip()]
    if not sents:
        return None
    rels = analyze(sents)
    body = [{"text": s, "rel": r["rel"], "cue": r["cue"]} for s, r in zip(sents[1:], rels[1:])]
    return "PROSE", "flow", 0.6, {"lead": sents[0], "body": body}, "connected explanation — kept as readable text, relationships marked"


_MATH_VERB = re.compile(r"^(?:expand|solve|simplify|multiply|factor(?:ise|ize)?|combine|substitute|divide|subtract|add|differentiate|integrate|evaluate|compute|calculate|check|rearrange|collect|cancel|square|take)\b", re.I)
_MATHY = re.compile(r"\d\s*[\^*/+\-=]\s*[\w(]|[a-z]\^\d|\)\s*\(|\d[a-z]\b")


def det_worked(title: str, sents: List[str]) -> Det:
    """A problem worked line by line: imperative maths verbs, each followed by an expression."""
    steps = [x for x in sents if _MATH_VERB.match(x.strip()) and _MATHY.search(x)]
    if len(steps) < 3:
        return None
    rows = []
    for x in steps[1:]:
        if ":" in x:
            reason, expr = x.split(":", 1)
            rows.append({"step": _strip_end(expr), "reason": _strip_end(reason)})
        else:
            rows.append({"step": _strip_end(x), "reason": ""})
    return "WORKED_EXAMPLE", "steps", 0.9, {"problem": _strip_end(steps[0]), "rows": rows[:10]}, "a problem worked step by step"


_REF_TITLE = re.compile(r"\b(references?|bibliography|text ?books?|reference books?|further reading|suggested reading|recommended reading|citations|sources)\b", re.I)


def det_references(title: str, text: str) -> Det:
    lines = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", l).strip() for l in re.split(r"\n+", text) if l.strip() and not l.strip().startswith("|")]
    if len(lines) == 1:
        lines = [x.strip() for x in re.split(r"(?<=\d{4})\.\s+(?=[A-Z])|(?<=\.)\s+(?=\d+\.\s)", lines[0]) if x.strip()]
    cites = sum(1 for l in lines if is_citation(l))
    if not lines or not (_REF_TITLE.search(title) and cites >= 1 or cites >= max(3, int(len(lines) * 0.6))):
        return None
    return "REFERENCES", "list", 0.93, {"items": [_strip_end(l) for l in lines[:12]]}, f"{len(lines)} references — shown compactly, not as content"


def det_table(title: str, text: str) -> Det:
    from learnova.parsers.pdf_tables import parse_table_block

    t = parse_table_block(text)
    if not t:
        return None
    rows = [r for r in t["rows"] if any(c.strip() for c in r)]
    if len(rows) < 1:
        return None
    return "COMPARE_TABLE", "table", 0.95, {"headers": t["headers"], "rows": rows[:8], "kind": "table", "total_rows": len(rows)}, \
        f"a {len(rows)}-row × {len(t['headers'])}-column table in the source — drawn as a real table"


def det_sections(title: str, text: str) -> Det:
    """Several short sibling subsections packed on one slide: each keeps its own heading, shown side by side."""
    parts = re.split(r"(?m)^###\s+", text)
    secs = []
    for chunk in parts[1:]:
        head, _, rest = chunk.partition("\n")
        sents = split_sentences(rest)
        if head.strip() and sents:
            secs.append({"title": head.strip(), "lead": sents[0], "body": sents[1:]})
    if len(secs) < 2:
        return None
    return "SECTIONS", "columns", 0.9, {"sections": secs[:3]}, f"{len(secs)} short subsections shown side by side"


def det_function(title: str, sents: List[str]) -> Det:
    blob = " ".join(sents)
    m = re.search(r"\b(?:y|f\(x\))\s*=\s*([-+*/^()\d.\sx]+?)(?=\s+(?:has|is|with|where|and|for|gives|so)\b|[.;,]|$)", blob)
    if not m or "x" not in m.group(1) or not re.search(r"\b(function|slope|intercept|graph|plot|curve|line|parabola|linear|quadratic)\b", blob, re.I):
        return None
    expr = re.sub(r"(\d)\s*x", r"\1*x", m.group(1).strip()).replace("^", "**").replace(" ", "")
    pts = []
    try:
        pts.append({"x": 0, "y": eval(expr, {"x": 0.0}), "label": "y-intercept"})  # noqa: S307 - digits/operators only
    except Exception:
        pass
    if re.search(r"[^-+*/().\dx]", expr.replace("**", "")):
        return None
    return "FUNCTION_PLOT", "curve", 0.88, {"expr": expr, "domain": [-5, 5], "key_points": pts}, "a function y = f(x) to plot"


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────
_STEM = {"FUNCTION_PLOT", "ALGORITHM_TRACE", "DATA_STRUCTURE", "WORKED_EXAMPLE", "GEOMETRY", "ML_VIZ", "CALCULUS_VIZ"}


def takeaway_for(family: str, d: Dict[str, Any]) -> str:
    """A one-line synthesis written from the visual's data ('' when the visual already says it all)."""
    try:
        if family in {"PROCESS_LINEAR", "PROCESS_CYCLIC"}:
            st = d["stages"]; return f"{len(st)} steps — from “{st[0]['label']}” to “{st[-1]['label']}”" + (", then it repeats." if family.endswith("CYCLIC") else ".")
        if family == "TIMELINE":
            ev = d["events"]; return f"{len(ev)} milestones between {ev[0]['date']} and {ev[-1]['date']}."
        if family == "COMPARE_TABLE" and d.get("kind") == "table":
            return f"{d.get('total_rows', len(d['rows']))} rows · {', '.join(h for h in d['headers'] if h)[:90]}"
        if family == "COMPARE_TABLE":
            h, r = d["headers"], d["rows"][0]; return f"Key difference — {h[0]}: {r[0]}  |  {h[1]}: {r[1]}"[:170]
        if family == "COMPARE_VISUAL":
            return f"{len(d['pros'])} advantages to weigh against {len(d['cons'])} trade-offs."
        if family == "STAT_TILES":
            t = d["tiles"][0]; return f"Headline: {t['value']} — {t['label'].lower()}."
        if family in {"DEFINITION"}:
            return _strip_end(d["definition"]) + "."
        if family == "FORMULA_CALLOUT":
            return f"Remember: {d['formula']}"
        if family in {"LAYERS", "HIERARCHY_NEST"}:
            lv = d["levels"]; return f"{len(lv)} levels, from {lv[0]['label'].lower()} to {lv[-1]['label'].lower()}."
        if family == "CAUSE_EFFECT":
            return f"One trigger sets off a chain of {len(d['nodes'])} effects" + (" that feeds back on itself." if d.get("loop") else ".")
        if family == "FUNNEL":
            st = d["stages"]; return f"From {st[0]['value']} {st[0]['label'].lower()} down to {st[-1]['value']}."
        if family.startswith("CHART_") and d.get("points"):
            top = max(d["points"], key=lambda p: p["value"]); return f"Highest: {top['label']} ({top['value']:g})."
        if family == "SET_DIAGRAM":
            return "What the two sets share — and what is unique to each."
    except Exception:
        pass
    return ""


def decide(title: str, text: str, bullets: Optional[List[str]] = None, vms: Any = None) -> Decision:
    """
    Pick the visual and build its data.

    ``vms`` is an optional ``VisualDecision`` from the Visual Modality Selector;
    its STEM families (plots, traces, worked examples) are trusted when they came
    with a payload, because their extractors are specialised.
    """
    bullets = [b for b in (bullets or []) if b and b.strip()]
    raw_text = text or ""
    tbl = det_table(title, raw_text)
    if tbl:
        # the table is the slide; prose around it becomes notes via the residual-notes pass
        return Decision(tbl[0], tbl[1], tbl[2], tbl[3], tbl[4], [], takeaway=takeaway_for("COMPARE_TABLE", tbl[3]))
    sec = det_sections(title, raw_text)
    if sec:
        return Decision(sec[0], sec[1], sec[2], sec[3], sec[4], [], takeaway="")
    text = "\n".join(l for l in raw_text.split("\n") if not l.strip().startswith("|") and l.strip() != "[TABLE DATA]")
    ref = det_references(title, text)
    if ref:
        return Decision(ref[0], ref[1], ref[2], ref[3], ref[4], [], takeaway="")
    sents = split_sentences(text) or [s for b in bullets for s in split_sentences(b)]
    if not sents:
        sents = [title or "Key idea"]
    cands: List[Tuple[str, str, float, Dict[str, Any], str]] = []

    def add(d: Det) -> None:
        if d:
            cands.append(d)

    if vms is not None and getattr(vms, "family", "") in _STEM and getattr(vms, "data", None) and getattr(vms, "confidence", 0) >= 0.55:
        # Equations alone are not "worked examples" — those need real steps.
        eq_lines = sum(1 for s in sents if "=" in s)
        if not (vms.family == "WORKED_EXAMPLE" and eq_lines < 2):
            cands.append((vms.family, vms.variant, float(vms.confidence) + 0.4, vms.data, "specialised STEM extractor"))

    add(det_function(title, sents))
    add(det_worked(title, sents))
    add(det_labelled(title, sents, text))
    add(det_compare(title, sents))
    add(det_pros_cons(title, sents))
    add(det_matrix(title, sents))
    add(det_timeline(title, sents))
    add(det_chart(title, sents))
    add(det_funnel(title, sents))
    add(det_venn(title, sents))
    add(det_definition(title, sents))
    add(det_layers(title, sents))
    add(det_cycle(title, sents))
    add(det_process(title, sents))
    add(det_process_implicit(title, sents))
    add(det_cause_effect(title, sents))
    add(det_stats(title, sents))
    base = det_checklist_or_points(title, sents, bullets)
    if base and base[0] == "CHECKLIST":
        cands.append(base)

    # Mutual-exclusion tweaks learned from the gold set:
    fams = {c[0] for c in cands}
    if "CHART_PART_TO_WHOLE" in fams or "CHART_TREND" in fams:
        cands = [c for c in cands if c[0] not in {"STAT_TILES", "FUNNEL"}]
    if "SET_DIAGRAM" in fams:
        cands = [c for c in cands if c[0] not in {"COMPARE_TABLE", "STAT_TILES"}]
    if "PROCESS_CYCLIC" in fams and "PROCESS_LINEAR" in fams:
        cands = [c for c in cands if c[0] != "PROCESS_LINEAR"]
    if {"FUNNEL", "STAT_TILES"} <= fams:
        cands = [c for c in cands if c[0] != "STAT_TILES"]
    if "TIMELINE" in fams:
        cands = [c for c in cands if c[0] not in {"STAT_TILES", "CAUSE_EFFECT", "PROCESS_LINEAR"}]
    if "LAYERS" in fams and "PROCESS_LINEAR" in fams:
        cands = [c for c in cands if c[0] != "PROCESS_LINEAR"]
    if {"DEFINITION", "FORMULA_CALLOUT"} & fams:
        cands = [c for c in cands if c[0] not in {"STAT_TILES", "CHART_CATEGORICAL", "CAUSE_EFFECT", "KEY_POINTS"}]

    if cands:
        cands.sort(key=lambda c: -c[2])
        fam, var, conf, data, why = cands[0]
        alts = [(c[0], c[2]) for c in cands[1:4]]
        return Decision(fam, var, min(conf, 0.97), data, why, alts, takeaway=takeaway_for(fam, data))
    fam, var, conf, data, why = base or det_prose(title, sents) or ("KEY_POINTS", "grid", 0.5,
                                         {"cards": [{"heading": heading_for(s), "body": _strip_end(s)} for s in sents[:6]]},
                                         "no structure found — lossless key-point cards")
    return Decision(fam, var, conf, data, why, [], takeaway=takeaway_for(fam, data))
