"""
Before/after analysis: what the source said vs what the new deck says.

For every slide it reports the source text, the new slide (visual chosen and
why, bullets, takeaway, notes), word counts, and — the part that answers "was
anything important lost?" — a **fact retention** check: numbers with units,
dates, formulae and defined terms are extracted from the source and searched for
in everything the new slide shows (title, bullets, visual data, notes).

Deterministic, no model, no network.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from learnova.visuals.engine import split_sentences

_NUM = re.compile(r"[$₹€£]?\d[\d,]*(?:\.\d+)?\s?(?:%|percent|billion|million|thousand|bn|mn|k|x|×|years?|months?|days?|hours?|minutes?)?", re.I)
_YEAR = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")
_FORMULA = re.compile(r"[A-Za-z][A-Za-z0-9_()]{0,6}\s*=\s*[^.;\n]{2,40}")
_TERM = re.compile(r"\b(?:[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+|[A-Z]{2,6}[a-z]?)\b")
_FAMILY_LABEL = {
    "PROCESS_LINEAR": "Process flow", "PROCESS_CYCLIC": "Cycle", "TIMELINE": "Timeline", "COMPARE_TABLE": "Comparison table",
    "COMPARE_VISUAL": "Pros & cons", "MATRIX_GRID": "2×2 matrix", "LAYERS": "Layered stack", "HIERARCHY_NEST": "Pyramid",
    "SET_DIAGRAM": "Venn diagram", "MIND_MAP": "Mind map", "LIST_STRUCTURED": "Card grid", "KEY_POINTS": "Key-point cards",
    "CHECKLIST": "Checklist", "STAT_TILES": "Stat tiles", "FUNNEL": "Funnel", "CAUSE_EFFECT": "Cause & effect",
    "DEFINITION": "Definition callout", "FORMULA_CALLOUT": "Formula callout", "QUOTE": "Statement callout",
    "CHART_CATEGORICAL": "Bar chart", "CHART_RANKING": "Ranked bars", "CHART_TREND": "Line chart", "CHART_PART_TO_WHOLE": "Pie chart",
    "FUNCTION_PLOT": "Function plot", "WORKED_EXAMPLE": "Worked example", "ALGORITHM_TRACE": "Algorithm trace",
    "DATA_STRUCTURE": "Data structure", "GEOMETRY": "Geometry figure", "ML_VIZ": "ML plot", "TEXT": "Plain text", "KPI": "KPI", "REFERENCES": "Reference list", "PROSE": "Text, relationships marked",
}


def _norm(s: str) -> str:
    return re.sub(r"[\s,]+", "", str(s).lower())


def extract_facts(text: str) -> List[Dict[str, str]]:
    """Facts worth protecting: figures, dates, formulae, named terms."""
    facts: List[Dict[str, str]] = []
    seen = set()

    def add(kind: str, value: str) -> None:
        v = value.strip(" .,;:()")
        k = (kind, _norm(v))
        if v and k not in seen:
            seen.add(k)
            facts.append({"kind": kind, "value": v})

    for m in _FORMULA.finditer(text):
        add("formula", re.split(r"\s+(?:gives|is|where|and|so)\b", m.group(0))[0])
    for m in _YEAR.finditer(text):
        add("date", m.group(0))
    for m in _NUM.finditer(text):
        tok = m.group(0).strip()
        if _YEAR.fullmatch(tok) or not re.search(r"\d", tok):
            continue
        if len(re.sub(r"\D", "", tok)) >= 1 and (re.search(r"[%$₹€£×x]|percent|illion|thousand|bn|mn|k\b", tok, re.I) or len(tok) >= 3):
            add("figure", tok)
    for m in _TERM.finditer(text):
        t = m.group(0)
        if len(t) > 3 and t.lower() not in {"the", "this", "that"}:
            add("term", t)
    return facts[:40]


def _slide_text(imp: Dict[str, Any], sp: Any) -> str:
    parts = [str(imp.get("title", "")), *map(str, imp.get("bullets") or []), str(imp.get("takeaway", ""))]
    if sp is not None:
        parts.append(json.dumps(sp.data, ensure_ascii=False, default=str))
        parts.extend((sp.params or {}).get("notes") or [])
        parts.append(str((sp.params or {}).get("takeaway", "")))
    return " ".join(parts)


def _preview(sp: Any) -> Dict[str, Any]:
    """A small, readable slice of the visual's data for the UI."""
    d = (sp.data or {}) if sp else {}
    for k in ("stages", "events", "tiles", "levels", "nodes", "cards", "points", "items", "pros", "quadrants", "rows"):
        if k in d and d[k]:
            return {"kind": k, "count": len(d[k]), "sample": d[k][:3]}
    return {"kind": "", "count": 0, "sample": []}


def build_analysis(result: Any) -> Dict[str, Any]:
    from learnova.rendering.deck_director import plan_deck

    deck: List[dict] = list(getattr(result, "final_deck", []) or [])
    plan = plan_deck(deck) if deck else None
    slides: List[Dict[str, Any]] = []
    tot_facts = kept_facts = 0
    wb = wa = vis_before = vis_after = illos = 0
    families: Dict[str, int] = {}

    for i, entry in enumerate(deck):
        imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else {}
        orig = entry.get("original") if isinstance(entry.get("original"), dict) else {}
        is_quiz = str(imp.get("layout_type", "")).upper() == "QUIZ"
        sp = plan.by_index(i) if plan else None
        src_text = str(orig.get("text") or "").strip()
        if is_quiz:
            slides.append({"index": i, "kind": "quiz", "title": imp.get("title", "Checkpoint"),
                           "quiz": {k: imp.get(k) for k in ("question", "options", "correct", "explanation", "difficulty")}})
            continue
        src_words = len(src_text.split())
        after_text = _slide_text(imp, sp)
        after_words = len(" ".join([str(imp.get("title", "")), *map(str, imp.get("bullets") or []), str(imp.get("takeaway", ""))]).split())
        facts = extract_facts(src_text)
        hay = _norm(after_text)
        missing = [f for f in facts if _norm(f["value"]) not in hay]
        has_fig = bool(orig.get("image"))
        has_tbl = "[TABLE DATA]" in src_text or bool(orig.get("table"))
        fam = sp.family if sp else "TEXT"
        label = _FAMILY_LABEL.get(fam, fam.replace("_", " ").title())
        families[label] = families.get(label, 0) + 1
        illo = imp.get("illustration")
        tot_facts += len(facts)
        kept_facts += len(facts) - len(missing)
        wb += src_words
        wa += after_words
        vis_before += 1 if (has_fig or has_tbl) else 0
        vis_after += 1 if fam not in {"TEXT", ""} else 0
        illos += 1 if illo else 0
        slides.append({
            "index": i, "kind": "content", "title": imp.get("title") or orig.get("title") or f"Slide {i + 1}",
            "before": {"title": orig.get("title", ""), "text": src_text, "words": src_words, "sentences": split_sentences(src_text)[:12],
                       "has_figure": has_fig, "has_table": has_tbl, "visual": "figure" if has_fig else "table" if has_tbl else "text only"},
            "after": {"title": imp.get("title", ""), "bullets": [str(b) for b in (imp.get("bullets") or [])],
                      "takeaway": (sp.params or {}).get("takeaway", imp.get("takeaway", "")) if sp else imp.get("takeaway", ""),
                      "notes": list((sp.params or {}).get("notes") or []) if sp else [], "words": after_words,
                      "family": fam, "family_label": label, "variant": sp.variant if sp else "",
                      "reason": sp.visual_reason if sp else "", "alternatives": [[_FAMILY_LABEL.get(f, f), c] for f, c in (sp.visual_alternatives if sp else [])],
                      "confidence": round(sp.confidence, 2) if sp else 0, "data_preview": _preview(sp),
                      "has_illustration": bool(illo), "illustration_reason": (imp.get("image_plan") or {}).get("reason", ""),
                      "illustration_icons": (illo or {}).get("icons", []), "transition": sp.transition if sp else ""},
            "change": {"words_delta": after_words - src_words,
                       "words_delta_pct": round(100 * (after_words - src_words) / max(1, src_words)),
                       "facts_total": len(facts), "facts_kept": len(facts) - len(missing), "facts_missing": missing[:8],
                       "visual": f"{'figure' if has_fig else 'table' if has_tbl else 'text only'} → {label}"},
        })

    content = [s for s in slides if s["kind"] == "content"]
    n = max(1, len(content))
    # PPTEval-style scorecard (deterministic): content fidelity, design balance, coherence
    balanced = sum(1 for s in content if 18 <= s["after"]["words"] <= 115 or s["after"]["family"] in {"COMPARE_TABLE", "REFERENCES"})
    titles = [s["title"].lower() for s in content]
    unique = len(set(titles)) / max(1, len(titles))
    aids = sum(1 for e in deck if isinstance(e.get("improved"), dict) and (e["improved"].get("key_terms") or e["improved"].get("is_overview") or e["improved"].get("is_glossary")))
    q_content = round(100 * kept_facts / tot_facts) if tot_facts else 100
    q_design = round((100 * vis_after / n + 100 * balanced / n) / 2)
    q_coherence = round((100 * unique + min(100, 100 * aids / max(1, n) * 2)) / 2)
    quality = {"content": q_content, "design": q_design, "coherence": q_coherence, "overall": round((q_content + q_design + q_coherence) / 3)}
    return {
        "summary": {
            "source_name": getattr(result, "source_name", ""),
            "slides_before": len({(s["before"]["title"] or s["title"]) for s in content}), "slides_after": len(content),
            "checkpoints": sum(1 for s in slides if s["kind"] == "quiz"),
            "words_before": wb, "words_after": wa, "words_change_pct": round(100 * (wa - wb) / max(1, wb)),
            "visual_slides_before": vis_before, "visual_slides_after": vis_after,
            "visual_coverage_before_pct": round(100 * vis_before / n), "visual_coverage_after_pct": round(100 * vis_after / n),
            "distinct_visual_types": len(families), "visual_types": families,
            "illustrations": illos, "facts_total": tot_facts, "facts_kept": kept_facts,
            "fact_retention_pct": round(100 * kept_facts / tot_facts) if tot_facts else 100,
            "engagement_score": int((getattr(result, "scores", {}) or {}).get("overall_score", 0) or 0),
            "quality": quality,
            "student_aids": {"key_term_slides": sum(1 for e in deck if isinstance(e.get("improved"), dict) and e["improved"].get("key_terms")),
                             "overview_slides": sum(1 for e in deck if isinstance(e.get("improved"), dict) and e["improved"].get("is_overview")),
                             "glossary_slides": sum(1 for e in deck if isinstance(e.get("improved"), dict) and e["improved"].get("is_glossary"))},
        },
        "slides": slides,
    }
