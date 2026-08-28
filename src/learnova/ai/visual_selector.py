"""
Visual Modality Selector (VMS).

The deterministic half of "which visual, when". Given a chunk of slide text
(plus optional image OCR), it scores every treatment in
``master_prompt.VISUAL_TREATMENTS`` from structural features of the content and
returns a ranked decision: the chosen treatment, a human-readable rationale, a
confidence, and a progressive-reveal segmentation.

Design goals
------------
* **Explainable** — every score is a sum of named feature contributions.
* **Conservative** — if nothing structural clears the threshold it returns
  MINIMAL_TEXT / KEEP_TEXT rather than forcing a diagram.
* **No LLM, no network, deterministic** — usable as the validation layer over
  the master-prompt LLM output and as a full standalone fallback.

It reuses ``learnova.intelligence`` when importable (richer step / comparison /
chronology extraction) and degrades to its own regex feature extractor
otherwise, so it works with zero project state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from learnova.ai.master_prompt import TREATMENT_KEYS, TREATMENT_TO_FAMILY
from learnova.ai.text_policy import classify_sentences, protect_verbatim
from learnova.logging_config import logger

_WORD = re.compile(r"[A-Za-z][A-Za-z\-']+")
_SENT = re.compile(r"(?<=[.!?])\s+")
_NUM = re.compile(
    r"[$₹€£¥]?\s?\d{1,3}(?:,\d{2,3})*(?:\.\d+)?\s?"
    r"(?:%|percent|percentage|bn|mn|million|billion|k|x|years?|months?|days?)?",
    re.I,
)
_PCT = re.compile(r"\d{1,3}(?:\.\d+)?\s?(?:%|percent)", re.I)
_YEAR = re.compile(r"\b(?:1[5-9]\d{2}|20\d{2})\b")
_STEP_CUE = re.compile(
    r"\b(step\s*\d|first(?:ly)?|second(?:ly)?|third(?:ly)?|then|next|finally|"
    r"stage\s*\d|phase\s*\d|begin by|start by)\b", re.I)
_DECISION_CUE = re.compile(r"\b(if\b.+\bthen|otherwise|whether|decide|branch|yes/no|"
                           r"depending on)\b", re.I)
_LOOP_CUE = re.compile(r"\b(cycle|loop|repeat|iterat|feedback|recurr|continuous|"
                       r"back to the (start|beginning)|ongoing)\b", re.I)
_COMPARE_CUE = re.compile(r"\b(vs\.?|versus|compared? (?:to|with)|whereas|on the other "
                          r"hand|in contrast|difference between|unlike)\b", re.I)
_PROCON_CUE = re.compile(r"\b(advantage|disadvantage|benefit|drawback|pros?|cons?|"
                         r"strength|weakness|limitation|upside|downside)\b", re.I)
_TWO_AXIS_CUE = re.compile(r"\b(high|low)\b.+\b(high|low)\b|\b(urgent|important)\b|"
                           r"\b(quadrant|matrix|2\s?[x×]\s?2)\b", re.I)
_LEVEL_CUE = re.compile(r"\b(level|tier|layer|hierarch|pyramid|foundation|builds? on|"
                        r"rests? on|base|apex|top of)\b", re.I)
_SET_CUE = re.compile(r"\b(both|shared|in common|overlap|intersection|unique to|"
                      r"only .* not|venn)\b", re.I)
_DEFINE_CUE = re.compile(r"\b(is defined as|refers to|is a measure of|means that|"
                         r"is a term|we call it|is known as|denoted by)\b", re.I)
_DATE_TOKEN = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|\d{1,2}\s?(?:BCE|CE|AD|BC)|"
                         r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d)", re.I)
_QUOTE_CUE = re.compile(r"[\"“].{15,}[\"”]|\b(law|principle|theorem|axiom|maxim|"
                        r"golden rule)\b", re.I)
_TIME_SERIES_CUE = re.compile(r"\b(over time|per year|annually|trend|grew|declined|"
                              r"increased? from|from \d{4} to \d{4}|q[1-4])\b", re.I)


@dataclass
class Features:
    text: str
    title: str
    n_sentences: int
    n_words: int
    bullet_lines: List[str]
    step_cues: int
    decision_cues: int
    loop_cues: int
    compare_cues: int
    procon_cues: int
    two_axis_cues: int
    level_cues: int
    set_cues: int
    define_cues: int
    quote_cues: int
    time_series_cues: int
    numbers: List[str]
    percentages: List[str]
    years: List[str]
    # from the intelligence engine when available
    steps: List[str] = field(default_factory=list)
    comparisons: List[dict] = field(default_factory=list)
    chronology: List[str] = field(default_factory=list)
    stats: List[str] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)
    definitions: Dict[str, str] = field(default_factory=dict)


@dataclass
class VisualDecision:
    treatment: str                    # flat key, e.g. "FLOWCHART"
    family: str                       # catalog family, e.g. "PROCESS_LINEAR"
    variant: str                      # catalog variant, e.g. "flowchart"
    confidence: float                 # 0..1
    rationale: str
    scores: Dict[str, float]
    bullets: List[str]
    verbatim: List[str]
    reveal_groups: List[List[int]]
    animation: Dict[str, Any]
    data: Dict[str, Any]              # structured data for the chosen family

    def to_dict(self) -> Dict[str, Any]:
        return {
            "treatment": self.treatment,
            "family": self.family,
            "variant": self.variant,
            "confidence": round(self.confidence, 3),
            "rationale": self.rationale,
            "scores": {k: round(v, 2) for k, v in self.scores.items() if v},
            "bullets": self.bullets,
            "verbatim": self.verbatim,
            "reveal_groups": self.reveal_groups,
            "animation": self.animation,
            "data": self.data,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Feature extraction
# ─────────────────────────────────────────────────────────────────────────────


def _bullet_lines(text: str) -> List[str]:
    out = []
    for line in (text or "").splitlines():
        s = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", line).strip()
        if s:
            out.append(s)
    return out


def extract_features(text: str, title: str = "") -> Features:
    text = text or ""
    sentences = [s for s in _SENT.split(text) if s.strip()]
    f = Features(
        text=text,
        title=title or "",
        n_sentences=len(sentences),
        n_words=len(_WORD.findall(text)),
        bullet_lines=_bullet_lines(text),
        step_cues=len(_STEP_CUE.findall(text)),
        decision_cues=len(_DECISION_CUE.findall(text)),
        loop_cues=len(_LOOP_CUE.findall(text)),
        compare_cues=len(_COMPARE_CUE.findall(text)),
        procon_cues=len(_PROCON_CUE.findall(text)),
        two_axis_cues=len(_TWO_AXIS_CUE.findall(text)),
        level_cues=len(_LEVEL_CUE.findall(text)),
        set_cues=len(_SET_CUE.findall(text)),
        define_cues=len(_DEFINE_CUE.findall(text)),
        quote_cues=len(_QUOTE_CUE.findall(text)),
        time_series_cues=len(_TIME_SERIES_CUE.findall(text)),
        numbers=[m.group(0).strip() for m in _NUM.finditer(text) if any(ch.isdigit() for ch in m.group(0))],
        percentages=_PCT.findall(text),
        years=_YEAR.findall(text),
    )

    # Optional enrichment from the intelligence engine.
    try:
        from learnova.intelligence.engine import SlideIntelligenceEngine
        from learnova.pipeline.visual_planner import _build_slide_entity

        intel = SlideIntelligenceEngine().analyze_slide(_build_slide_entity(title, text))
        f.steps = [s for s in (intel.steps or intel.processes or []) if s.strip()]
        f.comparisons = list(intel.comparisons or [])
        f.chronology = [c for c in (intel.chronology or []) if c.strip()]
        f.stats = [s for s in (intel.numbers_and_statistics or []) if s.strip()]
        f.key_concepts = [c for c in (intel.key_concepts or []) if c.strip()]
        f.definitions = dict(intel.definitions or {})
    except Exception as exc:  # pragma: no cover - depends on optional state
        logger.debug("intelligence enrichment unavailable in VMS: %s", exc)

    return f


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────

_THRESHOLD = 2.5   # minimum winning score to leave plain text


def _score(f: Features) -> Dict[str, float]:
    n_items = max(len(f.bullet_lines), f.n_sentences)
    n_steps = max(len(f.steps), f.step_cues)
    s: Dict[str, float] = {k: 0.0 for k in TREATMENT_KEYS}

    # FLOWCHART / CYCLE — ordered procedure
    if n_steps >= 3 or len(f.steps) >= 3:
        s["FLOWCHART"] += 2.0 + min(n_steps, 6) * 0.4 + f.decision_cues * 0.8
        s["CYCLE"] += 1.0 + min(n_steps, 6) * 0.3
    if f.loop_cues:
        s["CYCLE"] += 1.5 + f.loop_cues * 0.6
        s["FLOWCHART"] -= 0.5

    # TIMELINE — needs real dates, not just ordinal words ("first, second…")
    dated = [c for c in f.chronology if _DATE_TOKEN.search(c)]
    if len(set(f.years)) >= 2 or len(dated) >= 2:
        s["TIMELINE"] += 2.5 + min(max(len(dated), len(set(f.years))), 6) * 0.4
    elif len(f.chronology) >= 3 and n_steps < 3:
        s["TIMELINE"] += 1.6

    # COMPARISON_TABLE / PROS_CONS
    if len(f.comparisons) >= 2:
        s["COMPARISON_TABLE"] += 2.5 + min(len(f.comparisons), 5) * 0.4
    if f.compare_cues:
        s["COMPARISON_TABLE"] += 1.3 + f.compare_cues * 0.9
    if f.procon_cues >= 2:
        s["PROS_CONS"] += 2.0 + f.procon_cues * 0.4
        s["COMPARISON_TABLE"] -= 0.5

    # MATRIX_2X2
    if f.two_axis_cues >= 2:
        s["MATRIX_2X2"] += 2.5 + f.two_axis_cues * 0.4

    # PYRAMID
    if f.level_cues >= 2:
        s["PYRAMID"] += 2.0 + f.level_cues * 0.5

    # VENN
    if f.set_cues >= 1:
        s["VENN"] += 1.5 + f.set_cues * 0.8

    # MIND_MAP — many loosely-related concepts, little other structure
    if len(f.key_concepts) >= 4 and n_steps < 3 and not f.comparisons:
        s["MIND_MAP"] += 1.8 + min(len(f.key_concepts), 7) * 0.25
        s["CARD_GRID"] += 1.5 + min(len(f.key_concepts), 4) * 0.3

    # Charts / metric
    if len(f.percentages) >= 3 and _sums_near_100(f.percentages):
        s["PIE_CHART"] += 3.0
    if f.time_series_cues and len(f.numbers) >= 3:
        s["LINE_CHART"] += 2.6 + f.time_series_cues * 0.4
    if len(f.numbers) >= 3 and n_items >= 3 and not f.time_series_cues:
        s["BAR_CHART"] += 2.0 + min(len(f.numbers), 6) * 0.3
        if s["PIE_CHART"] > 0:
            s["BAR_CHART"] -= 2.5          # a valid pie should not be outscored by bar
    if len(f.numbers) <= 1 and f.n_words < 45 and (f.numbers or f.percentages):
        s["METRIC"] += 3.2
    elif len(f.percentages) == 1 and f.n_words < 60:
        s["METRIC"] += 2.6

    # DEFINITION / QUOTE / KEEP_TEXT
    # A definition needs an explicit definitional phrase in the prose — the
    # intelligence engine's dictionary alone fires on any "X: y" line.
    if f.define_cues and f.n_sentences <= 3 and len(f.numbers) <= 1:
        s["DEFINITION"] += 2.4 + (0.8 if f.definitions else 0.0)
    if f.quote_cues and f.n_words < 60:
        s["QUOTE"] += 2.0 + f.quote_cues * 0.6
    if _looks_verbatim(f):
        s["KEEP_TEXT"] += 2.6

    # CARD_GRID from explicit "Label: detail" prefixes
    labelled = sum(1 for b in f.bullet_lines if re.match(r"^[A-Z][\w /&-]{1,30}:\s", b))
    if labelled >= 3:
        s["CARD_GRID"] += 2.0 + labelled * 0.3

    # BULLETS baseline for several discrete lines
    if n_items >= 3:
        s["BULLETS"] += 1.4 + min(n_items, 8) * 0.15

    # ── STEM families (also reachable via the master prompt) ─────────────────
    # These beat the generic numeric families when their signal is present:
    # an array literal is a data structure, not a bar chart.
    t = f.text
    stem = False
    if re.search(r"\by\s*=\s*[-\d.]*\s*\*?\s*x\b", t, re.I) or re.search(r"\bf\s*\(\s*x\s*\)\s*=", t, re.I):
        s["FUNCTION_PLOT"] += 4.2
        stem = True
    if re.search(r"\bderivative|tangent|area under the curve|integral|riemann\b", t, re.I) and "x" in t.lower():
        s["FUNCTION_PLOT"] += 1.6
        stem = True
    arr_lit = re.search(r"\[\s*-?\d+(?:\s*,\s*-?\d+){2,}\s*\]", t)
    if arr_lit and re.search(r"\bsort|swap|compare|search|traverse|iterat|pointer\b", t, re.I):
        s["ALGORITHM_TRACE"] += 4.4
        stem = True
    elif arr_lit and re.search(r"\barray|list|stack|queue|index|element|node\b", t, re.I):
        s["DATA_STRUCTURE"] += 3.8
        stem = True
    if re.search(r"\bregression|best[- ]fit line|least squares|gradient descent|loss curve|decision boundary\b", t, re.I):
        s["ML_VIZ"] += 3.4
        stem = True
    if re.search(r"\btriangle|polygon|hypotenuse|vertex|vertices|angle [A-Z]{3}|perpendicular bisector\b", t, re.I):
        s["GEOMETRY"] += 2.4

    if stem:
        for k in ("BAR_CHART", "LINE_CHART", "PIE_CHART", "METRIC"):
            s[k] = max(0.0, s[k] - 3.0)

    return s


def _sums_near_100(pcts: List[str]) -> bool:
    try:
        total = sum(float(re.sub(r"[^\d.]", "", p)) for p in pcts)
    except ValueError:
        return False
    return 80 <= total <= 120


def _looks_verbatim(f: Features) -> bool:
    treat = classify_sentences(f.text)
    verbatim = sum(1 for t in treat if t.treatment == "VERBATIM")
    return f.n_sentences > 0 and verbatim / f.n_sentences >= 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Reveal segmentation
# ─────────────────────────────────────────────────────────────────────────────


# effect keyed by family — matches the meaning of the visual (master prompt C.4 r8)
_FAMILY_EFFECT = {
    "CHART_TREND": "draw", "FUNCTION_PLOT": "draw", "CALCULUS_VIZ": "draw",
    "CHART_CATEGORICAL": "grow", "CHART_RANKING": "grow",
    "CHART_RELATIONSHIP": "pop",
    "KPI": "count-up",
    "ALGORITHM_TRACE": "trace", "DATA_STRUCTURE": "trace",
    "PROCESS_LINEAR": "slide-left", "PROCESS_CYCLIC": "slide-left",
}
_INHERENTLY_ANIMATED = {"PHYSICS_DIAGRAM"}  # wave / orbit / pendulum sub-cases


def plan_animation_steps(bullets: List[str], treatment: str, family: str,
                         takeaway: str = "") -> Dict[str, Any]:
    """
    Deterministic progressive-reveal timeline (master prompt DECISION 5).

    Superset of ``plan_reveal_groups``: same grouping, plus a per-step label,
    an ``effect`` matched to the family, and the ``mode``. Capped at 7 steps
    (CLT working-memory limit); overflow is dropped from the animation but the
    bullets themselves are untouched (pagination handles them).
    """
    groups = plan_reveal_groups(bullets, treatment, has_takeaway=bool(takeaway))
    effect = _FAMILY_EFFECT.get(family, "fade")
    atomic = treatment in {"QUOTE", "METRIC", "DEFINITION"}
    mode = "static" if (atomic or len(groups) <= 1) else "build"

    steps: List[Dict[str, Any]] = []
    overflow = max(0, len(groups) - 7)
    for i, g in enumerate(groups[:7]):
        is_takeaway = bool(takeaway) and g == [len(bullets)]
        label = takeaway if is_takeaway else (
            bullets[g[0]] if (len(g) == 1 and g[0] < len(bullets)) else f"Reveal {i + 1}"
        )
        steps.append({
            "id": f"s{i + 1}",
            "label": label[:120],
            "adds": [f"el.{j}" for j in g],
            "transforms": [],
            "focus": [],
            "removes": [],
            "effect": "fade" if is_takeaway else effect,
            "duration_ms": 500 if effect in {"draw", "count-up"} else 400,
            "stagger_ms": 60 if len(g) > 1 else 0,
            "wait_for": "click",
        })
    if not steps:
        # A slide with no addressable bullets (e.g. a quiz) still needs one step.
        steps.append({
            "id": "s1", "label": takeaway[:120] if takeaway else "Show slide",
            "adds": ["all"], "transforms": [], "focus": [], "removes": [],
            "effect": effect, "duration_ms": 400, "stagger_ms": 0, "wait_for": "click",
        })
        mode = "static"
    if overflow:
        logger.debug("animation capped: %d reveal group(s) moved to a continuation slide", overflow)
    return {"mode": mode, "steps": steps, "overflow_groups": overflow}


_PRO_CUE = re.compile(r"\b(advantage|benefit|pro\b|strength|upside|plus|merit|"
                      r"faster|cheaper|simpler|easier|scal)", re.I)
_CON_CUE = re.compile(r"\b(disadvantage|drawback|con\b|weakness|downside|limitation|"
                      r"minus|risk|slower|costl|harder|complex|overfit)", re.I)


def build_family_data(bullets: List[str], family: str, f: "Features") -> Dict[str, Any]:
    """
    Best-effort structured data for a text-derivable family, so the renderers
    can draw a real visual without an LLM. Returns {} when nothing clean can be
    extracted (the renderer then falls back to a bullet list).
    """
    b = [x.strip() for x in bullets if x and x.strip()]
    if not b:
        return {}

    if family in {"PROCESS_LINEAR", "PROCESS_CYCLIC"}:
        steps = [re.sub(r"^\s*\d+[.)]\s*", "", s) for s in (f.steps or b)]
        steps = [s for s in steps if s][:8]
        if len(steps) >= 3:
            key = "stages" if family == "PROCESS_CYCLIC" else "steps"
            return {key: steps}

    if family == "TIMELINE":
        events = []
        for s in (f.chronology or b):
            m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", s)
            events.append({"date": m.group(1) if m else "", "title": s[:80]})
        events = [e for e in events if e["title"]][:8]
        if len(events) >= 3:
            return {"events": events}

    if family == "COMPARE_VISUAL":  # pros / cons
        pros = [s for s in b if _PRO_CUE.search(s) and not _CON_CUE.search(s)]
        cons = [s for s in b if _CON_CUE.search(s)]
        if pros and cons:
            return {"pros": pros[:5], "cons": cons[:5]}

    if family == "HIERARCHY_NEST":  # pyramid
        levels = [re.sub(r"^\s*(level|tier|layer)\s*\d*[:.\-]?\s*", "", s, flags=re.I) for s in b]
        levels = [s for s in levels if s][:5]
        if len(levels) >= 3:
            return {"levels": levels}

    if family == "LIST_STRUCTURED":  # card grid
        cards = []
        for s in b:
            m = re.match(r"^([A-Z][\w /&.\-]{1,34}):\s*(.+)$", s)
            if m:
                cards.append({"heading": m.group(1).strip(), "body": m.group(2).strip()})
            else:
                cards.append({"heading": "", "body": s})
        if 3 <= len(cards) <= 6:
            return {"cards": cards}

    if family == "SET_DIAGRAM":
        return {"sets": [], "items": b[:8]}

    if family == "DEFINITION":
        term = ""
        for t, d in (f.definitions or {}).items():
            term = t
            body = d
            break
        else:
            body = b[0] if b else ""
        if not term:
            m = re.match(r"^([A-Z][\w \-]{1,40})\s+(is|are|refers|means)\b", b[0] if b else "")
            term = m.group(1).strip() if m else (f.title if hasattr(f, "title") else "")
        return {"term": term, "definition": body, "notes": b[1:4]}

    if family == "QUOTE":
        m = re.search(r"[\"“]([^\"”]{10,})[\"”]", f.text)
        return {"text": m.group(1) if m else (b[0] if b else ""), "attribution": ""}

    if family == "KPI":  # metric
        val = next((n for n in (f.percentages + f.numbers)), "")
        return {"value": val, "label": (b[0][:60] if b else ""), "description": " ".join(b[1:3])}

    if family in {"FUNCTION_PLOT", "CALCULUS_VIZ"}:
        m = re.search(r"(?:y|f\s*\(\s*x\s*\))\s*=\s*([0-9x.+\-*/^() ]+)", f.text, re.I)
        if not m:
            return {}
        expr = m.group(1).strip().rstrip(".")
        dm = re.search(r"(?:for|on|where)\s*-?\d+\s*(?:<=|≤|<|to|,)\s*x\s*(?:<=|≤|<|to|,)\s*-?\d+", f.text, re.I)
        domain = [-5, 5]
        if dm:
            nums = re.findall(r"-?\d+(?:\.\d+)?", dm.group(0))
            if len(nums) >= 2:
                domain = [float(nums[0]), float(nums[-1])]
        return {"expr": expr, "domain": domain, "key_points": []}

    if family == "ALGORITHM_TRACE":
        am = re.search(r"\[\s*(-?\d+(?:\s*,\s*-?\d+)*)\s*\]", f.text)
        if not am:
            return {}
        initial = [int(x) for x in re.findall(r"-?\d+", am.group(1))]
        kind = "pointer_walk" if re.search(r"pointer|window|binary search", f.text, re.I) else "sort_bars"
        steps = [{"op": w.lower(), "args": []} for w in re.findall(r"\b(compare|swap|mark|split|merge|move)\b", f.text, re.I)][:6]
        return {"kind": kind, "initial": initial, "steps": steps}

    if family == "DATA_STRUCTURE":
        am = re.search(r"\[\s*([^\]]+)\s*\]", f.text)
        if not am:
            return {}
        items = [x.strip().strip("'\"") for x in am.group(1).split(",") if x.strip()][:12]
        kind = next((k for k in ("linked_list", "stack", "queue", "tree", "graph", "array")
                     if re.search(k.replace("_", " "), f.text, re.I)), "array")
        return {"kind": kind, "cells": [{"value": v} for v in items]}

    if family == "ML_VIZ":
        # No coordinates in prose -> hand the renderer a small illustrative set.
        return {}

    if family == "GEOMETRY":
        return {}

    return {}


def plan_reveal_groups(bullets: List[str], treatment: str,
                       has_takeaway: bool = False) -> List[List[int]]:
    """
    One idea per reveal step. Atomic treatments reveal in a single step; the
    takeaway (if any) is always the last group. Never reorders.
    """
    n = len(bullets)
    if treatment in {"QUOTE", "METRIC", "DEFINITION"} or n <= 1:
        groups = [list(range(n))] if n else []
    elif treatment == "COMPARISON_TABLE":
        groups = [[i] for i in range(n)]  # row by row
    elif treatment in {"PROS_CONS", "VENN"}:
        mid = (n + 1) // 2
        groups = [list(range(mid)), list(range(mid, n))] if n > 2 else [[i] for i in range(n)]
    else:
        groups = [[i] for i in range(n)]
    if has_takeaway:
        groups.append([n])  # index n == the takeaway slot
    return groups


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def select_visual(text: str, title: str = "", image_ocr: str = "") -> VisualDecision:
    """Score every treatment for this chunk and return the ranked decision."""
    combined = text if not image_ocr else f"{text}\n{image_ocr}"
    f = extract_features(combined, title)
    scores = _score(f)

    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]

    if best_score < _THRESHOLD:
        best = "KEEP_TEXT" if _looks_verbatim(f) else "MINIMAL_TEXT"
        rationale = (
            "No structural pattern cleared the threshold "
            f"(top candidate {max(scores, key=scores.get)} at {best_score:.1f}); "
            "kept as text."
        )
        confidence = 0.45
    else:
        runner_up = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
        margin = best_score - runner_up
        confidence = max(0.5, min(0.97, 0.55 + 0.09 * margin))
        rationale = _explain(best, f, best_score)

    # Prefer explicit line structure; but a single long prose line is not one
    # bullet — split it into sentences so reveal steps land per idea.
    if len(f.bullet_lines) > 1:
        bullets = list(f.bullet_lines)
    else:
        bullets = [s.strip() for s in _SENT.split(f.text) if s.strip()] or list(f.bullet_lines)
    verbatim = protect_verbatim(f.text)
    family, variant = TREATMENT_TO_FAMILY.get(best, ("TEXT", "minimal"))
    reveal = plan_reveal_groups(bullets, best, has_takeaway=False)
    animation = plan_animation_steps(bullets, best, family, takeaway="")
    data = build_family_data(bullets, family, f)

    return VisualDecision(
        treatment=best,
        family=family,
        variant=variant,
        confidence=confidence,
        rationale=rationale,
        scores=scores,
        bullets=bullets,
        verbatim=verbatim,
        reveal_groups=reveal,
        animation=animation,
        data=data,
    )


def _explain(treatment: str, f: Features, score: float) -> str:
    bits = {
        "FLOWCHART": f"{max(len(f.steps), f.step_cues)} ordered steps"
                     + (f", {f.decision_cues} decision points" if f.decision_cues else ""),
        "CYCLE": f"{f.loop_cues} loop/repeat cues over an ordered process",
        "TIMELINE": f"{max(len(f.chronology), len(set(f.years)))} dated events",
        "COMPARISON_TABLE": f"{len(f.comparisons) or f.compare_cues} compared aspects",
        "PROS_CONS": f"{f.procon_cues} advantage/disadvantage cues for one subject",
        "MATRIX_2X2": "two independent classification axes",
        "PYRAMID": f"{f.level_cues} level/tier cues that build on each other",
        "VENN": f"{f.set_cues} shared/unique-set cues",
        "MIND_MAP": f"{len(f.key_concepts)} loosely related concepts, no other structure",
        "CARD_GRID": "3+ parallel labelled pillars",
        "PIE_CHART": f"{len(f.percentages)} percentages summing to ~100",
        "LINE_CHART": "numeric series over an ordered/time dimension",
        "BAR_CHART": f"{len(f.numbers)} numeric values across categories",
        "METRIC": "a single headline figure carries the message",
        "DEFINITION": "one term is introduced and defined",
        "QUOTE": "a single memorable statement is the whole point",
        "KEEP_TEXT": "wording is precision-critical (definition/theorem/quote/code)",
        "BULLETS": "several discrete unrelated facts",
        "MINIMAL_TEXT": "connected explanatory prose",
    }.get(treatment, "structural match")
    return f"Chose {treatment} (score {score:.1f}): {bits}."


__all__ = [
    "Features",
    "VisualDecision",
    "extract_features",
    "select_visual",
    "plan_reveal_groups",
    "plan_animation_steps",
]
