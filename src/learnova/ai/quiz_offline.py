"""
Offline quiz generator — checkpoint questions built from the *same structured
data* the visuals use (dated events, process order, definitions, figures,
formulae, comparisons), so it needs no model, no network and no waiting.

Each question is a 4-option multiple choice with a plausible-distractor pool
drawn from the rest of the deck, and an explanation that quotes the source.
Deterministic: the same deck always yields the same quiz.
"""

from __future__ import annotations

import hashlib
import random
import re
from typing import Any, Dict, List, Optional

from learnova.visuals.engine import decide, short_label, split_sentences

_WORD = re.compile(r"[A-Za-z][A-Za-z\-']{4,}")
_STOP = {"which", "their", "there", "these", "those", "about", "after", "before", "because", "between", "during",
         "other", "while", "where", "would", "could", "should", "through", "under", "being", "using"}


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16))


def _clip(text: str, n: int = 16) -> str:
    w = str(text).split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


def _make(seed: str, question: str, correct: str, pool: List[str], why: str, difficulty: str = "recall") -> Optional[Dict[str, Any]]:
    correct = str(correct).strip()
    seen, wrong = {correct.lower()}, []
    for d in pool:
        d = str(d).strip()
        if d and d.lower() not in seen:
            seen.add(d.lower())
            wrong.append(d)
    if not correct or len(wrong) < 3:
        return None
    r = _rng(seed)
    wrong = r.sample(wrong, 3) if len(wrong) > 3 else wrong
    opts = wrong + [correct]
    r.shuffle(opts)
    return {"question": question, "options": [_clip(o, 22) for o in opts], "correct": "ABCD"[opts.index(correct)],
            "explanation": why, "difficulty": difficulty, "source": "offline"}


def _perturb_num(tok: str, r: random.Random) -> List[str]:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", tok)
    if not m:
        return []
    raw = m.group(0)
    v = float(raw.replace(",", ""))
    outs = []
    for f in (0.5, 2.0, 1.5, 0.75, 3.0):
        nv = v * f
        s = f"{nv:,.0f}" if float(raw.replace(",", "")).is_integer() and "." not in raw else f"{nv:.1f}"
        outs.append(tok.replace(raw, s, 1))
    r.shuffle(outs)
    return outs


def _perturb_formula(f: str) -> List[str]:
    outs = []
    for a, b in (("×", "+"), ("+", "×"), ("−", "+"), ("÷", "×"), ("=", "≠")):
        if a in f:
            outs.append(f.replace(a, b, 1))
    if "=" in f:
        l, r = f.split("=", 1)
        outs.append(f"{r.strip()} = {l.strip()}")
    outs.append(re.sub(r"²", "³", f))
    return [o for o in outs if o != f]


def _from_decision(idx: int, title: str, dec, pool_defs: List[str], pool_words: List[str], pool_titles: List[str]) -> Optional[Dict[str, Any]]:
    d, fam, seed = dec.data, dec.family, f"{idx}:{title}"
    r = _rng(seed)
    if fam == "TIMELINE":
        ev = d.get("events") or []
        if len(ev) >= 3:
            e = ev[len(ev) // 2]
            return _make(seed, f"When did this happen: “{_clip(e['title'], 14)}”?", e["date"], [x["date"] for x in ev if x is not e] + [str(int(re.search(r"\d{4}", e["date"]).group(0)) + d) for d in (-12, 15, 31) if re.search(r"\d{4}", e["date"])] + ["1900", "2010"],
                         f"{e['date']}: {e['title']}.")
    if fam in {"PROCESS_LINEAR", "PROCESS_CYCLIC", "CAUSE_EFFECT"} and not d.get("agenda"):
        st = d.get("stages") or d.get("nodes") or []
        if len(st) >= 3 and not any("?" in str(s.get("label", "")) for s in st):         # example sentences and questions are not an order to learn
            i = min(1, len(st) - 2)
            lab = [s["label"] for s in st]
            return _make(seed, f"What comes right after “{lab[i]}”?", lab[i + 1], [l for j, l in enumerate(lab) if j not in (i, i + 1)] + [t for t in pool_titles if t.lower() != short_label(title, 4).lower() and not re.match(r"(?:agenda|key takeaways|glossary|key terms|checkpoint|overview|thank you)", t, re.I)],
                         f"The order is: " + " → ".join(lab) + ".", "apply")
    if fam == "COMPARE_TABLE" and d.get("rows") and len(d.get("headers", [])) >= 2:
        a, b = d["headers"][:2]
        clean = lambda t: re.sub(r"[,;]?\s*(?:while|whereas|but|and)\s*$", "", str(t).strip(), flags=re.I)
        rows = [[clean(x[0]), clean(x[1])] for x in d["rows"] if x[0] and x[1]]
        short = lambda t: len(str(t).split()) <= 5
        if len(rows) >= 4 and all(short(x[0]) and short(x[1]) for x in rows):      # a lookup table (word → category): ask for one entry
            k = r.randrange(len(rows))
            q = _make(seed, f"What is the {b} of “{rows[k][0]}”?", rows[k][1], [x[1] for j, x in enumerate(rows) if j != k],
                      f"{rows[k][0]} → {rows[k][1]}.", "apply")
            if q:
                return q
        if len(rows) >= 2:
            return _make(seed, f"Which statement describes {a}?", rows[0][0], [rows[0][1], rows[1][1], rows[1][0]] + pool_defs[:3],
                         f"{a}: {rows[0][0]}. {b}: {rows[0][1]}.", "apply")
    if fam == "COMPARE_VISUAL" and d.get("pros") and d.get("cons"):
        return _make(seed, "Which of these is a drawback?", d["cons"][0], d["pros"] + d["cons"][1:2] + pool_defs[:2],
                     f"Drawback: {d['cons'][0]}")
    if fam == "DEFINITION" and d.get("term"):
        return _make(seed, f"Which best defines “{d['term']}”?", d["definition"], pool_defs[:5], f"{d['term']}: {d['definition']}")
    if fam == "FORMULA_CALLOUT" and d.get("formula"):
        return _make(seed, f"Which expression gives {d.get('term') or 'the relationship'}?", d["formula"], _perturb_formula(d["formula"]) + pool_titles,
                     f"{d['formula']}", "apply")
    if fam == "STAT_TILES" and d.get("tiles"):
        t = d["tiles"][0]
        return _make(seed, f"What was the figure for “{_clip(t['label'], 8)}”?", t["value"], _perturb_num(t["value"], r), t.get("detail") or t["label"])
    if fam.startswith("CHART_") and d.get("points"):
        p = d["points"][0]
        fmt = lambda v: f"{v:,.0f}" if float(v).is_integer() else f"{v:g}"
        val = fmt(p["value"])
        return _make(seed, f"What is the value for {p['label']}?", val, _perturb_num(val, r), f"{p['label']}: {val}")
    if fam == "LAYERS" and d.get("levels"):
        lv = d["levels"]
        pick = lv[min(1, len(lv) - 1)]
        return _make(seed, f"Which is described by: “{_clip(pick['detail'], 14)}”?", pick["label"], [x["label"] for x in lv if x is not pick] + [t for t in pool_titles if t.lower() != short_label(title, 4).lower()],
                     pick["detail"])
    if fam == "FUNNEL" and d.get("stages"):
        st = d["stages"]
        return _make(seed, "Which stage had the largest number?", st[0]["label"], [s["label"] for s in st[1:]] + [t for t in pool_titles if t.lower() != short_label(title, 4).lower()],
                     f"{st[0]['label']}: {st[0]['value']}")
    return None


def _cloze(idx: int, title: str, bullets: List[str], pool_words: List[str]) -> Optional[Dict[str, Any]]:
    tw = {w.lower() for w in _WORD.findall(title)}
    for s in bullets:
        text = s.strip()
        if (len(text.split()) < 8 or text.endswith(":") or re.search(r"\b(?:following|below|above|e\.g\.|i\.e\.)\b", text, re.I)
                or not re.search(r"[.!?]$", text)):
            continue                                              # a lead-in, a list header or a fragment makes a bad question
        words = _WORD.findall(text)
        cands = [w for i, w in enumerate(words) if w.lower() not in _STOP and w.lower() not in tw and len(w) >= 5 and i > 0]
        if not cands:
            continue

        def score(w: str) -> float:
            i = words.index(w)
            return len(w) + (3 if w[:1].isupper() and i > 0 else 0) + (3 if "-" in w or any(ch.isdigit() for ch in w) else 0) - (2 if w.lower().endswith(("ly", "ing")) else 0)

        key = max(cands, key=score)
        blanked = re.sub(rf"\b{re.escape(key)}\b", "_____", text, count=1)
        near = sorted({w for w in pool_words if w.lower() != key.lower() and abs(len(w) - len(key)) <= 3}, key=lambda w: (abs(len(w) - len(key)), w))
        q = _make(f"{idx}:{title}:cloze", f"Fill in the blank: “{_clip(blanked, 26)}”", key, near, f"“{text.rstrip('.')}.”", "recall")
        if q:
            return q
    return None


def offline_quizzes(slides: List[dict], frequency: int = 4, positions: Optional[List[int]] = None) -> List[dict]:
    """One question per checkpoint, drawn from the slide(s) it follows."""
    entries = []
    for e in slides:
        imp = e.get("improved") or {}
        if str(imp.get("layout_type", "")).upper() == "QUIZ":
            continue
        entries.append(e)
    if not entries:
        return []
    pool_defs, pool_words = [], []
    for e in entries:
        imp = e["improved"]
        pool_defs += [_clip(b, 14) for b in (imp.get("bullets") or []) if len(str(b).split()) >= 4]
        pool_words += _WORD.findall(" ".join(map(str, imp.get("bullets") or [])) + " " + str(imp.get("title", "")))
    pool_words = [w for w in dict.fromkeys(w for w in pool_words if w.lower() not in _STOP)]
    pool_titles = [short_label(str((e['improved'] or {}).get('title', '')), 4) for e in entries]
    if positions:
        marks = [p - 1 for p in positions if 1 <= p <= len(entries)]
    else:
        marks = list(range(frequency - 1, len(entries), frequency)) or [len(entries) - 1]
    quizzes: List[dict] = []
    for m in marks:
        # try the slide itself, then the ones just before it
        for j in (m, m - 1, m - 2):
            if j < 0:
                continue
            imp = entries[j]["improved"]
            title = str(imp.get("title", ""))
            bullets = [str(b) for b in (imp.get("bullets") or [])]
            text = str((entries[j].get("original") or {}).get("text") or "\n".join(bullets))
            dec = decide(title, text, bullets)
            q = _from_decision(j, title, dec, [x for x in pool_defs if x not in bullets], pool_words, pool_titles) or _cloze(j, title, bullets, pool_words)
            if q:
                q["source_slides"] = [title]
                quizzes.append(q)
                break
    return quizzes
