"""
Pipeline stage: let an LLM (when configured) refine the slides the deterministic engine is unsure about.

ONE batched request covers every uncertain slide (``ai/assist.refine_visuals``); answers are validated against
the renderers and stored on ``improved["visual_data"]`` with ``source="llm"``, which the Deck Director adopts.
No provider, or an engine that is confident everywhere → no request at all.
"""

from __future__ import annotations

from typing import List

from learnova.logging_config import logger

ENGINE_SURE = 0.7  # engine confidence above which no LLM call is made


def fill_visual_data(deck: List[dict]) -> int:
    """Attach ``improved['visual_data']`` for LLM-refined slides. Returns how many were refined."""
    from learnova.ai import assist

    if not assist.llm_available():
        return 0
    from learnova.ai.visual_selector import select_visual
    from learnova.visuals import decide

    uncertain = []
    for i, entry in enumerate(deck):
        imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else None
        if not imp or str(imp.get("layout_type", "")).upper() == "QUIZ":
            continue
        orig = entry.get("original") if isinstance(entry.get("original"), dict) else {}
        bullets = [str(b) for b in (imp.get("bullets") or []) if str(b).strip()]
        text = "\n".join(p for p in (str(orig.get("text") or "").strip(), "\n".join(bullets)) if p)
        title = str(imp.get("title") or "")
        if not text.strip():
            continue
        dec = decide(title, text, bullets, vms=select_visual(text, title))
        from learnova.ai.escalation import should_escalate

        if dec.confidence < ENGINE_SURE and dec.family not in {"COMPARE_TABLE", "REFERENCES"} and should_escalate("visual", True):
            uncertain.append({"id": i, "title": title, "text": text})
    answers = assist.refine_visuals(uncertain)
    for sid, a in answers.items():
        deck[sid]["improved"]["visual_data"] = {**a, "confidence": 0.9, "source": "llm"}
    logger.info("visual_data: %d uncertain slide(s), %d refined by the LLM in one request", len(uncertain), len(answers))
    return len(answers)


__all__ = ["fill_visual_data"]
