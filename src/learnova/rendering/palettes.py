"""
Palette library: 240 ready-made colour schemes, every one checked for legibility.

Each palette is built from a *seed* (a hue family with a primary and an accent)
and a *surface* (the background / card / text treatment). 48 seeds × 5 surfaces
= 240 palettes. The generator then nudges the primary until it clears WCAG
contrast on its own background and picks text colours the same way, so no
palette can produce unreadable titles, captions or badge labels — which is the
failure that hand-picked colour lists tend to have.

    from learnova.rendering.palettes import PALETTES, search_palettes, palette_by_id
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# ── colour maths ──────────────────────────────────────────────────────────────

def _rgb(hex_: str) -> Tuple[int, int, int]:
    h = hex_.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(rgb: Tuple[float, float, float]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c))) for c in rgb))


def luminance(hex_: str) -> float:
    out = []
    for raw in _rgb(hex_):
        c = raw / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _hls(hex_: str) -> Tuple[float, float, float]:
    r, g, b = (c / 255.0 for c in _rgb(hex_))
    return colorsys.rgb_to_hls(r, g, b)


def _from_hls(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return _hex((r * 255, g * 255, b * 255))


def ensure_contrast(color: str, against: str, minimum: float, *, prefer_darker: Optional[bool] = None) -> str:
    """Move ``color`` along lightness (keeping hue) until it reaches ``minimum`` against ``against``."""
    if contrast(color, against) >= minimum:
        return color
    h, l, s = _hls(color)
    darker = (luminance(against) > 0.4) if prefer_darker is None else prefer_darker
    step = -0.01 if darker else 0.01
    for _ in range(100):
        l += step
        if not 0.0 <= l <= 1.0:
            break
        cand = _from_hls(h, l, s)
        if contrast(cand, against) >= minimum:
            return cand
    return "#0b1220" if darker else "#ffffff"


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


# ── seeds: name, category, primary, accent ───────────────────────────────────

_SEEDS: List[Tuple[str, str, str, str]] = [
    # Corporate / trust
    ("Royal Blue", "Corporate", "#1D4ED8", "#FFC93C"),
    ("Navy Gold", "Corporate", "#1E3A8A", "#F5B301"),
    ("Steel Teal", "Corporate", "#0F766E", "#F59E0B"),
    ("Slate Ink", "Corporate", "#334155", "#38BDF8"),
    ("Harbor", "Corporate", "#0369A1", "#FB923C"),
    ("Boardroom", "Corporate", "#1F2937", "#10B981"),
    ("Cobalt Lime", "Corporate", "#2563EB", "#A3E635"),
    ("Indigo Peach", "Corporate", "#4338CA", "#FDBA74"),
    # Vivid / energetic
    ("Coral Sun", "Vivid", "#E8452E", "#FFD166"),
    ("Hot Magenta", "Vivid", "#C026D3", "#FDE047"),
    ("Electric Violet", "Vivid", "#7C3AED", "#22D3EE"),
    ("Tangerine", "Vivid", "#EA580C", "#FACC15"),
    ("Cherry Pop", "Vivid", "#DC2626", "#FCD34D"),
    ("Neon Mint", "Vivid", "#059669", "#F472B6"),
    ("Sky Rocket", "Vivid", "#0EA5E9", "#F97316"),
    ("Punch Pink", "Vivid", "#DB2777", "#2DD4BF"),
    # Nature / calm
    ("Forest", "Nature", "#166534", "#FDE68A"),
    ("Sage", "Nature", "#4D7C0F", "#FDBA74"),
    ("Ocean", "Nature", "#0E7490", "#FCA5A5"),
    ("Moss & Clay", "Nature", "#3F6212", "#EA580C"),
    ("Lagoon", "Nature", "#0D9488", "#FCD34D"),
    ("Meadow", "Nature", "#15803D", "#F9A8D4"),
    ("Tide Pool", "Nature", "#155E75", "#86EFAC"),
    ("Pine & Rose", "Nature", "#14532D", "#FB7185"),
    # Warm / editorial
    ("Terracotta", "Warm", "#B45309", "#FDE68A"),
    ("Rust", "Warm", "#9A3412", "#FDBA74"),
    ("Cinnamon", "Warm", "#92400E", "#FCD34D"),
    ("Brick & Cream", "Warm", "#B91C1C", "#FEF3C7"),
    ("Amber Ink", "Warm", "#A16207", "#7DD3FC"),
    ("Saffron", "Warm", "#C2410C", "#FEF08A"),
    ("Mulberry", "Warm", "#9D174D", "#FDE68A"),
    ("Paprika", "Warm", "#BE123C", "#FDBA74"),
    # Cool / tech
    ("Cyan Tech", "Tech", "#0891B2", "#A78BFA"),
    ("Circuit", "Tech", "#4F46E5", "#2DD4BF"),
    ("Aurora", "Tech", "#6D28D9", "#34D399"),
    ("Quantum", "Tech", "#1D4ED8", "#F0ABFC"),
    ("Signal", "Tech", "#0F766E", "#C084FC"),
    ("Orbit", "Tech", "#3730A3", "#67E8F9"),
    ("Pixel", "Tech", "#7E22CE", "#FDE047"),
    ("Voltage", "Tech", "#0284C7", "#FACC15"),
    # Soft / pastel-led
    ("Lavender Mist", "Soft", "#6D5BD0", "#FBCFE8"),
    ("Peach Fuzz", "Soft", "#C2603A", "#FDE2D3"),
    ("Mint Cream", "Soft", "#2F855A", "#C6F6D5"),
    ("Sky Whisper", "Soft", "#3B82C4", "#BAE6FD"),
    ("Rose Quartz", "Soft", "#BE4B7A", "#FBCFE8"),
    ("Butter", "Soft", "#B7791F", "#FEF3C7"),
    ("Lilac Haze", "Soft", "#7C5CBF", "#DDD6FE"),
    ("Seafoam", "Soft", "#2C7A7B", "#B2F5EA"),
]

# Each surface: id, label, mode, bg, card, how strongly the primary tints text, bg gradient hint
# Backgrounds can be tinted toward the seed primary so one seed feels different on each surface.
_SURFACES: List[Tuple[str, str, str, float, str]] = [
    # id, label, mode, bg-tint (mix of seed into white), card
    ("clean", "Clean", "light", 0.00, "#ffffff"),
    ("tint", "Tinted", "light", 0.07, "#ffffff"),
    ("paper", "Paper", "light", -1.0, "#ffffff"),   # warm paper white
    ("mist", "Mist", "light", 0.14, "#ffffff"),
    ("night", "Night", "dark", 0.0, ""),
]


@dataclass(frozen=True)
class PaletteSpec:
    id: str
    name: str
    category: str
    mode: str
    primary: str
    accent: str
    bg: str
    card: str
    text: str
    subtext: str
    on_primary: str        # label colour for text sitting on a primary fill
    on_accent: str
    tags: Tuple[str, ...]

    def swatches(self) -> List[str]:
        return [self.bg, self.primary, self.accent, self.text]

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id, "name": self.name, "category": self.category, "mode": self.mode,
            "primary": self.primary, "secondary": self.accent, "accent": self.accent,
            "background": self.bg, "card": self.card, "text": self.text, "subtext": self.subtext,
            "tags": list(self.tags),
        }


def hue_name(hex_: str) -> str:
    """Plain colour word for search ("blue", "green"…); greys come back as "grey"."""
    h, l, sat = _hls(hex_)
    if sat < 0.12:
        return "grey"
    deg = h * 360
    for limit, name in ((15, "red"), (40, "orange"), (65, "yellow"), (160, "green"), (190, "teal"), (255, "blue"),
                        (290, "purple"), (335, "pink"), (361, "red")):
        if deg < limit:
            return name
    return "red"


def _slug(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_").replace("__", "_")


def _build(seed: Tuple[str, str, str, str], surface: Tuple[str, str, str, float, str]) -> PaletteSpec:
    sname, category, primary, accent = seed
    sid, slabel, mode, tint, card_fixed = surface
    if mode == "dark":
        h, _, s = _hls(primary)
        bg = _from_hls(h, 0.10, min(0.55, s * 0.7))
        card = _from_hls(h, 0.16, min(0.5, s * 0.6))
        text = "#f4f6fb"
        subtext = ensure_contrast("#aab3c5", bg, 4.5, prefer_darker=False)
        # bright primary on dark
        pr = ensure_contrast(_from_hls(h, 0.66, min(1.0, s * 1.05)), bg, 4.5, prefer_darker=False)
        ac = ensure_contrast(accent, bg, 4.5, prefer_darker=False)
    else:
        if tint < 0:                                      # warm paper
            bg = "#fbf7f0"
        else:
            bg = mix("#ffffff", primary, tint) if tint else "#ffffff"
            if tint:
                h, l, s = _hls(bg)
                bg = _from_hls(h, max(l, 0.94), min(s, 0.6))
        card = card_fixed
        text = ensure_contrast("#111827", bg, 12.0, prefer_darker=True)
        subtext = ensure_contrast("#4b5563", bg, 5.5, prefer_darker=True)
        pr = ensure_contrast(primary, bg, 5.0, prefer_darker=True)
        ac = accent                                       # accents are fills, not text; label colour is derived below
    on_pr = "#ffffff" if contrast("#ffffff", pr) >= contrast("#111111", pr) else "#111111"
    on_ac = "#ffffff" if contrast("#ffffff", ac) >= contrast("#111111", ac) else "#111111"
    # Guarantee badge legibility: if neither extreme reaches 4.5, darken/lighten the fill itself.
    if max(contrast("#ffffff", pr), contrast("#111111", pr)) < 4.5:
        pr = ensure_contrast(pr, "#ffffff" if on_pr == "#ffffff" else "#111111", 4.5)
    if max(contrast("#ffffff", ac), contrast("#111111", ac)) < 4.5:
        ac = ensure_contrast(ac, "#ffffff" if on_ac == "#ffffff" else "#111111", 4.5)
    tags = (category.lower(), mode, slabel.lower(), sname.lower(), hue_name(primary), hue_name(accent))
    return PaletteSpec(
        id=f"{_slug(sname)}_{sid}", name=f"{sname} · {slabel}", category=category, mode=mode,
        primary=pr, accent=ac, bg=bg, card=card, text=text, subtext=subtext,
        on_primary=on_pr, on_accent=on_ac, tags=tags,
    )


def _generate() -> Dict[str, PaletteSpec]:
    out: Dict[str, PaletteSpec] = {}
    for seed in _SEEDS:
        for surface in _SURFACES:
            spec = _build(seed, surface)
            out[spec.id] = spec
    return out


PALETTES: Dict[str, PaletteSpec] = _generate()
CATEGORIES: List[str] = sorted({p.category for p in PALETTES.values()})


def palette_by_id(pid: str) -> Optional[PaletteSpec]:
    return PALETTES.get(pid)


def audit(spec: PaletteSpec) -> Dict[str, float]:
    """Contrast ratios the generator guarantees (used by the tests and the UI badge)."""
    return {
        "text_on_bg": contrast(spec.text, spec.bg),
        "text_on_card": contrast(spec.text, spec.card),
        "subtext_on_bg": contrast(spec.subtext, spec.bg),
        "primary_on_bg": contrast(spec.primary, spec.bg),
        "label_on_primary": contrast(spec.on_primary, spec.primary),
        "label_on_accent": contrast(spec.on_accent, spec.accent),
    }


def search_palettes(q: str = "", category: str = "", mode: str = "", limit: int = 0, offset: int = 0) -> List[PaletteSpec]:
    needle = (q or "").strip().lower()
    items: Iterable[PaletteSpec] = PALETTES.values()
    if category:
        items = (p for p in items if p.category.lower() == category.lower())
    if mode:
        items = (p for p in items if p.mode == mode.lower())
    if needle:
        words = needle.split()
        items = (p for p in items if all(any(w in t for t in p.tags) or w in p.name.lower() for w in words))
    result = list(items)
    if offset:
        result = result[offset:]
    return result[:limit] if limit else result


# Topic → palette category, for "auto" theming.
_TOPIC_CATEGORY: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("biology", "health", "medical", "nature", "environment", "ecology", "agri", "chemistry", "geography"), "Nature"),
    (("history", "literature", "art", "culture", "humanities", "philosophy", "language", "architecture"), "Warm"),
    (("computer", "software", "data", "machine", "ai", "network", "programming", "algorithm", "cyber", "robot", "electronics", "physics"), "Tech"),
    (("business", "finance", "management", "economics", "marketing", "accounting", "law", "policy", "report"), "Corporate"),
    (("kids", "school", "primary", "creative", "festival", "event", "sport", "game"), "Vivid"),
    (("psychology", "wellness", "design", "fashion", "lifestyle", "education"), "Soft"),
)


def category_for_topic(topic: str) -> str:
    import re
    t = (topic or "").lower()
    for words, cat in _TOPIC_CATEGORY:
        if any(re.search(r"\b" + re.escape(w), t) for w in words):
            return cat
    return ""


def pick_for_topic(topic: str, mode: str = "light", salt: str = "") -> Optional[PaletteSpec]:
    """Deterministic, topic-aware pick: same title always gets the same palette."""
    cat = category_for_topic(topic)
    pool = search_palettes(category=cat, mode=mode) if cat else search_palettes(mode=mode)
    if not pool:
        return None
    key = sum(ord(c) * (i + 1) for i, c in enumerate((topic or "") + salt))
    return pool[key % len(pool)]
