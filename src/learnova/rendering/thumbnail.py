"""Deck thumbnails: a designed 16:9 title card (PNG) rendered from SVG — fast, offline, no browser."""

from __future__ import annotations

import html
import textwrap

from learnova.ai.image_gen import _mix
from learnova.visuals.icons import icon_group, pick_icons, svg_to_png


def title_card_png(title: str, n_slides: int, primary: str = "#1D4ED8", accent: str = "#FFC93C", subject: str = "", width: int = 640) -> bytes:
    W, H = width, int(width * 9 / 16)
    lines = textwrap.wrap(title.strip() or "Untitled deck", 20)[:3]
    fs = 46 if len(lines) <= 2 and max(map(len, lines)) <= 14 else 36 if len(lines) <= 2 else 30
    fs = int(fs * W / 640)
    ink = "#ffffff"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
             f'<rect width="{W}" height="{H}" fill="{primary}"/>',
             f'<circle cx="{W * 0.88:.0f}" cy="{H * 0.9:.0f}" r="{H * 0.55:.0f}" fill="{accent}" opacity="0.95"/>',
             f'<circle cx="{W * 0.78:.0f}" cy="{-H * 0.05:.0f}" r="{H * 0.4:.0f}" fill="{_mix(primary, 0.25)}" opacity="0.6"/>',
             f'<rect x="{W * 0.07:.0f}" y="{H * 0.2:.0f}" width="{W * 0.12:.0f}" height="{H * 0.025:.0f}" rx="{H * 0.012:.0f}" fill="{accent}"/>']
    y = H * 0.2 + fs * 1.6
    for ln in lines:
        parts.append(f'<text x="{W * 0.07:.0f}" y="{y:.0f}" font-family="Helvetica, Arial, sans-serif" font-weight="700" font-size="{fs}" fill="{ink}">{html.escape(ln)}</text>')
        y += fs * 1.2
    parts.append(f'<text x="{W * 0.07:.0f}" y="{H * 0.9:.0f}" font-family="Helvetica, Arial, sans-serif" font-size="{int(15 * W / 640)}" fill="{_mix(primary, 0.75)}">{n_slides} slides</text>')
    cx, cy, r = W * 0.78, H * 0.55, H * 0.2
    parts.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="#ffffff"/>')
    parts.append(icon_group((pick_icons(subject or title, 1) or ["lightbulb"])[0], cx - r * 0.55, cy - r * 0.55, r * 1.1, primary, 1.7))
    parts.append("</svg>")
    return svg_to_png("".join(parts), W, H, alpha=False)
