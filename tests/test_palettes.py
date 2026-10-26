"""Palette library and templates: every palette must be legible, every template must render."""
import io

import pytest

from learnova.rendering.palettes import CATEGORIES, PALETTES, audit, pick_for_topic, search_palettes
from learnova.rendering.templates import TEMPLATES, get_template
from learnova.rendering.theme_engine import resolve_theme, get_theme


def test_library_size_and_uniqueness():
    assert len(PALETTES) >= 200
    assert len({(p.primary, p.accent, p.bg) for p in PALETTES.values()}) == len(PALETTES)
    assert len(CATEGORIES) >= 5


@pytest.mark.parametrize("pid", sorted(PALETTES))
def test_every_palette_is_legible(pid):
    a = audit(PALETTES[pid])
    assert a["text_on_bg"] >= 7 and a["text_on_card"] >= 7
    assert a["subtext_on_bg"] >= 4.5 and a["primary_on_bg"] >= 4.5
    assert a["label_on_primary"] >= 4.5 and a["label_on_accent"] >= 4.5


def test_search_and_topic_pick_are_deterministic():
    assert search_palettes(q="blue", mode="light")
    assert not search_palettes(q="zzzz")
    assert pick_for_topic("Intro to Biology").id == pick_for_topic("Intro to Biology").id
    assert pick_for_topic("Intro to Biology").mode == "light"


def test_library_ids_resolve_and_template_applies():
    t = get_theme("royal_blue_night")
    assert t.bg_hex != "#ffffff"
    assert resolve_theme("x", "royal_blue_clean", {"template_id": "poster"}).template_id == "poster"
    assert resolve_theme("x", "auto", {"template_id": "nope"}).template_id == "classic"
    assert get_template(None).id == "classic"


@pytest.mark.parametrize("tid", sorted(TEMPLATES))
def test_every_template_builds_a_valid_deck(tid):
    from pptx import Presentation
    from learnova.rendering.ppt_builder import build_pptx

    slides = [{"original": {"title": "Intro", "text": "t"},
               "improved": {"title": "Machine learning basics", "layout_type": "MINIMAL_TEXT",
                            "bullets": ["Models learn from data.", "Loss measures error."], "takeaway": "Learning means reducing error."}}]
    data = build_pptx(slides, "Machine Learning", "auto", {"template_id": tid})
    prs = Presentation(io.BytesIO(data))
    assert len(prs.slides) >= 2
