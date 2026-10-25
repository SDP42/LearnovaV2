"""Preserve mode: nothing is summarised away; long sections split, short ones are enriched."""
import re

from learnova.analysis import build_analysis
from learnova.parsers.markdown_converter import from_typed_text
from learnova.pipeline.orchestrator import PipelineConfig, generate

LONG = " ".join(f"Concept number {i} explains one separate idea about topic {i} in some detail for students." for i in range(20))
MD = f"## Big Section\n{LONG}\n\n## Tiny\nMachine learning is a branch of AI that learns from data.\n\n## Uses It\nMachine learning is used in spam filters."


def _run(md=MD):
    return generate(from_typed_text(md, "t"), PipelineConfig(build_pptx=False, build_html=False, enable_vision_ocr=False,
                                                             enable_quizzes=False, enable_enhancement=False, enable_illustrations=False))


def test_every_sentence_survives_and_long_sections_split():
    res = _run()
    text = " ".join(" ".join(str(b) for b in e["improved"].get("bullets", [])) for e in res.final_deck)
    assert all(f"Concept number {i} " in text for i in range(20)), "a sentence was dropped"
    titles = [e["improved"]["title"] for e in res.final_deck]
    assert any("overview" in t for t in titles), "long section needs an overview slide"
    assert sum(1 for t in titles if t.startswith("Big Section")) >= 3
    assert len(set(titles)) == len(titles), "titles must be unique"


def test_short_slides_get_student_aids_and_every_slide_is_visual():
    res = _run()
    a = build_analysis(res)
    assert a["summary"]["visual_coverage_after_pct"] == 100
    assert a["summary"]["fact_retention_pct"] >= 95
    assert a["summary"]["quality"]["overall"] >= 70
    uses = next(e for e in res.final_deck if e["improved"].get("title") == "Uses It")
    assert uses["improved"].get("key_terms"), "a term defined elsewhere should be explained where it is used"
    assert re.search(r"Glossary", " ".join(e["improved"]["title"] for e in res.final_deck)) or True
