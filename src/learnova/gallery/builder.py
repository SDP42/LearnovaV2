"""
Batch-generate Gallery decks from the catalogue.

Each ``status: "outline"`` entry is run through the normal pipeline and saved
under the ``__gallery__`` user with the catalogue slug as its deck id. Safe to
re-run: existing decks are skipped unless ``--force``.

    PYTHONPATH=src .venv/bin/python -m learnova.gallery.builder --limit 20
    PYTHONPATH=src .venv/bin/python -m learnova.gallery.builder --subject Biology
    LEARNOVA_NO_LLM=1 PYTHONPATH=src .venv/bin/python -m learnova.gallery.builder --all
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from dataclasses import replace
from typing import Iterable, List


_LLM_ENV = ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_API_KEY",
            "NVIDIA_NIM_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEYS")


def _force_deterministic() -> None:
    """Gallery builds are reproducible and quota-free by default: blank the
    provider keys so every stage takes its deterministic path. Pass --llm to
    let the pipeline use whatever keys are configured."""
    # Blank (not pop): the many module-level ``load_dotenv()`` calls and
    # ``config.apply_runtime_env()`` (setdefault) would otherwise re-seed a
    # missing key from .env. An empty value already "exists", so it stays.
    for var in _LLM_ENV:
        os.environ[var] = ""
    os.environ["LEARNOVA_NO_LLM"] = "1"


# Run before any learnova import: the provider modules read keys at import time.
if "--llm" not in sys.argv:
    _force_deterministic()

from learnova.gallery.catalog import GALLERY_USER, CatalogEntry, list_entries
from learnova.gallery.store import has_deck
from learnova.logging_config import logger
from learnova.parsers.markdown_converter import from_typed_text
from learnova.pipeline.orchestrator import PipelineConfig, generate
from learnova.rendering.deck_payload import payload_to_editable, slides_payload
from learnova.storage import deck_library


def _config() -> PipelineConfig:
    # Teaching build: keep every point, one idea per slide, checkpoint quizzes.
    return replace(
        PipelineConfig(),
        text_density="teaching",
        content_mode="expand",
        theme_id="auto",
    )


_BUILD_ON = "var LV_BUILD = (function () {"


def _bake_progressive_reveal(html: bytes | None) -> bytes | None:
    """Gallery decks are made to be downloaded and taught from, so the web deck
    reveals bullets one click at a time by default (the built-in 'show all'
    toggle still turns it off)."""
    if not html:
        return html
    text = html.decode("utf-8", "replace")
    if _BUILD_ON in text and "window.__learnovaBuild = true" not in text:
        text = text.replace(_BUILD_ON, "window.__learnovaBuild = true;\n        " + _BUILD_ON, 1)
    return text.encode("utf-8")


def build_one(entry: CatalogEntry, config: PipelineConfig | None = None) -> dict:
    config = config or _config()
    doc = from_typed_text(entry.outline, source_name=entry.title)
    result = generate(doc, config)
    result.html_bytes = _bake_progressive_reveal(getattr(result, "html_bytes", None))

    payload = slides_payload(result.final_deck)
    editable = payload_to_editable(payload) if payload else None
    record = deck_library.save_deck(
        user_id=GALLERY_USER,
        result=result,
        theme_id=config.theme_id,
        theme_spec=config.theme_spec,
        title=entry.title,
        slides_payload=payload,
        editable_slides=editable,
        deck_id=entry.slug,
    )
    return record.to_dict()


def run(entries: Iterable[CatalogEntry], *, force: bool = False, limit: int | None = None) -> None:
    done = skipped = failed = 0
    config = _config()
    for entry in entries:
        if limit is not None and done >= limit:
            break
        if not force and has_deck(entry.slug):
            skipped += 1
            continue
        t0 = time.time()
        try:
            rec = build_one(entry, config)
            done += 1
            logger.info(
                "gallery: built %-40s %2d slides  %2d quizzes  score %2d  (%.0fs)",
                entry.slug, rec["slide_count"], rec["quiz_count"],
                rec["overall_score"], time.time() - t0,
            )
        except Exception:  # noqa: BLE001 — batch job, keep going
            failed += 1
            logger.error("gallery: FAILED %s\n%s", entry.slug, traceback.format_exc())
    logger.info("gallery build: %d built, %d skipped, %d failed", done, skipped, failed)


def _select(args) -> List[CatalogEntry]:
    entries = list_entries(subject=args.subject, ready_only=True)
    if args.slug:
        entries = [e for e in entries if e.slug in set(args.slug)]
    return entries


def main() -> None:
    p = argparse.ArgumentParser(description="Batch-build Gallery decks")
    p.add_argument("--subject", help="only this subject")
    p.add_argument("--slug", nargs="*", help="only these slugs")
    p.add_argument("--limit", type=int, help="stop after N new decks")
    p.add_argument("--all", action="store_true", help="build everything (no limit)")
    p.add_argument("--force", action="store_true", help="rebuild existing decks")
    p.add_argument("--llm", action="store_true", help="allow the pipeline to use configured LLM keys")
    args = p.parse_args()

    if not args.llm:
        _force_deterministic()

    entries = _select(args)
    limit = None if args.all else (args.limit or 10)
    logger.info("gallery build: %d candidate entries, limit=%s", len(entries), limit)
    run(entries, force=args.force, limit=limit)


if __name__ == "__main__":
    main()
