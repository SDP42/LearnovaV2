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

MAX_CHUNKS = 80


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
