"""
Image-handling policy: for each figure attached to a slide, decide what to do
with it — keep it, redraw it as a native visual, enhance it, replace it, keep
only its text, or drop it.

Mirrors the image section of ``ai/master_prompt.py``. Deterministic, no model:
it reasons from cheap signals (pixel size, aspect ratio, the OCR/description
already produced by ``ai/image_describer.py``, and how much that text overlaps
the slide's own words).

Returned action vocabulary
--------------------------
KEEP_AS_IS              show the bitmap unchanged, with a caption
SUMMARISE_TO_STRUCTURE  the picture is really a diagram/table/chart — rebuild it
                        as a native Learnova visual and discard the bitmap
ENHANCE                 relevant but low-quality — keep, mark for upscale/cleanup
REGENERATE              decorative / stock / watermarked — replace with a
                        generated educational illustration
CAPTION_ONLY            can't show it, but its information matters — keep the text
DROP                    logo / divider / bullet icon / pure decoration
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Optional, Tuple

from learnova.logging_config import logger

ACTIONS = (
    "KEEP_AS_IS",
    "SUMMARISE_TO_STRUCTURE",
    "ENHANCE",
    "REGENERATE",
    "CAPTION_ONLY",
    "DROP",
)

_WORD = re.compile(r"[A-Za-z][A-Za-z\-']+")

# The OCR text of a structural figure is full of these.
_STRUCTURE_MARKERS = re.compile(
    r"(→|->|=>|▶|➜|→|\bstep\s*\d|\bphase\s*\d|\|.*\|.*\||"
    r"\byes\b\s*/\s*\bno\b|\bif\b.+\bthen\b|\d+\s*%|\baxis\b|\blegend\b)",
    re.I,
)
_DECORATIVE_HINT = re.compile(
    r"\b(logo|icon|clip[- ]?art|stock photo|watermark|shutterstock|getty|"
    r"istock|banner|divider|bullet point|decorative)\b",
    re.I,
)
_MIN_MEANINGFUL_OCR_WORDS = 8


@dataclass
class ImageMeta:
    width: int = 0
    height: int = 0
    ext: str = "png"
    ocr_text: str = ""              # from image_describer.describe_images
    referenced_in_text: bool = False
    slide_text: str = ""           # the surrounding slide's words, for relevance
    is_photo: Optional[bool] = None  # caller may already know

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000 if self.width and self.height else 0.0

    @property
    def aspect(self) -> float:
        return (self.width / self.height) if self.height else 0.0


@dataclass
class ImageDecision:
    action: str
    confidence: float
    rationale: str
    caption: str = ""
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "confidence": round(self.confidence, 3),
            "rationale": self.rationale,
            "caption": self.caption,
            "signals": self.signals,
        }


def meta_from_bytes(image_bytes: bytes, ext: str = "png", **kw) -> ImageMeta:
    """Build an ImageMeta, reading pixel dimensions via Pillow when possible."""
    w = h = 0
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as im:
            w, h = im.size
    except Exception as exc:  # pragma: no cover - malformed image
        logger.debug("could not read image dimensions: %s", exc)
    return ImageMeta(width=w, height=h, ext=ext, **kw)


def _clean_ocr(text: str) -> str:
    return re.sub(r"\[(?:OCR|Extracted)[^\]]*\]", "", text or "", flags=re.I).strip()


def _relevance(ocr: str, slide_text: str) -> float:
    ow = {w.lower() for w in _WORD.findall(ocr)}
    sw = {w.lower() for w in _WORD.findall(slide_text)}
    if not ow or not sw:
        return 0.0
    return len(ow & sw) / len(ow)


def decide_image_action(meta: ImageMeta) -> ImageDecision:
    """Choose an action for one figure. Never raises."""
    ocr = _clean_ocr(meta.ocr_text)
    ocr_words = _WORD.findall(ocr)
    n_ocr = len(ocr_words)
    structure_hits = len(_STRUCTURE_MARKERS.findall(ocr))
    decorative = bool(_DECORATIVE_HINT.search(ocr)) or bool(_DECORATIVE_HINT.search(meta.ext))
    relevance = _relevance(ocr, meta.slide_text)
    tiny = 0 < meta.megapixels < 0.02          # ~ < 140x140
    low_res = 0 < meta.megapixels < 0.12       # ~ < 400x300
    banner = meta.aspect and (meta.aspect > 4 or meta.aspect < 0.25)

    signals = {
        "megapixels": round(meta.megapixels, 3),
        "aspect": round(meta.aspect, 2),
        "ocr_words": n_ocr,
        "structure_markers": structure_hits,
        "relevance_to_slide": round(relevance, 2),
        "referenced_in_text": meta.referenced_in_text,
        "decorative_hint": decorative,
    }

    def d(action, conf, why):
        cap = ""
        if action in {"KEEP_AS_IS", "ENHANCE"}:
            cap = _caption_from(ocr, meta.slide_text)
        return ImageDecision(action, conf, why, cap, signals)

    # 1. Pure decoration / chrome.
    if (tiny and n_ocr < _MIN_MEANINGFUL_OCR_WORDS) or (banner and n_ocr < _MIN_MEANINGFUL_OCR_WORDS):
        return d("DROP", 0.9, "Tiny or banner-shaped image with no readable content — decoration.")
    if decorative and relevance < 0.15 and structure_hits == 0:
        return d("DROP", 0.75, "Matches decorative/stock/logo cues and is not relevant to the slide.")

    # 2. It's really structured data drawn as a picture.
    if structure_hits >= 2 and n_ocr >= _MIN_MEANINGFUL_OCR_WORDS:
        return d("SUMMARISE_TO_STRUCTURE", 0.82,
                 f"OCR shows {structure_hits} diagram/table/chart markers and "
                 f"{n_ocr} words — rebuild as a native visual, drop the bitmap.")
    if n_ocr >= 40 and relevance >= 0.25:
        return d("SUMMARISE_TO_STRUCTURE", 0.7,
                 "Text-dense figure closely tied to the slide — its content is "
                 "better re-expressed as structure than shown as an image.")

    # 3. Relevant but weak-quality raster.
    if (low_res or meta.megapixels == 0) and (relevance >= 0.2 or meta.referenced_in_text):
        return d("ENHANCE", 0.6,
                 "Relevant figure but low resolution / unknown quality — keep and "
                 "flag for upscaling.")

    # 4. Decorative but a slot for a real illustration would help.
    if decorative and (relevance >= 0.15 or meta.referenced_in_text):
        return d("REGENERATE", 0.55,
                 "Decorative image where an on-topic illustration would add value "
                 "— replace with a generated educational figure.")

    # 5. Good, relevant picture — keep it.
    if relevance >= 0.15 or meta.referenced_in_text or meta.megapixels >= 0.25:
        return d("KEEP_AS_IS", 0.7, "Clear, relevant figure — show unchanged with a caption.")

    # 6. Default: a figure extracted from the source document is wanted unless
    #    we found a concrete reason above to drop it. Keep it.
    return d("KEEP_AS_IS", 0.55,
             "Figure from the source document — shown with a caption "
             "(no drop signal).")


def _caption_from(ocr: str, slide_text: str) -> str:
    """A short caption: the first readable OCR line, else the slide's topic."""
    for line in (ocr or "").splitlines():
        line = line.strip(" .:-")
        if 3 <= len(_WORD.findall(line)) <= 14:
            return line
    head = " ".join(_WORD.findall(slide_text)[:8])
    return f"Figure: {head}".strip()


__all__ = [
    "ACTIONS",
    "ImageMeta",
    "ImageDecision",
    "meta_from_bytes",
    "decide_image_action",
]
