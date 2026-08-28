"""
Re-render a deck from an edited slide list (the Preview editor).

Given the improved-slide list a user edited (titles, bullets, family), rebuild
the web deck and the PPTX and the display payload. No LLM, no pipeline stages —
just the deck director + the two renderers, so an edit is fast.
"""

from __future__ import annotations

from typing import Any, Dict, List

from learnova.logging_config import logger


def rebuild(editable_slides: List[dict], *, title: str = "Presentation",
            theme_id: str = "auto", theme_spec: Dict[str, Any] | None = None,
            images: Dict[int, tuple] | None = None,
            build_pptx: bool = True, build_html: bool = True) -> Dict[str, Any]:
    """Returns {html_bytes, pptx_bytes, slides_payload, scores, quizzes}."""
    from learnova.rendering.deck_payload import editable_to_final_deck, slides_payload
    from learnova.rendering.subprocess_builder import build_html_safe, build_pptx_safe
    from learnova.scoring.scorer import score_all_slides

    final_deck = editable_to_final_deck(editable_slides, images)

    try:
        scores = score_all_slides(final_deck)
    except Exception as exc:
        logger.warning("edit rebuild: scoring failed (%s)", exc)
        scores = {"slide_scores": [], "overall_score": 0}

    quizzes = [
        {
            "question": s.get("question"),
            "options": s.get("options"),
            "correct": s.get("correct"),
            "explanation": s.get("explanation"),
        }
        for s in editable_slides
        if str(s.get("layout_type", "")).upper() == "QUIZ" and s.get("question")
    ]

    html_bytes = pptx_bytes = None
    if build_html:
        try:
            html_bytes = build_html_safe(final_deck, topic_title=title,
                                         theme_id=theme_id, theme_spec=theme_spec)
        except Exception as exc:
            logger.error("edit rebuild: html failed (%s)", exc)
    if build_pptx:
        try:
            pptx_bytes = build_pptx_safe(final_deck, topic_title=title,
                                         theme_id=theme_id, theme_spec=theme_spec)
        except Exception as exc:
            logger.error("edit rebuild: pptx failed (%s)", exc)

    return {
        "html_bytes": html_bytes,
        "pptx_bytes": pptx_bytes,
        "slides_payload": slides_payload(final_deck),
        "scores": scores,
        "quizzes": quizzes,
    }


__all__ = ["rebuild"]
