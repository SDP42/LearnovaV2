"""
The JSON-safe slide payload the frontend reads (Preview / Present / editor).

One place so the live-job path, the saved-deck path and the editor re-render
path all describe a slide the same way.
"""

from __future__ import annotations

from typing import Any, Dict, List


def slides_payload(final_deck: List[dict]) -> List[Dict[str, Any]]:
    plan_by_index: Dict[int, Any] = {}
    try:
        from learnova.rendering.deck_director import plan_deck

        for sp in plan_deck(final_deck).slides:
            plan_by_index[sp.index] = sp
    except Exception:  # director is advisory here
        plan_by_index = {}

    slides = []
    for index, entry in enumerate(final_deck):
        improved = entry.get("improved", {}) or {}
        original = entry.get("original", {}) or {}
        sp = plan_by_index.get(index)
        slides.append({
            "index": index,
            "layout_type": str(improved.get("layout_type", "MINIMAL_TEXT")).upper(),
            "title": improved.get("title", f"Slide {index + 1}"),
            "bullets": improved.get("bullets", []),
            "takeaway": improved.get("takeaway", ""),
            "mermaid_code": improved.get("mermaid_code"),
            "table_headers": improved.get("table_headers"),
            "table_rows": improved.get("table_rows"),
            "metric_value": improved.get("metric_value"),
            "metric_label": improved.get("metric_label"),
            "metric_desc": improved.get("metric_desc"),
            "question": improved.get("question"),
            "options": improved.get("options"),
            "correct": improved.get("correct"),
            "explanation": improved.get("explanation"),
            "difficulty": improved.get("difficulty"),
            "visual_source": improved.get("visual_source", "router"),
            "continued": bool(improved.get("continued")),
            "has_image": bool(original.get("image")),
            "source_text": original.get("text", ""),
            "family": getattr(sp, "family", None) or improved.get("family"),
            "variant": getattr(sp, "variant", None),
            "treatment": getattr(sp, "treatment", None),
            "transition": getattr(sp, "transition", None),
            "transition_reason": getattr(sp, "transition_reason", None),
            "summary_directive": getattr(sp, "summary_directive", None),
            "reveal_steps": len(getattr(sp, "animation", {}).get("steps", [])) if sp else 0,
            "speaker_notes": getattr(sp, "speaker_notes", ""),
            "est_seconds": getattr(sp, "est_seconds", None),
            "is_section_start": getattr(sp, "is_section_start", False),
        })
    return slides


def _fallback_family_data(fam: str, bullets: List[str], title: str) -> Dict[str, Any]:
    """A last-resort structured payload from a plain bullet list, per family."""
    b = [str(x).strip() for x in bullets if str(x).strip()][:12]
    if not b:
        return {}
    if fam in {"PROCESS_LINEAR", "WORKED_EXAMPLE"}:
        return {"steps": b, "rows": [{"step": x, "reason": ""} for x in b]}
    if fam == "PROCESS_CYCLIC":
        return {"stages": b}
    if fam == "MIND_MAP":
        return {"center": title or b[0], "branches": b if title else b[1:]}
    if fam == "HIERARCHY_NEST":
        return {"levels": b[:5]}
    if fam == "LIST_STRUCTURED":
        return {"cards": [{"heading": "", "body": x} for x in b[:6]]}
    if fam == "SET_DIAGRAM":
        return {"items": b[:8]}
    if fam == "TIMELINE":
        return {"events": [{"date": "", "title": x} for x in b[:8]]}
    if fam == "COMPARE_VISUAL":
        mid = (len(b) + 1) // 2
        return {"pros": b[:mid], "cons": b[mid:]}
    if fam in {"DEFINITION"}:
        return {"term": title, "definition": b[0], "notes": b[1:4]}
    if fam == "QUOTE":
        return {"text": b[0], "attribution": ""}
    return {}


# Fields a client may edit and send back; anything else is derived.
_EDITABLE_KEYS = (
    "layout_type", "title", "bullets", "takeaway", "family",
    "mermaid_code", "table_headers", "table_rows",
    "question", "options", "correct", "explanation", "source_text",
)


def payload_to_editable(payload: List[dict]) -> List[Dict[str, Any]]:
    """Project a display ``slides_payload`` down to the editable-slide shape
    (``_EDITABLE_KEYS``). One definition, used by both the persist hook and the
    deck-library fallback, so the two can't drift."""
    out: List[Dict[str, Any]] = []
    for s in payload or []:
        s = s or {}
        row = {k: s.get(k) for k in _EDITABLE_KEYS}
        row["layout_type"] = row.get("layout_type") or "MINIMAL_TEXT"
        row["title"] = row.get("title") or ""
        row["bullets"] = list(row.get("bullets") or [])
        row["takeaway"] = row.get("takeaway") or ""
        row["source_text"] = row.get("source_text") or ""
        out.append(row)
    return out


def editable_to_final_deck(editable: List[dict],
                           images: Dict[int, tuple] | None = None) -> List[dict]:
    """Rebuild a minimal ``final_deck`` (original/improved pairs) from edited slides.

    ``images`` maps a slide index to ``(bytes, ext)`` — the figure persisted with
    the deck (and any crop/annotation the user applied). Text, structure, family
    and figures all round-trip.
    """
    images = images or {}
    deck = []
    for i, s in enumerate(editable or []):
        s = s or {}
        improved = {k: s.get(k) for k in _EDITABLE_KEYS if s.get(k) is not None}
        improved.setdefault("layout_type", "MINIMAL_TEXT")
        improved.setdefault("title", "")
        improved.setdefault("bullets", [])
        fam = s.get("family")
        # A user-forced family is carried as visual_data so the director adopts
        # it. Build the renderer payload from the bullets right here — try the
        # cheap heuristic first, and fall back to a bare structure the renderers
        # can still use (steps / items / branches).
        vdata = None
        if fam and fam not in {"AUTO", "auto", "", "TEXT"}:
            data = dict(s.get("visual_data") or {})
            bullets = [b for b in (improved.get("bullets") or []) if str(b).strip()]
            if not data and bullets:
                try:
                    from learnova.ai.visual_selector import build_family_data, extract_features

                    f = extract_features("\n".join(bullets), improved.get("title", ""))
                    data = build_family_data(bullets, fam, f) or {}
                except Exception:
                    data = {}
            if not data and bullets:
                data = _fallback_family_data(fam, bullets, improved.get("title", ""))
            if data:
                vdata = {"family": fam, "variant": s.get("variant") or "default",
                         "confidence": 0.9, "data": data, "forced": True}
        original = {"text": s.get("source_text", "") or "\n".join(improved.get("bullets") or [])}
        img = images.get(i)
        if img and img[0]:
            original["image"] = {
                "bytes": img[0], "ext": img[1] or "png",
                "description": s.get("image_caption", "") or improved.get("title", ""),
            }
        entry = {
            "original": original,
            "improved": {**improved, **({"visual_data": vdata} if vdata else {})},
        }
        deck.append(entry)
    return deck


__all__ = ["slides_payload", "editable_to_final_deck", "payload_to_editable"]
