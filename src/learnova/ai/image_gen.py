"""
Illustration engine: *when* a slide deserves an image, and how to make one.

When to draw (``plan_image``)
-----------------------------
Draw only where a picture adds meaning and does not steal room from data:

* concept slides — definitions, formulas, principles, key points, checklists,
  short cause-and-effect chains — where the text alone leaves the page feeling bare;
* never when the source already supplied a figure (keep that one);
* never on slides whose visual *is* the data (charts, tables, timelines, matrices,
  funnels, plots, worked examples) or on quiz slides;
* only when the subject maps to a concrete concept (no keyword match → no image,
  because a generic picture is decoration, not teaching);
* paced: at most ~45 % of slides, never back-to-back, so the deck has rhythm.

How it draws (``generate_image``)
---------------------------------
Provider chain, first success wins, results cached on disk by content hash:
1. ``gemini``  — Gemini image model, only if ``LEARNOVA_IMAGE_AI=1`` and a key is set;
2. ``vector``  — always available: a theme-coloured flat illustration composed from
   open-source Lucide icons (hero glyph in a halo, orbiting concept chips, soft
   shapes), rendered to PNG. Deterministic, offline, free, instant.
"""

from __future__ import annotations

import hashlib
import math
import os
import pathlib
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from learnova.config import CACHE_DIR
from learnova.logging_config import logger
from learnova.visuals.icons import has_icon, icon_group, pick_icons, svg_to_png

_NO_IMAGE_FAMILIES = {
    "CHART_CATEGORICAL", "CHART_RANKING", "CHART_TREND", "CHART_PART_TO_WHOLE", "COMPARE_TABLE", "TIMELINE",
    "MATRIX_GRID", "FUNNEL", "STAT_TILES", "FUNCTION_PLOT", "CALCULUS_VIZ", "WORKED_EXAMPLE", "ALGORITHM_TRACE",
    "DATA_STRUCTURE", "GEOMETRY", "ML_VIZ", "LAYERS", "SET_DIAGRAM", "MIND_MAP", "COMPARE_VISUAL", "QUIZ", "LINEAR_ALGEBRA",
    "CIRCUIT", "CHEM_DIAGRAM", "PROCESS_CYCLIC", "SECTIONS", "REFERENCES",
}
_CONCEPT_FAMILIES = {"DEFINITION", "FORMULA_CALLOUT", "QUOTE", "KEY_POINTS", "CHECKLIST", "CAUSE_EFFECT", "LIST_STRUCTURED",
                     "PROCESS_LINEAR", "TEXT", "PROSE"}
MAX_SHARE = 0.45


@dataclass
class ImagePlan:
    draw: bool
    reason: str
    subject: str = ""
    icons: List[str] = field(default_factory=list)
    kind: str = "panel"  # panel (portrait side panel) | hero (landscape)


def _size_ok(family: str, data: Dict[str, Any]) -> bool:
    """Is there room beside the visual for a side panel?"""
    if family == "KEY_POINTS":
        return len(data.get("cards") or []) <= 4
    if family == "PROSE":
        words = len(str(data.get("lead", "")).split()) + sum(len(str(b.get("text", "")).split()) for b in (data.get("body") or []))
        return words <= 115
    if family == "CHECKLIST":
        return len(data.get("items") or []) <= 5
    if family == "PROCESS_LINEAR":
        return len(data.get("stages") or []) <= 3
    if family == "CAUSE_EFFECT":
        return len(data.get("nodes") or []) <= 3
    if family == "LIST_STRUCTURED":
        return len(data.get("cards") or []) <= 4
    return True


def plan_image(title: str, text: str, family: str, data: Dict[str, Any], *, has_figure: bool = False,
               is_quiz: bool = False, prev_drawn: bool = False, drawn_so_far: int = 0, index: int = 0, total: int = 1) -> ImagePlan:
    if is_quiz or family == "QUIZ":
        return ImagePlan(False, "quiz slide — keep it clean")
    if has_figure:
        return ImagePlan(False, "the source already has a figure — keep that one")
    if family in _NO_IMAGE_FAMILIES:
        return ImagePlan(False, f"the {family.lower().replace('_', ' ')} visual is the content — an image would only crowd it")
    if family == "PROSE" and data.get("facts"):
        return ImagePlan(False, "the side panel shows this slide's figures instead of a picture")
    if family not in _CONCEPT_FAMILIES or not _size_ok(family, data):
        return ImagePlan(False, "no room beside the visual")
    if prev_drawn and total >= 4:
        return ImagePlan(False, "previous slide already has an illustration — pacing")
    if total >= 4 and drawn_so_far >= max(1, math.ceil(total * MAX_SHARE)):
        return ImagePlan(False, "illustration budget for this deck is used")
    subject = f"{title}. {text}"[:600]
    icons = pick_icons(subject, 5)
    from learnova.visuals.icons import _KEYWORDS  # noqa: PLC0415

    matched = [i for i in icons if i in _KEYWORDS and _KEYWORDS[i] and any(
        w[:5] in subject.lower() for w in _KEYWORDS[i].split()[:40] if len(w) >= 4)]
    if not matched:
        return ImagePlan(False, "no concrete subject to depict — a generic picture would be decoration")
    return ImagePlan(True, f"concept slide about “{title}” — an illustration of {matched[0].replace('-', ' ')} adds meaning", subject, icons)


# ── vector illustrator ───────────────────────────────────────────────────────
def _mix(hex_color: str, t: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#%02x%02x%02x" % (int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t))


def vector_illustration(icons: List[str], primary: str, accent: str, seed: str, kind: str = "panel", width: int = 900) -> bytes:
    W, H = (width, int(width * 1.25)) if kind == "panel" else (width, int(width * 0.62))
    r = random.Random(int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16))
    u = min(W, H)
    cx, cy = W / 2, H * (0.46 if kind == "panel" else 0.5)
    main = icons[0] if icons and has_icon(icons[0]) else "lightbulb"
    others = [i for i in icons[1:] if has_icon(i)][:4]
    p_soft, p_mid, a_soft, a_mid = _mix(primary, 0.92), _mix(primary, 0.78), _mix(accent, 0.72), _mix(accent, 0.45)

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
                f'<rect width="{W}" height="{H}" rx="{u * 0.06:.0f}" fill="{p_soft}"/>',
        f'<circle cx="{W * 0.88:.0f}" cy="{H * 0.1:.0f}" r="{u * 0.34:.0f}" fill="{a_mid}" opacity="0.55"/>',
        f'<circle cx="{W * 0.06:.0f}" cy="{H * 0.95:.0f}" r="{u * 0.4:.0f}" fill="{p_mid}" opacity="0.7"/>',
        f'<circle cx="{W * 0.82:.0f}" cy="{H * 0.9:.0f}" r="{u * 0.12:.0f}" fill="{a_mid}" opacity="0.7"/>',
    ]
    # dotted grid
    for i in range(6):
        for j in range(4):
            parts.append(f'<circle cx="{u * 0.07 + i * u * 0.035:.1f}" cy="{u * 0.07 + j * u * 0.035:.1f}" r="{u * 0.005:.1f}" fill="{_mix(primary, 0.5)}" opacity="0.7"/>')
    # halo rings + disc
    R = u * 0.27
    parts.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R * 1.5:.0f}" fill="none" stroke="{primary}" stroke-width="{u * 0.004:.1f}" stroke-dasharray="{u * 0.012:.0f} {u * 0.02:.0f}" opacity="0.55"/>')
    parts.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R * 1.18:.0f}" fill="#ffffff" opacity="0.55"/>')
    parts.append(f'<circle cx="{cx:.0f}" cy="{cy + u * 0.012:.0f}" r="{R:.0f}" fill="{_mix(primary, 0.55)}" opacity="0.35"/>')
    parts.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R:.0f}" fill="#ffffff"/>')
    parts.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R * 0.86:.0f}" fill="none" stroke="{p_mid}" stroke-width="{u * 0.006:.1f}"/>')
    ms = R * 1.12
    parts.append(icon_group(main, cx - ms / 2, cy - ms / 2, ms, primary, 1.55))
    # orbiting chips
    base = r.uniform(0, math.tau)
    for k, name in enumerate(others):
        ang = base + k * (math.tau / max(1, len(others))) + r.uniform(-0.2, 0.2)
        ox, oy = cx + math.cos(ang) * R * 1.5, cy + math.sin(ang) * R * 1.5
        cr = u * 0.075
        col = accent if k % 2 == 0 else primary
        parts.append(f'<circle cx="{ox:.0f}" cy="{oy + u * 0.008:.0f}" r="{cr:.0f}" fill="{_mix(col, 0.6)}" opacity="0.45"/>')
        parts.append(f'<circle cx="{ox:.0f}" cy="{oy:.0f}" r="{cr:.0f}" fill="#ffffff" stroke="{_mix(col, 0.55)}" stroke-width="{u * 0.004:.1f}"/>')
        parts.append(icon_group(name, ox - cr * 0.55, oy - cr * 0.55, cr * 1.1, col, 2.0))
    # sparkles / plus marks
    for _ in range(7):
        x, y, s = r.uniform(0.08, 0.92) * W, r.uniform(0.06, 0.94) * H, u * r.uniform(0.012, 0.024)
        if math.hypot(x - cx, y - cy) < R * 1.7:
            continue
        col = _mix(r.choice([primary, accent]), 0.25)
        parts.append(f'<path d="M{x - s:.1f} {y:.1f}H{x + s:.1f}M{x:.1f} {y - s:.1f}V{y + s:.1f}" stroke="{col}" stroke-width="{u * 0.006:.1f}" stroke-linecap="round"/>')
    parts.append("</svg>")
    return svg_to_png("".join(parts), W, H, alpha=True)


def _cache_path(key: str) -> pathlib.Path:
    d = CACHE_DIR / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.png"


def generate_image(plan: ImagePlan, primary_hex: str, accent_hex: str, *, use_ai: bool = True, title: str = "", style: str = "") -> Dict[str, Any]:
    """The picture for one slide: an AI image when a provider is configured (and allowed), otherwise the vector illustrator."""
    from learnova.ai import image_providers as ip

    style = style or os.getenv("LEARNOVA_IMAGE_STYLE", "flat")
    ai_on = use_ai and bool(ip.provider_name())
    key = hashlib.sha1(f"{plan.subject}|{primary_hex}|{accent_hex}|{plan.kind}|{ip.provider_name() if ai_on else 'vector'}|{style}".encode()).hexdigest()[:24]
    cp = _cache_path(key)
    provider = "cache"
    data: Optional[bytes] = cp.read_bytes() if cp.exists() else None
    if data is None:
        if ai_on:
            data = ip.generate(ip.style_prompt(plan.subject, primary_hex, accent_hex, style), "3:4" if plan.kind == "panel" else "4:3")
            provider = ip.provider_name() if data else "vector"
        else:
            provider = "vector"
        if not data:
            data = vector_illustration(plan.icons, primary_hex, accent_hex, plan.subject, plan.kind)
        try:
            cp.write_bytes(data)
        except OSError:
            pass
    return {"bytes": data, "ext": "png", "provider": provider, "icons": plan.icons[:4], "reason": plan.reason,
            "alt": f"Illustration: {title or plan.subject[:80]}"}


def illustrate_deck(final_deck: List[dict], theme, mode: str = "auto") -> int:
    """Plan + generate an illustration for each eligible slide. ``mode``: "auto" (AI when a key is set, else vector), "vector", or "ai".
    Returns how many were drawn."""
    from learnova.rendering.deck_director import plan_deck

    plan = plan_deck(final_deck)
    drawn, prev, total, ai_used = 0, False, len(final_deck), 0
    max_ai = int(os.getenv("LEARNOVA_IMAGE_MAX", "8"))      # cost control: at most this many generated images per deck
    for i, (entry, sp) in enumerate(zip(final_deck, plan.slides)):
        imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else None
        if imp is None:
            continue
        orig = entry.get("original") or {}
        text = " ".join(str(b) for b in (imp.get("bullets") or []))
        ip = plan_image(str(imp.get("title", "")), text, sp.family, sp.data or {}, has_figure=bool((orig or {}).get("image")),
                        is_quiz=str(imp.get("layout_type", "")).upper() == "QUIZ", prev_drawn=prev, drawn_so_far=drawn, index=i, total=total)
        imp["image_plan"] = {"draw": ip.draw, "reason": ip.reason}
        prev = ip.draw
        if not ip.draw:
            imp.pop("illustration", None)
            continue
        use_ai = mode != "vector" and ai_used < max_ai
        imp["illustration"] = generate_image(ip, theme.primary_hex, theme.accent_hex, use_ai=use_ai, title=str(imp.get("title", "")))
        ai_used += imp["illustration"].get("provider") not in {"vector", "cache"}
        drawn += 1
    return drawn
