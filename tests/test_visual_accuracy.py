"""Visual-selection accuracy gates. Every set must stay near-perfect; any regression names the slide that broke."""
import pathlib

import pytest

import learnova.evaluation.visual_accuracy as va

FIX = pathlib.Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("name", ["gold_visuals", "gold_holdout", "gold_blind"])
def test_strict_accuracy(name, monkeypatch):
    monkeypatch.setattr(va, "GOLD", FIX / f"{name}.json")
    res = va.evaluate()
    misses = [(r["id"], r["got"], r["ok"]) for r in res["rows"] if not r["strict"]]
    assert res["coverage"] == 1.0 and res["data"] == 1.0, "every slide must get a drawable visual"
    assert res["strict"] >= 0.95, f"{name}: {misses}"


def test_no_slide_is_ever_plain_text_and_nothing_is_lost():
    from learnova.analysis.compare import build_analysis
    from learnova.parsers.markdown_converter import from_typed_text
    from learnova.pipeline.orchestrator import PipelineConfig, generate

    md = "\n".join(f"## {c['title']}\n{c['text']}" for c in va.load_gold()[:14])
    res = generate(from_typed_text(md, "t"), PipelineConfig(build_pptx=False, build_html=False, enable_enhancement=False,
                                                           enable_vision_ocr=False, enable_quizzes=False))
    a = build_analysis(res)["summary"]
    assert a["visual_coverage_after_pct"] == 100
    assert a["fact_retention_pct"] >= 90
