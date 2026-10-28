"""
Before vs after: the source lecture deck against the deck Learnova built from it.

    python scripts/research/before_after.py name=source.pdf|pptx:built.pptx [...] > before_after.json

Source side (read page by page with the slide reader; a PPTX is first rendered to PDF): slides, words per slide, the
densest slide, untitled slides, slides with a picture. Built side (python-pptx): the same, plus slides drawn as a visual
structure, quizzes, lab buttons and linked illustrations.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from pptx import Presentation  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE_TYPE  # noqa: E402


def source_stats(path: str) -> dict:
    from learnova.parsers.markdown_converter import pptx_to_pdf
    from learnova.parsers.slide_pdf import read_slide_pdf

    pdf = pptx_to_pdf(path) if path.endswith(".pptx") else path
    pages = read_slide_pdf(pdf, ocr=False, previews=False)["pages"]
    words = [sum(len(i["text"].split()) for i in p["items"]) + sum(len(" ".join(r).split()) for t in p["tables"] for r in t) for p in pages]
    return {"slides": len(pages), "avg_words": round(sum(words) / max(1, len(words)), 1), "max_words": max(words or [0]),
            "untitled": sum(1 for p in pages if not p["title"]), "with_picture": sum(1 for p in pages if p["figure"]),
            "visual_structures": 0, "quizzes": 0, "labs": 0, "linked_illustrations": 0}


def _walk(shapes):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(sh.shapes)
        else:
            yield sh


def built_stats(path: str) -> dict:
    prs = Presentation(path)
    slides = list(prs.slides)[1:-1]                    # title and closing slides left out
    words, pics, quizzes, labs, links, visual = [], 0, 0, 0, 0, 0
    for s in slides:
        shapes = list(_walk(s.shapes))
        texts = [sh.text_frame.text for sh in shapes if sh.has_text_frame and sh.text_frame.text.strip()]
        body = " ".join(texts[1:])                       # first text is the header title
        body = re.sub(r"\bLearnova\b|\d+\s*/\s*\d+|Open the interactive lab:.*", " ", body)
        words.append(len(body.split()))
        has_pic = any(sh.shape_type == MSO_SHAPE_TYPE.PICTURE for sh in shapes)
        pics += has_pic
        quizzes += any("QUESTION" in t for t in texts)
        lab = any((sh.click_action.hyperlink.address or "").find("/api/labs/") >= 0 for sh in shapes if hasattr(sh, "click_action"))
        labs += lab
        links += any((sh.click_action.hyperlink.address or "").find("/api/art/") >= 0 for sh in shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE)
        auto = sum(1 for sh in shapes if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE)
        visual += auto >= 4                              # cards, flows, timelines, tables of shapes
    return {"slides": len(slides), "avg_words": round(sum(words) / max(1, len(words)), 1), "max_words": max(words or [0]),
            "untitled": 0, "with_picture": pics, "visual_structures": visual, "quizzes": quizzes, "labs": labs, "linked_illustrations": links}


if __name__ == "__main__":
    out = {}
    for arg in sys.argv[1:]:
        name, rest = arg.split("=", 1)
        src, built = rest.rsplit(":", 1)
        out[name] = {"before": source_stats(src), "after": built_stats(built)}
    print(json.dumps(out, indent=1))
