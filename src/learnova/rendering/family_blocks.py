"""
HTML/SVG blocks for the expanded visual families in the web deck.

Given a family + the structured ``data`` the Deck Director carried
(``visual_selector.build_family_data``), each builder returns a self-contained
HTML string themed with the deck's palette. Returns ``None`` when the data is
insufficient, so the caller falls back to a bullet list.

Every element gets a stable ``data-el`` id and text bullets carry ``data-build``
so the deck's present-mode script can turn them into progressive-reveal
fragments (matching the animation timeline).

Pure string building — no LLM, no network.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional

_esc = html.escape


def _chip(text: str, i: int, bg: str, fg: str, border: str) -> str:
    return (
        f'<div data-el="el.{i}" data-build="{i}" '
        f'style="flex:1 1 0;min-width:120px;background:{bg};color:{fg};'
        f'border:2px solid {border};border-radius:10px;padding:14px 16px;'
        f'font-size:0.9rem;line-height:1.35;">{_esc(text)}</div>'
    )


def _cards(data: Dict[str, Any], theme) -> Optional[str]:
    cards = data.get("cards") or []
    if len(cards) < 3:
        return None
    cells = ""
    for i, c in enumerate(cards[:6]):
        head = _esc(str(c.get("heading", "")))
        body = _esc(str(c.get("body", "")))
        head_html = (
            f'<div style="font-weight:800;text-transform:uppercase;'
            f'letter-spacing:.04em;color:{theme.primary_hex};font-size:0.8rem;'
            f'margin-bottom:6px;">{head}</div>' if head else ""
        )
        cells += (
            f'<div data-el="el.{i}" data-build="{i}" '
            f'style="flex:1 1 30%;min-width:180px;background:{theme.card_bg_hex};'
            f'border:1px solid {theme.primary_hex}22;border-top:4px solid '
            f'{theme.primary_hex};border-radius:12px;padding:16px;">{head_html}'
            f'<div style="font-size:0.92rem;line-height:1.4;color:{theme.text_hex};">{body}</div></div>'
        )
    return f'<div style="display:flex;flex-wrap:wrap;gap:14px;margin-top:20px;">{cells}</div>'


def _pros_cons(data: Dict[str, Any], theme) -> Optional[str]:
    pros = data.get("pros") or []
    cons = data.get("cons") or []
    if not (pros and cons):
        return None

    def col(title, items, colour, start):
        lis = "".join(
            f'<li data-el="el.{start + j}" data-build="{start + j}" '
            f'style="margin-bottom:8px;">{_esc(str(x))}</li>'
            for j, x in enumerate(items[:5])
        )
        return (
            f'<div style="flex:1;background:{theme.card_bg_hex};border:2px solid {colour};'
            f'border-radius:12px;padding:16px;">'
            f'<div style="font-weight:800;color:{colour};text-transform:uppercase;'
            f'font-size:0.85rem;margin-bottom:10px;">{title}</div>'
            f'<ul style="margin:0;padding-left:18px;font-size:0.9rem;line-height:1.4;">{lis}</ul></div>'
        )

    return (
        f'<div style="display:flex;gap:16px;margin-top:20px;">'
        f'{col("Advantages", pros, "#1a7f4b", 0)}'
        f'{col("Trade-offs", cons, "#b23b3b", len(pros))}</div>'
    )


def _timeline(data: Dict[str, Any], theme) -> Optional[str]:
    events = data.get("events") or []
    if len(events) < 3:
        return None
    n = len(events[:8])
    dots = ""
    for i, e in enumerate(events[:8]):
        date = _esc(str(e.get("date", "")))
        title = _esc(str(e.get("title", "")))
        dots += (
            f'<div data-el="el.{i}" data-build="{i}" '
            f'style="flex:1;position:relative;padding:0 6px;text-align:center;">'
            f'<div style="width:14px;height:14px;border-radius:50%;background:{theme.accent_hex};'
            f'border:3px solid {theme.primary_hex};margin:0 auto 8px;"></div>'
            f'<div style="font-weight:700;color:{theme.primary_hex};font-size:0.8rem;">{date}</div>'
            f'<div style="font-size:0.78rem;color:{theme.text_hex};line-height:1.3;">{title}</div></div>'
        )
    return (
        f'<div style="margin-top:26px;">'
        f'<div style="position:relative;height:3px;background:{theme.primary_hex}44;margin:0 6px 12px;"></div>'
        f'<div style="display:flex;">{dots}</div></div>'
    )


def _stages(data: Dict[str, Any], theme, *, cyclic: bool) -> Optional[str]:
    stages = data.get("stages") or data.get("steps") or []
    if len(stages) < 3:
        return None
    n = len(stages[:8])
    arrow = "↻" if cyclic else "→"
    chips = []
    for i, s in enumerate(stages[:8]):
        chips.append(
            _chip(str(s), i, theme.card_bg_hex, theme.text_hex, theme.primary_hex)
        )
    joined = f'<span style="color:{theme.primary_hex};font-size:1.4rem;align-self:center;">{arrow}</span>'.join(chips)
    return f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:22px;">{joined}</div>'


def _pyramid(data: Dict[str, Any], theme) -> Optional[str]:
    levels = data.get("levels") or []
    if len(levels) < 3:
        return None
    rows = ""
    total = len(levels[:5])
    for i, lv in enumerate(levels[:5]):
        # apex first visually; base widest
        width = 40 + (i / max(1, total - 1)) * 55
        rows = (
            f'<div data-el="el.{total - 1 - i}" data-build="{total - 1 - i}" '
            f'style="width:{width:.0f}%;margin:4px auto;background:{theme.primary_hex};'
            f'color:{_on(theme)};border-radius:6px;padding:10px 14px;text-align:center;'
            f'font-size:0.85rem;opacity:{0.55 + i * 0.12:.2f};">{_esc(str(lv))}</div>'
        ) + rows
    return f'<div style="margin-top:22px;">{rows}</div>'


def _definition(data: Dict[str, Any], theme) -> Optional[str]:
    term = _esc(str(data.get("term", "")))
    body = _esc(str(data.get("definition", "")))
    if not body:
        return None
    notes = data.get("notes") or []
    extra = "".join(
        f'<li data-el="el.{j + 1}" data-build="{j + 1}" style="margin-bottom:6px;">{_esc(str(x))}</li>'
        for j, x in enumerate(notes[:3])
    )
    extra_html = f'<ul style="margin-top:12px;padding-left:18px;font-size:0.9rem;">{extra}</ul>' if extra else ""
    return (
        f'<div data-el="el.0" data-build="0" style="margin-top:22px;background:{theme.card_bg_hex};'
        f'border-left:6px solid {theme.accent_hex};border-radius:8px;padding:18px 20px;">'
        f'<div style="font-weight:800;color:{theme.primary_hex};font-size:1.1rem;">{term}</div>'
        f'<div style="font-size:1rem;line-height:1.5;color:{theme.text_hex};margin-top:6px;">{body}</div>'
        f'{extra_html}</div>'
    )


def _worked_example(data: Dict[str, Any], theme) -> Optional[str]:
    """
    A problem solved one line at a time. Every line carries ``data-build`` so
    present mode reveals them one click apart — and because they are ordinary
    (not replaced) elements, each solved line **stays on screen** as the
    derivation grows. Optional per-line reason in a right column.
    """
    rows = data.get("rows") or [{"step": s, "reason": ""} for s in (data.get("steps") or [])]
    rows = [r for r in rows if str(r.get("step", "")).strip()][:14]
    if len(rows) < 2:
        return None
    problem = _esc(str(data.get("problem", "")))
    has_reasons = any(str(r.get("reason", "")).strip() for r in rows)
    head = (
        f'<div style="font-weight:700;color:{theme.primary_hex};margin-bottom:10px;'
        f'font-size:0.95rem;">{problem}</div>' if problem else ""
    )
    lines = ""
    for i, r in enumerate(rows):
        step = _esc(str(r.get("step", "")))
        reason = _esc(str(r.get("reason", "")))
        reason_html = (
            f'<div style="flex:0 0 38%;color:{theme.subtext_hex};font-size:0.82rem;'
            f'padding-left:12px;border-left:2px dashed {theme.primary_hex}44;">{reason}</div>'
            if has_reasons else ""
        )
        lines += (
            f'<div data-el="el.{i}" data-build="{i}" '
            f'style="display:flex;align-items:baseline;gap:12px;padding:7px 0;'
            f'border-bottom:1px solid {theme.primary_hex}14;">'
            f'<span style="flex:0 0 22px;color:{theme.primary_hex};font-weight:700;'
            f'font-size:0.8rem;">{i + 1}</span>'
            f'<div style="flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;'
            f'font-size:1.05rem;color:{theme.text_hex};line-height:1.5;">{step}</div>'
            f'{reason_html}</div>'
        )
    return (
        f'<div style="margin-top:18px;background:{theme.card_bg_hex};border:1px solid '
        f'{theme.primary_hex}33;border-radius:10px;padding:16px 18px;max-width:780px;">'
        f'{head}{lines}</div>'
    )


def _quote(data: Dict[str, Any], theme) -> Optional[str]:
    text = _esc(str(data.get("text", "")))
    if not text:
        return None
    who = _esc(str(data.get("attribution", "")))
    who_html = f'<div style="margin-top:12px;font-size:0.9rem;color:{theme.subtext_hex};">— {who}</div>' if who else ""
    return (
        f'<div data-el="el.0" data-build="0" style="margin-top:30px;text-align:center;">'
        f'<div style="font-size:1.6rem;line-height:1.4;font-style:italic;color:{theme.text_hex};'
        f'max-width:80%;margin:0 auto;">“{text}”</div>{who_html}</div>'
    )


def _venn(data: Dict[str, Any], theme) -> Optional[str]:
    items = data.get("items") or []
    if len(items) < 2:
        return None
    lis = "".join(
        f'<li data-el="el.{j}" data-build="{j}" style="margin-bottom:8px;">{_esc(str(x))}</li>'
        for j, x in enumerate(items[:8])
    )
    return (
        f'<div style="display:flex;gap:20px;align-items:center;margin-top:22px;">'
        f'<svg viewBox="0 0 120 80" style="width:180px;flex-shrink:0;">'
        f'<circle cx="46" cy="40" r="34" fill="{theme.primary_hex}" fill-opacity="0.25" stroke="{theme.primary_hex}"/>'
        f'<circle cx="74" cy="40" r="34" fill="{theme.accent_hex}" fill-opacity="0.25" stroke="{theme.accent_hex}"/>'
        f'</svg>'
        f'<ul style="margin:0;padding-left:18px;font-size:0.9rem;line-height:1.4;">{lis}</ul></div>'
    )


def _num(v) -> Optional[float]:
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v)))
    except (ValueError, TypeError):
        return None


def _series(data: Dict[str, Any]) -> list:
    """Normalise chart data to [(label, value), ...]."""
    pts = data.get("points") or data.get("series") or data.get("items") or []
    out = []
    for p in pts:
        if isinstance(p, dict):
            lbl = str(p.get("label") or p.get("name") or p.get("x") or "")
            val = _num(p.get("value") if p.get("value") is not None else p.get("y"))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            lbl, val = str(p[0]), _num(p[1])
        else:
            lbl, val = str(p), None
        if lbl and val is not None:
            out.append((lbl, val))
    return out[:8]


def _bar_chart(data: Dict[str, Any], theme) -> Optional[str]:
    pts = _series(data)
    if len(pts) < 2:
        return None
    mx = max(v for _, v in pts) or 1
    rows = ""
    for i, (lbl, val) in enumerate(pts):
        w = max(2.0, val / mx * 100)
        rows += (
            f'<div data-el="el.{i}" data-build="{i}" style="display:flex;align-items:center;'
            f'gap:10px;margin:6px 0;font-size:0.85rem;">'
            f'<span style="flex:0 0 32%;text-align:right;color:{theme.text_hex};">{_esc(lbl)}</span>'
            f'<span style="flex:1;background:{theme.card_bg_hex};border-radius:4px;">'
            f'<span style="display:block;height:20px;width:{w:.0f}%;background:{theme.primary_hex};'
            f'border-radius:4px;"></span></span>'
            f'<span style="flex:0 0 auto;color:{theme.subtext_hex};font-variant-numeric:tabular-nums;">'
            f'{_esc(str(val).rstrip("0").rstrip(".") if "." in str(val) else str(val))}</span></div>'
        )
    return f'<div style="margin-top:20px;max-width:720px;">{rows}</div>'


def _line_chart(data: Dict[str, Any], theme) -> Optional[str]:
    pts = _series(data)
    if len(pts) < 3:
        return None
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    W, H, PAD = 320, 160, 24
    xs = [PAD + (W - 2 * PAD) * i / (len(pts) - 1) for i in range(len(pts))]
    ys = [H - PAD - (H - 2 * PAD) * (v - lo) / span for v in vals]
    path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
    dots = "".join(
        f'<circle data-el="el.{i}" data-build="{i}" cx="{x:.1f}" cy="{y:.1f}" r="3" '
        f'fill="{theme.accent_hex}"/>' for i, (x, y) in enumerate(zip(xs, ys))
    )
    labels = "".join(
        f'<text x="{x:.1f}" y="{H - 6}" font-size="8" fill="{theme.subtext_hex}" '
        f'text-anchor="middle">{_esc(pts[i][0][:8])}</text>' for i, x in enumerate(xs)
    )
    return (
        f'<div style="margin-top:20px;display:flex;justify-content:center;">'
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;max-width:560px;">'
        f'<line x1="{PAD}" y1="{H-PAD}" x2="{W-6}" y2="{H-PAD}" stroke="{theme.primary_hex}55"/>'
        f'<line x1="{PAD}" y1="6" x2="{PAD}" y2="{H-PAD}" stroke="{theme.primary_hex}55"/>'
        f'<path d="{path}" fill="none" stroke="{theme.primary_hex}" stroke-width="2"/>'
        f'{dots}{labels}</svg></div>'
    )


def _pie_chart(data: Dict[str, Any], theme) -> Optional[str]:
    pts = _series(data)
    if len(pts) < 2:
        return None
    total = sum(v for _, v in pts) or 1
    palette = [theme.primary_hex, theme.accent_hex, "#3aa07b", "#c9772f", "#6b6bd6", "#b8506b", "#4a90c4"]
    cx = cy = 60
    r = 52
    ang = -90.0
    wedges = ""
    legend = ""
    for i, (lbl, val) in enumerate(pts):
        frac = val / total
        a2 = ang + frac * 360
        large = 1 if frac > 0.5 else 0
        x1 = cx + r * _cos(ang)
        y1 = cy + r * _sin(ang)
        x2 = cx + r * _cos(a2)
        y2 = cy + r * _sin(a2)
        col = palette[i % len(palette)]
        wedges += (
            f'<path data-el="el.{i}" data-build="{i}" d="M{cx} {cy} L{x1:.1f} {y1:.1f} '
            f'A{r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{col}"/>'
        )
        legend += (
            f'<div data-el="el.{i}" data-build="{i}" style="display:flex;align-items:center;'
            f'gap:6px;font-size:0.82rem;margin:3px 0;">'
            f'<span style="width:11px;height:11px;background:{col};border-radius:2px;"></span>'
            f'{_esc(lbl)} — {frac * 100:.0f}%</div>'
        )
        ang = a2
    return (
        f'<div style="margin-top:20px;display:flex;gap:24px;align-items:center;flex-wrap:wrap;">'
        f'<svg viewBox="0 0 120 120" style="width:180px;flex-shrink:0;">{wedges}</svg>'
        f'<div>{legend}</div></div>'
    )


def _matrix_2x2(data: Dict[str, Any], theme) -> Optional[str]:
    quads = data.get("quadrants") or data.get("cells") or []
    if len(quads) < 3:
        return None
    x_axis = data.get("x_axis") or ["Low", "High"]
    y_axis = data.get("y_axis") or ["Low", "High"]
    labels = []
    for q in quads[:4]:
        if isinstance(q, dict):
            labels.append((str(q.get("title", "")), [str(i) for i in (q.get("items") or [])][:3]))
        else:
            labels.append((str(q), []))
    while len(labels) < 4:
        labels.append(("", []))
    cell = lambda t, items, i: (
        f'<div data-el="el.{i}" data-build="{i}" style="border:1px solid {theme.primary_hex}33;'
        f'background:{theme.card_bg_hex};border-radius:8px;padding:12px;min-height:96px;">'
        f'<div style="font-weight:700;color:{theme.primary_hex};font-size:0.85rem;">{_esc(t)}</div>'
        + "".join(f'<div style="font-size:0.78rem;color:{theme.text_hex};margin-top:4px;">• {_esc(x)}</div>' for x in items)
        + "</div>"
    )
    return (
        f'<div style="margin-top:18px;display:grid;grid-template-columns:auto 1fr 1fr;'
        f'grid-template-rows:auto 1fr 1fr;gap:8px;max-width:640px;align-items:center;">'
        f'<div></div>'
        f'<div style="text-align:center;font-size:0.75rem;color:{theme.subtext_hex};">{_esc(str(x_axis[0]))}</div>'
        f'<div style="text-align:center;font-size:0.75rem;color:{theme.subtext_hex};">{_esc(str(x_axis[-1]))}</div>'
        f'<div style="writing-mode:vertical-rl;transform:rotate(180deg);text-align:center;'
        f'font-size:0.75rem;color:{theme.subtext_hex};">{_esc(str(y_axis[-1]))}</div>'
        f'{cell(labels[0][0], labels[0][1], 0)}{cell(labels[1][0], labels[1][1], 1)}'
        f'<div style="writing-mode:vertical-rl;transform:rotate(180deg);text-align:center;'
        f'font-size:0.75rem;color:{theme.subtext_hex};">{_esc(str(y_axis[0]))}</div>'
        f'{cell(labels[2][0], labels[2][1], 2)}{cell(labels[3][0], labels[3][1], 3)}</div>'
    )


def _compare_table(data: Dict[str, Any], theme) -> Optional[str]:
    headers = data.get("headers") or []
    rows = data.get("rows") or []
    if len(headers) < 2 or len(rows) < 2:
        return None
    on = _on(theme)
    th = "".join(
        f'<th style="background:{theme.primary_hex};color:{on};padding:8px 12px;'
        f'text-align:left;font-size:0.82rem;">{_esc(str(h))}</th>' for h in headers
    )
    body = ""
    for i, r in enumerate(rows[:8]):
        cells = "".join(
            f'<td style="padding:8px 12px;border-bottom:1px solid {theme.primary_hex}22;'
            f'font-size:0.82rem;color:{theme.text_hex};">{_esc(str(c))}</td>'
            for c in (list(r) + [""] * len(headers))[:len(headers)]
        )
        body += f'<tr data-el="el.{i}" data-build="{i}">{cells}</tr>'
    return (
        f'<div style="margin-top:18px;overflow-x:auto;max-width:820px;">'
        f'<table style="width:100%;border-collapse:collapse;background:{theme.card_bg_hex};'
        f'border-radius:8px;overflow:hidden;">'
        f'<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def _mind_map(data: Dict[str, Any], theme) -> Optional[str]:
    center = str(data.get("center") or data.get("central") or "")
    branches = [str(b) for b in (data.get("branches") or data.get("items") or []) if str(b).strip()][:8]
    if not center or len(branches) < 2:
        return None
    on = _on(theme)
    chips = "".join(
        f'<div data-el="el.{i}" data-build="{i}" style="background:{theme.card_bg_hex};'
        f'border:1px solid {theme.primary_hex}44;border-radius:16px;padding:8px 14px;'
        f'font-size:0.85rem;color:{theme.text_hex};">{_esc(b)}</div>'
        for i, b in enumerate(branches)
    )
    return (
        f'<div style="margin-top:22px;display:flex;flex-direction:column;align-items:center;gap:16px;">'
        f'<div style="background:{theme.primary_hex};color:{on};font-weight:800;'
        f'border-radius:50%;padding:18px 22px;text-align:center;max-width:220px;">{_esc(center)}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;justify-content:center;max-width:720px;">'
        f'{chips}</div></div>'
    )


def _cos(deg):
    import math
    return math.cos(math.radians(deg))


def _sin(deg):
    import math
    return math.sin(math.radians(deg))


def _on(theme) -> str:
    try:
        from learnova.rendering.theme_engine import readable_text_hex

        return readable_text_hex(theme.primary_hex)
    except Exception:
        return "#ffffff"


# ─────────────────────────────────────────────────────────────────────────────
# STEM renderers — consume the structured `data` the master prompt produces.
# A plot canvas is 320x200 user units; data coords are mapped into it.
# ─────────────────────────────────────────────────────────────────────────────

_PW, _PH = 320, 200
_PAD = 28


def _axes(theme, x_label="x", y_label="y") -> str:
    c = theme.primary_hex
    return (
        f'<line x1="{_PAD}" y1="{_PH-_PAD}" x2="{_PW-6}" y2="{_PH-_PAD}" stroke="{c}" stroke-width="1.5"/>'
        f'<line x1="{_PAD}" y1="6" x2="{_PAD}" y2="{_PH-_PAD}" stroke="{c}" stroke-width="1.5"/>'
        f'<text x="{_PW-4}" y="{_PH-_PAD+14}" font-size="9" fill="{theme.subtext_hex}" text-anchor="end">{_esc(x_label)}</text>'
        f'<text x="{_PAD-4}" y="12" font-size="9" fill="{theme.subtext_hex}" text-anchor="end">{_esc(y_label)}</text>'
    )


def _map_pts(pts, xr, yr):
    (x0, x1), (y0, y1) = xr, yr
    sx = (_PW - _PAD - 8) / (x1 - x0 or 1)
    sy = (_PH - _PAD - 8) / (y1 - y0 or 1)
    return [((px - x0) * sx + _PAD, (_PH - _PAD) - (py - y0) * sy) for px, py in pts]


def _eval_expr(expr: str, x: float) -> Optional[float]:
    """Evaluate a very restricted arithmetic expression in x. Returns None if unsafe."""
    e = expr.lower().replace("^", "**").replace(" ", "")
    e = re.sub(r"(\d)(x)", r"\1*\2", e)
    e = re.sub(r"(x)(\d)", r"\1*\2", e)
    if not re.fullmatch(r"[0-9x.+\-*/()]*", e):
        return None
    try:
        return float(eval(e, {"__builtins__": {}}, {"x": x}))  # noqa: S307 - sanitised above
    except Exception:
        return None


def _svg(inner: str, wrap_style: str = "") -> str:
    return (
        f'<div style="margin-top:18px;display:flex;justify-content:center;{wrap_style}">'
        f'<svg viewBox="0 0 {_PW} {_PH}" style="width:100%;max-width:560px;">{inner}</svg></div>'
    )


def _function_plot(data: Dict[str, Any], theme) -> Optional[str]:
    expr = str(data.get("expr", "")).strip()
    dom = data.get("domain") or [-5, 5]
    try:
        a, b = float(dom[0]), float(dom[1])
    except Exception:
        a, b = -5.0, 5.0
    xs = [a + (b - a) * i / 60 for i in range(61)]
    ys = [_eval_expr(expr, x) for x in xs]
    pairs = [(x, y) for x, y in zip(xs, ys) if y is not None and abs(y) < 1e6]
    if len(pairs) < 5:
        return None
    yv = [p[1] for p in pairs]
    mapped = _map_pts(pairs, (a, b), (min(yv), max(yv)))
    poly = " ".join(f"{px:.1f},{py:.1f}" for px, py in mapped)
    dots = ""
    for i, kp in enumerate((data.get("key_points") or [])[:4]):
        try:
            kx, ky = float(kp["x"]), float(kp["y"])
        except Exception:
            continue
        mx, my = _map_pts([(kx, ky)], (a, b), (min(yv), max(yv)))[0]
        dots += (f'<circle data-el="el.{i}" cx="{mx:.1f}" cy="{my:.1f}" r="3.5" fill="{theme.accent_hex}"/>'
                 f'<text x="{mx+5:.1f}" y="{my-4:.1f}" font-size="8" fill="{theme.text_hex}">{_esc(str(kp.get("label","")))}</text>')
    return _svg(
        _axes(theme, data.get("x_axis", "x"), data.get("y_axis", "y"))
        + f'<polyline points="{poly}" fill="none" stroke="{theme.primary_hex}" stroke-width="2"/>'
        + dots
        + f'<text x="{_PW-8}" y="16" font-size="9" fill="{theme.primary_hex}" text-anchor="end">y = {_esc(expr)}</text>'
    )


def _ml_regression(data: Dict[str, Any], theme) -> Optional[str]:
    pts = []
    for p in data.get("points") or []:
        try:
            pts.append((float(p["x"]), float(p["y"])))
        except Exception:
            pass
    if len(pts) < 3:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    xr, yr = (min(xs), max(xs)), (min(ys), max(ys))
    mp = _map_pts(pts, xr, yr)
    dots = "".join(
        f'<circle data-el="el.{i}" cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{theme.primary_hex}"/>'
        for i, (x, y) in enumerate(mp)
    )
    chosen = data.get("chosen") or {}
    line = ""
    resid = ""
    try:
        m, c = float(chosen["slope"]), float(chosen["intercept"])
        lp = _map_pts([(xr[0], m * xr[0] + c), (xr[1], m * xr[1] + c)], xr, yr)
        line = f'<line x1="{lp[0][0]:.1f}" y1="{lp[0][1]:.1f}" x2="{lp[1][0]:.1f}" y2="{lp[1][1]:.1f}" stroke="{theme.accent_hex}" stroke-width="2"/>'
        if data.get("show_residuals"):
            for (dx, dy), (px, py) in zip(pts, mp):
                fy = _map_pts([(dx, m * dx + c)], xr, yr)[0][1]
                resid += f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{fy:.1f}" stroke="{theme.subtext_hex}" stroke-width="1" stroke-dasharray="2 2"/>'
    except Exception:
        pass
    eq = _esc(str(data.get("equation", "")))
    eq_txt = f'<text x="{_PW-8}" y="16" font-size="9" fill="{theme.primary_hex}" text-anchor="end">{eq}</text>' if eq else ""
    return _svg(_axes(theme) + resid + line + dots + eq_txt)


def _algorithm_trace(data: Dict[str, Any], theme) -> Optional[str]:
    arr = data.get("initial") or data.get("array") or []
    try:
        vals = [float(v) for v in arr][:16]
    except Exception:
        return None
    if len(vals) < 3:
        return None
    mx = max(vals) or 1
    n = len(vals)
    bw = (_PW - _PAD - 8) / n
    bars = ""
    for i, v in enumerate(vals):
        h = (v / mx) * (_PH - _PAD - 10)
        x = _PAD + i * bw + 2
        bars += (f'<rect data-el="el.{i}" x="{x:.1f}" y="{_PH-_PAD-h:.1f}" width="{bw-4:.1f}" '
                 f'height="{h:.1f}" fill="{theme.primary_hex}" rx="2"/>'
                 f'<text x="{x+(bw-4)/2:.1f}" y="{_PH-_PAD+12}" font-size="8" fill="{theme.subtext_hex}" text-anchor="middle">{v:g}</text>')
    steps = data.get("steps") or []
    ops = " · ".join(
        f'{s.get("op","")}({",".join(str(a) for a in (s.get("args") or []))})'
        for s in steps[:6]
    )
    cap = f'<text x="{_PAD}" y="12" font-size="8.5" fill="{theme.text_hex}">{_esc(data.get("kind","trace"))}: {_esc(ops)}</text>' if ops else ""
    return _svg(cap + bars)


def _data_structure(data: Dict[str, Any], theme) -> Optional[str]:
    cells = data.get("cells") or []
    vals = [str(c.get("value", c)) if isinstance(c, dict) else str(c) for c in cells][:12]
    if len(vals) < 2:
        return None
    kind = str(data.get("kind", "array"))
    cw = min(48, (_PW - _PAD * 2) / len(vals))
    boxes = ""
    for i, v in enumerate(vals):
        x = _PAD + i * (cw + 4)
        arrow = (f'<line x1="{x+cw:.1f}" y1="{_PH/2:.1f}" x2="{x+cw+4:.1f}" y2="{_PH/2:.1f}" '
                 f'stroke="{theme.primary_hex}" stroke-width="1.5" marker-end="url(#lvarr)"/>') if kind == "linked_list" and i < len(vals) - 1 else ""
        boxes += (f'<rect data-el="el.{i}" x="{x:.1f}" y="{_PH/2-16:.1f}" width="{cw:.1f}" height="32" '
                  f'fill="{theme.card_bg_hex}" stroke="{theme.primary_hex}" stroke-width="1.5" rx="3"/>'
                  f'<text x="{x+cw/2:.1f}" y="{_PH/2+4:.1f}" font-size="10" fill="{theme.text_hex}" text-anchor="middle">{_esc(v)}</text>'
                  f'<text x="{x+cw/2:.1f}" y="{_PH/2-22:.1f}" font-size="7" fill="{theme.subtext_hex}" text-anchor="middle">{i}</text>'
                  + arrow)
    defs = f'<defs><marker id="lvarr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="{theme.primary_hex}"/></marker></defs>'
    return _svg(defs + boxes)


def _geometry(data: Dict[str, Any], theme) -> Optional[str]:
    verts = data.get("vertices") or []
    pts = []
    for v in verts:
        try:
            pts.append((float(v[0]), float(v[1])))
        except Exception:
            pass
    if len(pts) < 3:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    mp = _map_pts(pts, (min(xs), max(xs)), (min(ys), max(ys)))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in mp)
    labels = ""
    for i, lb in enumerate((data.get("labels") or [])[:8]):
        if i < len(mp):
            labels += f'<text data-el="el.{i}" x="{mp[i][0]+4:.1f}" y="{mp[i][1]-4:.1f}" font-size="9" fill="{theme.text_hex}">{_esc(str(lb.get("text", lb)))}</text>'
    return _svg(
        f'<polygon points="{poly}" fill="{theme.primary_hex}" fill-opacity="0.12" stroke="{theme.primary_hex}" stroke-width="2"/>'
        + "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{theme.accent_hex}"/>' for x, y in mp)
        + labels
    )


def _circuit(data: Dict[str, Any], theme) -> Optional[str]:
    comps = data.get("components") or data.get("blocks") or []
    if len(comps) < 2:
        return None
    n = len(comps[:6])
    bw = (_PW - _PAD * 2) / n
    boxes = ""
    for i, c in enumerate(comps[:6]):
        label = str(c.get("id") or c.get("label") or c.get("type") or "?")
        val = str(c.get("value", ""))
        x = _PAD + i * bw
        boxes += (f'<rect data-el="el.{i}" x="{x+6:.1f}" y="{_PH/2-18:.1f}" width="{bw-12:.1f}" height="36" '
                  f'fill="{theme.card_bg_hex}" stroke="{theme.primary_hex}" stroke-width="1.5" rx="3"/>'
                  f'<text x="{x+bw/2:.1f}" y="{_PH/2:.1f}" font-size="9" fill="{theme.text_hex}" text-anchor="middle">{_esc(label)}</text>'
                  f'<text x="{x+bw/2:.1f}" y="{_PH/2+11:.1f}" font-size="7" fill="{theme.subtext_hex}" text-anchor="middle">{_esc(val)}</text>')
        if i < n - 1:
            boxes += f'<line x1="{x+bw-6:.1f}" y1="{_PH/2:.1f}" x2="{x+bw+6:.1f}" y2="{_PH/2:.1f}" stroke="{theme.primary_hex}" stroke-width="1.5"/>'
    return _svg(boxes)


def _chem(data: Dict[str, Any], theme) -> Optional[str]:
    kind = str(data.get("kind", ""))
    if kind == "energy_profile" or data.get("points"):
        pts = []
        for p in data.get("points") or []:
            try:
                pts.append((float(p.get("x", len(pts))), float(p["energy"] if "energy" in p else p["y"])))
            except Exception:
                pass
        if len(pts) < 2:
            return None
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        mp = _map_pts(pts, (min(xs), max(xs)), (min(ys), max(ys)))
        path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in mp)
        labels = "".join(
            f'<text x="{mp[i][0]:.1f}" y="{mp[i][1]-5:.1f}" font-size="8" fill="{theme.text_hex}" text-anchor="middle">{_esc(str(p.get("label","")))}</text>'
            for i, p in enumerate(data.get("points") or []) if i < len(mp)
        )
        return _svg(_axes(theme, "reaction coordinate", "energy")
                    + f'<path d="{path}" fill="none" stroke="{theme.primary_hex}" stroke-width="2"/>' + labels)
    # molecule_2d
    atoms = data.get("atoms") or []
    ap = []
    for a in atoms:
        try:
            ap.append((float(a["xy"][0]), float(a["xy"][1]), str(a.get("el", "C"))))
        except Exception:
            pass
    if len(ap) < 2:
        return None
    xs, ys = [p[0] for p in ap], [p[1] for p in ap]
    mp = _map_pts([(x, y) for x, y, _ in ap], (min(xs), max(xs)), (min(ys), max(ys)))
    bonds = ""
    for bd in data.get("bonds") or []:
        try:
            i, j = int(bd["a"]), int(bd["b"])
            bonds += f'<line x1="{mp[i][0]:.1f}" y1="{mp[i][1]:.1f}" x2="{mp[j][0]:.1f}" y2="{mp[j][1]:.1f}" stroke="{theme.primary_hex}" stroke-width="1.5"/>'
        except Exception:
            pass
    nodes = "".join(
        f'<circle cx="{mp[i][0]:.1f}" cy="{mp[i][1]:.1f}" r="9" fill="{theme.card_bg_hex}" stroke="{theme.primary_hex}"/>'
        f'<text x="{mp[i][0]:.1f}" y="{mp[i][1]+3:.1f}" font-size="9" fill="{theme.text_hex}" text-anchor="middle">{_esc(el)}</text>'
        for i, (_, _, el) in enumerate(ap)
    )
    return _svg(bonds + nodes)


_BUILDERS = {
    "LIST_STRUCTURED": _cards,
    "COMPARE_VISUAL": _pros_cons,
    "COMPARE_TABLE": _compare_table,
    "MATRIX_GRID": _matrix_2x2,
    "MIND_MAP": _mind_map,
    "CHART_CATEGORICAL": _bar_chart,
    "CHART_RANKING": _bar_chart,
    "CHART_TREND": _line_chart,
    "CHART_PART_TO_WHOLE": _pie_chart,
    "WORKED_EXAMPLE": _worked_example,
    "TIMELINE": _timeline,
    "HIERARCHY_NEST": _pyramid,
    "DEFINITION": _definition,
    "QUOTE": _quote,
    "SET_DIAGRAM": _venn,
    "FUNCTION_PLOT": _function_plot,
    "CALCULUS_VIZ": _function_plot,
    "ML_VIZ": _ml_regression,
    "ALGORITHM_TRACE": _algorithm_trace,
    "DATA_STRUCTURE": _data_structure,
    "GEOMETRY": _geometry,
    "LINEAR_ALGEBRA": _geometry,
    "CIRCUIT": _circuit,
    "CHEM_DIAGRAM": _chem,
}


def render_family_block(family: str, data: Dict[str, Any], theme) -> Optional[str]:
    """Return an HTML block for ``family`` given its structured data, or None."""
    if not data:
        return None
    if family in {"PROCESS_LINEAR"}:
        return _stages(data, theme, cyclic=False)
    if family in {"PROCESS_CYCLIC"}:
        return _stages(data, theme, cyclic=True)
    fn = _BUILDERS.get(family)
    if not fn:
        return None
    try:
        return fn(data, theme)
    except Exception:
        return None


__all__ = ["render_family_block"]
