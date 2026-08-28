"""
Pipeline stage: fill in structured visual data the regex extractor missed.

Runs the deterministic VMS over each slide; when it picks a data-hungry family
(chart, matrix, comparison table, mind map, dated timeline, …) but
``build_family_data`` came back empty, it asks the LLM once for the exact JSON
the renderer needs and stashes it on ``improved["visual_data"]`` so the deck
director uses it instead of falling back to bullets.

Bounded, rate-limit-aware, no-op without a provider.
"""

from __future__ import annotations

from typing import List

from learnova.logging_config import logger

MAX_LLM_EXTRACTIONS = 10
_MIN_CONFIDENCE = 0.55


def fill_visual_data(deck: List[dict]) -> int:
    """Attach ``improved['visual_data']`` where an LLM extraction helped. Returns count."""
    try:
        from learnova.ai.visual_data import LLM_EXTRACTABLE, extract_family_data
        from learnova.ai.visual_selector import build_family_data, extract_features, select_visual
    except Exception as exc:  # pragma: no cover - import guard
        logger.info("visual_data stage skipped: %s", exc)
        return 0

    filled = 0
    used_llm = 0
    for entry in deck:
        improved = entry.get("improved") if isinstance(entry.get("improved"), dict) else None
        if not improved:
            continue
        if str(improved.get("layout_type", "")).upper() == "QUIZ":
            continue

        original = entry.get("original") if isinstance(entry.get("original"), dict) else {}
        title = str(improved.get("title") or "")
        bullets = [str(b) for b in (improved.get("bullets") or []) if str(b).strip()]
        source = "\n".join(
            p for p in (str((original or {}).get("text") or "").strip(),
                        "\n".join(bullets)) if p
        )
        if not source.strip():
            continue

        vd = select_visual(source, title)
        if vd.family not in LLM_EXTRACTABLE or vd.confidence < _MIN_CONFIDENCE:
            continue

        # Heuristic first — free.
        try:
            f = extract_features(source, title)
            data = vd.data or build_family_data(vd.bullets or bullets, vd.family, f) or {}
        except Exception:
            data = vd.data or {}

        if not data:
            if used_llm >= MAX_LLM_EXTRACTIONS:
                continue
            data = extract_family_data(source, title, vd.family)
            used_llm += 1
            if not data:
                # A rate-limited provider returns {} for everything now — stop.
                if used_llm >= 3 and filled == 0:
                    logger.info("visual_data: no extractions landing, stopping early")
                    break
                continue

        improved["visual_data"] = {
            "family": vd.family,
            "variant": vd.variant,
            "data": data,
            "confidence": round(vd.confidence, 3),
        }
        filled += 1

    logger.info("visual_data: %d slide(s) enriched (%d via LLM)", filled, used_llm)
    return filled


__all__ = ["fill_visual_data", "MAX_LLM_EXTRACTIONS"]
