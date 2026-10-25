"""
Native PowerPoint drawing for every visual family the Content Decision Engine can
choose. Shapes, tables and real chart objects — editable in PowerPoint, no
screenshots — so the .pptx matches the web deck instead of falling back to bullets.

``draw_family`` returns True if it drew something. Any family without a bespoke
drawing is rendered as a card grid built from its text, so a visual slide never
degrades to a plain bullet list.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from learnova.logging_config import logger
from learnova.rendering import layout as L
from learnova.visuals.icons import icon_png, pick_icons


def _blend(rgb: RGBColor, t: float) -> RGBColor:
    """Mix ``rgb`` toward white by ``t`` (0 = rgb, 1 = white)."""
    r, g, b = rgb[0], rgb[1], rgb[2]
    return RGBColor(int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t))


def _on(rgb: RGBColor) -> RGBColor:
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return RGBColor(0x10, 0x14, 0x24) if lum > 150 else RGBColor(0xFF, 0xFF, 0xFF)


class _Canvas:
    def __init__(self, slide, theme, band, reserve: float = 0.0):
        self.s, self.t = slide, theme
        self.x = band.left + 0.3
        self.y = band.top + 0.1
        self.w = band.width - 0.6
        self.h = band.height - 0.2 - reserve
        self.tint = _blend(theme.primary_rgb, 0.9)
        # type scale: body text grows to fill roomy slides, shrinks when a quiz/takeaway squeezes the band
        self.k = max(0.62, min(1.28, self.h / 4.2))

    # -- primitives -----------------------------------------------------------
    def shape(self, kind, x, y, w, h, fill=None, line=None, line_w=0.75, radius=0.12):
        shp = self.s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(max(0.05, w)), Inches(max(0.05, h)))
        if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
            try:
                shp.adjustments[0] = radius
            except Exception:
                pass
        if fill is None:
            shp.fill.background()
        else:
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill
        if line is None:
            shp.line.fill.background()
        else:
            shp.line.color.rgb = line
            shp.line.width = Pt(line_w)
        shp.shadow.inherit = False
        return shp

    def card(self, x, y, w, h, fill=None, line=None, radius=0.1):
        return self.shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill or self.t.card_bg_rgb,
                          line or _blend(self.t.primary_rgb, 0.7), radius=radius)

    def text(self, x, y, w, h, runs: Sequence[Tuple[str, float, bool, RGBColor]], align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, shape=None):
        shp = shape or self.s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = shp.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.08)
        tf.margin_top = tf.margin_bottom = Inches(0.04)
        first = True
        for txt, size, bold, color in runs:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.alignment = align
            r = p.add_run()
            r.text = str(txt)
            r.font.size = Pt(max(8, round(size * self.k, 1)))
            r.font.bold = bold
            r.font.color.rgb = color
        return shp

    def fit(self, texts, w, h, mx=24.0, mn=10.0, spacing=6.0) -> float:
        """Largest point size at which ``texts`` fill a w×h box without overflowing (then the type scale ``k`` is NOT applied)."""
        return L.fit_font_size([t for t in texts if t], max(0.3, w), max(0.2, h), max_pt=mx, min_pt=mn, spacing_pt=spacing)

    def runs_fit(self, x, y, w, h, head, body, hmax=26, bmax=19, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT,
                 head_color=None, body_color=None):
        """Heading + body sized so the pair fills the box (heading ≈ 1.35× body)."""
        iw, ih = (w - 0.2) * 0.9, (h - 0.12) * 0.94   # safety margin: real glyphs run wider than the estimate
        bsz = self.fit([body], iw, ih * (0.62 if head else 1.0), bmax, 10.5) if body else 0
        hsz = min(hmax, max(13.0, (bsz * 1.35) if body else self.fit([head], iw, ih, hmax, 13)))
        hsz = min(hsz, self.fit([head], iw, ih * 0.45 if body else ih, hmax, 12)) if head else 0
        shp = self.s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = shp.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.1)
        tf.margin_top = tf.margin_bottom = Inches(0.05)
        first = True
        for txt, size, bold, color in ((head, hsz, True, head_color or self.t.primary_rgb), (body, bsz, False, body_color or self.t.text_rgb)):
            if not txt:
                continue
            para = tf.paragraphs[0] if first else tf.add_paragraph()
            if not first:
                para.space_before = Pt(5)
            first = False
            para.alignment = align
            r = para.add_run()
            r.text = str(txt)
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
        return shp

    def icon_circle(self, x, y, d, name, fill=None, color=None):
        """A tinted disc with a concept icon (PNG) centred in it."""
        fill = fill or _blend(self.t.primary_rgb, 0.86)
        self.shape(MSO_SHAPE.OVAL, x, y, d, d, fill)
        hexc = "#%02x%02x%02x" % tuple((color or self.t.primary_rgb)[i] for i in range(3))
        try:
            self.s.shapes.add_picture(__import__("io").BytesIO(icon_png(name, hexc, 192)), Inches(x + d * 0.2), Inches(y + d * 0.2),
                                      Inches(d * 0.6), Inches(d * 0.6))
        except Exception:
            pass

    def picture(self, png: bytes, x, y, w, h):
        """Place a PNG so it covers the (x, y, w, h) box without distortion (centre-cropped)."""
        import io

        from PIL import Image

        im = Image.open(io.BytesIO(png))
        iw, ih = im.size
        box_ratio, img_ratio = w / h, iw / ih
        if img_ratio > box_ratio:   # too wide → crop sides
            nw = int(ih * box_ratio); l = (iw - nw) // 2
            im = im.crop((l, 0, l + nw, ih))
        else:
            nh = int(iw / box_ratio); t = (ih - nh) // 2
            im = im.crop((0, t, iw, t + nh))
        buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
        return self.s.shapes.add_picture(buf, Inches(x), Inches(y), Inches(w), Inches(h))

    def badge(self, x, y, n, d=0.42, fill=None):
        fill = fill or self.t.primary_rgb
        shp = self.shape(MSO_SHAPE.OVAL, x, y, d, d, fill)
        self.text(0, 0, 0, 0, [(str(n), 13, True, _on(fill))], PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, shape=shp)
        return shp


def _readable_accent(theme) -> RGBColor:
    """Accent colour for text on a white card — falls back to the primary when the accent is too pale."""
    a = theme.accent_rgb
    lum = 0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2]
    return theme.primary_rgb if lum > 150 else a


def _pt(n_chars: int, base: float, lo: float, scale: float = 1.0) -> float:
    return max(lo, min(base, base - (n_chars - 60) / 30.0)) * scale


def _flatten(data: Any, out: List[str]) -> None:
    if isinstance(data, str):
        if data.strip() and len(data) > 2:
            out.append(data.strip())
    elif isinstance(data, dict):
        for v in data.values():
            _flatten(v, out)
    elif isinstance(data, (list, tuple)):
        for v in data:
            _flatten(v, out)


def _grid(c: _Canvas, items: List[Tuple[str, str]], numbered: bool = False, cols: int = 0, icons: bool = True) -> None:
    """Cards that tile the whole canvas (no leftover whitespace); each carries an icon and fitted text."""
    n = len(items)
    cols = cols or (1 if n == 1 else 2 if n in (2, 4) else 3)
    rows = math.ceil(n / cols)
    gap = 0.24
    cw = (c.w - gap * (cols - 1)) / cols
    ch = (c.h - gap * (rows - 1)) / rows
    names = pick_icons(" ".join(h + " " + b for h, b in items), n + 3)
    used: List[str] = []
    for i, (head, body) in enumerate(items):
        if body and body.lower().rstrip('. ').startswith(head.lower().rstrip('. ')):
            head, body = body, ""   # the heading was just the opening words — show the sentence once, large
        r, k = divmod(i, cols)
        x, y = c.x + k * (cw + gap), c.y + r * (ch + gap)
        c.card(x, y, cw, ch, radius=0.08)
        horiz = cw > 3.4 and ch < 2.2
        d = min(0.78, ch * 0.34, cw * 0.28)
        if icons:
            mine = pick_icons(head + " " + body, 6)
            name = next((m for m in mine if m not in used), mine[0])
            used.append(name)
            c.icon_circle(x + 0.2, y + 0.2, d, name)
        elif numbered:
            c.badge(x + 0.2, y + 0.2, i + 1, d=d)
        top_off = 0.0 if horiz else (d + 0.3 if (icons or numbered) else 0.1)
        left_off = (d + 0.4) if horiz and (icons or numbered) else 0.1
        c.runs_fit(x + left_off, y + (0.15 if horiz else top_off), cw - left_off - 0.1, ch - (0.3 if horiz else top_off) - 0.1, head, body,
                   anchor=MSO_ANCHOR.MIDDLE if horiz or not (icons or numbered) else MSO_ANCHOR.TOP)


# ── family drawers ────────────────────────────────────────────────────────────
def _process(c: _Canvas, data, cyclic: bool) -> bool:
    raw = data.get("stages") or data.get("steps") or []
    items = []
    for st in raw[:8]:
        if isinstance(st, dict):
            items.append((str(st.get("label", "")), str(st.get("detail", ""))))
        else:
            items.append((str(st), ""))
    if len(items) < 2:
        return False
    n = len(items)
    per = n if n <= 4 else math.ceil(n / 2)
    rows = math.ceil(n / per)
    gap = 0.42
    foot = 0.5 if cyclic else 0.0
    cw = (c.w - gap * (per - 1)) / per
    ch = (c.h - foot - 0.3 * (rows - 1)) / rows
    for i, (lab, det) in enumerate(items):
        r, k = divmod(i, per)
        x, y = c.x + k * (cw + gap), c.y + r * (ch + 0.3)
        c.card(x, y, cw, ch, radius=0.08)
        d = min(0.62, ch * 0.28)
        c.badge(x + 0.2, y + 0.2, i + 1, d=d)
        if det and det.strip().lower() == lab.strip().lower():
            det = ""
        c.runs_fit(x + 0.05, y + d + 0.3, cw - 0.1, ch - d - 0.4, lab, det, hmax=22, bmax=16)
        if k < per - 1 and i < n - 1:
            c.shape(MSO_SHAPE.RIGHT_ARROW, x + cw + 0.04, y + ch / 2 - 0.17, gap - 0.08, 0.34, c.t.accent_rgb)
    if cyclic:
        c.text(c.x, c.y + c.h - 0.46, c.w, 0.42, [("↻  and the cycle repeats", 15, True, c.t.primary_rgb)], PP_ALIGN.CENTER)
    return True


def _worked(c: _Canvas, data) -> bool:
    rows = data.get("rows") or [{"step": s, "reason": ""} for s in (data.get("steps") or [])]
    rows = [r for r in rows if str(r.get("step", "")).strip()][:8]
    if len(rows) < 2:
        return False
    rh = min(0.85, c.h / len(rows))
    for i, r in enumerate(rows):
        y = c.y + i * rh
        c.badge(c.x, y + 0.05, i + 1, d=min(0.4, rh - 0.12))
        runs = [(r["step"], 14, True, c.t.primary_rgb)]
        if str(r.get("reason", "")).strip():
            runs.append((r["reason"], 11, False, c.t.text_rgb))
        c.text(c.x + 0.6, y, c.w - 0.6, rh - 0.05, runs, anchor=MSO_ANCHOR.MIDDLE)
    return True


def _timeline(c: _Canvas, data) -> bool:
    ev = [e for e in (data.get("events") or []) if e.get("title")][:7]
    if len(ev) < 3:
        return False
    n = len(ev)
    cy = c.y + c.h / 2
    c.shape(MSO_SHAPE.RECTANGLE, c.x, cy - 0.025, c.w, 0.05, _blend(c.t.primary_rgb, 0.4))
    step = c.w / n
    cw, ch = min(step * 1.7, 2.7), min(1.9, (c.h - 0.9) / 2)
    for i, e in enumerate(ev):
        cx = c.x + step * (i + 0.5)
        c.shape(MSO_SHAPE.OVAL, cx - 0.11, cy - 0.11, 0.22, 0.22, c.t.accent_rgb, c.t.primary_rgb, 2)
        up = i % 2 == 0
        y = cy - 0.3 - ch if up else cy + 0.3
        x = min(max(c.x, cx - cw / 2), c.x + c.w - cw)
        c.card(x, y, cw, ch)
        c.text(x, y, cw, ch, [(e.get("date", ""), 20, True, c.t.primary_rgb),
                              (e.get("title", ""), _pt(len(str(e.get("title", ""))), 14, 10.5), False, c.t.text_rgb)],
               PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    return True


def _compare_table(c: _Canvas, data) -> bool:
    heads, rows = data.get("headers") or [], data.get("rows") or []
    if len(heads) < 2 or len(rows) < 2:
        return False
    rows = rows[:7]
    gf = c.s.shapes.add_table(len(rows) + 1, len(heads), Inches(c.x), Inches(c.y + 0.05), Inches(c.w),
                              Inches(c.h - 0.1))
    tbl = gf.table
    for j, h in enumerate(heads):
        cell = tbl.cell(0, j)
        cell.fill.solid(); cell.fill.fore_color.rgb = c.t.primary_rgb
        cell.text = str(h)
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(22); r.font.bold = True; r.font.color.rgb = _on(c.t.primary_rgb)
    for i, row in enumerate(rows, start=1):
        for j in range(len(heads)):
            cell = tbl.cell(i, j)
            cell.fill.solid(); cell.fill.fore_color.rgb = c.t.card_bg_rgb if i % 2 else _blend(c.t.primary_rgb, 0.92)
            cell.text = str((list(row) + [""] * len(heads))[j])
            for p in cell.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(c.fit([str(x) for x in (list(rows[0]) if rows else [])], c.w / len(heads) - 0.4, c.h / (len(rows) + 1) - 0.2, 20, 12)); r.font.color.rgb = c.t.text_rgb; cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    return True


def _pros_cons(c: _Canvas, data) -> bool:
    pros, cons = [str(x) for x in data.get("pros") or []][:5], [str(x) for x in data.get("cons") or []][:5]
    if not (pros and cons):
        return False
    cw = c.w / 2 - 0.15
    for k, (title, items, col) in enumerate((("Advantages", pros, RGBColor(0x1A, 0x7F, 0x4B)), ("Trade-offs", cons, RGBColor(0xB2, 0x3B, 0x3B)))):
        x = c.x + k * (cw + 0.3)
        c.card(x, c.y + 0.1, cw, c.h - 0.2, line=col)
        c.text(x + 0.1, c.y + 0.18, cw - 0.2, 0.5, [(title.upper(), 15, True, col)])
        c.text(x + 0.1, c.y + 0.75, cw - 0.2, c.h - 1.0, [("•  " + t, 13, False, c.t.text_rgb) for t in items])
    return True


def _matrix(c: _Canvas, data) -> bool:
    q = (data.get("quadrants") or data.get("cells") or [])[:4]
    if len(q) < 3:
        return False
    gap = 0.2
    cw, ch = (c.w - gap) / 2, (c.h - gap) / 2
    for i, qd in enumerate(q):
        r, k = divmod(i, 2)
        x, y = c.x + k * (cw + gap), c.y + r * (ch + gap)
        c.card(x, y, cw, ch, fill=_blend(c.t.primary_rgb, 0.88 - 0.05 * i))
        items = [str(t) for t in (qd.get("items") or [])]
        c.text(x + 0.1, y + 0.1, cw - 0.2, ch - 0.2, [(qd.get("title", ""), 15, True, c.t.primary_rgb)] + [(t, 12, False, c.t.text_rgb) for t in items[:3]],
               anchor=MSO_ANCHOR.MIDDLE)
    return True


def _layers(c: _Canvas, data) -> bool:
    lv = (data.get("levels") or [])[:6]
    if len(lv) < 3:
        return False
    n = len(lv)
    gap = 0.12
    rh = (c.h - gap * (n - 1)) / n
    for i, it in enumerate(lv):
        label, detail = (it.get("label", ""), it.get("detail", "")) if isinstance(it, dict) else (str(it), "")
        frac = 1.0 - i * (0.22 / max(1, n - 1))
        w = c.w * frac
        fill = _blend(c.t.primary_rgb, 0.8 - 0.8 * (i / max(1, n - 1)))
        y = c.y + i * (rh + gap)
        shp = c.shape(MSO_SHAPE.ROUNDED_RECTANGLE, c.x + (c.w - w) / 2, y, w, rh, fill, radius=0.18)
        fg = _on(fill)
        if detail and detail.strip().lower() == label.strip().lower():
            detail = ""
        lw = min(3.0, w * 0.28)
        c.runs_fit(c.x + (c.w - w) / 2 + 0.1, y, lw, rh, label, "", hmax=24, head_color=fg, anchor=MSO_ANCHOR.MIDDLE)
        if detail:
            c.runs_fit(c.x + (c.w - w) / 2 + lw + 0.1, y, w - lw - 0.3, rh, "", detail, bmax=17, body_color=fg, anchor=MSO_ANCHOR.MIDDLE)
    return True


def _venn(c: _Canvas, data) -> bool:
    items = [str(x) for x in data.get("items") or []][:8]
    if len(items) < 3:
        return False
    d = min(c.h * 0.85, c.w * 0.38)
    top = c.y + (c.h - d) / 2
    c.shape(MSO_SHAPE.OVAL, c.x, top, d, d, _blend(c.t.primary_rgb, 0.7), c.t.primary_rgb, 1.5)
    c.shape(MSO_SHAPE.OVAL, c.x + d * 0.6, top, d, d, _blend(c.t.accent_rgb, 0.7), c.t.accent_rgb, 1.5)
    c.text(c.x + d * 1.75, c.y, c.w - d * 1.75, c.h, [("•  " + t, 13, False, c.t.text_rgb) for t in items], anchor=MSO_ANCHOR.MIDDLE)
    return True


def _stat_tiles(c: _Canvas, data) -> bool:
    tiles = (data.get("tiles") or [])[:4]
    if not tiles:
        return False
    n = len(tiles)
    cols = n if n <= 2 else 2 if n == 4 and c.w < 8 else n
    rows = math.ceil(n / cols)
    gap = 0.25
    cw = (c.w - gap * (cols - 1)) / cols
    ch = (c.h - gap * (rows - 1)) / rows
    names = pick_icons(" ".join(str(t.get("label", "")) for t in tiles), n + 2)
    for i, t in enumerate(tiles):
        r, k = divmod(i, cols)
        x, y = c.x + k * (cw + gap), c.y + r * (ch + gap)
        c.card(x, y, cw, ch, radius=0.08)
        d = min(0.6, ch * 0.2)
        c.icon_circle(x + 0.2, y + 0.18, d, names[i % len(names)], fill=_blend(c.t.accent_rgb, 0.7), color=_readable_accent(c.t))
        val = str(t.get("value", ""))
        vsz = c.fit([val], cw - 0.3, ch * 0.34, 54, 24)
        det = str(t.get("detail", ""))
        runs = [(val, vsz, True, c.t.primary_rgb), (str(t.get("label", "")).upper(), 13, True, _readable_accent(c.t))]
        if det and det.lower() != str(t.get("label", "")).lower():
            runs.append((det, c.fit([det], cw - 0.3, ch * 0.28, 15, 10), False, c.t.text_rgb))
        tb = c.s.shapes.add_textbox(Inches(x + 0.1), Inches(y + d + 0.25), Inches(cw - 0.2), Inches(ch - d - 0.35))
        tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        for j, (txt, sz, bold, col) in enumerate(runs):
            para = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            para.alignment = PP_ALIGN.LEFT
            rr = para.add_run(); rr.text = txt; rr.font.size = Pt(sz); rr.font.bold = bold; rr.font.color.rgb = col
    return True


def _cause_effect(c: _Canvas, data) -> bool:
    nodes = (data.get("nodes") or [])[:6]
    if len(nodes) < 3:
        return False
    n = len(nodes)
    arrow_h = 0.24
    foot = 0.4 if data.get("loop") else 0.0
    nh = (c.h - arrow_h * (n - 1) - foot) / n
    for i, nd in enumerate(nodes):
        y = c.y + i * (nh + arrow_h)
        c.card(c.x, y, c.w, nh, radius=0.12)
        d = min(0.6, nh * 0.6)
        c.badge(c.x + 0.2, y + (nh - d) / 2, i + 1, d=d)
        det = str(nd.get("detail", ""))
        if det.strip().lower() == str(nd.get("label", "")).strip().lower():
            det = ""
        c.runs_fit(c.x + d + 0.35, y + 0.04, c.w - d - 0.5, nh - 0.08, nd.get("label", ""), det, hmax=20, bmax=15, anchor=MSO_ANCHOR.MIDDLE)
        if i < n - 1:
            c.shape(MSO_SHAPE.DOWN_ARROW, c.x + c.w / 2 - 0.13, y + nh + 0.01, 0.26, arrow_h - 0.02, c.t.accent_rgb)
    if data.get("loop"):
        c.text(c.x, c.y + c.h - 0.4, c.w, 0.38, [("↺  and the effect feeds back into the cause", 13, True, _readable_accent(c.t))], PP_ALIGN.CENTER)
    return True


def _formula(c: _Canvas, data) -> bool:
    f = str(data.get("formula", "")).strip()
    if not f:
        return False
    notes = [str(x) for x in data.get("notes") or []][:3]
    oy = max(0.0, (c.h - 4.1 * c.k) / 2)
    c.text(c.x, c.y + oy, c.w, 0.45, [(str(data.get("term", "")).upper(), 14, True, c.t.accent_rgb)])
    c.text(c.x, c.y + oy + 0.45, c.w, 1.0, [(str(data.get("statement", "")), 20, False, c.t.text_rgb)])
    box = c.shape(MSO_SHAPE.ROUNDED_RECTANGLE, c.x, c.y + oy + 1.55 * c.k, c.w, 1.6 * c.k, c.t.primary_rgb)
    c.text(0, 0, 0, 0, [(f, 38, True, _on(c.t.primary_rgb))], PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, shape=box)
    if notes:
        c.text(c.x, c.y + oy + 3.3 * c.k, c.w, max(0.6, c.h - oy - 3.3 * c.k), [("•  " + t, 15, False, c.t.text_rgb) for t in notes])
    return True


def _definition(c: _Canvas, data) -> bool:
    term, meaning = str(data.get("term", "")), str(data.get("definition", ""))
    if not (term and meaning):
        return False
    notes = [str(x) for x in data.get("notes") or []][:4]
    oy = max(0.0, (c.h - 4.0 * c.k) / 2)
    box = c.shape(MSO_SHAPE.ROUNDED_RECTANGLE, c.x, c.y + oy, c.w, 2.4 * c.k, _blend(c.t.primary_rgb, 0.9), c.t.primary_rgb, 1.5)
    c.text(0, 0, 0, 0, [(term, 32, True, c.t.primary_rgb), (meaning, 20, False, c.t.text_rgb)], PP_ALIGN.LEFT, MSO_ANCHOR.MIDDLE, shape=box)
    if notes:
        c.text(c.x, c.y + oy + 2.6 * c.k, c.w, max(0.6, c.h - oy - 2.6 * c.k), [("•  " + t, 16, False, c.t.text_rgb) for t in notes])
    return True


def _quote(c: _Canvas, data) -> bool:
    t = str(data.get("text", ""))
    if not t:
        return False
    box = c.shape(MSO_SHAPE.ROUNDED_RECTANGLE, c.x, c.y + 0.4, c.w, c.h - 0.8, _blend(c.t.primary_rgb, 0.9))
    runs = [("“" + t + "”", 26, True, c.t.primary_rgb)]
    if data.get("attribution"):
        runs.append(("— " + str(data["attribution"]), 14, False, c.t.text_rgb))
    c.text(0, 0, 0, 0, runs, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, shape=box)
    return True


def _funnel(c: _Canvas, data) -> bool:
    st = (data.get("stages") or [])[:6]
    if len(st) < 3:
        return False
    n = len(st)
    rh = min(0.95, c.h / n - 0.1)
    for i, s_ in enumerate(st):
        w = c.w * (1.0 - i * (0.58 / max(1, n - 1)))
        fill = _blend(c.t.primary_rgb, 0.05 + 0.5 * i / max(1, n - 1))
        y = c.y + (c.h - (rh + 0.1) * n) / 2 + i * (rh + 0.1)
        shp = c.shape(MSO_SHAPE.ROUNDED_RECTANGLE, c.x + (c.w - w) / 2, y, w, rh, fill)
        c.text(0, 0, 0, 0, [(f"{s_.get('value', '')}   {s_.get('label', '')}", 15, True, _on(fill))], PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, shape=shp)
    return True


def _chart(c: _Canvas, data, kind: str) -> bool:
    pts = []
    for p in data.get("points") or data.get("series") or data.get("items") or []:
        try:
            pts.append((str(p.get("label") or p.get("x") or ""), float(p.get("value") if p.get("value") is not None else p.get("y"))))
        except (AttributeError, TypeError, ValueError):
            continue
    pts = pts[:10]
    if len(pts) < 2:
        return False
    cd = CategoryChartData()
    cd.categories = [l for l, _ in pts]
    cd.add_series("Value", [v for _, v in pts])
    ctype = {"pie": XL_CHART_TYPE.PIE, "line": XL_CHART_TYPE.LINE_MARKERS, "bar": XL_CHART_TYPE.BAR_CLUSTERED}[kind]
    gf = c.s.shapes.add_chart(ctype, Inches(c.x), Inches(c.y), Inches(c.w), Inches(c.h), cd)
    ch = gf.chart
    ch.has_legend = kind == "pie"
    if kind == "pie":
        ch.legend.position = XL_LEGEND_POSITION.RIGHT
        ch.legend.include_in_layout = False
    plot = ch.plots[0]
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(12)
    if kind == "pie":
        for i in range(len(pts)):
            pt = plot.series[0].points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = _blend(c.t.primary_rgb, 0.0 if i == 0 else min(0.75, 0.18 * i))
    else:
        ser = plot.series[0]
        if kind == "bar":
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = c.t.primary_rgb
        else:
            ser.format.line.color.rgb = c.t.primary_rgb
            ser.format.line.width = Pt(3)
        ch.category_axis.tick_labels.font.size = Pt(12)
        ch.value_axis.tick_labels.font.size = Pt(11)
        ch.value_axis.has_major_gridlines = False
    return True


def _function_plot(c: _Canvas, data) -> bool:
    from learnova.rendering.family_blocks import _eval_expr

    expr = str(data.get("expr", "")).strip()
    a, b = (data.get("domain") or [-5, 5])[:2]
    xs = [a + (b - a) * i / 80 for i in range(81)]
    ys = [(x, _eval_expr(expr, x)) for x in xs]
    pts = [(x, y) for x, y in ys if y is not None and abs(y) < 1e6]
    if len(pts) < 6:
        return False
    ymin, ymax = min(y for _, y in pts), max(y for _, y in pts)
    if ymax == ymin:
        ymax += 1
    px, py, pw, ph = c.x + 0.4, c.y + 0.3, c.w - 0.8, c.h - 0.9
    c.shape(MSO_SHAPE.RECTANGLE, px, py, pw, ph, _blend(c.t.primary_rgb, 0.95), _blend(c.t.primary_rgb, 0.6))
    if ymin < 0 < ymax:
        yy = py + ph * (1 - (0 - ymin) / (ymax - ymin))
        c.shape(MSO_SHAPE.RECTANGLE, px, yy - 0.01, pw, 0.02, c.t.text_rgb)
    if a < 0 < b:
        xx = px + pw * (0 - a) / (b - a)
        c.shape(MSO_SHAPE.RECTANGLE, xx - 0.01, py, 0.02, ph, c.t.text_rgb)
    coords = [(Inches(px + pw * (x - a) / (b - a)), Inches(py + ph * (1 - (y - ymin) / (ymax - ymin)))) for x, y in pts]
    fb = c.s.shapes.build_freeform(Emu(int(coords[0][0])), Emu(int(coords[0][1])), scale=1.0)
    fb.add_line_segments([(Emu(int(x)), Emu(int(y))) for x, y in coords[1:]], close=False)
    curve = fb.convert_to_shape()
    curve.fill.background()
    curve.line.color.rgb = c.t.primary_rgb
    curve.line.width = Pt(3.5)
    c.text(px, py + ph + 0.05, pw, 0.4, [(f"y = {expr}", 14, True, c.t.primary_rgb)], PP_ALIGN.CENTER)
    return True


def _mind_map(c: _Canvas, data) -> bool:
    center = str(data.get("center") or data.get("central") or "")
    br = [str(b) for b in (data.get("branches") or data.get("items") or []) if str(b).strip()][:8]
    if not center or len(br) < 3:
        return False
    cx, cy = c.x + c.w / 2, c.y + c.h / 2
    hub = c.shape(MSO_SHAPE.OVAL, cx - 1.1, cy - 0.6, 2.2, 1.2, c.t.primary_rgb)
    c.text(0, 0, 0, 0, [(center, 15, True, _on(c.t.primary_rgb))], PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, shape=hub)
    rx, ry = c.w / 2 - 1.3, c.h / 2 - 0.55
    for i, b in enumerate(br):
        ang = 2 * math.pi * i / len(br) - math.pi / 2
        x, y = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
        c.card(x - 1.2, y - 0.4, 2.4, 0.8)
        c.text(x - 1.2, y - 0.4, 2.4, 0.8, [(b, 12, False, c.t.text_rgb)], PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    return True


def draw_family(slide, sp, theme, band) -> bool:
    family = getattr(sp, "family", "") or ""
    data = getattr(sp, "data", {}) or {}
    if not data:
        return False
    notes = [str(n) for n in ((getattr(sp, "params", None) or {}).get("notes") or []) if str(n).strip()]
    c = _Canvas(slide, theme, band, reserve=0.75 if notes else 0.0)
    try:
        if family in {"PROCESS_LINEAR", "PROCESS_CYCLIC"}:
            ok = _process(c, data, family == "PROCESS_CYCLIC")
        elif family == "WORKED_EXAMPLE":
            ok = _worked(c, data)
        elif family == "TIMELINE":
            ok = _timeline(c, data)
        elif family == "COMPARE_TABLE":
            ok = _compare_table(c, data)
        elif family == "COMPARE_VISUAL":
            ok = _pros_cons(c, data)
        elif family == "MATRIX_GRID":
            ok = _matrix(c, data)
        elif family in {"LAYERS", "HIERARCHY_NEST"}:
            ok = _layers(c, {"levels": [{"label": x} if isinstance(x, str) else x for x in data.get("levels", [])]})
        elif family == "SET_DIAGRAM":
            ok = _venn(c, data)
        elif family == "STAT_TILES":
            ok = _stat_tiles(c, data)
        elif family == "CAUSE_EFFECT":
            ok = _cause_effect(c, data)
        elif family == "FORMULA_CALLOUT":
            ok = _formula(c, data)
        elif family == "DEFINITION":
            ok = _definition(c, data)
        elif family == "QUOTE":
            ok = _quote(c, data)
        elif family == "FUNNEL":
            ok = _funnel(c, data)
        elif family in {"CHART_CATEGORICAL", "CHART_RANKING"}:
            ok = _chart(c, data, "bar")
        elif family == "CHART_TREND":
            ok = _chart(c, data, "line")
        elif family == "CHART_PART_TO_WHOLE":
            ok = _chart(c, data, "pie")
        elif family in {"FUNCTION_PLOT", "CALCULUS_VIZ"}:
            ok = _function_plot(c, data)
        elif family == "MIND_MAP":
            ok = _mind_map(c, data)
        elif family in {"KEY_POINTS", "LIST_STRUCTURED"}:
            cards = [(str(x.get("heading", "")), str(x.get("body", ""))) for x in (data.get("cards") or [])[:6] if isinstance(x, dict)]
            ok = len(cards) >= 2
            if ok:
                _grid(c, cards, icons=True)
        elif family == "CHECKLIST":
            items = [(str(x.get("text", x)) if isinstance(x, dict) else str(x), "") for x in (data.get("items") or [])[:8]]
            ok = len(items) >= 2
            if ok:
                _grid(c, [(t, "") for t, _ in items], numbered=False, cols=2 if len(items) > 4 else 1, icons=True)
        else:
            ok = False
        if not ok:  # any other family: a card grid from its text — still a visual, never bullets
            flat: List[str] = []
            _flatten(data, flat)
            flat = flat[:6]
            if len(flat) < 2:
                return False
            _grid(c, [(t[:60], t if len(t) > 60 else "") for t in flat], icons=True)
        if notes:
            box = c.shape(MSO_SHAPE.ROUNDED_RECTANGLE, c.x, band.top + band.height - 0.85, c.w, 0.7, _blend(theme.accent_rgb, 0.85), None)
            c.text(0, 0, 0, 0, [(" ".join(notes)[:420], 14, False, theme.text_rgb)], PP_ALIGN.LEFT, MSO_ANCHOR.MIDDLE, shape=box)
        return True
    except Exception as exc:  # best-effort: never break deck export
        logger.warning("pptx visual %s failed: %s", family, exc)
        return False
