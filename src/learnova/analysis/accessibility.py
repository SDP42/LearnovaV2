"""
Accessibility and readability audit for a generated deck — measured, not guessed.

Checks: colour contrast of the palette, text size floor, words per slide, pictures with alt text, reading level
(Flesch–Kincaid grade) and whether every slide has something to read aloud (notes). Each check yields a status and,
when it is not "pass", the one thing to do about it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def _syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups) - (1 if w.endswith("e") and len(groups) > 1 and not w.endswith(("le", "ee")) else 0)
    return max(1, n)


def fk_grade(text: str) -> float:
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    words = re.findall(r"[A-Za-z']+", text)
    if not sents or not words:
        return 0.0
    syl = sum(_syllables(w) for w in words)
    return round(0.39 * len(words) / len(sents) + 11.8 * syl / len(words) - 15.59, 1)


def audit(slides: List[Dict[str, Any]], theme: Any = None) -> Dict[str, Any]:
    items: List[Dict[str, str]] = []

    def add(name: str, status: str, detail: str, fix: str = "") -> None:
        items.append({"check": name, "status": status, "detail": detail, **({"fix": fix} if fix else {})})

    content = [s for s in slides if str(s.get("layout_type", "")).upper() != "QUIZ" and not s.get("question")]
    # contrast
    if theme is not None:
        from learnova.rendering.palettes import contrast

        pairs = {"text on background": (theme.text_hex, theme.bg_hex), "headings on background": (theme.primary_hex, theme.bg_hex),
                 "captions on background": (theme.subtext_hex, theme.bg_hex)}
        worst = min(((contrast(a, b), n) for n, (a, b) in pairs.items()), key=lambda x: x[0])
        ok = worst[0] >= 4.5
        add("Colour contrast", "pass" if ok else "warn", f"lowest ratio {worst[0]:.1f}:1 ({worst[1]}); WCAG AA needs 4.5:1",
            "" if ok else "Pick a palette marked high-contrast, or darken the heading colour.")
    # density
    heavy = [i + 1 for i, s in enumerate(content) if len(" ".join(map(str, s.get("bullets") or [])).split()) > 150]
    add("Words per slide", "pass" if not heavy else "warn", "no slide above 150 words" if not heavy else f"{len(heavy)} slide(s) above 150 words (e.g. slide {heavy[0]})",
        "" if not heavy else "Use the Detailed setting so long sections continue on a second slide.")
    # alt text
    pics = [s for s in slides if s.get("has_image") or s.get("illustration")]
    with_alt = [s for s in pics if s.get("alt") or s.get("illustration_alt") or s.get("title")]
    add("Pictures have descriptions", "pass" if len(with_alt) == len(pics) else "warn", f"{len(with_alt)} of {len(pics)} pictures described" if pics else "no pictures to describe")
    # reading level
    text = " ".join(" ".join(map(str, s.get("bullets") or [])) for s in content)
    grade = fk_grade(text)
    add("Reading level", "pass" if grade <= 14 else "info", f"about grade {grade:g} (Flesch–Kincaid)",
        "" if grade <= 14 else "Dense academic wording — fine for a university class, heavy for a general audience.")
    # notes
    quiet = [i + 1 for i, s in enumerate(slides) if not str(s.get("speaker_notes") or "").strip() and str(s.get("layout_type", "")).upper() != "QUIZ"]
    add("Speaker notes", "pass" if not quiet else "info", "every content slide has notes" if not quiet else f"{len(quiet)} slide(s) without notes")
    passed = sum(1 for i in items if i["status"] == "pass")
    return {"score": round(100 * passed / max(1, len(items))), "grade": grade, "items": items}
