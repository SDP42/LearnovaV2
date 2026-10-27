"""
Scene illustrator: a picture that is *about* the slide, drawn offline as vector art.

The older illustrator put one icon in a circle on every slide. This one composes small scenes — a parse tree for a
syntax lecture, a chat of tagged words for a language slide, a window of code, bar charts that use the slide's own
numbers, a lab bench, a cell, a globe, columns for history — chosen from the slide's words, in the deck's palette.
Everything is solid-fill SVG (renders identically in PowerPoint, the browser and MuPDF) and returned both as SVG,
which the web deck animates, and as PNG for PowerPoint.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from typing import Callable, Dict, List, Optional, Tuple

from learnova.visuals.icons import icon_group, has_icon, pick_icons, svg_to_png

# ── colour helpers ────────────────────────────────────────────────────────────


def _rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(hex_: str, t: float, to: str = "#ffffff") -> str:
    a, b = _rgb(hex_), _rgb(to)
    return "#{:02x}{:02x}{:02x}".format(*(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))


class Pal:
    def __init__(self, primary: str, accent: str):
        self.p, self.a = primary, accent
        self.p_soft, self.p_mid, self.p_dark = mix(primary, 0.9), mix(primary, 0.7), mix(primary, 0.35, "#000000")
        self.a_soft, self.a_mid = mix(accent, 0.75), mix(accent, 0.45)
        self.ink, self.paper = "#1f2937", "#ffffff"
        self.grey = "#d9dee7"


# ── svg primitives ────────────────────────────────────────────────────────────
def rect(x, y, w, h, r=0, fill="#fff", stroke=None, sw=2, op=1.0, extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    o = f' opacity="{op}"' if op < 1 else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r:.1f}" fill="{fill}"{s}{o}{extra}/>'


def circ(cx, cy, r, fill="#fff", stroke=None, sw=2, op=1.0, extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    o = f' opacity="{op}"' if op < 1 else ""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{s}{o}{extra}/>'


def line(x1, y1, x2, y2, stroke, sw=3, cap="round", dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"{d}/>'


def path(d, fill="none", stroke=None, sw=3, op=1.0):
    s = f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"' if stroke else ""
    o = f' opacity="{op}"' if op < 1 else ""
    return f'<path d="{d}" fill="{fill}"{s}{o}/>'


def text(x, y, t, size, fill, weight=700, anchor="middle"):
    t = t.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="Helvetica, Arial, sans-serif" font-size="{size:.0f}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}">{t}</text>')


def icon(name: str, x, y, size, color, sw=2.0) -> str:
    return icon_group(name if has_icon(name) else "lightbulb", x, y, size, color, sw)


def float_g(inner: str, i: int = 0) -> str:
    """A group the web deck lets drift gently (ignored by PowerPoint's PNG)."""
    return f'<g class="lvf lvf{i % 3}">{inner}</g>'


def badge(cx, cy, r, name, P: Pal, fill=None, color=None) -> str:
    return circ(cx, cy + r * 0.07, r, mix(P.p, 0.55), op=0.28) + circ(cx, cy, r, fill or "#ffffff", P.p_mid, 3) + icon(name, cx - r * 0.55, cy - r * 0.55, r * 1.1, color or P.p, 2.1)


def frame(W, H, P: Pal, r: random.Random) -> str:
    """Rounded tinted card, soft blobs and a dotted grid — the shared backdrop."""
    u = min(W, H)
    out = [rect(0, 0, W, H, u * 0.06, P.p_soft)]
    out.append(circ(W * 0.9, H * 0.1, u * 0.3, P.a_mid, op=0.5))
    out.append(circ(W * 0.05, H * 0.96, u * 0.36, P.p_mid, op=0.6))
    out.append(circ(W * 0.86, H * 0.9, u * 0.1, P.a_mid, op=0.7))
    for i in range(6):
        for j in range(4):
            out.append(circ(u * 0.07 + i * u * 0.036, u * 0.07 + j * u * 0.036, u * 0.005, mix(P.p, 0.5), op=0.7))
    return "".join(out)


def sparkles(W, H, P: Pal, r: random.Random, avoid: Tuple[float, float, float], n=6) -> str:
    u, out = min(W, H), []
    for _ in range(n):
        x, y, s = r.uniform(0.08, 0.92) * W, r.uniform(0.06, 0.94) * H, u * r.uniform(0.012, 0.024)
        if math.hypot(x - avoid[0], y - avoid[1]) < avoid[2]:
            continue
        out.append(path(f"M{x - s:.1f} {y:.1f}H{x + s:.1f}M{x:.1f} {y - s:.1f}V{y + s:.1f}", stroke=mix(r.choice([P.p, P.a]), 0.25), sw=u * 0.006))
    return "".join(out)


# ── scenes ────────────────────────────────────────────────────────────────────
Scene = Callable[[int, int, Pal, random.Random, List[str], Dict], str]


def scene_speech(W, H, P, r, icons, ctx) -> str:
    u, cx, cy = min(W, H), W / 2, H * 0.48
    words = ctx.get("words") or ["Words", "carry", "meaning"]
    tags = ["NN", "VB", "JJ", "DT", "RB", "IN"]
    out = [rect(W * 0.12, cy - u * 0.34, W * 0.62, u * 0.3, u * 0.05, "#ffffff", P.p_mid, 3)]
    out.append(path(f"M{W * 0.22:.1f} {cy - u * 0.04:.1f} l{u * 0.05:.1f} {u * 0.07:.1f} l{u * 0.05:.1f} {-u * 0.07:.1f}", fill="#ffffff", stroke=P.p_mid, sw=3))
    x = W * 0.16
    for i, w in enumerate(words[:3]):
        wd = max(u * 0.2, len(w) * u * 0.034 + u * 0.06)
        if x + wd > W * 0.7:
            break
        out.append(rect(x, cy - u * 0.27, wd, u * 0.1, u * 0.03, [P.p_soft, P.a_soft, P.p_mid][i % 3]))
        out.append(text(x + wd / 2, cy - u * 0.2, w[:9], u * 0.045, P.p_dark))
        out.append(rect(x + wd / 2 - u * 0.05, cy - u * 0.14, u * 0.1, u * 0.05, u * 0.02, [P.p, P.a, P.p_dark][i % 3]))
        out.append(text(x + wd / 2, cy - u * 0.105, tags[(i + ctx["seed"]) % len(tags)], u * 0.032, "#ffffff" if i % 3 != 1 else P.ink))
        x += wd + u * 0.03
    out.append(rect(W * 0.3, cy + u * 0.06, W * 0.56, u * 0.24, u * 0.05, P.p, None))
    out.append(path(f"M{W * 0.78:.1f} {cy + u * 0.3:.1f} l{u * 0.05:.1f} {u * 0.07:.1f} l{-u * 0.05:.1f} {-u * 0.07:.1f}", fill=P.p))
    for k in range(3):
        out.append(line(W * 0.35, cy + u * (0.12 + k * 0.055), W * (0.8 - 0.1 * (k == 2)), cy + u * (0.12 + k * 0.055), "#ffffff", u * 0.016))
    out.append(float_g(badge(W * 0.82, cy - u * 0.36, u * 0.075, icons[0], P), 0))
    return "".join(out)


def scene_window(W, H, P, r, icons, ctx) -> str:
    u, x0, y0, w, h = min(W, H), W * 0.1, H * 0.2, W * 0.8, H * 0.58
    out = [rect(x0, y0, w, h, u * 0.04, "#ffffff", P.p_mid, 3), rect(x0, y0, w, u * 0.09, u * 0.04, P.p), rect(x0, y0 + u * 0.05, w, u * 0.04, 0, P.p)]
    for i, c in enumerate(["#ff6b6b", P.a, "#ffffff"]):
        out.append(circ(x0 + u * (0.05 + i * 0.045), y0 + u * 0.045, u * 0.012, c))
    ly = y0 + u * 0.15
    for i in range(6):
        indent = (i in (1, 2, 4)) * u * 0.05 + (i == 3) * u * 0.1
        wd = u * r.uniform(0.18, 0.42)
        out.append(rect(x0 + u * 0.05 + indent, ly, wd, u * 0.022, u * 0.011, [P.p, P.a, P.p_mid, P.p_dark][i % 4]))
        ly += u * 0.05
    out.append(text(x0 + w - u * 0.09, y0 + h - u * 0.07, "{ }", u * 0.07, P.p_mid))
    out.append(float_g(badge(W * 0.84, H * 0.2, u * 0.08, icons[0], P), 1))
    out.append(float_g(badge(W * 0.14, H * 0.82, u * 0.065, icons[1] if len(icons) > 1 else "cpu", P, fill=P.a_soft), 2))
    return "".join(out)


def scene_tree(W, H, P, r, icons, ctx) -> str:
    u = min(W, H)
    syn = ctx.get("syntax")
    nodes = {"S": (0.5, 0.2), "NP": (0.3, 0.42), "VP": (0.7, 0.42), "Det": (0.2, 0.66), "N": (0.4, 0.66), "V": (0.62, 0.66), "NP2": (0.82, 0.66)}
    labels = {"S": "S", "NP": "NP", "VP": "VP", "Det": "Det", "N": "N", "V": "V", "NP2": "NP"} if syn else {k: "" for k in nodes}
    edges = [("S", "NP"), ("S", "VP"), ("NP", "Det"), ("NP", "N"), ("VP", "V"), ("VP", "NP2")]
    out = []
    for a, b in edges:
        out.append(line(W * nodes[a][0], H * nodes[a][1] + u * 0.04, W * nodes[b][0], H * nodes[b][1] - u * 0.03, P.p_mid, u * 0.01))
    for k, (x, y) in nodes.items():
        leaf = k in ("Det", "N", "V", "NP2")
        fill = P.a if leaf else P.p
        out.append(circ(W * x, H * y, u * 0.065, fill, "#ffffff", 4))
        if labels[k]:
            out.append(text(W * x, H * y + u * 0.018, labels[k], u * 0.05, "#ffffff" if not leaf else P.ink))
    if not syn:
        for k, ic in zip(["S", "NP", "VP"], icons + ["lightbulb"] * 3):
            x, y = nodes[k]
            out.append(icon(ic, W * x - u * 0.03, H * y - u * 0.03, u * 0.06, "#ffffff", 2.4))
    for x, w in ((0.2, "the"), (0.4, "cat"), (0.62, "sat"), (0.82, "down")):
        if syn:
            out.append(text(W * x, H * 0.82, w, u * 0.042, P.p_dark, 600))
            out.append(line(W * x, H * 0.7 + u * 0.03, W * x, H * 0.78, P.grey, 2))
    return "".join(out)


def scene_chart(W, H, P, r, icons, ctx) -> str:
    u = min(W, H)
    vals = ctx.get("numbers") or [r.uniform(0.3, 1.0) for _ in range(5)]
    vals = vals[:6]
    mx = max(vals) or 1
    x0, y0, w, h = W * 0.14, H * 0.2, W * 0.72, H * 0.52
    out = [rect(x0 - u * 0.04, y0 - u * 0.04, w + u * 0.08, h + u * 0.1, u * 0.04, "#ffffff", P.p_mid, 3), line(x0, y0 + h, x0 + w, y0 + h, P.grey, 3)]
    n = len(vals)
    bw = w / (n * 1.6)
    pts = []
    for i, v in enumerate(vals):
        bh = h * 0.9 * v / mx
        bx = x0 + (i + 0.3) * w / n
        out.append(rect(bx, y0 + h - bh, bw, bh, u * 0.012, P.p if i % 2 == 0 else P.p_mid))
        pts.append((bx + bw / 2, y0 + h - bh - u * 0.03))
    out.append(path("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts), stroke=P.a, sw=u * 0.012))
    for x, y in pts:
        out.append(circ(x, y, u * 0.016, P.a, "#ffffff", 2))
    out.append(float_g(badge(W * 0.84, H * 0.17, u * 0.075, "trending-up" if has_icon("trending-up") else icons[0], P), 0))
    out.append(float_g(badge(W * 0.14, H * 0.84, u * 0.06, "coins" if has_icon("coins") else icons[-1], P, fill=P.a_soft), 2))
    return "".join(out)


def scene_flow(W, H, P, r, icons, ctx) -> str:
    u = min(W, H)
    n = 4 if W >= H * 0.9 else 3
    out = []
    ys = [H * (0.22 + 0.2 * i) for i in range(n)] if H > W else [H * 0.5] * n
    xs = [W * (0.22 + 0.19 * i) for i in range(n)] if H <= W else [W * (0.3 + 0.2 * (i % 2)) for i in range(n)]
    pts = list(zip(xs, ys))
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        out.append(line(x1, y1, x2, y2, P.p_mid, u * 0.012))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        out.append(circ(mx, my, u * 0.018, P.a, "#ffffff", 2))
    for i, (x, y) in enumerate(pts):
        out.append(float_g(badge(x, y, u * 0.085, (icons + ["workflow", "settings", "target", "rocket"])[i], P, fill=P.a_soft if i % 2 else "#ffffff"), i))
        out.append(text(x, y + u * 0.14, str(i + 1), u * 0.04, P.p_dark))
    return "".join(out)


def scene_lab(W, H, P, r, icons, ctx) -> str:
    u, cx = min(W, H), W / 2
    out = [path(f"M{cx - u * 0.07:.1f} {H * 0.22:.1f} H{cx + u * 0.07:.1f} V{H * 0.42:.1f} L{cx + u * 0.2:.1f} {H * 0.7:.1f} Q{cx + u * 0.22:.1f} {H * 0.76:.1f} {cx + u * 0.15:.1f} {H * 0.76:.1f} H{cx - u * 0.15:.1f} Q{cx - u * 0.22:.1f} {H * 0.76:.1f} {cx - u * 0.2:.1f} {H * 0.7:.1f} L{cx - u * 0.07:.1f} {H * 0.42:.1f} Z",
                "#ffffff", P.p, 5)]
    out.append(path(f"M{cx - u * 0.17:.1f} {H * 0.6:.1f} Q{cx:.1f} {H * 0.55:.1f} {cx + u * 0.17:.1f} {H * 0.6:.1f} L{cx + u * 0.2:.1f} {H * 0.7:.1f} Q{cx + u * 0.22:.1f} {H * 0.76:.1f} {cx + u * 0.15:.1f} {H * 0.76:.1f} H{cx - u * 0.15:.1f} Q{cx - u * 0.22:.1f} {H * 0.76:.1f} {cx - u * 0.2:.1f} {H * 0.7:.1f} Z", P.a_mid))
    for i in range(5):
        out.append(float_g(circ(cx + r.uniform(-0.1, 0.1) * u, H * (0.5 - 0.08 * i), u * r.uniform(0.012, 0.03), "#ffffff", P.p_mid, 2), i))
    hx, hy, hr = W * 0.8, H * 0.3, u * 0.07
    out.append(path("M" + " L".join(f"{hx + hr * math.cos(math.pi / 3 * k):.1f} {hy + hr * math.sin(math.pi / 3 * k):.1f}" for k in range(6)) + " Z", P.a_soft, P.a, 4))
    out.append(float_g(badge(W * 0.18, H * 0.3, u * 0.07, "atom" if has_icon("atom") else icons[0], P), 1))
    return "".join(out)


def scene_bio(W, H, P, r, icons, ctx) -> str:
    u, cx, cy = min(W, H), W / 2, H * 0.5
    out = [circ(cx, cy, u * 0.3, P.a_soft, P.a, 5), circ(cx + u * 0.05, cy - u * 0.04, u * 0.1, P.p, "#ffffff", 4)]
    for i, (dx, dy) in enumerate(((-0.14, 0.1), (0.12, 0.13), (-0.05, -0.17), (0.18, -0.06))):
        out.append(float_g(circ(cx + u * dx, cy + u * dy, u * 0.032, [P.p_mid, P.a, P.p_dark][i % 3], "#ffffff", 3), i))
    out.append(float_g(badge(W * 0.82, H * 0.2, u * 0.075, "leaf" if has_icon("leaf") else icons[0], P), 0))
    out.append(float_g(badge(W * 0.16, H * 0.82, u * 0.07, "dna" if has_icon("dna") else icons[-1], P, fill=P.a_soft), 2))
    return "".join(out)


def scene_physics(W, H, P, r, icons, ctx) -> str:
    u, cy = min(W, H), H * 0.5
    out = []
    for k, rad in enumerate((0.34, 0.24, 0.14)):
        out.append(circ(W / 2, cy, u * rad, "none", P.p_mid, 3, extra=' stroke-dasharray="10 12"'))
    out.append(circ(W / 2, cy, u * 0.07, P.p, "#ffffff", 4))
    for i, (ang, rad) in enumerate(((20, 0.34), (140, 0.24), (250, 0.14))):
        a = math.radians(ang)
        out.append(float_g(circ(W / 2 + u * rad * math.cos(a), cy + u * rad * math.sin(a), u * 0.03, P.a, "#ffffff", 3), i))
    pts = " ".join(f"{W * 0.12 + i * W * 0.76 / 40:.1f},{H * 0.84 + math.sin(i / 3.2) * u * 0.035:.1f}" for i in range(41))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{P.p}" stroke-width="{u * 0.012}" stroke-linecap="round"/>')
    out.append(float_g(badge(W * 0.82, H * 0.17, u * 0.07, "zap" if has_icon("zap") else icons[0], P), 0))
    return "".join(out)


def scene_math(W, H, P, r, icons, ctx) -> str:
    u = min(W, H)
    x0, y0, w, h = W * 0.14, H * 0.2, W * 0.72, H * 0.55
    out = [rect(x0 - u * 0.03, y0 - u * 0.03, w + u * 0.06, h + u * 0.06, u * 0.04, "#ffffff", P.p_mid, 3),
           line(x0, y0 + h / 2, x0 + w, y0 + h / 2, P.grey, 3), line(x0 + w / 2, y0, x0 + w / 2, y0 + h, P.grey, 3)]
    pts = " ".join(f"{x0 + i * w / 40:.1f},{y0 + h / 2 - math.sin((i - 20) / 6) * h * 0.3 - ((i - 20) ** 2) * 0.0006 * h * 0.3:.1f}" for i in range(41))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{P.p}" stroke-width="{u * 0.014}" stroke-linecap="round"/>')
    out.append(path(f"M{W * 0.2:.1f} {H * 0.88:.1f} L{W * 0.34:.1f} {H * 0.88:.1f} L{W * 0.2:.1f} {H * 0.8:.1f} Z", P.a_soft, P.a, 3))
    out.append(float_g(badge(W * 0.84, H * 0.17, u * 0.07, "sigma" if has_icon("sigma") else icons[0], P), 0))
    out.append(float_g(badge(W * 0.78, H * 0.86, u * 0.055, "infinity" if has_icon("infinity") else icons[-1], P, fill=P.a_soft), 1))
    return "".join(out)


def scene_history(W, H, P, r, icons, ctx) -> str:
    u = min(W, H)
    out = [path(f"M{W * 0.14:.1f} {H * 0.34:.1f} L{W * 0.5:.1f} {H * 0.18:.1f} L{W * 0.86:.1f} {H * 0.34:.1f} Z", P.p), rect(W * 0.14, H * 0.34, W * 0.72, u * 0.03, 0, P.p_dark)]
    for i in range(4):
        x = W * (0.2 + i * 0.185)
        out.append(rect(x, H * 0.38, u * 0.06, H * 0.34, u * 0.012, "#ffffff", P.p_mid, 3))
    out.append(rect(W * 0.12, H * 0.72, W * 0.76, u * 0.04, 0, P.p_dark))
    out.append(line(W * 0.14, H * 0.86, W * 0.86, H * 0.86, P.p_mid, u * 0.008))
    for i in range(4):
        out.append(float_g(circ(W * (0.18 + i * 0.21), H * 0.86, u * 0.018, P.a if i % 2 else P.p, "#ffffff", 2), i))
    out.append(float_g(badge(W * 0.84, H * 0.14, u * 0.06, "landmark" if has_icon("landmark") else icons[0], P, fill=P.a_soft), 0))
    return "".join(out)


def scene_earth(W, H, P, r, icons, ctx) -> str:
    u, cx, cy = min(W, H), W / 2, H * 0.5
    out = [circ(cx, cy, u * 0.3, P.p_mid, P.p, 5), path(f"M{cx - u * 0.2:.1f} {cy - u * 0.08:.1f} q{u * 0.1:.1f} {-u * 0.14:.1f} {u * 0.2:.1f} {-u * 0.02:.1f} q{u * 0.1:.1f} {u * 0.1:.1f} {u * 0.15:.1f} {u * 0.02:.1f} l0 {u * 0.1:.1f} q{-u * 0.15:.1f} {u * 0.06:.1f} {-u * 0.35:.1f} {u * 0.02:.1f} z", P.a),
           path(f"M{cx + u * 0.02:.1f} {cy + u * 0.12:.1f} q{u * 0.08:.1f} {-u * 0.05:.1f} {u * 0.14:.1f} {u * 0.04:.1f} q{-u * 0.04:.1f} {u * 0.1:.1f} {-u * 0.13:.1f} {u * 0.07:.1f} z", P.a)]
    out.append(circ(cx, cy, u * 0.4, "none", P.p_mid, 3, extra=' stroke-dasharray="6 12"'))
    out.append(float_g(badge(W * 0.84, H * 0.2, u * 0.07, "sun" if has_icon("sun") else icons[0], P, fill=P.a_soft), 0))
    out.append(float_g(badge(W * 0.15, H * 0.8, u * 0.065, "cloud" if has_icon("cloud") else icons[-1], P), 2))
    return "".join(out)


def scene_health(W, H, P, r, icons, ctx) -> str:
    u, cx, cy = min(W, H), W / 2, H * 0.42
    heart = f"M{cx:.1f} {cy + u * 0.2:.1f} C{cx - u * 0.38:.1f} {cy - u * 0.04:.1f} {cx - u * 0.2:.1f} {cy - u * 0.3:.1f} {cx:.1f} {cy - u * 0.1:.1f} C{cx + u * 0.2:.1f} {cy - u * 0.3:.1f} {cx + u * 0.38:.1f} {cy - u * 0.04:.1f} {cx:.1f} {cy + u * 0.2:.1f} Z"
    out = [path(heart, P.p), path(heart, "none", "#ffffff", 4, 0.0)]
    out.append(rect(W * 0.1, H * 0.74, W * 0.8, u * 0.14, u * 0.04, "#ffffff", P.p_mid, 3))
    pts = f"M{W * 0.14:.1f} {H * 0.81:.1f} H{W * 0.3:.1f} l{u * 0.03:.1f} {-u * 0.05:.1f} l{u * 0.05:.1f} {u * 0.1:.1f} l{u * 0.04:.1f} {-u * 0.08:.1f} l{u * 0.03:.1f} {u * 0.03:.1f} H{W * 0.86:.1f}"
    out.append(path(pts, stroke=P.a, sw=u * 0.014))
    out.append(float_g(badge(W * 0.84, H * 0.16, u * 0.065, "stethoscope" if has_icon("stethoscope") else icons[0], P, fill=P.a_soft), 0))
    return "".join(out)


def scene_society(W, H, P, r, icons, ctx) -> str:
    u, cx = min(W, H), W / 2
    out = [rect(cx - u * 0.01, H * 0.22, u * 0.02, H * 0.46, 0, P.p_dark), rect(cx - u * 0.16, H * 0.68, u * 0.32, u * 0.03, 0, P.p_dark), line(cx - u * 0.3, H * 0.28, cx + u * 0.3, H * 0.28, P.p, u * 0.012)]
    for sx in (-0.3, 0.3):
        out.append(line(cx + u * sx, H * 0.28, cx + u * sx, H * 0.4, P.p_mid, 3))
        out.append(path(f"M{cx + u * sx - u * 0.1:.1f} {H * 0.4:.1f} H{cx + u * sx + u * 0.1:.1f} Q{cx + u * sx:.1f} {H * 0.5:.1f} {cx + u * sx - u * 0.1:.1f} {H * 0.4:.1f} Z", P.a_soft, P.a, 3))
    for i, dx in enumerate((-0.2, 0, 0.2)):
        out.append(float_g(circ(cx + u * dx, H * 0.82, u * 0.045, [P.p, P.a, P.p_mid][i], "#ffffff", 3) + rect(cx + u * dx - u * 0.05, H * 0.86, u * 0.1, u * 0.05, u * 0.02, [P.p, P.a, P.p_mid][i]), i))
    return "".join(out)


def scene_network(W, H, P, r, icons, ctx) -> str:
    u = min(W, H)
    pts = [(r.uniform(0.18, 0.82) * W, r.uniform(0.2, 0.8) * H) for _ in range(7)]
    out = []
    for i, a in enumerate(pts):
        for b in pts[i + 1:i + 3]:
            out.append(line(a[0], a[1], b[0], b[1], P.p_mid, u * 0.008))
    for i, (x, y) in enumerate(pts):
        out.append(float_g(circ(x, y, u * (0.04 if i else 0.07), P.p if i % 2 == 0 else P.a, "#ffffff", 4), i))
    out.append(icon(icons[0], pts[0][0] - u * 0.035, pts[0][1] - u * 0.035, u * 0.07, "#ffffff", 2.4))
    return "".join(out)


def scene_book(W, H, P, r, icons, ctx) -> str:
    u, cx, cy = min(W, H), W / 2, H * 0.55
    out = [path(f"M{cx:.1f} {cy - u * 0.16:.1f} Q{cx - u * 0.16:.1f} {cy - u * 0.24:.1f} {cx - u * 0.32:.1f} {cy - u * 0.14:.1f} V{cy + u * 0.18:.1f} Q{cx - u * 0.16:.1f} {cy + u * 0.1:.1f} {cx:.1f} {cy + u * 0.2:.1f} Z", "#ffffff", P.p, 4),
           path(f"M{cx:.1f} {cy - u * 0.16:.1f} Q{cx + u * 0.16:.1f} {cy - u * 0.24:.1f} {cx + u * 0.32:.1f} {cy - u * 0.14:.1f} V{cy + u * 0.18:.1f} Q{cx + u * 0.16:.1f} {cy + u * 0.1:.1f} {cx:.1f} {cy + u * 0.2:.1f} Z", P.p_soft, P.p, 4)]
    for k in range(4):
        out.append(line(cx - u * 0.26, cy - u * (0.06 - k * 0.06), cx - u * 0.06, cy - u * (0.08 - k * 0.06), P.p_mid, 3))
        out.append(line(cx + u * 0.06, cy - u * (0.08 - k * 0.06), cx + u * 0.26, cy - u * (0.06 - k * 0.06), P.p_mid, 3))
    out.append(float_g(badge(cx, cy - u * 0.33, u * 0.085, icons[0] if icons else "lightbulb", P, fill=P.a_soft), 0))
    out.append(float_g(badge(W * 0.18, H * 0.2, u * 0.05, "graduation-cap" if has_icon("graduation-cap") else icons[-1], P), 1))
    return "".join(out)


def scene_orbit(W, H, P, r, icons, ctx) -> str:
    u, cx, cy = min(W, H), W / 2, H * 0.46
    R = u * 0.27
    out = [circ(cx, cy, R * 1.5, "none", P.p, 2, 0.55, ' stroke-dasharray="10 16"'), circ(cx, cy, R * 1.18, "#ffffff", op=0.55), circ(cx, cy, R, "#ffffff"), circ(cx, cy, R * 0.86, "none", P.p_mid, 3)]
    out.append(icon(icons[0], cx - R * 0.56, cy - R * 0.56, R * 1.12, P.p, 1.6))
    base = r.uniform(0, math.tau)
    for k, name in enumerate(icons[1:5]):
        ang = base + k * math.tau / max(1, len(icons[1:5]))
        out.append(float_g(badge(cx + math.cos(ang) * R * 1.5, cy + math.sin(ang) * R * 1.5, u * 0.07, name, P, fill="#ffffff" if k % 2 else P.a_soft), k))
    return "".join(out)


SCENES: Dict[str, Tuple[Scene, str]] = {
    "speech": (scene_speech, r"\b(word|words|language|grammar|syntactic|sentence|noun|verb|adjective|tagging|tagger|lexical|corpus|linguistic|meaning|speech|translation|semantic|vocabulary|pos|nlp|text|phrase|lemma|sense)\w*"),
    "tree": (scene_tree, r"\b(parse|parser|parsing|tree|syntax|constituen\w*|hierarch\w*|grammar|cfg|cyk|derivation|dependency|taxonomy)\b"),
    "window": (scene_window, r"\b(code|program\w*|algorithm|compiler|software|python|function|api|implementation|pseudo|script|debug|interface|app)\w*"),
    "chart": (scene_chart, r"\b(revenue|sales|growth|market|profit|cost|budget|financ\w*|econom\w*|price|percent|rate|statistic\w*|probabilit\w*|data|average|distribution|trend)\w*"),
    "flow": (scene_flow, r"\b(process|workflow|step|steps|pipeline|stage|stages|procedure|method|cycle|phase|sequence|lifecycle)\w*"),
    "lab": (scene_lab, r"\b(chemi\w*|reaction|molecul\w*|acid|compound|element|lab|experiment|catalyst|equilibrium|solution|bond)\w*"),
    "bio": (scene_bio, r"\b(cell|cells|biolog\w*|dna|gene\w*|organism|plant|photosynth\w*|protein|species|evolution|ecosystem|bacteria|enzyme)\w*"),
    "physics": (scene_physics, r"\b(energy|force|motion|wave|gravity|electric\w*|magnet\w*|quantum|velocity|physics|momentum|atom|thermodynamic|optics)\w*"),
    "math": (scene_math, r"\b(equation|theorem|proof|geometry|algebra|calculus|matrix|integral|derivative|vector|function|probability|polynomial|logarithm)\w*"),
    "history": (scene_history, r"\b(war|empire|revolution|century|ancient|king|treaty|colonial|dynasty|civili[sz]ation|history|medieval|renaissance|industrial)\w*"),
    "earth": (scene_earth, r"\b(climate|earth|geograph\w*|ocean|weather|environment\w*|continent|ecolog\w*|atmosphere|global|planet|pollution)\w*"),
    "health": (scene_health, r"\b(health\w*|disease|patient|medical|clinical|heart|medicine|therapy|nutrition|diagnos\w*|surgery|virus)\w*"),
    "society": (scene_society, r"\b(law|legal|court|rights|government|policy|society|political|constitution|justice|ethic\w*|democracy)\w*"),
    "network": (scene_network, r"\b(network|graph|node|nodes|relationship|connection|topology|internet|model|neural|markov|hidden|state|states)\w*"),
    "book": (scene_book, r"\b(introduction|overview|summary|concept|learn\w*|education|study|lesson|module|course|definition)\w*"),
    "orbit": (scene_orbit, r"$^"),
}
_DEFAULT_ORDER = ["book", "orbit", "network", "flow"]


# On a tie the subject-specific scene beats the generic one ("financial institution" in a linguistics slide must not win a chart).
_TIE_ORDER = ["speech", "tree", "lab", "bio", "physics", "math", "history", "earth", "health", "society", "window", "network", "flow", "chart", "book"]


def _scores(blob: str, title: str) -> Dict[str, float]:
    scores = {name: float(len(re.findall(pat, blob))) for name, (_, pat) in SCENES.items() if pat != r"$^"}
    for name, (_, pat) in SCENES.items():                 # a topic word in the TITLE outweighs incidental words in the body
        if pat != r"$^" and re.search(pat, (title or "").lower()):
            scores[name] += 2
    return scores


def deck_prior(texts: List[str]) -> Dict[str, float]:
    """The deck's own subject: its two strongest scenes get a bonus on every slide, so an NLP lecture is not drawn as a finance chart."""
    totals: Dict[str, float] = {}
    for t in texts:
        for name, sc in _scores(str(t).lower(), "").items():
            totals[name] = totals.get(name, 0.0) + sc
    top = sorted(((n, v) for n, v in totals.items() if v >= 6), key=lambda kv: -kv[1])[:2]
    return {n: (1.6 if k == 0 else 0.8) for k, (n, _) in enumerate(top)}


def choose_scene(title: str, text: str, avoid: Optional[List[str]] = None, seed: str = "", prior: Optional[Dict[str, float]] = None) -> str:
    blob = f"{title} {title} {text}".lower()
    scores = _scores(blob, title)
    for name, bonus in (prior or {}).items():
        if scores.get(name, 0) > 0:                       # the deck's subject only breaks ties between scenes the slide itself supports
            scores[name] += bonus
    rank = {n: i for i, n in enumerate(_TIE_ORDER)}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], rank.get(kv[0], 99)))
    avoid = avoid or []
    for name, sc in ranked:
        if sc > 0 and name not in avoid[-1:]:
            return name
    h = int(hashlib.sha1((seed or title or "x").encode()).hexdigest()[:6], 16)
    pool = [n for n in _DEFAULT_ORDER if n not in avoid[-1:]]
    return pool[h % len(pool)]


def _context(title: str, text: str, seed: int) -> Dict:
    nums = []
    for m in re.finditer(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s?(?:%|percent|million|billion|thousand)?", text or ""):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if not (1900 <= v <= 2100 and "." not in m.group(1)):
            nums.append(v)
    words = [w for w in re.findall(r"\b[A-Za-z][a-z]{3,9}\b", f"{title} {text}") if w.lower() not in {"this", "that", "with", "from", "which", "their", "there", "these", "those", "about", "also", "have", "been"}]
    seen, uniq = set(), []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            uniq.append(w)
    return {"numbers": nums[:6] if len(nums) >= 3 else [], "words": uniq[:4], "syntax": bool(re.search(r"\b(parse|syntax|constituen|cfg|cyk|grammar)\w*", f"{title} {text}".lower())), "seed": seed}


def scene_illustration(title: str, text: str, primary: str, accent: str, seed: str, kind: str = "panel", width: int = 800,
                       avoid: Optional[List[str]] = None, scene: Optional[str] = None, prior: Optional[Dict[str, float]] = None,
                       png: bool = True) -> Dict:
    """{"svg", "png", "scene", "alt"} for one slide."""
    W = width
    H = int(width * 1.25) if kind == "panel" else int(width * 0.62)
    r = random.Random(int(hashlib.sha1(f"{seed}|{title}".encode()).hexdigest()[:8], 16))
    P = Pal(primary, accent)
    name = scene or choose_scene(title, text, avoid, seed, prior)
    fn = SCENES[name][0]
    icons = pick_icons(f"{title} {text}", 5)
    ctx = _context(title, text, r.randint(0, 5))
    body = frame(W, H, P, r) + fn(W, H, P, r, icons, ctx)
    body += sparkles(W, H, P, r, (W / 2, H / 2, min(W, H) * 0.33))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{body}</svg>'
    return {"svg": svg, "png": svg_to_png(svg, W, H, alpha=True) if png else b"", "scene": name, "alt": f"Illustration for “{title}” ({name.replace('_', ' ')} scene)"}
