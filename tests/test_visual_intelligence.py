"""Tests for the visual-intelligence decision layer:
master_prompt, visual_selector, image_policy, text_policy."""

from __future__ import annotations

import pytest

from learnova.ai import master_prompt as mp
from learnova.ai.image_policy import ImageMeta, decide_image_action
from learnova.ai.text_policy import classify_sentences, protect_verbatim
from learnova.ai.visual_selector import (
    plan_animation_steps,
    plan_reveal_groups,
    select_visual,
)


# ── master prompt ───────────────────────────────────────────────────────────


def test_master_prompt_lists_every_family():
    for fam in mp.FAMILY_KEYS:
        assert fam in mp.MASTER_SYSTEM_PROMPT
    for token in ("animation", "steps", "verbatim", "family", "variant"):
        assert token in mp.MASTER_SYSTEM_PROMPT


def test_catalog_loads_and_has_many_variants():
    fams = mp.load_catalog().get("families", {})
    assert len(fams) >= 35
    total_variants = sum(len(f.get("variants", {})) for f in fams.values())
    assert total_variants >= 120
    # every flat treatment maps to a real catalog entry
    for t in mp.VISUAL_TREATMENTS:
        assert t.variant in mp.variants_for(t.family), (t.family, t.variant)


def test_build_user_prompt_includes_image_ocr_only_when_present():
    assert "EMBEDDED FIGURE" not in mp.build_user_prompt("text", "Title")
    assert "EMBEDDED FIGURE" in mp.build_user_prompt("text", "Title", image_ocr="arrow A -> B")


# ── visual selector ─────────────────────────────────────────────────────────


def test_ordered_steps_pick_flowchart():
    text = ("First, collect the sample. Second, stain the slide. "
            "Third, examine under the microscope. Finally, record the result.")
    d = select_visual(text, "Lab procedure")
    assert d.treatment == "FLOWCHART"
    assert d.confidence > 0.5


def test_repeating_process_picks_cycle():
    text = ("The water evaporates, then condenses into clouds, then falls as "
            "precipitation, then collects and the cycle repeats continuously.")
    d = select_visual(text, "Water cycle")
    assert d.treatment in {"CYCLE", "FLOWCHART"}
    assert d.scores["CYCLE"] > 0


def test_percentages_summing_to_100_pick_pie():
    text = ("Budget allocation: salaries 50%, equipment 30%, and overheads 20% "
            "of total spend.")
    d = select_visual(text, "Budget")
    assert d.treatment == "PIE_CHART"


def test_single_number_picks_metric():
    d = select_visual("Model accuracy reached 94% on the held-out test set.", "Result")
    assert d.treatment == "METRIC"


def test_comparison_picks_table_or_proscons():
    text = ("Supervised learning needs labelled data whereas unsupervised "
            "learning does not. Supervised is accurate; unsupervised scales "
            "cheaply. In contrast, unsupervised is harder to evaluate.")
    d = select_visual(text, "Learning paradigms")
    assert d.treatment in {"COMPARISON_TABLE", "PROS_CONS"}


def test_definition_heavy_text_is_kept_or_defined():
    text = ("Entropy is defined as the measure of disorder in a system. "
            "It is denoted by S. The second law states that entropy never "
            "decreases in an isolated system.")
    d = select_visual(text, "Entropy")
    assert d.treatment in {"KEEP_TEXT", "DEFINITION"}


def test_plain_prose_stays_text():
    text = ("Machine learning has grown popular in recent years and touches many "
            "parts of daily life in ways people rarely notice.")
    d = select_visual(text, "Intro")
    assert d.treatment in {"MINIMAL_TEXT", "BULLETS", "KEEP_TEXT"}


def test_decision_is_serialisable_and_explained():
    d = select_visual("Step 1 do X. Step 2 do Y. Step 3 do Z.", "P")
    out = d.to_dict()
    assert set(out) >= {"treatment", "family", "variant", "confidence",
                        "rationale", "scores", "reveal_groups", "animation"}
    assert d.treatment.lower() in d.rationale.lower()


def test_decision_carries_catalog_family_and_variant():
    d = select_visual("First, collect the sample. Second, stain it. Third, examine it.", "Lab")
    assert d.family == "PROCESS_LINEAR"
    assert d.variant in mp.variants_for(d.family)
    assert d.animation["mode"] in {"build", "static", "animate"}
    assert d.animation["steps"]


# ── progressive reveal ──────────────────────────────────────────────────────


def test_reveal_one_idea_per_step():
    groups = plan_reveal_groups(["a", "b", "c"], "BULLETS")
    assert groups == [[0], [1], [2]]


def test_reveal_atomic_treatment_single_step():
    assert plan_reveal_groups(["the whole quote"], "QUOTE") == [[0]]
    assert plan_reveal_groups(["x", "y"], "METRIC") == [[0, 1]]


def test_reveal_appends_takeaway_group():
    groups = plan_reveal_groups(["a", "b"], "BULLETS", has_takeaway=True)
    assert groups[-1] == [2]


def test_reveal_never_reorders():
    groups = plan_reveal_groups(list("abcde"), "FLOWCHART")
    flat = [i for g in groups for i in g]
    assert flat == sorted(flat) == list(range(5))


# ── animation planner ───────────────────────────────────────────────────────


def test_animation_caps_at_seven_steps():
    a = plan_animation_steps([f"point {i}" for i in range(12)], "BULLETS", "TEXT")
    assert len(a["steps"]) == 7
    assert a["overflow_groups"] == 5


def test_animation_effect_matches_family():
    assert plan_animation_steps(["a", "b"], "LINE_CHART", "CHART_TREND")["steps"][0]["effect"] == "draw"
    assert plan_animation_steps(["a", "b"], "BAR_CHART", "CHART_CATEGORICAL")["steps"][0]["effect"] == "grow"


def test_animation_atomic_is_static_single_step():
    a = plan_animation_steps(["the whole quote"], "QUOTE", "QUOTE")
    assert a["mode"] == "static"
    assert len(a["steps"]) == 1


def test_animation_takeaway_is_last_and_faded():
    a = plan_animation_steps(["a", "b"], "BULLETS", "TEXT", takeaway="the key lesson")
    assert a["steps"][-1]["label"] == "the key lesson"
    assert a["steps"][-1]["effect"] == "fade"


# ── text policy ─────────────────────────────────────────────────────────────


def test_definition_and_quote_are_verbatim():
    text = ('Osmosis is defined as the net movement of water across a membrane. '
            'Darwin wrote: "It is not the strongest that survives." '
            'Water tends to move toward higher solute concentration.')
    treats = {t.text[:15]: t.treatment for t in classify_sentences(text)}
    assert any(v == "VERBATIM" for v in treats.values())
    assert any(v == "TIGHTEN" for v in treats.values())


def test_formula_in_prose_is_verbatim():
    v = protect_verbatim("The kinetic energy equals one half m v squared, so E = 0.5*m*v^2 here.")
    assert len(v) >= 1


def test_near_duplicate_sentence_is_merged():
    text = ("The mitochondria produce ATP for the cell. "
            "The mitochondria produce ATP for the cell to use.")
    treats = [t.treatment for t in classify_sentences(text)]
    assert "MERGE" in treats


# ── image policy ────────────────────────────────────────────────────────────


def test_tiny_image_is_dropped():
    d = decide_image_action(ImageMeta(width=60, height=60, ocr_text=""))
    assert d.action == "DROP"


def test_diagram_screenshot_is_summarised_to_structure():
    ocr = ("Data ingestion -> Preprocessing -> Model training -> Evaluation. "
           "Step 1 load data. Step 2 clean. Step 3 fit. Step 4 score.")
    d = decide_image_action(ImageMeta(width=1200, height=800, ocr_text=ocr,
                                      slide_text="the model training pipeline has four steps"))
    assert d.action == "SUMMARISE_TO_STRUCTURE"


def test_relevant_photo_is_kept_with_caption():
    d = decide_image_action(ImageMeta(
        width=1600, height=1200,
        ocr_text="Figure 3 mitochondrion cross section",
        slide_text="the mitochondrion has an inner and outer membrane cross section",
        referenced_in_text=True))
    assert d.action == "KEEP_AS_IS"
    assert d.caption


def test_low_res_relevant_image_is_enhanced():
    d = decide_image_action(ImageMeta(
        width=280, height=200,
        ocr_text="neuron soma axon dendrite",
        slide_text="a neuron has a soma an axon and dendrites"))
    assert d.action == "ENHANCE"


def test_decision_dict_round_trips():
    d = decide_image_action(ImageMeta(width=800, height=600, ocr_text="hello world example figure",
                                      slide_text="hello world example"))
    out = d.to_dict()
    assert out["action"] in {
        "KEEP_AS_IS", "SUMMARISE_TO_STRUCTURE", "ENHANCE", "REGENERATE",
        "CAPTION_ONLY", "DROP",
    }
    assert "signals" in out
