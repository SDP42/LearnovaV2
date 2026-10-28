"""
Topic diagrams written by a language model, one per slide — the way an assistant draws an artifact for a topic.

The model gets the slide's title and words and returns one SVG that *shows the idea*: the actual mechanism, labelled
with the slide's own terms (points with a fitted line and residuals for least squares, a target board for bias and
variance, a word linked to its senses for disambiguation, a pixel grid growing from a seed for region growing).

Every answer is checked before use: it must parse, contain only plain drawing elements (no script, foreign objects,
images, links, CSS or filters), stay a sensible size and render with MuPDF. Results are cached on disk by content, so
building the same deck again costs nothing. Without a key, or when every key is spent, ``diagram`` returns None and the
offline scene illustrator is used instead.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from learnova.config import DATA_DIR
from learnova.logging_config import logger

ART_DIR = DATA_DIR / "art"
W, H = 600, 720            # portrait: the side panel of a slide

_SYSTEM = """You are an expert information designer drawing figures for a university lecture.
Draw ONE SVG figure that teaches the slide's idea visually, like a good textbook diagram: show the actual mechanism or
structure (for example data points with a fitted line and residual segments for least squares; a 2x2 grid of targets
for bias versus variance; a word linked to its candidate senses for word sense disambiguation; a parse tree for a
grammar; a pixel grid with a seed and a growing region for region growing; boxes and arrows for a pipeline).
Rules:
- Root element: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 720">. Keep everything inside 24..576 x 24..696.
- Elements allowed: g, rect, circle, ellipse, line, polyline, polygon, path, text, tspan, defs, marker. Nothing else.
- Colours: PRIMARY for the main subject, ACCENT for the highlight, #1f2937 for text and axes, #e5e7eb/#9ca3af for guides.
  White background (a rect filling the viewBox, fill #ffffff).
- Text: font-family="Inter, Arial, sans-serif", sizes 15 to 24, 3 to 9 short labels (at most 4 words each) using the
  slide's own terms. Labels must not overlap each other or the drawing. No title at the top: the slide already has one.
- Plain text only in labels: no LaTeX, no $ signs; write formulas with Unicode (Σ, ², β₀, ≤). Keep every label short
  enough to fit inside the viewBox at its font size (about 0.55 x font-size per character).
- Be accurate to the slide: do not invent facts, numbers or steps it does not support.
- No script, style, foreignObject, image, href, filter, CSS or animation.
Reply with the SVG only."""

_ALLOWED = {"svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "defs", "marker", "title", "desc"}
_BAD_ATTR = re.compile(r"^(?:on\w+|href|xlink:href|style|filter|class)$", re.I)

# Visuals that need the slide's full width: they get the header picture, not a side diagram (so no diagram is requested).
_WIDE = {"COMPARE_TABLE", "TIMELINE", "STEPPER", "WORKED_EXAMPLE", "PROCESS_LINEAR", "PROCESS_CYCLIC", "CAUSE_EFFECT", "MATRIX_2X2",
         "FUNNEL", "LAYERS", "OUTLINE", "COMPARE_VISUAL", "ALGORITHM_TRACE", "DATA_STRUCTURE", "FUNCTION_PLOT", "FIGURE"}

_lock = threading.Lock()
_rr = itertools.count()


def available() -> bool:
    try:
        from learnova.providers.gemini_provider import gemini_keys

        if gemini_keys():
            return True
        from learnova.ai import assist

        return assist.llm_available()
    except Exception:
        return False


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean_svg(raw: str, primary: str, accent: str) -> Optional[str]:
    """The model's answer as a safe, self-contained SVG string, or None when it is not usable."""
    m = re.search(r"<svg\b[\s\S]*?</svg>", raw or "", re.I)
    if not m:
        return None
    text = m.group(0).replace("PRIMARY", primary).replace("ACCENT", accent)
    if len(text) > 40000:
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    if _local(root.tag) != "svg":
        return None
    shapes = texts = 0
    for el in root.iter():
        name = _local(el.tag)
        if name not in _ALLOWED:
            return None
        for k in list(el.attrib):
            if _BAD_ATTR.match(_local(k)) or "url(" in el.attrib[k] and name != "marker" and not el.attrib[k].startswith("url(#"):
                return None
        shapes += name in {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path"}
        texts += name == "text"
    if shapes < 6 or texts > 16:
        return None
    _fit_labels(root)
    root.set("viewBox", root.get("viewBox") or f"0 0 {W} {H}")
    root.set("width", str(W))
    root.set("height", str(H))
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    svg = ET.tostring(root, encoding="unicode")
    try:
        from learnova.visuals.icons import svg_to_png

        if len(svg_to_png(svg, 120, 144)) < 400:
            return None
    except Exception:
        return None
    return svg


def _num(v: Optional[str], default: float) -> float:
    m = re.match(r"\s*(-?[\d.]+)", v or "")
    return float(m.group(1)) if m else default


def _fit_labels(root) -> None:
    """LaTeX dollars out, and a label that would run past the edge gets a smaller font (never below 11)."""
    for el in root.iter():
        if _local(el.tag) != "text":
            continue
        for node in el.iter():
            if node.text:
                node.text = node.text.replace("$", "")
            if node.tail:
                node.tail = node.tail.replace("$", "")
        label = "".join(el.itertext())
        size = _num(el.get("font-size"), 16.0)
        x = _num(el.get("x"), 0.0)
        anchor = el.get("text-anchor", "start")
        width = 0.56 * size * len(label)
        room = {"middle": 2 * min(x - 12, W - 12 - x), "end": x - 12}.get(anchor, W - 12 - x)
        if width > room > 0:
            el.set("font-size", f"{max(11.0, size * room / width):.1f}")


def art_url(art_id: str) -> str:
    """Public page of one diagram (the PowerPoint picture links here; set LEARNOVA_PUBLIC_URL when deployed)."""
    return f"{os.getenv('LEARNOVA_PUBLIC_URL', 'http://localhost:8000').rstrip('/')}/api/art/{art_id}"


def save_svg(svg: str, title: str) -> Optional[str]:
    """Keep any illustration (an offline scene included) as a page of its own; returns its id for ``art_url``."""
    import html as _html

    if not svg:
        return None
    key = hashlib.sha1(svg.encode("utf-8")).hexdigest()[:20]
    cp = _cache(key)
    if not cp.is_file():
        if "<title>" not in svg:
            svg = re.sub(r"(<svg\b[^>]*>)", lambda m: m.group(1) + f"<title>{_html.escape(title)}</title>", svg, count=1)
        try:
            ART_DIR.mkdir(parents=True, exist_ok=True)
            cp.write_text(svg, encoding="utf-8")
        except OSError:
            return None
    return key


def art_page(art_id: str) -> Optional[str]:
    """A small standalone HTML page showing one cached diagram, or None."""
    import html as _html

    if not re.fullmatch(r"[0-9a-f]{20}", art_id or ""):
        return None
    cp = _cache(art_id)
    if not cp.is_file():
        return None
    svg = cp.read_text(encoding="utf-8")
    if svg == "-":
        return None
    title = re.search(r"<title>(.*?)</title>", svg)
    name = _html.escape(title.group(1)) if title else "Illustration"
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{name} · Learnova</title><style>body{{margin:0;background:#f6f7fb;font-family:Inter,Arial,sans-serif;display:flex;"
            "min-height:100vh;align-items:center;justify-content:center}}figure{{margin:16px;background:#fff;border-radius:18px;"
            "box-shadow:0 12px 40px rgba(0,0,0,.12);padding:16px;max-width:min(96vw,720px)}}svg{{width:100%;height:auto;display:block}}"
            "figcaption{{color:#6b7280;font-size:13px;text-align:center;margin-top:8px}}</style></head><body><figure>"
            f"{svg}<figcaption>Illustration generated by Learnova for this slide</figcaption></figure></body></html>")


def _cache(key: str):
    return ART_DIR / f"{key}.svg"


def _ask(prompt: str) -> str:
    """One generation: Gemini keys round-robin (each paced on its own), then the router as a fallback."""
    try:
        from learnova.providers.gemini_provider import GeminiProvider, gemini_keys

        keys = gemini_keys()
    except Exception:
        keys = []
    if keys:
        start = next(_rr) % len(keys)
        order = keys[start:] + keys[:start]
        last: Optional[Exception] = None
        for k in order:
            try:
                return GeminiProvider(api_key=k, timeout=60.0).generate(prompt, system_prompt=_SYSTEM, temperature=0.4, max_tokens=4096)
            except Exception as exc:          # spent or rejected key: the next one
                last = exc
                continue
        logger.info("topic_art: every Gemini key failed (%s) — trying the router", last)
    from learnova.ai import assist
    from learnova.providers.router import TASK_DIAGRAM, get_router

    if not assist.llm_available():
        return ""
    return get_router().generate(prompt, system_prompt=_SYSTEM, task=TASK_DIAGRAM, temperature=0.4, max_tokens=4096, timeout=60.0)


def diagram(title: str, text: str, primary: str, accent: str, family: str = "") -> Optional[Dict[str, Any]]:
    """{"svg", "png", "alt", "provider"} for one slide, or None."""
    words = re.sub(r"\s+", " ", f"{title} {text}").strip()
    if len(re.findall(r"[A-Za-z]{3,}", words)) < 4:
        return None
    key = hashlib.sha1(json.dumps([title, text[:1500], primary, accent, "v2"]).encode()).hexdigest()[:20]
    cp = _cache(key)
    svg = None
    if cp.is_file():
        svg = cp.read_text(encoding="utf-8") or None
        if svg == "-":
            return None                      # tried before and nothing usable came back
    if svg is None:
        prompt = (f"PRIMARY={primary} ACCENT={accent}\nSlide title: {title}\nWhat the slide says:\n{text[:1500]}\n"
                  f"(The slide's content is shown as: {family or 'text'}. Draw the figure that explains it.)")
        try:
            svg = clean_svg(_ask(prompt), primary, accent)
            if svg:
                import html as _html

                svg = re.sub(r"(<svg\b[^>]*>)", lambda m: m.group(1) + f"<title>{_html.escape(title)}</title>", svg, count=1)
        except Exception as exc:
            logger.info("topic_art: %s", exc)
            svg = None
        try:
            ART_DIR.mkdir(parents=True, exist_ok=True)
            cp.write_text(svg or "-", encoding="utf-8")
        except OSError:
            pass
        if not svg:
            return None
    from learnova.visuals.icons import svg_to_png

    try:
        png = svg_to_png(svg, W, H, alpha=False)
    except Exception:
        return None
    return {"svg": svg, "png": png, "alt": f"Diagram: {title}", "provider": "ai-diagram", "id": key}


def illustrate(entries: List[dict], families: List[str], primary: str, accent: str, limit: int = 40, workers: int = 0) -> int:
    """AI diagrams for the topic slides of a deck, in parallel. Sets ``improved["illustration"]``; returns how many."""
    from concurrent.futures import ThreadPoolExecutor

    todo = []
    seen = set()
    for entry, fam in zip(entries, families):
        imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else None
        if imp is None or str(imp.get("layout_type", "")).upper() == "QUIZ" or fam in _WIDE or fam.startswith("CHART_"):
            continue
        if (entry.get("original") or {}).get("image") or any(imp.get(f) for f in ("is_agenda", "is_summary", "is_glossary", "is_activity")):
            continue
        title = re.sub(r"\s*\(\d+/\d+\)\s*$", "", str(imp.get("title", ""))).strip()
        if not title or title.lower() in {"agenda", "key takeaways", "glossary", "thank you", "contents", "syllabus"}:
            continue
        text = " ".join(str(b) for b in (imp.get("bullets") or []))
        base = title.lower()
        if base in seen:                     # continuation slides of one topic share a diagram budget: draw the first only
            continue
        seen.add(base)
        todo.append((imp, title, text, fam))
        if len(todo) >= limit:
            break
    if not todo:
        return 0
    t0 = time.time()
    if not workers:                          # two requests in flight per key: one is being written while the next waits its pace
        try:
            from learnova.providers.gemini_provider import gemini_keys

            workers = max(4, min(12, 2 * len(gemini_keys())))
        except Exception:
            workers = 4
    with ThreadPoolExecutor(max_workers=workers) as pool:
        done = list(pool.map(lambda a: diagram(a[1], a[2], primary, accent, a[3]), todo))
    n = 0
    for (imp, *_), d in zip(todo, done):
        if d:
            imp["illustration"] = {"bytes": d["png"], "ext": "png", "svg": d["svg"], "alt": d["alt"], "provider": d["provider"], "scene": "", "art_id": d["id"]}
            n += 1
    logger.info("topic_art: %d/%d AI diagrams in %.1fs", n, len(todo), time.time() - t0)
    return n
