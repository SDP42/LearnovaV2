"""
The Learnova pipeline, decoupled from any UI.

This module contains **zero** Streamlit/FastAPI imports. Both frontends drive
the same code path and differ only in how they render ``StageEvent`` progress.

The run is split into two halves so an editable markdown review step can sit
between them:

    build_markdown(...)   →  MarkdownDocument   (fast; user may edit the text)
    generate(...)         →  PipelineResult     (slow; LLM + rendering)

``run_all()`` chains both for callers that do not want the review step.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional

from learnova.config import DEFAULT_QUIZ_FREQUENCY
from learnova.pipeline.density import DEFAULT_DENSITY
from learnova.logging_config import logger

# Progress callback: (stage_name, status, fraction_complete, detail)
ProgressFn = Callable[[str, str, float, str], None]

# Below roughly one short paragraph of real text there is nothing to build a
# deck from, and continuing produces a deck whose only content slide reads
# "Page 1" — indistinguishable from a renderer bug.
_MIN_EXTRACTED_CHARS = 120

# Marker wrapping a figure's OCR text inside a chunk. The layout classifier and
# visual selector read it; every bulletiser strips it (textutils.strip_ocr_block).
_OCR_OPEN = "<<FIGURE_TEXT>>"
_OCR_CLOSE = "<<END_FIGURE_TEXT>>"

STAGES: List[str] = [
    "convert",
    "chunk",
    "vision_ocr",
    "index",
    "layout",
    "visual_plan",
    "visual_data",
    "expand",
    "enhance",
    "density",
    "quiz",
    "score",
    "build_pptx",
    "build_html",
]


@dataclass
class PipelineConfig:
    """Everything the pipeline needs that is not the document itself."""

    theme_id: str = "auto"
    # User-chosen palette/typography from the studio UI:
    #   {"primary": "#...", "secondary": "#...", "background": "#...",
    #    "font_id": "anton_poppins"}
    # When present it overrides theme_id entirely.
    theme_spec: Optional[Dict[str, Any]] = None
    quiz_frequency: int = DEFAULT_QUIZ_FREQUENCY
    # Explicit 1-indexed content-slide numbers to drop a checkpoint AFTER. When
    # set, overrides quiz_frequency and forces a standalone quiz slide.
    quiz_positions: Optional[List[int]] = None
    # "inline" = a band at the foot of a slide; "slide" = a dedicated
    # interactive checkpoint slide.
    quiz_style: str = "inline"
    textbook_mode: bool = False
    enable_vision_ocr: bool = True
    enable_quizzes: bool = True
    build_pptx: bool = True
    build_html: bool = True
    prefer_anydoc: bool = True
    use_cache: bool = True
    # Deterministic flowchart/table/KPI detection from the intelligence engine.
    enable_visual_planner: bool = True
    # How much text belongs on one slide: "low" | "medium" | "heavy".
    # Drives bullet counts, trimming, and when a slide overflows to the next.
    text_density: str = DEFAULT_DENSITY
    # Pedagogical enrichment (examples, analogies, revision points). LLM-backed,
    # so it is skipped automatically at low density or with no provider.
    enable_enhancement: bool = True
    # "compress" suits a 200-page PDF; "expand" suits a short typed syllabus.
    content_mode: str = "compress"


@dataclass
class StageEvent:
    name: str
    status: str          # "running" | "ok" | "failed" | "skipped"
    seconds: float = 0.0
    detail: str = ""


@dataclass
class PipelineResult:
    source_name: str
    markdown: str = ""
    converter: str = ""
    parsed_units: List[dict] = field(default_factory=list)
    chunks: List[dict] = field(default_factory=list)
    improved: List[dict] = field(default_factory=list)
    quizzes: List[dict] = field(default_factory=list)
    final_deck: List[dict] = field(default_factory=list)
    scores: Dict[str, Any] = field(default_factory=dict)
    pptx_bytes: Optional[bytes] = None
    html_bytes: Optional[bytes] = None
    stages: List[StageEvent] = field(default_factory=list)
    total_seconds: float = 0.0
    density_profile: str = DEFAULT_DENSITY

    def summary(self) -> dict:
        """JSON-safe summary (no raw bytes) for API responses and logging."""
        return {
            "source_name": self.source_name,
            "converter": self.converter,
            "slide_count": len(self.final_deck),
            "quiz_count": len(self.quizzes),
            "overall_score": self.scores.get("overall_score", 0),
            "density_profile": self.density_profile,
            "has_pptx": self.pptx_bytes is not None,
            "has_html": self.html_bytes is not None,
            "total_seconds": round(self.total_seconds, 2),
            "stages": [
                {"name": s.name, "status": s.status,
                 "seconds": round(s.seconds, 2), "detail": s.detail}
                for s in self.stages
            ],
        }


class _StageRunner:
    """Times each stage, reports progress, and records the outcome."""

    def __init__(self, result: PipelineResult, progress: Optional[ProgressFn]):
        self.result = result
        self.progress = progress
        self._index = 0

    def _emit(self, name: str, status: str, detail: str) -> None:
        if self.progress:
            fraction = self._index / len(STAGES)
            try:
                self.progress(name, status, fraction, detail)
            except Exception:  # a broken UI callback must never kill the run
                logger.debug("progress callback raised", exc_info=True)

    def run(self, name: str, fn: Callable[[], Any], *,
            critical: bool = False, skip: bool = False, skip_reason: str = "") -> Any:
        self._index += 1
        if skip:
            self.result.stages.append(StageEvent(name, "skipped", 0.0, skip_reason))
            self._emit(name, "skipped", skip_reason)
            return None

        self._emit(name, "running", "")
        started = time.time()
        try:
            value = fn()
        except Exception as exc:
            elapsed = time.time() - started
            self.result.stages.append(StageEvent(name, "failed", elapsed, str(exc)))
            self._emit(name, "failed", str(exc))
            logger.error("[pipeline] FAILURE %s (%.2fs): %s", name, elapsed, exc)
            if critical:
                raise
            return None

        elapsed = time.time() - started
        self.result.stages.append(StageEvent(name, "ok", elapsed))
        self._emit(name, "ok", "")
        logger.info("[pipeline] SUCCESS %s (%.2fs)", name, elapsed)
        return value


# ── Half 1: document → markdown ───────────────────────────────────────────────
def build_markdown(
    path: str,
    source_name: Optional[str] = None,
    config: Optional[PipelineConfig] = None,
):
    """Convert a document to the markdown IR. Cheap; safe to call eagerly."""
    from learnova.parsers.markdown_converter import convert_to_markdown

    config = config or PipelineConfig()
    return convert_to_markdown(
        path,
        source_name=source_name,
        textbook_mode=config.textbook_mode,
        use_cache=config.use_cache,
        prefer_anydoc=config.prefer_anydoc,
    )


# ── Half 2: markdown → deck ───────────────────────────────────────────────────
def generate(
    markdown_doc,
    config: Optional[PipelineConfig] = None,
    progress: Optional[ProgressFn] = None,
) -> PipelineResult:
    """
    Run every stage from the markdown IR through to rendered artifacts.

    ``markdown_doc`` is a ``MarkdownDocument``; its ``markdown`` field may have
    been edited by the user since ``build_markdown`` produced it.
    """
    from learnova.ai.improver import improve_chunks
    from learnova.ai.quiz_gen import generate_quizzes, interleave_quizzes_into_slides
    from learnova.parsers.markdown_converter import (
        attach_assets_to_units,
        sections_to_parsed_dicts,
        split_sections,
    )
    from learnova.pipeline.density import apply_density, get_profile
    from learnova.pipeline.enhancer import enhance_deck
    from learnova.pipeline.visual_planner import enrich_deck
    from learnova.rag.chunker import chunk_parsed_data, merge_chunks_by_section
    from learnova.rendering.subprocess_builder import build_html_safe, build_pptx_safe
    from learnova.scoring.scorer import score_all_slides

    config = config or PipelineConfig()

    # Short typed input is a lesson outline the user wants *taught*, not a long
    # document to compress. When they left the defaults, switch to the teaching
    # profile + expansion so every step is explained rather than trimmed.
    _typed_len = len(markdown_doc.markdown or "")
    if (markdown_doc.converter == "typed"
            and _typed_len < 2000
            and config.text_density == DEFAULT_DENSITY
            and config.content_mode == "compress"):
        config = replace(config, text_density="teaching", content_mode="expand")
        logger.info(
            "short typed input (%d chars) — using 'teaching' density + expansion pass",
            _typed_len,
        )

    result = PipelineResult(
        source_name=markdown_doc.source_name,
        markdown=markdown_doc.markdown,
        converter=markdown_doc.converter,
    )
    runner = _StageRunner(result, progress)
    started = time.time()

    # 1. Markdown → semantic sections (heading boundaries, not word windows)
    sections: List[dict] = []

    def _convert():
        nonlocal sections
        sections = split_sections(markdown_doc.markdown, max_level=2)
        result.parsed_units = sections_to_parsed_dicts(sections)

        # A scanned PDF extracts to almost nothing — page headers and little
        # else. Every downstream stage then runs happily on empty input and the
        # deck comes out with one slide reading "Page 1", which looks like a
        # bug in the renderer rather than a document that needs OCR. Say so.
        #
        # Typed input is exempt: a short outline is the user's own words and
        # however brief it is, it is deliberate — there is no failed extraction
        # to warn about.
        if markdown_doc.converter != "typed":
            body = " ".join(str(u.get("text") or "") for u in result.parsed_units)
            body = re.sub(r"(?i)\bpage\s*\d+\b", "", body).strip()
            if len(body) < _MIN_EXTRACTED_CHARS:
                has_images = bool(getattr(markdown_doc, "assets", None))
                raise ValueError(
                    f"Only {len(body)} characters of text could be extracted "
                    f"from {markdown_doc.source_name!r}. "
                    + (
                        "The document appears to be scanned or image-only, so "
                        "it needs OCR: set GEMINI_API_KEY and enable vision OCR."
                        if has_images
                        else "The document appears to be empty or unreadable."
                    )
                )
        return len(result.parsed_units)

    runner.run("convert", _convert, critical=True)

    # 2. Sections → chunks, with images anchored to the section that discusses
    #    them rather than to whichever one shares their list position.
    def _chunk():
        attached = attach_assets_to_units(
            result.parsed_units, sections, markdown_doc.assets
        )
        if attached:
            logger.info("anchored %d image(s) to their matching sections", attached)
        # One section becomes one slide; the density stage decides how much
        # fits and paginates the rest. Without this, a 22-paragraph section
        # produced 22 near-empty slides sharing one title.
        result.chunks = merge_chunks_by_section(chunk_parsed_data(result.parsed_units))
        return len(result.chunks)

    runner.run("chunk", _chunk, critical=True)

    # 3. Vision OCR over unique images
    def _vision():
        from learnova.ai.image_describer import describe_images

        pending, seen = [], set()
        for i, chunk in enumerate(result.chunks):
            image = chunk.get("image")
            if not image or not image.get("bytes"):
                continue
            key = hashlib.sha256(image["bytes"]).hexdigest()[:16]
            if key in seen:
                continue
            seen.add(key)
            pending.append({"index": i, "bytes": image["bytes"],
                            "ext": image.get("ext", "png")})
        if not pending:
            return 0

        described = describe_images(pending)
        by_bytes = {d["bytes"]: d["description"]
                    for d in described if "bytes" in d and "description" in d}
        for chunk in result.chunks:
            image = chunk.get("image")
            if not image:
                continue
            description = by_bytes.get(image.get("bytes"))
            if description:
                # Strip any nested marker the describer added; keep just the text.
                clean = re.sub(r"^\s*\[[^\n\]]*:?\s*|\s*\]\s*$", "", str(description)).strip()
                image["description"] = clean
                # A single-line, easily-stripped marker (see textutils.strip_ocr_block).
                chunk["text"] += f"\n\n{_OCR_OPEN}\n{clean}\n{_OCR_CLOSE}"
        return len(by_bytes)

    has_images = any(
        c.get("image") and c["image"].get("bytes") for c in result.chunks
    )
    runner.run(
        "vision_ocr", _vision,
        skip=not (config.enable_vision_ocr and has_images),
        skip_reason="no images" if not has_images else "disabled",
    )

    # 4. Keyword context store. Not queried by the main path, so failure is
    #    harmless — it exists for future retrieval-augmented stages.
    def _index():
        from learnova.rag.retriever import ChunkRetriever

        store = ChunkRetriever(result.chunks)
        count = len(store.get_all_chunks())
        del store
        return count

    runner.run("index", _index)

    # 5. Layout classification (LLM, with heuristic fallback inside)
    def _layout():
        result.improved = improve_chunks(result.chunks)
        # A takeaway that repeats verbatim across slides (a filler line, or the
        # same sentence the heuristic lifted twice) is noise — keep the first,
        # blank the rest. Also drop a takeaway that just restates a bullet.
        seen_tk: set = set()
        for entry in result.improved:
            imp = entry.get("improved") or {}
            tk = re.sub(r"\s+", " ", str(imp.get("takeaway", ""))).strip()
            if not tk:
                continue
            norm = re.sub(r"[^a-z0-9 ]", "", tk.lower())
            bullets_norm = " ".join(
                re.sub(r"[^a-z0-9 ]", "", str(b).lower()) for b in (imp.get("bullets") or [])
            )
            if norm in seen_tk or (len(norm) > 15 and norm in bullets_norm):
                imp["takeaway"] = ""
            else:
                seen_tk.add(norm)
        return len(result.improved)

    runner.run("layout", _layout, critical=True)

    # 6. Deterministic visual planning. Detects real flowcharts, comparison
    #    tables and KPI callouts from the text itself — the only source of
    #    visual structure when the input is a typed syllabus with no images.
    def _visual_plan():
        return enrich_deck(result.improved)

    runner.run(
        "visual_plan", _visual_plan,
        skip=not config.enable_visual_planner, skip_reason="disabled",
    )

    # 6a. Visual data — for slides whose chosen visual needs structured data
    #     (a chart, a 2x2 matrix, a comparison table, a mind map, a dated
    #     timeline) that the regex extractor could not pull, ask the LLM for it
    #     once. Attaches ``improved["visual_data"]`` for the deck director.
    #     Bounded, rate-limit-aware, and a no-op without a provider.
    _visual_data_on = os.getenv("LEARNOVA_VISUAL_DATA_LLM", "1").lower() in {"1", "true", "yes", "on"}

    def _visual_data():
        from learnova.pipeline.visual_data_stage import fill_visual_data

        return f"{fill_visual_data(result.improved)} slide(s) enriched"

    runner.run(
        "visual_data", _visual_data,
        skip=not _visual_data_on,
        skip_reason="LEARNOVA_VISUAL_DATA_LLM=0",
    )

    # 6b. Expansion pass — turn terse bullets into full teaching sentences that
    #     keep the reasoning. Only for lessons meant to be taught (content_mode
    #     "expand" or the "teaching" density). LLM-backed; degrades to a no-op.
    _do_expand = (
        config.content_mode == "expand"
        or str(config.text_density).lower() == "teaching"
    )

    def _expand():
        from learnova.pipeline.expander import expand_deck

        n = expand_deck(
            result.improved,
            density=config.text_density,
            content_mode=config.content_mode,
        )
        return f"{n} slide(s) expanded"

    runner.run(
        "expand", _expand,
        skip=not _do_expand,
        skip_reason="not a teaching build (content_mode!='expand', density!='teaching')",
    )

    # 7. Pedagogical enhancement — examples, analogies, revision points.
    #    Optional and LLM-backed; an empty result just means plainer slides.
    profile = get_profile(config.text_density)
    enhanced_by_index: Dict[int, Any] = {}

    def _enhance():
        nonlocal enhanced_by_index
        enhanced_by_index = enhance_deck(result.improved, density=config.text_density)
        return len(enhanced_by_index)

    runner.run(
        "enhance", _enhance,
        skip=not (config.enable_enhancement and profile.include_enhancement),
        skip_reason=("disabled" if not config.enable_enhancement
                     else f"density '{profile.id}' omits enrichment"),
    )

    # 8. Apply the density budget and paginate overflow onto continuation
    #    slides, so nothing is truncated.
    def _density():
        before = len(result.improved)
        result.improved = apply_density(
            result.improved, config.text_density, enhanced_by_index
        )
        result.density_profile = profile.id
        return f"{before} -> {len(result.improved)} slides"

    runner.run("density", _density)

    # 9. Quiz generation + interleaving
    def _quiz():
        result.quizzes = generate_quizzes(result.improved)
        result.final_deck = interleave_quizzes_into_slides(
            result.improved, result.quizzes,
            frequency=config.quiz_frequency,
            inline=(config.quiz_style != "slide"),
            positions=config.quiz_positions or None,
        )
        return len(result.final_deck)

    if config.enable_quizzes:
        runner.run("quiz", _quiz)
    else:
        runner.run("quiz", _quiz, skip=True, skip_reason="disabled")

    # A quiz failure must not cost us the deck.
    if not result.final_deck:
        result.final_deck = list(result.improved)

    # 7. Engagement scoring
    def _score():
        result.scores = score_all_slides(result.final_deck)
        return result.scores.get("overall_score", 0)

    if runner.run("score", _score) is None:
        result.scores = {"slide_scores": [], "overall_score": 0}

    # 11/12. Artifact rendering, each in an isolated interpreter
    def _pptx():
        result.pptx_bytes = build_pptx_safe(
            result.final_deck, topic_title=result.source_name,
            theme_id=config.theme_id, theme_spec=config.theme_spec,
        )
        return len(result.pptx_bytes or b"")

    runner.run("build_pptx", _pptx, skip=not config.build_pptx, skip_reason="disabled")

    def _html():
        result.html_bytes = build_html_safe(
            result.final_deck, topic_title=result.source_name,
            theme_id=config.theme_id, theme_spec=config.theme_spec,
        )
        return len(result.html_bytes or b"")

    runner.run("build_html", _html, skip=not config.build_html, skip_reason="disabled")

    result.total_seconds = time.time() - started
    logger.info("[pipeline] COMPLETE — total=%.1fs", result.total_seconds)
    return result


def run_all(
    path: str,
    source_name: Optional[str] = None,
    config: Optional[PipelineConfig] = None,
    progress: Optional[ProgressFn] = None,
) -> PipelineResult:
    """Convenience wrapper: convert then generate, with no review step."""
    config = config or PipelineConfig()
    markdown_doc = build_markdown(path, source_name=source_name, config=config)
    return generate(markdown_doc, config=config, progress=progress)


__all__ = [
    "PipelineConfig",
    "PipelineResult",
    "StageEvent",
    "STAGES",
    "build_markdown",
    "generate",
    "run_all",
]
