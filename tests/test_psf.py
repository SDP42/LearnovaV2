"""Tests for the PSF metric and the CLASS segmentation DP (scoring/psf.py)."""

from __future__ import annotations

import pytest

from learnova.scoring.psf import (
    DEFAULT_PARAMS,
    SlideFeatures,
    cognitive_load,
    features_from_slide,
    information_efficiency,
    psf_deck,
    psf_slide,
    segment_blocks,
)
from learnova.scoring.scorer import score_all_slides


def _slide(title, bullets, **imp):
    return {"improved": {"title": title, "bullets": bullets, **imp}, "original": {}}


# ── PSF sub-indices ──────────────────────────────────────────────────────────


def test_psf_in_unit_interval():
    f = SlideFeatures(title="Calvin Cycle", bullets=["RuBisCO fixes carbon dioxide"])
    r = psf_slide(f)
    assert 0.0 <= r["psf"] <= 1.0
    assert 0.0 <= r["E"] <= 1.0 and 0.0 <= r["L"] <= 1.0 and 0.0 <= r["C"] <= 1.0


def test_wall_of_text_has_higher_load_than_terse_slide():
    terse = SlideFeatures(bullets=["Mitochondria produce ATP"])
    wall = SlideFeatures(bullets=[
        "The mitochondrion is a double membrane bound organelle that generates most "
        "of the chemical energy needed to power the cell's biochemical reactions",
        "Chemical energy produced by the mitochondrion is stored in adenosine triphosphate",
        "Mitochondria are commonly between 0.75 and 3 micrometres squared in area",
        "They are found in nearly all eukaryotic organisms including plants and fungi",
        "The number of mitochondria in a cell varies widely by organism tissue and cell type",
    ])
    assert cognitive_load(wall)[0] > cognitive_load(terse)[0]


def test_redundant_bullets_lower_information_efficiency():
    unique = SlideFeatures(title="Photosynthesis",
                           bullets=["Chlorophyll absorbs photons", "Stroma hosts carbon fixation"])
    repeated = SlideFeatures(title="Photosynthesis",
                             bullets=["Photosynthesis is photosynthesis", "Photosynthesis photosynthesis process"])
    assert information_efficiency(unique, frozenset())[0] > information_efficiency(repeated, frozenset())[0]


def test_empty_slide_scores_near_zero():
    assert psf_slide(SlideFeatures(title="Slide 4", bullets=[]))["psf"] < 0.15


def test_prior_concepts_reduce_novelty():
    f = SlideFeatures(title="Osmosis", bullets=["Osmosis moves water across a membrane"])
    fresh = information_efficiency(f, frozenset())[0]
    stale = information_efficiency(f, frozenset({"osmosis", "water", "membrane", "moves"}))[0]
    assert stale < fresh


# ── deck aggregation ────────────────────────────────────────────────────────


def test_psf_deck_shape_and_flow():
    deck = [
        _slide("Cell Structure", ["The nucleus stores genetic material", "Ribosomes synthesise proteins"]),
        _slide("Cell Membrane", ["The phospholipid bilayer regulates transport", "Membrane proteins enable signalling"]),
    ]
    out = psf_deck(deck)
    assert 0.0 <= out["psf_deck"] <= 1.0
    assert len(out["slide_scores"]) == 2
    assert 0.0 <= out["flow"] <= 1.0


def test_scorer_psf_engine_matches_contract():
    deck = [_slide("Kinematics", ["Velocity is the derivative of position", "Acceleration is the derivative of velocity"])]
    out = score_all_slides(deck, engine="psf")
    assert set(out) >= {"overall_score", "slide_scores", "psf"}
    assert 0 <= out["overall_score"] <= 100
    assert out["slide_scores"][0]["breakdown"].keys() == {"E", "L", "C"}


def test_heuristic_engine_unchanged():
    deck = [_slide("Kinematics", ["Velocity is the derivative of position"])]
    assert "psf" not in score_all_slides(deck)
    assert "psf" not in score_all_slides(deck, engine="heuristic")


# ── CLASS segmentation ──────────────────────────────────────────────────────


def test_segment_preserves_every_block():
    blocks = [f"point number {i} about thermodynamics and entropy" for i in range(11)]
    groups = segment_blocks(blocks, max_per_slide=4)
    flat = [b for g in groups for b in g]
    assert flat == blocks                       # order and completeness
    assert all(1 <= len(g) <= 4 for g in groups)


def test_segment_respects_hard_cap():
    blocks = [f"item {i}" for i in range(20)]
    groups = segment_blocks(blocks, max_per_slide=5)
    assert max(len(g) for g in groups) <= 5
    assert sum(len(g) for g in groups) == 20


def test_segment_short_input_is_single_slide():
    assert segment_blocks(["a", "b"], max_per_slide=5) == [["a", "b"]]
    assert segment_blocks([], max_per_slide=5) == []


def test_segment_avoids_orphan_last_slide():
    # 5 items, cap 4: even chunking gives 4+1; CLASS should prefer 3+2.
    blocks = [
        "enzymes lower activation energy",
        "substrate binds the active site",
        "induced fit changes enzyme shape",
        "products are released from the enzyme",
        "the enzyme is regenerated unchanged",
    ]
    groups = segment_blocks(blocks, max_per_slide=4)
    assert [len(g) for g in groups] != [4, 1]
    assert all(len(g) >= 2 for g in groups)


def test_segment_is_optimal_against_bruteforce():
    from learnova.scoring.psf import _group_cost

    blocks = [f"concept {w}" for w in ("alpha beta gamma delta epsilon zeta eta".split())]
    cap, target, lam = 3, 2, DEFAULT_PARAMS.lambda_slide

    def brute(items):
        if not items:
            return 0.0, []
        best = (float("inf"), None)
        for k in range(1, min(cap, len(items)) + 1):
            head, tail = items[:k], items[k:]
            c = _group_cost(head, DEFAULT_PARAMS, soft_target=target) + lam
            rest_cost, rest = brute(tail)
            if c + rest_cost < best[0]:
                best = (c + rest_cost, [head] + rest)
        return best

    _, optimal = brute(blocks)
    assert segment_blocks(blocks, max_per_slide=cap, soft_target=target) == optimal


def test_features_from_pipeline_dict():
    entry = _slide("Ohm's Law", ["Voltage equals current times resistance"],
                   layout_type="METRIC", takeaway="V = IR")
    f = features_from_slide(entry)
    assert f.title == "Ohm's Law"
    assert f.layout_type == "METRIC"
    assert f.takeaway == "V = IR"
