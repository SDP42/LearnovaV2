"""Tests for the Deck Director (rendering/deck_director.py)."""

from __future__ import annotations

from learnova.rendering.deck_director import (
    choose_summary_directive,
    choose_transition,
    plan_deck,
)


def _s(title, bullets, **imp):
    return {"improved": {"title": title, "bullets": bullets, **imp}, "original": {}}


# ── transitions ─────────────────────────────────────────────────────────────


def test_first_slide_transition_is_opening():
    t, reason, section = choose_transition(None, _s("Intro", ["a"]), set(), {"a"})
    assert t == "slide" and section is True


def test_continuation_slide_has_no_visual_break():
    prev = _s("The Krebs Cycle (1/2)", ["step one about acetyl coa"])
    curr = _s("The Krebs Cycle (2/2)", ["step two about citrate"])
    t, reason, _ = choose_transition(prev, curr, {"krebs", "cycle"}, {"krebs", "cycle"})
    assert t == "none"


def test_topic_shift_uses_convex():
    prev = _s("Photosynthesis", ["chlorophyll absorbs light energy in the chloroplast"])
    curr = _s("French Revolution", ["the bastille was stormed in 1789 by revolutionaries"])
    t, reason, section = choose_transition(
        prev, curr, {"chlorophyll", "light", "chloroplast"}, {"bastille", "revolution", "1789"}
    )
    assert t == "convex" and section is True


def test_related_slide_uses_fade():
    pw = {"neural", "network", "layer", "weights", "activation"}
    cw = {"neural", "network", "layer", "backpropagation", "weights"}
    t, reason, _ = choose_transition(_s("NN a", ["x"]), _s("NN b", ["y"]), pw, cw)
    assert t == "fade"


def test_quiz_slide_uses_concave():
    t, reason, _ = choose_transition(
        _s("Topic", ["x"]), _s("Checkpoint", [], layout_type="QUIZ", question="What is X?"),
        {"topic"}, {"checkpoint"},
    )
    assert t == "concave"


def test_section_head_uses_zoom():
    t, reason, section = choose_transition(
        _s("Details", ["lots of technical detail about the prior topic here"]),
        _s("Chapter 3: Optimisation", []),
        {"technical", "detail", "prior", "topic"}, {"chapter", "optimisation"},
    )
    assert t == "zoom" and section is True


# ── summary directive ───────────────────────────────────────────────────────


def test_verbatim_heavy_slide_is_preserve():
    text = ('Entropy is defined as the measure of disorder. The second law states '
            'that entropy never decreases. It is denoted by S.')
    d = choose_summary_directive(text, verbatim=[text[:30], text[31:60]], n_sentences=3)
    assert d == "PRESERVE"


def test_light_slide_is_balanced():
    d = choose_summary_directive("A short friendly sentence about the topic.", [], 1)
    assert d == "BALANCED"


# ── full plan ───────────────────────────────────────────────────────────────


def test_plan_deck_shape_and_notes():
    deck = [
        _s("Introduction to Sorting", ["Sorting arranges elements in order",
                                        "Common algorithms include bubble, merge and quick sort"]),
        _s("Bubble Sort Steps", ["First, compare adjacent elements",
                                  "Second, swap them if out of order",
                                  "Third, repeat until no swaps are needed"],
           takeaway="Bubble sort makes multiple passes swapping neighbours."),
        _s("Checkpoint", [], layout_type="QUIZ", question="Which sort is O(n log n)?"),
    ]
    plan = plan_deck(deck)
    assert len(plan.slides) == 3
    assert plan.est_minutes > 0
    # every slide has a transition and speaker notes
    for sp in plan.slides:
        assert sp.transition in {"none", "fade", "slide", "convex", "concave", "zoom"}
        assert sp.animation["steps"]
        assert sp.summary_directive in {"PRESERVE", "BALANCED", "COMPRESS"}
    # the steps slide should get a real progressive-reveal build
    steps_slide = plan.slides[1]
    assert len(steps_slide.animation["steps"]) >= 3
    assert "KEY POINT TO LAND" in steps_slide.speaker_notes
    # quiz slide gets the checkpoint transition
    assert plan.slides[2].transition == "concave"


def test_plan_deck_serialises():
    deck = [_s("A", ["one point here"]), _s("B", ["another point entirely different"])]
    out = plan_deck(deck).to_dict()
    assert "slides" in out and "est_minutes" in out
    assert out["slides"][0]["transition"] == "slide"
