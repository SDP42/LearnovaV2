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

_SYSTEM = """You are an expert information designer drawing a figure for a university or school lecture slide.
Draw ONE detailed SVG figure that teaches the slide's idea the way a good textbook figure does: show the real mechanism,
apparatus or structure, not icons or decoration. Examples: least squares → scatter points, the fitted line and the residual
segments with the squared error marked; the Haber process → compressor, reactor with iron catalyst (450 °C, 200 atm),
condenser removing liquid ammonia, recycle loop; bias versus variance → a 2x2 grid of targets; a parse tree for a grammar;
the water cycle → sun, sea, cloud, rain, run-off with arrows.
The figure kind is given in the request (FLOW, PLOT, ANATOMY, COMPARE or SCENE): follow it.
Rules:
- Root: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 720">. Everything inside 24..576 x 24..696.
- Elements allowed: g, rect, circle, ellipse, line, polyline, polygon, path, text, tspan, defs, marker, linearGradient,
  radialGradient, stop, title. Soft gradients on large shapes are welcome. Use arrow markers for flows.
- Group each teachable part in <g id="part-1">, <g id="part-2">, … in teaching order (3 to 6 parts). Put a <title> as the
  first child of each part group, a 3–8 word name of that part. Put a small numbered badge (circle + digit) next to each part.
- Colours: PRIMARY for the main subject, ACCENT for the one highlighted element, #1f2937 for text and axes, #e5e7eb/#9ca3af for
  guides, light tints of PRIMARY for fills. White background rect filling the viewBox.
- Text: font-family="Inter, Arial, sans-serif", sizes 14 to 22, 6 to 14 labels of at most 5 words, using the slide's own terms
  and any numbers the slide gives (temperatures, pressures, values, units). Labels must not overlap each other or the drawing.
  No title at the top: the slide already has one.
- Plain text only: no LaTeX, no $; write formulas with Unicode (Σ, ², β₀, ≤, ⇌). Keep each label inside the viewBox
  (about 0.55 × font-size per character).
- Be accurate to the slide: never invent facts, numbers or steps it does not support.
- No script, style, foreignObject, image, href to files, filter, CSS or animation.
Keep the whole SVG under 9000 characters (integer coordinates, no comments). Reply with the SVG only."""

_KIND_HINT = {
    "FLOW": "FLOW — the stages or apparatus in order, left to right or top to bottom, with arrows and what changes at each stage",
    "PLOT": "PLOT — axes with labelled units, the data or curve the slide describes, and annotations on the key feature",
    "ANATOMY": "ANATOMY — the thing with its labelled parts or the hierarchy of its types, leader lines to each label",
    "COMPARE": "COMPARE — two or more cases side by side with matching parts so the difference is visible",
    "SCENE": "SCENE — a concrete everyday situation that shows the idea at work, with labels tying it to the terms",
}
_NO_ART_TITLE = re.compile(r"^(?:agenda|contents?|outline|syllabus|references?|bibliography|thank you|questions?|key takeaways|"
                           r"summary|recap|glossary|key terms|checkpoint|quiz|exercise|assignment|lab manual)\b", re.I)


def art_kind(title: str, text: str, family: str = "") -> Optional[str]:
    """Which figure a slide needs — or None when a drawing would add nothing (agenda, references, quizzes, tables,
    algorithms, a slide that is already a figure, or too little content to draw from)."""
    if family in _WIDE or family.startswith("CHART_") or _NO_ART_TITLE.match((title or "").strip()):
        return None
    words = re.findall(r"[A-Za-z]{3,}", f"{title} {text}")
    if len(words) < 6:
        return None
    t = f"{title} {text}".lower()
    if family in {"PROCESS_LINEAR", "PROCESS_CYCLIC", "CAUSE_EFFECT"} or re.search(
            r"\b(steps?|stages?|process|cycle|pipeline|flow|then|next|finally|workflow|procedure|mechanism|reaction)\b", t):
        return "FLOW"
    if re.search(r"\b(graph|plot|curve|axis|slope|line of best fit|regression|distribution|function|rate|trend|error|loss|"
                 r"gradient|probability|equation|=)\b", t):
        return "PLOT"
    if family in {"COMPARE_TABLE", "COMPARE_VISUAL", "SET_DIAGRAM"} or re.search(r"\b(versus|vs\.?|compared|differ|advantages?|disadvantages?)\b", t):
        return "COMPARE"
    if re.search(r"\b(types?|kinds?|parts?|components?|structure|layers?|organ|cell|anatomy|consists of|classif)\w*", t):
        return "ANATOMY"
    return "SCENE"


_ALLOWED = {"svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "defs", "marker", "title", "desc",
            "linearGradient", "radialGradient", "stop", "clipPath", "pattern", "symbol", "use"}
_DROP = {"script", "foreignObject", "image", "iframe", "a", "audio", "video", "animate", "animateTransform", "animateMotion", "set", "style", "filter",
         "feGaussianBlur", "feOffset", "feBlend", "feMerge", "feMergeNode", "feFlood", "feComposite", "feColorMatrix", "feDropShadow", "mask", "metadata"}
_STYLE_PROPS = {"fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity",
                "font-size", "font-family", "font-weight", "font-style", "text-anchor", "dominant-baseline", "marker-end", "marker-start"}
_BAD_ATTR = re.compile(r"^(?:on\w+|class|filter|mask)$", re.I)

# Visuals that need the slide's full width: they get the header picture, not a side diagram (so no diagram is requested).
_WIDE = {"COMPARE_TABLE", "ALGORITHM", "TIMELINE", "STEPPER", "WORKED_EXAMPLE", "PROCESS_LINEAR", "PROCESS_CYCLIC", "CAUSE_EFFECT", "MATRIX_2X2",
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
    # sanitise rather than reject: unsafe or unsupported elements are removed, inline styles become attributes
    for parent in list(root.iter()):
        for child in list(parent):
            if _local(child.tag) in _DROP or _local(child.tag) not in _ALLOWED:
                parent.remove(child)
    shapes = texts = 0
    for el in root.iter():
        name = _local(el.tag)
        style = el.attrib.pop("style", "")
        for decl in style.split(";"):
            if ":" in decl:
                k, v = (t.strip() for t in decl.split(":", 1))
                if k in _STYLE_PROPS and "url(" not in v.replace("url(#", ""):
                    el.set(k, v)
        for k in list(el.attrib):
            v = el.attrib[k]
            lk = _local(k)
            if _BAD_ATTR.match(lk):
                del el.attrib[k]
            elif lk == "href" and not v.startswith("#"):
                return None                                   # an external link or embedded file: not used
            elif "url(" in v and not v.replace(" ", "").startswith("url(#"):
                del el.attrib[k]
        shapes += name in {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "use"}
        texts += name == "text"
    if shapes < 5 or texts > 28:
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
    vb = (root.get("viewBox") or "").replace(",", " ").split()
    vw = _num(vb[2], W) if len(vb) == 4 else W            # the model's own canvas width, not the panel's
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
        room = {"middle": 2 * min(x - 12, vw - 12 - x), "end": x - 12}.get(anchor, vw - 12 - x)
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
            f"<title>{name} · Learnova</title><style>"
            "body{margin:0;background:#f6f7fb;font-family:Inter,Arial,sans-serif;color:#1f2937;display:flex;min-height:100vh;align-items:center;justify-content:center}"
            ".wrap{display:flex;gap:18px;flex-wrap:wrap;justify-content:center;align-items:flex-start;margin:16px;max-width:1100px}"
            "figure{margin:0;background:#fff;border-radius:18px;box-shadow:0 12px 40px rgba(0,0,0,.12);padding:16px;width:min(96vw,560px)}"
            "svg{width:100%;height:auto;display:block}svg g[id^=part]{transition:opacity .35s,filter .2s;cursor:pointer}"
            "svg g[id^=part]:hover{filter:drop-shadow(0 0 6px rgba(37,99,235,.55))}svg.stepping g[id^=part].off{opacity:.12}"
            ".panel{background:#fff;border-radius:18px;box-shadow:0 12px 40px rgba(0,0,0,.08);padding:18px 20px;width:min(96vw,380px)}"
            ".panel h1{font-size:18px;margin:0 0 10px}.panel ol{padding-left:20px;margin:0 0 14px;line-height:1.6}"
            ".panel li{cursor:pointer;border-radius:6px;padding:2px 6px}.panel li.on{background:#e8efff;font-weight:700}"
            "button{font:600 14px Inter,Arial,sans-serif;border:0;border-radius:10px;padding:9px 14px;margin-right:6px;background:#1f2937;color:#fff;cursor:pointer}"
            "button.ghost{background:#e5e7eb;color:#1f2937}figcaption,.small{color:#6b7280;font-size:13px;text-align:center;margin-top:8px}"
            "</style></head><body><div class='wrap'><figure>"
            f"{svg}<figcaption>Illustration generated by Learnova for this slide</figcaption></figure>"
            f"<div class='panel'><h1>{name}</h1><ol id='parts'></ol><button id='back' class='ghost'>Back</button><button id='step'>Step</button>"
            "<button id='all' class='ghost'>Show all</button><p class='small'>Step through the figure part by part, or hover a part to highlight it.</p></div></div>"
            "<script>(function(){var svg=document.querySelector('figure svg');if(!svg)return;"
            "var parts=[].slice.call(svg.querySelectorAll('g[id^=part]')).sort(function(a,b){return parseInt(a.id.slice(5))-parseInt(b.id.slice(5))});"
            "var ol=document.getElementById('parts'),k=parts.length;if(!parts.length){document.querySelector('.panel').style.display='none';return;}"
            "parts.forEach(function(g,i){var t=g.querySelector('title'),li=document.createElement('li');li.textContent=t?t.textContent:('Part '+(i+1));"
            "li.onclick=function(){show(i+1)};ol.appendChild(li);g.onclick=function(){show(i+1)};});"
            "function show(n){k=n;svg.classList.toggle('stepping',n<parts.length);parts.forEach(function(g,i){g.classList.toggle('off',i>=n)});"
            "[].forEach.call(ol.children,function(li,i){li.classList.toggle('on',i===n-1)});}"
            "document.getElementById('step').onclick=function(){show(Math.min(parts.length,k>=parts.length?1:k+1))};"
            "document.getElementById('back').onclick=function(){show(Math.max(1,k-1))};"
            "document.getElementById('all').onclick=function(){show(parts.length)};show(1);})();</script></body></html>")


def _cache(key: str):
    return ART_DIR / f"{key}.svg"


def _ask(prompt: str) -> str:
    """One generation: Gemini keys round-robin (each paced on its own), then the router as a fallback."""
    try:
        from learnova.providers.gemini_provider import _KEY_RETRY_S, GeminiProvider, _dead_keys, _key_is_dead, gemini_keys

        keys = gemini_keys()
    except Exception:
        keys = []
    if keys:
        start = next(_rr) % len(keys)
        order = keys[start:] + keys[:start]
        live = [k for k in order if time.time() - _dead_keys.get(k, -1e18) > _KEY_RETRY_S]
        last: Optional[Exception] = None
        for k in live:                        # a key known to be spent is skipped, so it does not cost a paced slot
            try:
                return GeminiProvider(api_key=k, timeout=60.0).generate(prompt, system_prompt=_SYSTEM, temperature=0.4, max_tokens=8192)
            except Exception as exc:          # spent or rejected key: remember it, then the next one
                if _key_is_dead(exc):
                    _dead_keys[k] = time.time()
                last = exc
                continue
        logger.info("topic_art: every Gemini key failed (%s) — trying the router", last)
    from learnova.ai import assist
    from learnova.providers.router import TASK_DIAGRAM, get_router

    if not assist.llm_available():
        return ""
    return get_router().generate(prompt, system_prompt=_SYSTEM, task=TASK_DIAGRAM, temperature=0.4, max_tokens=8192, timeout=60.0)


def diagram(title: str, text: str, primary: str, accent: str, family: str = "") -> Optional[Dict[str, Any]]:
    """{"svg", "png", "alt", "provider"} for one slide, or None."""
    words = re.sub(r"\s+", " ", f"{title} {text}").strip()
    if len(re.findall(r"[A-Za-z]{3,}", words)) < 4:
        return None
    key = hashlib.sha1(json.dumps([title, text[:1800], primary, accent, "v4"]).encode()).hexdigest()[:20]
    cp = _cache(key)
    svg = None
    if cp.is_file():
        svg = cp.read_text(encoding="utf-8") or None
        if svg == "-":
            return None                      # tried before and nothing usable came back
    if svg is None:
        kind = art_kind(title, text, family) or "SCENE"
        prompt = (f"PRIMARY={primary} ACCENT={accent}\nFigure kind: {_KIND_HINT[kind]}\nSlide title: {title}\n"
                  f"What the slide says:\n{text[:1800]}\n(The slide's text is laid out as: {family or 'text'}; your figure sits beside it.)")
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
        if imp is None or str(imp.get("layout_type", "")).upper() == "QUIZ":
            continue
        if (entry.get("original") or {}).get("image") or any(imp.get(f) for f in ("is_agenda", "is_summary", "is_glossary", "is_activity")):
            continue
        title = re.sub(r"\s*\(\d+/\d+\)\s*$", "", str(imp.get("title", ""))).strip()
        if not title or title.lower() in {"agenda", "key takeaways", "glossary", "thank you", "contents", "syllabus"}:
            continue
        text = " ".join(str(b) for b in (imp.get("bullets") or []))
        if art_kind(title, text, fam) is None:     # nothing worth drawing here: the slide keeps its own visual
            continue
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
