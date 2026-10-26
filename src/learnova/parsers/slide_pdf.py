"""
Reader for slide decks that were exported to PDF (lecture slides, "boring" PowerPoints).

Such a PDF already *is* a deck: one page, one slide. What it lacks is structure a program can use: bullets are
separate glyph characters in a symbol font, nesting is only an indent, tables are often pictures and diagrams are
drawings. This reader recovers what the page really says:

* the slide title (the largest line near the top), a title page, section dividers;
* bullets with their nesting level, from the glyph's x position (wrapped lines are re-joined);
* real tables (ruled grids), kept as tables, with their text removed from the bullets;
* figures: the largest picture, or a rendered crop when the slide is a vector diagram;
* running headers/footers/slide numbers, removed.

``read_slide_pdf`` returns plain dicts so the rest of the pipeline does not depend on PyMuPDF.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from learnova.logging_config import logger

_GLYPHS = set("➔→➢➤►▶◆◇■□▪▫●○•◦‣⁃–—-*»✓✔❖➜➝➞➡⮚➧◘◙")
_SYMBOL_FONTS = re.compile(r"wingdings|symbol|courier|pmincho|dingbats|webdings", re.I)
_PUA = re.compile(r"^[-]$")
_SENT_END = re.compile(r"[.!?:;]$|[.!?][\"'”’)\]]$")


def _is_glyph(text: str, font: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if len(t) == 1 and (t in _GLYPHS or _PUA.match(t)):
        return True
    return len(t) == 1 and t in "oOØq§vü" and bool(_SYMBOL_FONTS.search(font or ""))


def _strip_leading_glyph(text: str) -> Tuple[str, bool]:
    m = re.match(r"^\s*([➔→➢➤►▶◆◇■□▪▫●○•◦‣⁃✓✔❖➜➝➞➡-])\s*", text)
    return (text[m.end():], True) if m else (text, False)


class _Line:
    __slots__ = ("x0", "y0", "x1", "y1", "size", "bold", "text", "font", "glyph")

    def __init__(self, x0, y0, x1, y1, size, bold, text, font, glyph):
        self.x0, self.y0, self.x1, self.y1, self.size, self.bold, self.text, self.font, self.glyph = x0, y0, x1, y1, size, bold, text, font, glyph


def _page_lines(page) -> List[_Line]:
    out: List[_Line] = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b.get("lines", []):
            spans = [s for s in l["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = re.sub(r"\s+", " ", "".join(s["text"] for s in l["spans"])).strip()
            s0 = spans[0]
            size = max(s["size"] for s in spans)
            bold = any(s["flags"] & 16 or "bold" in s["font"].lower() for s in spans)
            x0, y0, x1, y1 = l["bbox"]
            out.append(_Line(x0, y0, x1, y1, size, bold, text, s0["font"], _is_glyph(text, s0["font"])))
    return out


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())


# ── OCR for slides that are pictures of slides ───────────────────────────────
_OCR_BULLET = re.compile(r"^[•●○◦▪■□◆◇➢➔→>»\-–—*+©®°¢@¬§]$")
_OCR_CACHE = None


def _ocr_cache_dir():
    global _OCR_CACHE
    if _OCR_CACHE is None:
        import pathlib

        from learnova.config import CACHE_DIR

        _OCR_CACHE = pathlib.Path(CACHE_DIR) / "slide_ocr"
        _OCR_CACHE.mkdir(parents=True, exist_ok=True)
    return _OCR_CACHE


def _ocr_words(png: bytes) -> Optional[Dict[str, Any]]:
    """Tesseract word boxes for one slide image, cached on disk by content hash. None when OCR is unavailable."""
    import hashlib
    import json

    key = hashlib.sha1(png).hexdigest()
    cp = _ocr_cache_dir() / f"{key}.json"
    if cp.exists():
        try:
            return json.loads(cp.read_text())
        except Exception:
            pass
    try:
        import io

        import pytesseract
        from PIL import Image

        im = Image.open(io.BytesIO(png)).convert("RGB")
        if im.width < 1400:                                  # small screenshots read better enlarged
            k = 1400 / im.width
            im = im.resize((1400, int(im.height * k)))
        elif im.width > 2200:
            k = 2200 / im.width
            im = im.resize((2200, int(im.height * k)))
        d = pytesseract.image_to_data(im, lang="eng", config="--oem 1 --psm 4", output_type=pytesseract.Output.DICT, timeout=60)
    except Exception as exc:
        logger.info("slide OCR unavailable (%s)", type(exc).__name__)
        return None
    words = []
    for i, t in enumerate(d["text"]):
        t = (t or "").strip()
        try:
            conf = float(d["conf"][i])
        except Exception:
            conf = -1
        if t and conf >= 0:
            words.append({"t": t, "x": d["left"][i], "y": d["top"][i], "w": d["width"][i], "h": d["height"][i], "c": conf,
                          "k": (d["block_num"][i], d["par_num"][i], d["line_num"][i])})
    out = {"w": im.width, "h": im.height, "words": words}
    try:
        cp.write_text(json.dumps(out))
    except Exception:
        pass
    return out


def _graphic_ratio(png: bytes, words: List[Dict[str, Any]], img_w: int, img_h: int) -> float:
    """Share of the picture's ink that is NOT text: ~0 for a slide of bullets, high for a diagram, plot or table drawn as a picture."""
    try:
        import io

        import numpy as np
        from PIL import Image

        im = Image.open(io.BytesIO(png)).convert("L").resize((img_w, img_h))
        ink = np.asarray(im) < 170
        mask = np.zeros_like(ink)
        pad = 4
        for w in words:
            mask[max(0, w["y"] - pad): w["y"] + w["h"] + pad, max(0, w["x"] - pad): w["x"] + w["w"] + pad] = True
        total = int(ink.sum())
        return float((ink & ~mask).sum()) / total if total > 200 else 0.0
    except Exception:
        return 0.0


def _ocr_lines(png: bytes, bbox: Tuple[float, float, float, float]) -> Tuple[List[_Line], float, float]:
    """_Line objects (page coordinates) built from OCR words, bullet marks split out as glyph lines; and the mean word confidence."""
    res = _ocr_words(png)
    if not res or not res["words"]:
        return [], 0.0, 1.0
    x0, y0, x1, y1 = bbox
    sx, sy = (x1 - x0) / res["w"], (y1 - y0) / res["h"]
    by_line: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = defaultdict(list)
    for w in res["words"]:
        if w["c"] >= 35:
            by_line[tuple(w["k"])].append(w)
    lines: List[_Line] = []
    confs = [w["c"] for w in res["words"] if w["c"] >= 0]
    for ws in by_line.values():
        ws.sort(key=lambda w: w["x"])
        hs = sorted(w["h"] for w in ws if len(w["t"]) >= 3) or sorted(w["h"] for w in ws)
        h_med = hs[len(hs) // 2]
        glyph_w = None
        if len(ws) >= 2 and (_OCR_BULLET.match(ws[0]["t"]) or (ws[0]["t"] in {"e", "o", "O", "E"} and ws[1]["x"] - (ws[0]["x"] + ws[0]["w"]) >= 0.5 * h_med)):
            glyph_w, ws = ws[0], ws[1:]
        text = " ".join(w["t"] for w in ws).strip()
        if not text:
            continue
        lx0, lx1 = min(w["x"] for w in ws), max(w["x"] + w["w"] for w in ws)
        ly0, ly1 = min(w["y"] for w in ws), max(w["y"] + w["h"] for w in ws)
        size = h_med * sy * 0.82
        bold = False
        if glyph_w is not None:
            gx0 = x0 + glyph_w["x"] * sx
            lines.append(_Line(gx0, y0 + glyph_w["y"] * sy, gx0 + glyph_w["w"] * sx, y0 + (glyph_w["y"] + glyph_w["h"]) * sy, size, False, "•", "ocr", True))
        lines.append(_Line(x0 + lx0 * sx, y0 + ly0 * sy, x0 + lx1 * sx, y0 + ly1 * sy, size, bold, text, "ocr", False))
    return lines, (sum(confs) / len(confs) if confs else 0.0), _graphic_ratio(png, res["words"], res["w"], res["h"])


def _furniture(pages_lines: List[List[_Line]], heights: List[float]) -> set:
    """Text that repeats in the top/bottom band of many pages (author line, deck name, slide numbers)."""
    seen: Dict[Tuple[str, str], set] = defaultdict(set)
    for pi, (lines, H) in enumerate(zip(pages_lines, heights)):
        for l in lines:
            band = "top" if l.y1 < H * 0.12 else "bottom" if l.y0 > H * 0.86 else ""
            if band and not l.glyph:
                seen[(band, _norm(l.text))].add(pi)
    n = max(1, len(pages_lines))
    return {k for k, v in seen.items() if k[1] and len(v) >= max(3, int(0.3 * n))}


def _cluster(values: List[float], tol: float = 9.0) -> List[float]:
    out: List[float] = []
    for v in sorted(values):
        if out and v - out[-1] <= tol:
            continue
        out.append(v)
    return out


def _level(x: float, anchors: List[float], tol: float = 9.0) -> int:
    best = min(range(len(anchors)), key=lambda i: abs(anchors[i] - x))
    return best


def _looks_like_title(t: str) -> bool:
    letters = len(re.sub(r"[^A-Za-z]", "", t))
    words = t.split()
    return bool(words) and letters >= 4 and letters >= 0.65 * len(t.replace(" ", "")) and len(words) <= 14 and any(len(w) >= 3 for w in words)


def _title_of(lines: List[_Line], H: float, body_size: float) -> Tuple[str, List[_Line]]:
    top = [l for l in lines if l.y0 < H * 0.34 and not l.glyph and len(l.text) > 1]
    if not top:
        return "", []
    big = max(top, key=lambda l: (l.size, -l.y0))
    if big.size < body_size * 1.18 and not (big.bold and big.y0 < H * 0.2):
        return "", []
    parts = [big]
    for l in sorted(top, key=lambda l: l.y0):                       # a title that wraps onto a second line
        if l is not big and abs(l.size - big.size) < 0.8 and 0 < l.y0 - parts[-1].y1 < big.size * 0.9 and abs(l.x0 - big.x0) < 60:
            parts.append(l)
    parts.sort(key=lambda l: l.y0)
    text = " ".join(p.text for p in parts).strip()
    return (text, parts) if _looks_like_title(text) else ("", [])


def _tables(page) -> List[Dict[str, Any]]:
    out = []
    try:
        for t in page.find_tables().tables:
            rows = [[re.sub(r"\s+", " ", str(c or "")).strip() for c in r] for r in t.extract()]
            rows = [r for r in rows if any(r)]
            cols = max((len(r) for r in rows), default=0)
            filled = sum(1 for r in rows for c in r if c)
            if len(rows) >= 2 and cols >= 2 and filled >= 0.6 * len(rows) * cols:
                out.append({"bbox": tuple(t.bbox), "rows": rows})
    except Exception:
        pass
    return out


def _figures(doc, page, H: float, W: float, decor: Optional[set] = None) -> List[Dict[str, Any]]:
    figs = []
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:
        infos = []
    for info in infos:
        x0, y0, x1, y1 = info["bbox"]
        area = max(0.0, (x1 - x0) * (y1 - y0)) / (W * H)
        if area >= 0.06 and info.get("xref") and info.get("xref") not in (decor or set()):
            try:
                img = doc.extract_image(info["xref"])
            except Exception:
                continue
            if img and img.get("image"):
                figs.append({"bbox": (x0, y0, x1, y1), "area": area, "bytes": img["image"], "ext": img.get("ext", "png"),
                             "w": img.get("width", 0), "h": img.get("height", 0)})
    figs.sort(key=lambda f: -f["area"])
    return figs


def _render_clip(page, clip) -> Optional[Dict[str, Any]]:
    try:
        import fitz

        pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), clip=fitz.Rect(*clip), alpha=False)
        return {"bytes": pix.tobytes("png"), "ext": "png", "w": pix.width, "h": pix.height}
    except Exception:
        return None


def _is_vector_diagram(page, lines: List[_Line], H: float) -> bool:
    try:
        d = page.get_drawings()
    except Exception:
        return False
    shapes = [x for x in d if x.get("rect") is not None and x["rect"].width > 6 and x["rect"].height > 6 and x["rect"].y0 > H * 0.12]
    return len(shapes) >= 10 and sum(1 for l in lines if l.glyph) <= 2


def _items(body: List[_Line]) -> List[Dict[str, Any]]:
    """Bullet items with levels, from glyph positions; wrapped lines are re-joined."""
    glyphs = [l for l in body if l.glyph]
    texts = sorted([l for l in body if not l.glyph], key=lambda l: (round(l.y0 / 3), l.x0))
    items: List[Dict[str, Any]] = []
    used_glyph = set()
    cur: Optional[Dict[str, Any]] = None
    for l in texts:
        text, inline = _strip_leading_glyph(l.text)
        g = None
        for gi, gl in enumerate(glyphs):
            if gi not in used_glyph and abs((gl.y0 + gl.y1) / 2 - (l.y0 + l.y1) / 2) <= max(6.0, l.size * 0.7) and gl.x1 <= l.x0 + 2 and l.x0 - gl.x1 < 70:
                g = gi
                break
        if g is not None:
            used_glyph.add(g)
            cur = {"key": glyphs[g].x0, "text": text, "text_x": l.x0, "y1": l.y1, "size": l.size, "bullet": True}
            items.append(cur)
        elif inline:
            cur = {"key": l.x0, "text": text, "text_x": l.x0 + l.size * 1.2, "y1": l.y1, "size": l.size, "bullet": True}
            items.append(cur)
        elif (cur and abs(l.x0 - cur["text_x"]) <= 12 and 0 <= l.y0 - cur["y1"] <= l.size * 1.1
              and not (_SENT_END.search(cur["text"]) and l.text[:1].isupper() and len(cur["text"].split()) > 12)):
            cur["text"] = f"{cur['text']} {l.text}"
            cur["y1"] = l.y1
        else:
            cur = {"key": l.x0, "text": text, "text_x": l.x0, "y1": l.y1, "size": l.size, "bullet": False}
            items.append(cur)
    if not items:
        return []
    anchors = _cluster([i["key"] for i in items])
    for i in items:
        i["level"] = min(3, _level(i["key"], anchors))
        i["text"] = re.sub(r"\s+([,.;:!?)])", r"\1", i["text"]).strip()
    return [i for i in items if len(i["text"]) > 1]


def read_slide_pdf(path: str, ocr: bool = True) -> Optional[Dict[str, Any]]:
    try:
        import fitz

        doc = fitz.open(path)
    except Exception:
        return None
    n = len(doc)
    if n < 3:
        return None
    pages_lines = [_page_lines(p) for p in doc]
    heights = [p.rect.height for p in doc]
    furn = _furniture(pages_lines, heights)
    sizes = Counter()
    for lines in pages_lines:
        for l in lines:
            if not l.glyph:
                sizes[round(l.size)] += len(l.text)
    body_size = sizes.most_common(1)[0][0] if sizes else 12
    # a picture that repeats on many pages (a logo, a watermark, a background) is decoration
    xref_pages: Counter = Counter()
    for page in doc:
        for xr in {i[0] for i in page.get_images()}:
            xref_pages[xr] += 1
    decor = {xr for xr, c in xref_pages.items() if c >= max(3, int(0.2 * n))}

    # Pre-pass: pictures per page, and OCR of the pages that are just a picture of a slide — run in parallel, cached on disk
    figs_by_page: Dict[int, List[Dict[str, Any]]] = {}
    ocr_jobs: List[bytes] = []
    for pi, (page, lines) in enumerate(zip(doc, pages_lines)):
        figs_by_page[pi] = _figures(doc, page, page.rect.height, page.rect.width, decor)
        fs = figs_by_page[pi]
        if ocr and fs and fs[0]["area"] >= 0.45 and sum(len(l.text.split()) for l in lines if not l.glyph) <= 12:
            ocr_jobs.append(fs[0]["bytes"])
    if ocr_jobs:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(_ocr_words, ocr_jobs))
        logger.info("slide-pdf: OCR read %d slide pictures", len(ocr_jobs))

    pages: List[Dict[str, Any]] = []
    for pi, (page, lines) in enumerate(zip(doc, pages_lines)):
        H, W = page.rect.height, page.rect.width
        lines = [l for l in lines if not (_norm(l.text) and (("top" if l.y1 < H * 0.12 else "bottom" if l.y0 > H * 0.86 else ""), _norm(l.text)) in furn)
                 and not re.fullmatch(r"\s*\d{1,3}\s*", l.text)]
        tables = _tables(page)
        in_tbl = lambda l: any(t["bbox"][0] - 3 <= l.x0 and l.x1 <= t["bbox"][2] + 3 and t["bbox"][1] - 3 <= l.y0 and l.y1 <= t["bbox"][3] + 3 for t in tables)  # noqa: E731
        lines = [l for l in lines if not in_tbl(l)]
        local_body = Counter()
        for l in lines:
            if not l.glyph:
                local_body[round(l.size)] += len(l.text)
        page_body = local_body.most_common(1)[0][0] if local_body else body_size
        title, title_lines = _title_of(lines, H, min(page_body, body_size + 2))
        body = [l for l in lines if l not in title_lines]
        figs = figs_by_page.get(pi, [])
        ocr_used = False
        figure_text = ""
        # A slide that is only a picture of a slide: read it with OCR and treat the result like text on the page
        if ocr and figs and figs[0]["area"] >= 0.45 and sum(len(l.text.split()) for l in lines if not l.glyph) <= 12:
            ol, conf, graphic = _ocr_lines(figs[0]["bytes"], figs[0]["bbox"])
            good = [l for l in ol if not l.glyph]
            alpha = sum(1 for l in good if len(re.sub(r"[^A-Za-z]", "", l.text)) >= 0.6 * max(1, len(l.text)))
            figure_text = " ".join(l.text for l in sorted(good, key=lambda l: (l.y0, l.x0)))[:1200] if len(good) >= 2 else ""
            if len(good) >= 3 and conf >= 62 and sum(len(l.text.split()) for l in good) >= 12 and alpha >= 0.7 * len(good) and graphic <= 0.42:
                lines = ol
                ocr_used = True
                local_body = Counter()
                for l in lines:
                    if not l.glyph:
                        local_body[round(l.size)] += len(l.text)
                page_body = local_body.most_common(1)[0][0] if local_body else page_body
                title, title_lines = _title_of(lines, H, min(page_body, body_size + 2))
                body = [l for l in lines if l not in title_lines]
                figs = figs[1:]                                     # the screenshot itself is no longer a figure
        diagram = (not figs) and _is_vector_diagram(page, body, H)
        figure = None
        if figs:
            f = figs[0]
            figure = {k: f[k] for k in ("bytes", "ext", "w", "h")}
            figure["area"] = round(f["area"], 3)
        elif diagram:
            top = max([l.y1 for l in title_lines] + [H * 0.10]) + 4
            figure = _render_clip(page, (0, top, W, H * 0.97))
            if figure:
                figure["area"] = 0.7
        items = [] if diagram else _items(body)
        if ocr_used:                                    # formula / table-cell debris read as text is worse than nothing
            def _texty(t: str) -> bool:
                core = t.replace(" ", "")
                return len(re.sub(r"[^A-Za-z]", "", t)) >= 4 and len(re.sub(r"[^A-Za-z]", "", core)) >= 0.6 * max(1, len(core)) and any(len(w) >= 3 and w.isalpha() for w in t.split())
            items = [i for i in items if _texty(i["text"])]
        if diagram and body:
            labels = [l.text for l in sorted(body, key=lambda l: (l.y0, l.x0)) if len(l.text) > 1][:30]
        else:
            labels = []
        kind = "content"
        words = sum(len(i["text"].split()) for i in items)
        if pi == 0 and not items and not tables:
            kind = "title"
        elif pi == 0 and len(items) <= 4 and words <= 18 and not tables:
            kind = "title"
        elif not items and not tables and not figure and title:
            kind = "section"
        elif figure and figure["area"] >= 0.2 and words <= 25 and not tables:
            kind = "figure"
        pages.append({"page": pi, "title": title, "items": [{"level": i["level"], "text": i["text"]} for i in items], "tables": [t["rows"] for t in tables],
                      "figure": figure, "kind": kind, "labels": labels, "words": words, "ocr": ocr_used, "figure_text": "" if ocr_used else figure_text})

    # a title page: the biggest text of page 1 plus the lines under it
    deck_title, subtitle = "", ""
    if pages and pages[0]["kind"] == "title":
        p0 = pages[0]
        first = [l for l in pages_lines[0] if not l.glyph]
        if first:
            big = max(first, key=lambda l: l.size)
            deck_title = " ".join(l.text for l in sorted([l for l in first if abs(l.size - big.size) < 1], key=lambda l: l.y0))
            subtitle = " · ".join(l.text for l in sorted(first, key=lambda l: l.y0) if abs(l.size - big.size) >= 1 and l.text not in deck_title)[:140]
        p0["title"] = deck_title or p0["title"]
    logger.info("slide-pdf: %d pages, deck title %r, %d with figures, %d with tables", n, deck_title[:40],
                sum(1 for p in pages if p["figure"]), sum(1 for p in pages if p["tables"]))
    doc.close()
    return {"pages": pages, "title": deck_title, "subtitle": subtitle}


def pages_to_markdown(pages: List[Dict[str, Any]]) -> str:
    """Nested markdown, one ``##`` section per slide; consecutive slides with one title are numbered (1/3), (2/3)…"""
    out: List[str] = []
    titles = [p["title"] or "" for p in pages]
    for i, p in enumerate(pages):
        if p["kind"] == "title":
            continue
        t = titles[i]
        if not t:                                    # a slide without its own heading continues the previous one
            t = next((titles[j] for j in range(i - 1, -1, -1) if titles[j]), "Slide " + str(i + 1))
        out.append(f"## {t}")
        out.append("")
        for it in p["items"]:
            out.append("  " * it["level"] + "- " + it["text"])
        for lab in p.get("labels") or []:
            out.append(f"- {lab}")
        for rows in p["tables"]:
            out.append("[TABLE DATA]")
            out.append("| " + " | ".join(rows[0]) + " |")
            out.append("|" + "---|" * len(rows[0]))
            out.extend("| " + " | ".join((r + [""] * len(rows[0]))[:len(rows[0])]) + " |" for r in rows[1:])
        out.append("")
    return "\n".join(out).strip()
