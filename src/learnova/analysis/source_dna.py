"""
Colour DNA of a source deck: the palette its authors actually used.

A converted deck that comes out in an unrelated blue feels like a stranger's slides. This reads a handful of pages
of the source, finds the dominant background and the saturated brand colours (ignoring white, black and greys),
and returns a palette whose text and heading colours are pushed to readable contrast — so the new deck is
recognisably the same course, only better designed.
"""

from __future__ import annotations

import colorsys
import io
from typing import Any, Dict, List, Optional, Tuple


def _hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _hsv(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    return colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)


def _hue_gap(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1 - d) * 360


def from_images(images: List[bytes], k: int = 14) -> Optional[Dict[str, Any]]:
    """Dominant background + brand colours from page renders (PNG/JPEG bytes)."""
    try:
        from PIL import Image
    except Exception:
        return None
    tiles = []
    for b in images:
        try:
            im = Image.open(io.BytesIO(b)).convert("RGB")
            im.thumbnail((160, 160))
            tiles.append(im)
        except Exception:
            continue
    if not tiles:
        return None
    w = max(t.width for t in tiles)
    h = sum(t.height for t in tiles)
    sheet = Image.new("RGB", (w, h), (255, 255, 255))
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y))
        y += t.height
    q = sheet.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: k * 3]
    counts = sorted(q.getcolors(), reverse=True)           # [(count, index)]
    total = sum(c for c, _ in counts) or 1
    cols = [(c / total, (pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2])) for c, i in counts]

    bg = (255, 255, 255)
    top_frac, top = cols[0]
    hv, sv, vv = _hsv(top)
    if top_frac >= 0.25 and vv > 0.82 and sv < 0.2:            # a light, barely-tinted ground: keep its tint (cream, ice blue)
        bg = top
    # brand colours: cluster only the saturated pixels, so thin coloured text and lines still count
    import numpy as np

    arr = np.asarray(sheet).reshape(-1, 3).astype(float) / 255.0
    mx, mn = arr.max(axis=1), arr.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    keep = (sat >= 0.3) & (mx >= 0.25) & (mx <= 0.98)
    if int(keep.sum()) < 60:
        return None
    px = (arr[keep] * 255).astype("uint8")
    sub = Image.fromarray(px.reshape(1, -1, 3), "RGB")
    q2 = sub.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal2 = q2.getpalette()[: 8 * 3]
    brand = sorted(((c, (pal2[i * 3], pal2[i * 3 + 1], pal2[i * 3 + 2])) for c, i in q2.getcolors()), reverse=True)
    primary = brand[0][1]
    ph = _hsv(primary)[0]
    accent = next((rgb for c, rgb in brand[1:] if _hue_gap(_hsv(rgb)[0], ph) >= 35 and c >= 0.12 * brand[0][0]), None)
    return {"primary": _hex(primary), "accent": _hex(accent) if accent else None, "background": _hex(bg), "coverage": round(sum(f for f, _ in cols[:6]), 2),
            "swatches": [_hex(c) for _, c in cols[:6]]}


def from_pdf(path: str, max_pages: int = 14) -> Optional[Dict[str, Any]]:
    try:
        import fitz

        doc = fitz.open(path)
        n = len(doc)
        step = max(1, n // max_pages)
        imgs = []
        for i in range(0, n, step)[:max_pages]:
            pix = doc[i].get_pixmap(dpi=36)
            imgs.append(pix.tobytes("png"))
        doc.close()
        return from_images(imgs)
    except Exception:
        return None


def to_theme_spec(dna: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """A custom-theme spec for ``resolve_theme`` with colours adjusted until text and headings are readable."""
    if not dna:
        return None
    from learnova.rendering.palettes import contrast, ensure_contrast, mix

    bg = dna.get("background") or "#ffffff"
    if contrast("#111111", bg) < 8:                             # a dark source ground would need a dark theme: keep the deck light
        bg = "#ffffff"
    primary = ensure_contrast(dna["primary"], bg, 4.8, prefer_darker=True)
    if dna.get("accent"):
        accent = dna["accent"]
    else:                                                       # no second brand colour: a lively complement of the first
        import colorsys

        r_, g_, b_ = (int(primary[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h_, s_, v_ = colorsys.rgb_to_hsv(r_, g_, b_)
        accent = "#{:02x}{:02x}{:02x}".format(*(round(c * 255) for c in colorsys.hsv_to_rgb((h_ + 0.46) % 1.0, 0.72, 0.97)))
    return {"primary": primary, "secondary": accent, "background": bg, "name": "From your deck"}
