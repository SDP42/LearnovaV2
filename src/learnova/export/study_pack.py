"""
Study pack: what a student takes away from a deck, built from the deck's own slides (nothing invented).

* flashcards     — definitions, key terms, quiz questions and "explain this" prompts (CSV, or Anki's tab format)
* quiz bank      — every checkpoint question with options, answer and explanation (CSV / JSON)
* cheat sheet    — one printable page: each slide's headline, its key line, formulas and figures
* narration      — a spoken script per slide with timings, for rehearsal or text-to-speech
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
from typing import Any, Dict, List, Tuple

from learnova.visuals.engine import _GLOSS_SENT, _strip_end, split_sentences  # noqa: PLC2701

WPM = 150


def _is_quiz(s: Dict[str, Any]) -> bool:
    return str(s.get("layout_type", "")).upper() == "QUIZ" or bool(s.get("question"))


def _content(slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [s for s in slides if not _is_quiz(s)]


def _bullets(s: Dict[str, Any]) -> List[str]:
    return [re.sub(r"^###\s*", "", str(b)).strip() for b in (s.get("bullets") or []) if str(b).strip()]


def _lead(s: Dict[str, Any], words: int = 28) -> str:
    text = str(s.get("takeaway") or "").strip() or next(iter(_bullets(s)), "")
    toks = text.split()
    return text if len(toks) <= words else " ".join(toks[:words]).rstrip(",;: ") + "…"


# ── flashcards ───────────────────────────────────────────────────────────────
def flashcards(slides: List[Dict[str, Any]], max_cards: int = 60) -> List[Tuple[str, str, str]]:
    """[(front, back, tag)]"""
    cards: List[Tuple[str, str, str]] = []
    seen = set()

    def add(front: str, back: str, tag: str) -> None:
        key = front.strip().lower()
        if front.strip() and back.strip() and key not in seen:
            seen.add(key)
            cards.append((front.strip(), back.strip(), tag))

    for s in _content(slides):
        title = re.sub(r"\s*\(\d+/\d+\)$", "", str(s.get("title", ""))).strip()
        for b in _bullets(s):
            for sent in split_sentences(b):
                m = _GLOSS_SENT.match(_strip_end(sent))
                if m and len(m.group(1).split()) <= 5 and len(sent.split()) >= 6:
                    subj = re.split(r"\s+(?:is|are|means|refers to|denotes|states that|describes)\s+", _strip_end(sent), 1)[0].strip()
                    if subj.split()[0].lower() in {"a", "an", "the"}:
                        subj = subj[0].lower() + subj[1:]
                    add(f"What is {subj}?" if " are " not in sent[:len(subj) + 6] else f"What are {subj}?", _strip_end(sent) + ".", "definition")
        lead = _lead(s)
        if title and lead and not str(s.get("family", "")).startswith("REFERENCES"):
            topic = re.sub(r"^(?:what|why|how)\s+(?:is|are|does|do)\s+(?:the\s+)?", "", title, flags=re.I) or title
            add(f"Explain: {topic[:1].upper() + topic[1:]}", lead, "concept")
    for s in slides:
        if _is_quiz(s) and s.get("options") and s.get("correct") in "ABCD":
            i = "ABCD".index(s["correct"])
            opts = s["options"]
            add(str(s.get("question", "")), f"{opts[i] if i < len(opts) else s['correct']} — {s.get('explanation', '')}".strip(" —"), "quiz")
    return cards[:max_cards]


def flashcards_csv(cards: List[Tuple[str, str, str]], anki: bool = False) -> str:
    out = io.StringIO()
    if anki:
        out.write("#separator:tab\n#html:false\n#tags column:3\n")
        w = csv.writer(out, delimiter="\t", lineterminator="\n")
    else:
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["Front", "Back", "Tag"])
    for f, b, t in cards:
        w.writerow([f, b, t])
    return out.getvalue()


# ── quiz bank ────────────────────────────────────────────────────────────────
def quiz_bank(slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for s in slides:
        if _is_quiz(s) and s.get("options"):
            out.append({"question": s.get("question", ""), "options": list(s.get("options") or []), "correct": s.get("correct", ""),
                        "explanation": s.get("explanation", ""), "difficulty": s.get("difficulty") or "recall", "slide": s.get("index", 0) + 1})
    return out


def quiz_csv(bank: List[Dict[str, Any]]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["Question", "A", "B", "C", "D", "Correct", "Explanation", "Difficulty"])
    for q in bank:
        o = (q["options"] + ["", "", "", ""])[:4]
        w.writerow([q["question"], *o, q["correct"], q["explanation"], q["difficulty"]])
    return out.getvalue()


# ── narration ────────────────────────────────────────────────────────────────
_OPEN = ["Let's start with", "Next, ", "Now, ", "Moving on to", "Here is", "Let's look at", "Finally, "]


def narration(slides: List[Dict[str, Any]], title: str = "") -> List[Dict[str, Any]]:
    """A script you can read aloud: the slide's sentences joined into spoken paragraphs, with a timing estimate."""
    out: List[Dict[str, Any]] = []
    content = [s for s in slides]
    for n, s in enumerate(content):
        t = str(s.get("title", "")).strip()
        if _is_quiz(s):
            q = str(s.get("question", "")).strip()
            opts = ", ".join(f"{'ABCD'[i]}, {o}" for i, o in enumerate(s.get("options") or []))
            text = f"Pause and think. {q} Is it {opts}? Take a moment, then check the answer on the slide."
        else:
            sents = [x if re.search(r"[.!?]$", x) else x + "." for x in (_strip_end(b) for b in _bullets(s)) if x]
            body = " ".join(sents)
            if str(s.get("takeaway") or "").strip() and str(s["takeaway"]) not in body:
                body += f" The takeaway: {str(s['takeaway']).strip().rstrip('.')}."
            opener = "Welcome. " if n == 0 and title else ""
            text = f"{opener}{t}. {body}".strip()
        words = len(text.split())
        out.append({"index": n + 1, "title": t, "text": text, "words": words, "seconds": max(8, round(words / WPM * 60))})
    return out


def narration_markdown(script: List[Dict[str, Any]], title: str = "Deck") -> str:
    total = sum(x["seconds"] for x in script)
    lines = [f"# {title} — narration script", f"_About {total // 60} min {total % 60:02d} s at a natural pace._", ""]
    for x in script:
        lines += [f"## Slide {x['index']}: {x['title']}  ({x['seconds']} s)", x["text"], ""]
    return "\n".join(lines)


# ── cheat sheet ──────────────────────────────────────────────────────────────
def cheatsheet_html(slides: List[Dict[str, Any]], title: str = "Cheat sheet") -> str:
    blocks = []
    for s in _content(slides):
        t = re.sub(r"\s*\(\d+/\d+\)$", "", str(s.get("title", ""))).strip()
        if not t or s.get("is_overview"):
            continue
        facts = re.findall(r"\bO\([^)]+\)|[$₹€£]?\d[\d,.]*\s?(?:%|percent|million|billion|kJ|kg|km|m|s)\b|\b[A-Za-z0-9₀-₉()]+(?:\s*\+\s*[A-Za-z0-9₀-₉()]+)+\s*(?:⇌|→|=|<->|->)\s*\S+(?:\s*\+\s*\S+)*", " ".join(_bullets(s)))
        chips = "".join(f'<span class="chip">{html.escape(f.strip())}</span>' for f in list(dict.fromkeys(facts))[:4])
        lines = _bullets(s)[:3]
        body = "".join(f"<li>{html.escape(_strip_end(x)[:170])}</li>" for x in lines)
        blocks.append(f'<section><h2>{html.escape(t)}</h2><ul>{body}</ul>{chips}</section>')
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{html.escape(title)} — cheat sheet</title>
<style>
@page {{ size: A4; margin: 12mm }}
body{{font:11px/1.45 Manrope,system-ui,sans-serif;color:#402B25;background:#fff;margin:0;padding:18px}}
h1{{font:700 22px 'Bricolage Grotesque',system-ui;margin:0 0 4px}} .sub{{color:#715A4E;margin:0 0 14px}}
.grid{{column-count:2;column-gap:18px}} section{{break-inside:avoid;border:1px solid #E8D8C9;border-radius:10px;padding:9px 12px;margin:0 0 10px;background:#FFFAF5}}
h2{{font:700 13px 'Bricolage Grotesque',system-ui;margin:0 0 5px;color:#8F3A18}} ul{{margin:0 0 6px;padding-left:16px}} li{{margin:0 0 3px}}
.chip{{display:inline-block;background:#FCE5D6;border-radius:999px;padding:2px 9px;margin:0 4px 3px 0;font-weight:700;font-size:10px}}
@media print{{body{{padding:0}}}}
</style><h1>{html.escape(title)}</h1><p class="sub">One-page revision sheet generated from the deck · {len(blocks)} topics</p><div class="grid">{''.join(blocks)}</div></html>"""


def to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
