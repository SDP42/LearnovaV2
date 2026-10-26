"""A word must never be cut across two lines ("Quadrati/c"): the fitters shrink type until the longest word fits."""
from learnova.analysis.compare import build_analysis  # noqa: F401  (import check: analysis still loads with the layout changes)
from learnova.evaluation.layout_audit import audit_pptx
from learnova.parsers.markdown_converter import from_typed_text
from learnova.pipeline.orchestrator import PipelineConfig, generate
from learnova.rendering import layout as L

_MD = """# Algebra basics

## Solving a linear equation
Solve 3x + 5 = 20. We want the value of x that makes both sides equal.

## Quadratic equations
Solve x^2 - 5x + 6 = 0 by factorising. The discriminant tells us how many real answers to expect.

## Spam filtering
Bayes rule updates a belief when new evidence arrives. P(spam|free) depends on the prior and the likelihood.

## Averages
The mean of 4, 8, 15, 16, 23, 42 is the total divided by the count. Determiners and homophones are not numbers.
"""


def test_word_scale_shrinks_only_when_a_word_cannot_fit():
    assert L.word_scale([("Quadratic", 20, True)], 3.0) == 1.0
    assert L.word_scale([("Quadratic", 40, True)], 1.5) < 1.0
    assert L.word_scale([("Quadratic", 400, True)], 0.5) >= 0.62            # never collapses to nothing


def test_hyphenated_words_may_break_at_the_hyphen():
    assert L.longest_word_fits(["Transformation-based"], 1.4, 10.5)
    assert not L.longest_word_fits(["Transformationbased"], 1.4, 10.5)


def test_generated_deck_has_no_mid_word_breaks():
    res = generate(from_typed_text(_MD, "algebra"), PipelineConfig(enable_enhancement=False, enable_vision_ocr=False, enable_quizzes=True))
    rep = audit_pptx(res.pptx_bytes)
    broken = [(s["index"] + 1, f) for s in rep["per_slide"] for f in s["flags"] if f.startswith("word breaks")]
    assert not broken, broken
