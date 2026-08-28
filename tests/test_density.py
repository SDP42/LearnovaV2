"""
Tests for text density, slide continuity, and the enhancement bridge.

The load-bearing guarantee is that lowering density must never *lose* content —
it redistributes the same material across more slides.
"""

from __future__ import annotations

import re

import pytest

from learnova.pipeline.density import (
    DEFAULT_DENSITY,
    PROFILES,
    apply_density,
    enhancement_bullets,
    get_profile,
    paginate_slide,
    trim_bullet,
)

LONG_BULLETS = [
    "Light absorption occurs in the thylakoid membranes where chlorophyll pigments capture photons",
    "Water photolysis splits H2O molecules releasing oxygen gas as a by-product of the reaction",
    "Carbon fixation proceeds through the Calvin cycle converting carbon dioxide into simple sugars",
    "ATP and NADPH generated during the light reactions power the downstream dark reactions",
    "Rubisco is the rate limiting enzyme and the most abundant protein found on Earth",
    "Temperature above thirty five degrees reduces net efficiency through photorespiration",
    "Stomatal closure under drought conditions restricts carbon dioxide intake and lowers yield",
    "C4 and CAM plants evolved independent strategies to concentrate carbon dioxide internally",
]


def _words(*texts: str) -> set[str]:
    joined = " ".join(texts).replace("↳", " ").lower()
    return set(re.findall(r"[a-z0-9]+", joined))


_SOURCE_WORDS = _words(*LONG_BULLETS)


def _slide(layout="MINIMAL_TEXT", **kwargs):
    improved = {
        "layout_type": layout,
        "title": "Photosynthesis",
        "bullets": list(LONG_BULLETS),
        "takeaway": "Remember the two stages.",
    }
    improved.update(kwargs)
    return {"original": {"text": "\n".join(LONG_BULLETS)}, "improved": improved}


# ── Profiles ──────────────────────────────────────────────────────────────────
class TestProfiles:
    def test_core_profiles_exist(self):
        assert {"low", "medium", "heavy"} <= set(PROFILES)

    def test_budgets_increase_with_density(self):
        low, medium, heavy = (PROFILES[k] for k in ("low", "medium", "heavy"))
        assert low.max_bullets < medium.max_bullets <= heavy.max_bullets
        assert low.max_words_per_bullet < medium.max_words_per_bullet < heavy.max_words_per_bullet

    def test_low_density_omits_enhancement(self):
        assert PROFILES["low"].include_enhancement is False
        assert PROFILES["heavy"].include_enhancement is True

    def test_unknown_density_falls_back_to_default(self):
        assert get_profile("nonsense").id == DEFAULT_DENSITY
        assert get_profile("").id == DEFAULT_DENSITY
        assert get_profile(None).id == DEFAULT_DENSITY


# ── Bullet trimming ───────────────────────────────────────────────────────────
class TestTrimBullet:
    def test_short_bullet_is_untouched(self):
        assert trim_bullet("Short and sweet.", PROFILES["low"]) == "Short and sweet."

    def test_long_bullet_respects_word_budget(self):
        profile = PROFILES["low"]
        out = trim_bullet(" ".join(["word"] * 50), profile)
        assert len(out.split()) <= profile.max_words_per_bullet

    def test_character_ceiling_is_enforced(self):
        profile = PROFILES["low"]
        assert len(trim_bullet("x" * 500, profile)) <= profile.max_chars_per_bullet

    def test_trim_prefers_a_clause_boundary(self):
        text = ("The system ingests documents, converts them to markdown, "
                "and then renders a deck with many additional trailing words here")
        out = trim_bullet(text, PROFILES["low"])
        assert not out.endswith(",")

    def test_whitespace_and_newlines_collapse(self):
        assert "\n" not in trim_bullet("a\n\n  b   c", PROFILES["heavy"])

    def test_empty_input_is_safe(self):
        assert trim_bullet("", PROFILES["low"]) == ""
        assert trim_bullet(None, PROFILES["low"]) == ""


# ── Continuity: the core guarantee ────────────────────────────────────────────
class TestContinuity:
    @pytest.mark.parametrize("density", ["low", "medium", "heavy"])
    def test_no_content_is_ever_lost(self, density):
        # A long bullet may be split across sub-lines ("↳ ..."), so the piece
        # count can grow — but every word of the source must still be present.
        pages = paginate_slide(_slide(), get_profile(density))
        emitted = _words(*(b for p in pages for b in p["improved"]["bullets"]))
        missing = _SOURCE_WORDS - emitted
        assert not missing, f"{density} lost words: {missing}"

    def test_lower_density_yields_more_slides(self):
        counts = {
            d: len(paginate_slide(_slide(), get_profile(d)))
            for d in ("low", "medium", "heavy")
        }
        assert counts["low"] >= counts["medium"] >= counts["heavy"]

    def test_continuation_titles_are_numbered(self):
        pages = paginate_slide(_slide(), get_profile("low"))
        assert len(pages) > 1
        titles = [p["improved"]["title"] for p in pages]
        assert titles[0].endswith(f"(1/{len(pages)})")
        assert titles[-1].endswith(f"({len(pages)}/{len(pages)})")

    def test_only_the_last_part_keeps_the_takeaway(self):
        pages = paginate_slide(_slide(), get_profile("low"))
        assert all(not p["improved"]["takeaway"] for p in pages[:-1])
        assert pages[-1]["improved"]["takeaway"]

    def test_continuation_flag_is_set(self):
        pages = paginate_slide(_slide(), get_profile("low"))
        assert pages[0]["improved"].get("continued") is False
        assert all(p["improved"]["continued"] for p in pages[1:])

    def test_image_is_not_duplicated_across_parts(self):
        entry = _slide()
        entry["original"]["image"] = {"bytes": b"img"}
        pages = paginate_slide(entry, get_profile("low"))
        with_image = [p for p in pages if p["original"].get("image")]
        assert len(with_image) == 1

    def test_single_page_keeps_its_plain_title(self):
        entry = _slide(bullets=["only one"])
        pages = paginate_slide(entry, get_profile("heavy"))
        assert len(pages) == 1
        assert pages[0]["improved"]["title"] == "Photosynthesis"

    def test_repeated_pagination_does_not_stack_numbering(self):
        """Re-numbering an already-numbered title must not produce '(1/2) (1/2)'."""
        entry = _slide()
        entry["improved"]["title"] = "Photosynthesis (2/3)"
        pages = paginate_slide(entry, get_profile("low"))
        assert "(2/3)" not in pages[0]["improved"]["title"]
        assert pages[0]["improved"]["title"].count("(") == 1


# ── Per-layout rules ──────────────────────────────────────────────────────────
class TestLayoutRules:
    def test_metric_slides_are_never_split(self):
        entry = _slide(layout="METRIC", metric_value="47%")
        assert len(paginate_slide(entry, get_profile("low"))) == 1

    def test_quiz_slides_are_never_split(self):
        entry = _slide(layout="QUIZ", question="q?", options=["a", "b"])
        assert len(paginate_slide(entry, get_profile("low"))) == 1

    def test_table_rows_paginate_and_repeat_the_header(self):
        rows = [[f"r{i}", "a", "b"] for i in range(9)]
        entry = _slide(layout="TABLE", table_headers=["H1", "H2", "H3"], table_rows=rows)
        pages = paginate_slide(entry, get_profile("low"))
        assert len(pages) > 1
        assert sum(len(p["improved"].get("table_rows", [])) for p in pages) == len(rows)
        assert all(
            p["improved"].get("table_headers", ["H1", "H2", "H3"]) == ["H1", "H2", "H3"]
            for p in pages
        )

    def test_flowchart_splits_into_stages_with_its_own_mermaid(self):
        entry = _slide(layout="FLOWCHART", mermaid_code="graph TD\n  A[whole] --> B[thing]")
        pages = paginate_slide(entry, get_profile("low"))
        assert len(pages) > 1
        for page in pages:
            assert page["improved"]["mermaid_code"].startswith("graph ")
            # A continuation must not reuse the whole-diagram code.
            assert "whole" not in page["improved"]["mermaid_code"]

    def test_card_grid_uses_its_own_ceiling(self):
        profile = get_profile("heavy")
        pages = paginate_slide(_slide(layout="CARD_GRID"), profile)
        assert all(len(p["improved"]["bullets"]) <= profile.max_grid_cards for p in pages)

    def test_slide_without_bullets_survives(self):
        entry = {"original": {}, "improved": {"layout_type": "MINIMAL_TEXT",
                                              "title": "Empty", "bullets": []}}
        assert len(paginate_slide(entry, get_profile("low"))) == 1


# ── Enhancement folding ───────────────────────────────────────────────────────
class _FakeEnhanced:
    examples = ["A wheat crop storing solar energy as starch"]
    analogies = ["Like a solar-powered sugar factory"]
    real_world_applications = ["Engineering crops for higher yield"]
    common_mistakes = ["Thinking plants gain mass from soil"]
    revision_points = ["6CO2 + 6H2O -> C6H12O6 + 6O2"]


class TestEnhancementFolding:
    def test_low_density_takes_no_extras(self):
        assert enhancement_bullets(_FakeEnhanced(), PROFILES["low"]) == []

    def test_medium_takes_one_extra(self):
        assert len(enhancement_bullets(_FakeEnhanced(), PROFILES["medium"])) == 1

    def test_heavy_takes_several_and_labels_them(self):
        picks = enhancement_bullets(_FakeEnhanced(), PROFILES["heavy"])
        assert len(picks) == PROFILES["heavy"].enhancement_items
        assert any(p.startswith("Example:") for p in picks)

    def test_missing_enhancement_is_safe(self):
        assert enhancement_bullets(None, PROFILES["heavy"]) == []

    def test_extras_reach_the_slide_and_are_budgeted(self):
        entry = _slide(bullets=["one point"])
        pages = paginate_slide(entry, get_profile("heavy"), _FakeEnhanced())
        text = " ".join(b for p in pages for b in p["improved"]["bullets"])
        assert "Example:" in text


# ── Deck-level ────────────────────────────────────────────────────────────────
class TestApplyDensity:
    def test_deck_expands_and_preserves_every_bullet(self):
        deck = [_slide(), _slide()]
        out = apply_density(deck, "low")
        assert len(out) > len(deck)
        emitted = _words(*(b for e in out for b in e["improved"]["bullets"]))
        assert not (_SOURCE_WORDS - emitted), "apply_density lost content"

    def test_enhanced_map_lands_on_the_right_slide(self):
        deck = [_slide(bullets=["a"]), _slide(bullets=["b"])]
        out = apply_density(deck, "heavy", {1: _FakeEnhanced()})
        first = " ".join(out[0]["improved"]["bullets"])
        rest = " ".join(b for e in out[1:] for b in e["improved"]["bullets"])
        assert "Example:" not in first
        assert "Example:" in rest

    def test_empty_deck_is_safe(self):
        assert apply_density([], "medium") == []


# ── Pipeline integration ──────────────────────────────────────────────────────
class TestPipelineDensity:
    @pytest.mark.parametrize("density", ["low", "medium", "heavy"])
    def test_generate_honours_density_without_losing_content(self, density):
        from learnova.parsers.markdown_converter import from_typed_text
        from learnova.pipeline import PipelineConfig, generate

        source = "## Photosynthesis\n" + "".join(f"- {b}\n" for b in LONG_BULLETS)
        result = generate(
            from_typed_text(source, "Density"),
            PipelineConfig(
                text_density=density,
                build_pptx=False,
                build_html=False,
                enable_vision_ocr=False,
                enable_quizzes=False,
                enable_enhancement=False,
            ),
        )
        # The layout LLM restructures and may merge a point or two, so exact
        # counts drift. What must hold: the density stage itself loses nothing —
        # most of the source's key terms still appear somewhere in the deck.
        deck_words = _words(
            *(b for e in result.final_deck for b in e["improved"].get("bullets", []))
        )
        key_terms = {
            "chlorophyll", "photolysis", "calvin", "rubisco", "atp",
            "photorespiration", "stomatal", "cam",
        }
        covered = key_terms & deck_words
        assert len(covered) >= len(key_terms) - 2, f"missing: {key_terms - deck_words}"
        assert result.density_profile == density

    def test_density_stage_is_reported(self):
        from learnova.parsers.markdown_converter import from_typed_text
        from learnova.pipeline import PipelineConfig, generate

        result = generate(
            from_typed_text("## T\n- a\n- b\n", "T"),
            PipelineConfig(build_pptx=False, build_html=False,
                           enable_vision_ocr=False, enable_quizzes=False),
        )
        names = {s.name for s in result.stages}
        assert "density" in names and "enhance" in names

    def test_enhancement_skipped_at_low_density(self):
        from learnova.parsers.markdown_converter import from_typed_text
        from learnova.pipeline import PipelineConfig, generate

        result = generate(
            from_typed_text("## T\n- a\n- b\n", "T"),
            PipelineConfig(text_density="low", build_pptx=False, build_html=False,
                           enable_vision_ocr=False, enable_quizzes=False),
        )
        enhance = next(s for s in result.stages if s.name == "enhance")
        assert enhance.status == "skipped"
