"""
AI Improver Module for Learnova
Uses Groq and Layout Router to transform raw slide text into structured, visual educational content.

IMPORTANT: Do NOT use ThreadPoolExecutor here.
httpx.Client has internal keepalive connection pool background threads. When a ThreadPoolExecutor
exits and Python GC destroys the GroqProvider (httpx client), those background threads crash
macOS with exit code 139 (SIGSEGV). Sequential processing with singleton provider is safe.
"""

import os

from learnova.ai.layout_router import classify_and_structure_chunk
from learnova.logging_config import logger

# A hard ceiling only to bound cost on a pathological input — high enough that
# a real lecture (with per-phase slide explosion) is never truncated. Content
# preservation beats a shorter deck; see docs/MASTER_PROMPT.md.
MAX_CHUNKS = int(os.getenv("LEARNOVA_MAX_CHUNKS", "400"))

# The LLM path must not summarise a section away. When its own bullets carry
# less than this fraction of the (now fully verbatim) extractive baseline, we
# keep the LLM's layout / title / visual choices but swap in the extractive
# bullets. At 0.95 the model has to keep essentially everything.
_MIN_RETENTION_VS_EXTRACTIVE = float(os.getenv("LEARNOVA_MIN_RETENTION", "0.95"))


def _wc(bullets) -> int:
    return sum(len(str(b).split()) for b in (bullets or []))


def _reconcile_with_extractive(improved: dict, chunk_text: str, chunk_title: str) -> dict:
    """Guarantee content retention: fall back to extractive bullets when the
    LLM dropped too much, without losing its layout/visual choices."""
    try:
        from learnova.ai.extractive import structure_chunk as _sc

        base = _sc(chunk_text, chunk_title)
    except Exception:
        return improved

    # Judge the model on what it actually wrote, not on the restore-padded list.
    raw = improved.get("_llm_bullets_raw")
    llm_wc = _wc(raw if raw is not None else improved.get("bullets"))
    base_wc = _wc(base.get("bullets"))
    improved.pop("_llm_bullets_raw", None)
    if base_wc and llm_wc < _MIN_RETENTION_VS_EXTRACTIVE * base_wc:
        logger.info(
            "[improver] LLM bullets kept %d/%d words (<%.0f%%) — using extractive bullets for %r",
            llm_wc, base_wc, _MIN_RETENTION_VS_EXTRACTIVE * 100, chunk_title[:40],
        )
        merged = dict(improved)
        merged["bullets"] = base.get("bullets") or improved.get("bullets")
        if not str(merged.get("takeaway", "")).strip():
            merged["takeaway"] = base.get("takeaway", "")
        return merged
    return improved


def _provider_available() -> bool:
    if os.getenv("LEARNOVA_NO_LLM", "").lower() in {"1", "true", "yes", "on"}:
        return False
    try:
        from learnova.providers.router import get_router

        return bool(get_router().available)
    except Exception:
        return False


def improve_chunks(chunks: list[dict]) -> list[dict]:
    """
    Transform raw text chunks into visually classified slide items.
    Sequential execution — safe on macOS with httpx connection pools.

    With no LLM provider configured we use the extractive summariser
    (``ai/extractive.py``) rather than dumping raw sentences onto slides.
    """
    capped = chunks[:MAX_CHUNKS]
    results = []

    use_extractive = not _provider_available()
    if use_extractive:
        from learnova.ai.extractive import structure_chunk

        logger.info("No LLM provider — using extractive summariser for all chunks")

    for i, chunk in enumerate(capped):
        chunk_text = (chunk.get("text") or "").strip()
        chunk_title = (chunk.get("title") or "").strip()

        try:
            if use_extractive:
                improved = structure_chunk(chunk_text, chunk_title)
            else:
                improved = classify_and_structure_chunk(chunk_text, chunk_title)
                improved = _reconcile_with_extractive(improved, chunk_text, chunk_title)
        except Exception as e:
            logger.error("Error structuring chunk %d: %s", chunk.get("id", i), e)
            from learnova.ai.extractive import structure_chunk as _sc

            try:
                improved = _sc(chunk_text, chunk_title)
            except Exception:
                improved = {
                    "layout_type": "MINIMAL_TEXT",
                    "title": chunk_title or "Overview",
                    "bullets": [chunk_text[:200]],
                    "takeaway": "",
                }

        results.append({
            "original": chunk,
            "improved": improved,
        })

    logger.info("Improved and visually routed %d / %d chunks", len(results), len(chunks))
    return results
