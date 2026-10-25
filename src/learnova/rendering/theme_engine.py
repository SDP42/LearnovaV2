"""
Learnova Presentation Theme Engine
Provides 10 Curated Color Schemes and 10 Slide Design Layout Styles (100+ Template Variations)
for PPTX Decks and HTML5 Web Presentations.
"""

import re
from dataclasses import dataclass, replace
from pptx.dml.color import RGBColor

@dataclass
class ColorPalette:
    id: str
    name: str
    description: str
    bg_hex: str
    bg_rgb: RGBColor
    primary_hex: str
    primary_rgb: RGBColor
    accent_hex: str
    accent_rgb: RGBColor
    card_bg_hex: str
    card_bg_rgb: RGBColor
    text_hex: str
    text_rgb: RGBColor
    subtext_hex: str
    subtext_rgb: RGBColor
    # Typography. Defaults keep every existing theme rendering as before.
    heading_font: str = "Bebas Neue"
    body_font: str = "Inter"

# ── 10 Curated Professional Color Palettes ────────────────────────────────────
THEMES = {
    "canva_bright": ColorPalette(
        id="canva_bright",
        name="Bright Blue (Default)",
        description="Airy white canvas, strong blue headings and a sunny yellow accent — clean and friendly.",
        bg_hex="#F7FAFF", bg_rgb=RGBColor(247, 250, 255),
        primary_hex="#1D4ED8", primary_rgb=RGBColor(29, 78, 216),
        accent_hex="#FFC93C", accent_rgb=RGBColor(255, 201, 60),
        card_bg_hex="#FFFFFF", card_bg_rgb=RGBColor(255, 255, 255),
        text_hex="#0F172A", text_rgb=RGBColor(15, 23, 42),
        subtext_hex="#475569", subtext_rgb=RGBColor(71, 85, 105),
        heading_font="Poppins", body_font="Inter",
    ),
    "sunrise_pop": ColorPalette(
        id="sunrise_pop",
        name="Sunrise Pop",
        description="Warm cream with a confident coral-red and golden highlights.",
        bg_hex="#FFF8F1", bg_rgb=RGBColor(255, 248, 241),
        primary_hex="#C2371C", primary_rgb=RGBColor(194, 55, 28),
        accent_hex="#FFD166", accent_rgb=RGBColor(255, 209, 102),
        card_bg_hex="#FFFFFF", card_bg_rgb=RGBColor(255, 255, 255),
        text_hex="#2B1B17", text_rgb=RGBColor(43, 27, 23),
        subtext_hex="#6B5B54", subtext_rgb=RGBColor(107, 91, 84),
        heading_font="Poppins", body_font="Inter",
    ),
    "forest_calm": ColorPalette(
        id="forest_calm",
        name="Forest Calm",
        description="Fresh pale-green canvas with deep emerald and amber accents.",
        bg_hex="#F4FBF6", bg_rgb=RGBColor(244, 251, 246),
        primary_hex="#0F6B4F", primary_rgb=RGBColor(15, 107, 79),
        accent_hex="#F6C453", accent_rgb=RGBColor(246, 196, 83),
        card_bg_hex="#FFFFFF", card_bg_rgb=RGBColor(255, 255, 255),
        text_hex="#0F2A20", text_rgb=RGBColor(15, 42, 32),
        subtext_hex="#4B6358", subtext_rgb=RGBColor(75, 99, 88),
        heading_font="Poppins", body_font="Inter",
    ),
    "violet_soft": ColorPalette(
        id="violet_soft",
        name="Violet Soft",
        description="Light lavender canvas with rich violet and a pink accent.",
        bg_hex="#FAF7FF", bg_rgb=RGBColor(250, 247, 255),
        primary_hex="#5B3FD8", primary_rgb=RGBColor(91, 63, 216),
        accent_hex="#FF9EC7", accent_rgb=RGBColor(255, 158, 199),
        card_bg_hex="#FFFFFF", card_bg_rgb=RGBColor(255, 255, 255),
        text_hex="#1E1B3A", text_rgb=RGBColor(30, 27, 58),
        subtext_hex="#5B5878", subtext_rgb=RGBColor(91, 88, 120),
        heading_font="Poppins", body_font="Inter",
    ),
    # The id is load-bearing: saved decks store it in their metadata, so it
    # stays "brutalist_neon" regardless of the accent colour.
    "brutalist_neon": ColorPalette(
        id="brutalist_neon",
        name="Brutalist Amber (Default)",
        description="High-contrast black & neon amber accent for modern tech presentations.",
        bg_hex="#ffffff",
        bg_rgb=RGBColor(255, 255, 255),
        primary_hex="#000000",
        primary_rgb=RGBColor(0, 0, 0),
        accent_hex="#ffbd00",
        accent_rgb=RGBColor(255, 189, 0),
        card_bg_hex="#f7f9fa",
        card_bg_rgb=RGBColor(247, 249, 250),
        text_hex="#1a1a1a",
        text_rgb=RGBColor(26, 26, 26),
        subtext_hex="#555555",
        subtext_rgb=RGBColor(85, 85, 85),
    ),
    "midnight_cyber": ColorPalette(
        id="midnight_cyber",
        name="Midnight Cyber",
        description="Dark slate backdrop with luminous cyan and deep navy cards.",
        bg_hex="#0f172a",
        bg_rgb=RGBColor(15, 23, 42),
        primary_hex="#1e293b",
        primary_rgb=RGBColor(30, 41, 59),
        accent_hex="#38bdf8",
        accent_rgb=RGBColor(56, 189, 248),
        card_bg_hex="#1e293b",
        card_bg_rgb=RGBColor(30, 41, 59),
        text_hex="#f8fafc",
        text_rgb=RGBColor(248, 250, 252),
        subtext_hex="#94a3b8",
        subtext_rgb=RGBColor(148, 163, 184),
    ),
    "emerald_academic": ColorPalette(
        id="emerald_academic",
        name="Emerald Academic",
        description="Rich forest emerald and mint green for science & research lectures.",
        bg_hex="#064e3b",
        bg_rgb=RGBColor(6, 78, 59),
        primary_hex="#047857",
        primary_rgb=RGBColor(4, 120, 87),
        accent_hex="#6ee7b7",
        accent_rgb=RGBColor(110, 231, 183),
        card_bg_hex="#065f46",
        card_bg_rgb=RGBColor(6, 95, 70),
        text_hex="#ecfdf5",
        text_rgb=RGBColor(236, 253, 245),
        subtext_hex="#a7f3d0",
        subtext_rgb=RGBColor(167, 243, 208),
    ),
    "swiss_corporate": ColorPalette(
        id="swiss_corporate",
        name="Swiss Corporate Minimalist",
        description="Clean white canvas with bold charcoal typography and red Swiss accents.",
        bg_hex="#ffffff",
        bg_rgb=RGBColor(255, 255, 255),
        primary_hex="#18181b",
        primary_rgb=RGBColor(24, 24, 27),
        accent_hex="#ef4444",
        accent_rgb=RGBColor(239, 68, 68),
        card_bg_hex="#f4f4f5",
        card_bg_rgb=RGBColor(244, 244, 245),
        text_hex="#18181b",
        text_rgb=RGBColor(24, 24, 27),
        subtext_hex="#71717a",
        subtext_rgb=RGBColor(113, 113, 122),
    ),
    "sunset_editorial": ColorPalette(
        id="sunset_editorial",
        name="Sunset Pastel Editorial",
        description="Warm lavender & deep violet tones with gold highlights for humanities.",
        bg_hex="#fff7ed",
        bg_rgb=RGBColor(255, 247, 237),
        primary_hex="#4c1d95",
        primary_rgb=RGBColor(76, 29, 149),
        accent_hex="#f59e0b",
        accent_rgb=RGBColor(245, 158, 11),
        card_bg_hex="#ffedd5",
        card_bg_rgb=RGBColor(255, 237, 213),
        text_hex="#292524",
        text_rgb=RGBColor(41, 37, 36),
        subtext_hex="#78716c",
        subtext_rgb=RGBColor(120, 113, 108),
    ),
    "ocean_tech": ColorPalette(
        id="ocean_tech",
        name="Deep Ocean Tech",
        description="Marine blue background with ice-blue metric containers.",
        bg_hex="#0c4a6e",
        bg_rgb=RGBColor(12, 74, 110),
        primary_hex="#0369a1",
        primary_rgb=RGBColor(3, 105, 161),
        accent_hex="#38bdf8",
        accent_rgb=RGBColor(56, 189, 248),
        card_bg_hex="#075985",
        card_bg_rgb=RGBColor(7, 89, 133),
        text_hex="#f0f9ff",
        text_rgb=RGBColor(240, 249, 255),
        subtext_hex="#bae6fd",
        subtext_rgb=RGBColor(186, 230, 253),
    ),
    "charcoal_gold": ColorPalette(
        id="charcoal_gold",
        name="Charcoal Gold Luxury",
        description="Matte dark charcoal with warm metallic gold accents for executive decks.",
        bg_hex="#1c1917",
        bg_rgb=RGBColor(28, 25, 23),
        primary_hex="#292524",
        primary_rgb=RGBColor(41, 37, 36),
        accent_hex="#eab308",
        accent_rgb=RGBColor(234, 179, 8),
        card_bg_hex="#292524",
        card_bg_rgb=RGBColor(41, 37, 36),
        text_hex="#fef08a",
        text_rgb=RGBColor(254, 240, 138),
        subtext_hex="#d6d3d1",
        subtext_rgb=RGBColor(214, 211, 209),
    ),
    "nordic_slate": ColorPalette(
        id="nordic_slate",
        name="Nordic Clean Slate",
        description="Minimalist cool slate and soft grey tones with crisp typography.",
        bg_hex="#f8fafc",
        bg_rgb=RGBColor(248, 250, 252),
        primary_hex="#1e293b",
        primary_rgb=RGBColor(30, 41, 59),
        accent_hex="#0284c7",
        accent_rgb=RGBColor(2, 132, 199),
        card_bg_hex="#e2e8f0",
        card_bg_rgb=RGBColor(226, 232, 240),
        text_hex="#0f172a",
        text_rgb=RGBColor(15, 23, 42),
        subtext_hex="#475569",
        subtext_rgb=RGBColor(71, 85, 105),
    ),
    "warm_terracotta": ColorPalette(
        id="warm_terracotta",
        name="Warm Terracotta Earth",
        description="Earthy clay, rust red, and cream tones for design & architecture.",
        bg_hex="#fff7ed",
        bg_rgb=RGBColor(255, 247, 237),
        primary_hex="#7c2d12",
        primary_rgb=RGBColor(124, 45, 18),
        accent_hex="#ea580c",
        accent_rgb=RGBColor(234, 88, 12),
        card_bg_hex="#ffedd5",
        card_bg_rgb=RGBColor(255, 237, 213),
        text_hex="#431407",
        text_rgb=RGBColor(67, 20, 7),
        subtext_hex="#9a3412",
        subtext_rgb=RGBColor(154, 52, 18),
    ),
    "glass_indigo": ColorPalette(
        id="glass_indigo",
        name="Glassmorphism Indigo",
        description="Deep indigo with semi-transparent frosted card containers.",
        bg_hex="#1e1b4b",
        bg_rgb=RGBColor(30, 27, 75),
        primary_hex="#312e81",
        primary_rgb=RGBColor(49, 46, 129),
        accent_hex="#818cf8",
        accent_rgb=RGBColor(129, 140, 248),
        card_bg_hex="#3730a3",
        card_bg_rgb=RGBColor(55, 48, 163),
        text_hex="#e0e7ff",
        text_rgb=RGBColor(224, 231, 255),
        subtext_hex="#a5b4fc",
        subtext_rgb=RGBColor(165, 180, 252),
    ),
}

# ── 50 Distinct Slide Layout Variation Patterns ──────────────────────────────
LAYOUT_STYLES = [
    "header_banner",          # 1. Top header banner with crisp content cards
    "floating_cards",         # 2. Floating elevated cards with thick accent left borders
    "split_column",           # 3. Dual panel side-by-side split layout
    "gradient_frame",         # 4. Full outer accent frame border
    "left_pillar",            # 5. Solid colored left sidebar pillar
    "hero_centered",          # 6. Large center stage focus callout block
    "grid_matrix",            # 7. 2x2 grid container boxes
    "minimal_line",           # 8. Clean ultra-thin outline minimal cards
    "pill_header",            # 9. Pill badge tags and rounded pill containers
    "glass_floating",         # 10. Frosted glass look containers
    "timeline_stepper",       # 11. Horizontal numbered timeline flow
    "asymmetric_split",       # 12. 60/40 weighted split column layout
    "triple_pillar_hero",     # 13. 3 tall vertical pillar cards
    "diagonal_accent",        # 14. Diagonal accent header geometry
    "framed_takeaway",        # 15. Central takeaway box with outer highlight frame
    "stat_banner_top",        # 16. Top numeric stat callout banner
    "checkerboard_grid",      # 17. Alternating card background grid
    "floating_glass_stack",   # 18. Stacked vertical cards with drop shadows
    "badge_pill_grid",        # 19. Pill-shaped badge header with grid cards
    "bottom_bar_footer",      # 20. Bottom accent takeaway footer strip
    "vertical_stepper",       # 21. Vertical step-by-step progress cards
    "bento_grid_3col",        # 22. Modern Bento-box 3 column grid
    "dual_tone_cards",        # 23. Alternating high-contrast dual tone cards
    "subtle_shadow_card",     # 24. Soft shadow floating cards
    "accent_left_border",     # 25. Thick 6px left border callout panels
    "accent_top_stripe",      # 26. Top colored stripe accent cards
    "highlight_box_center",   # 27. Highlighted central box focus
    "two_tone_split",         # 28. Top half dark, bottom half light split
    "timeline_horizontal",    # 29. Horizontal process node line
    "quote_hero_box",         # 30. Large quote style key insight hero
    "numbered_list_cards",    # 31. Numbered index badge cards 1, 2, 3
    "full_bleed_accent",      # 32. Full bleed accent background for key slides
    "compact_dense_table",    # 33. Structured compact grid table
    "giant_stat_left",        # 34. Giant stat number on left, text on right
    "giant_stat_right",       # 35. Text on left, giant stat number on right
    "comparison_dual_card",   # 36. Side-by-side vs comparison cards
    "step_flow_horizontal",   # 37. 4 horizontal arrow step cards
    "step_flow_vertical",     # 38. 4 vertical arrow step cards
    "bento_box_large",        # 39. Bento-box main hero + 2 sub cards
    "header_pill_floating",   # 40. Floating top pill header bar
    "left_accent_ribbon",     # 41. Vertical ribbon stripe on left
    "dark_contrast_card",     # 42. Inverted high-contrast dark card
    "light_minimal_card",     # 43. Clean ultra-light minimal container
    "floating_shadow_grid",   # 44. Grid of soft-shadow floating cards
    "pill_stepper_row",       # 45. Row of connected pill step badges
    "top_accent_bar",         # 46. Top header bar with accent line
    "bottom_accent_bar",      # 47. Bottom footer bar with accent line
    "framed_card_matrix",     # 48. Framed matrix container with 4 cards
    "dual_badge_header",      # 49. Header with dual layout and category badges
    "hero_stat_split",        # 50. Split hero stat number + key takeaway box
]

# Map layout types to compatible style candidate pools
LAYOUT_TYPE_POOLS = {
    "FLOWCHART": [
        "step_flow_horizontal", "step_flow_vertical", "timeline_stepper", "vertical_stepper",
        "pill_stepper_row", "timeline_horizontal", "header_banner", "left_pillar", "badge_pill_grid", "accent_top_stripe"
    ],
    "TABLE": [
        "compact_dense_table", "comparison_dual_card", "grid_matrix", "bento_grid_3col",
        "checkerboard_grid", "two_tone_split", "split_column", "framed_card_matrix", "minimal_line", "dual_badge_header"
    ],
    "METRIC": [
        "giant_stat_left", "giant_stat_right", "hero_stat_split", "stat_banner_top",
        "hero_centered", "quote_hero_box", "full_bleed_accent", "dark_contrast_card", "highlight_box_center", "floating_cards"
    ],
    "CARD_GRID": [
        "bento_grid_3col", "bento_box_large", "triple_pillar_hero", "numbered_list_cards",
        "grid_matrix", "checkerboard_grid", "floating_glass_stack", "framed_card_matrix", "floating_shadow_grid", "dual_tone_cards"
    ],
    "MINIMAL_TEXT": [
        "accent_left_border", "light_minimal_card", "pill_header", "glass_floating",
        "asymmetric_split", "diagonal_accent", "framed_takeaway", "bottom_bar_footer", "subtle_shadow_card", "header_pill_floating"
    ],
}

def select_slide_layout(slide_idx: int, layout_type: str, prev_layout_style: str = None) -> str:
    """
    Intelligent layout router algorithm:
    1. Selects candidate pool based on slide content layout_type.
    2. Ensures consecutive slides never reuse the exact same layout style.
    3. Rotates deterministically using slide_idx for reproducible decks.
    """
    l_type = (layout_type or "MINIMAL_TEXT").upper()
    pool = LAYOUT_TYPE_POOLS.get(l_type, LAYOUT_TYPE_POOLS["MINIMAL_TEXT"])
    
    # Pick style based on slide index offset
    chosen_style = pool[slide_idx % len(pool)]
    
    # Avoid exact repetition with previous slide
    if chosen_style == prev_layout_style and len(pool) > 1:
        chosen_style = pool[(slide_idx + 1) % len(pool)]
        
    return chosen_style

# ── Custom palettes & fonts ───────────────────────────────────────────────────
# Fonts offered in the UI. PPTX embeds the family name, so the viewer needs the
# font installed; each entry therefore names a safe fallback that Office and
# every browser already ship.
FONT_CHOICES = {
    "bebas_inter":     {"label": "Bebas Neue + Inter (Default)", "heading": "Bebas Neue",      "body": "Inter",           "fallback": "Arial"},
    "anton_poppins":   {"label": "Anton + Poppins",              "heading": "Anton",           "body": "Poppins",         "fallback": "Arial"},
    "oswald_lato":     {"label": "Oswald + Lato",                "heading": "Oswald",          "body": "Lato",            "fallback": "Arial"},
    "montserrat":      {"label": "Montserrat",                   "heading": "Montserrat",      "body": "Montserrat",      "fallback": "Arial"},
    "playfair_source": {"label": "Playfair Display + Source Sans", "heading": "Playfair Display", "body": "Source Sans Pro", "fallback": "Georgia"},
    "georgia":         {"label": "Georgia (Serif, always available)", "heading": "Georgia",     "body": "Georgia",         "fallback": "Georgia"},
    "arial":           {"label": "Arial (Safest)",               "heading": "Arial Black",     "body": "Arial",           "fallback": "Arial"},
}

DEFAULT_FONT_ID = "bebas_inter"


def _hex_to_rgb(value: str, fallback: tuple = (0, 0, 0)) -> RGBColor:
    """Parse '#rrggbb' or 'rrggbb' into an RGBColor, tolerating bad input."""
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:                      # '#abc' shorthand
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return RGBColor(*fallback)
    try:
        return RGBColor(int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return RGBColor(*fallback)


def _normalise_hex(value: str, fallback: str) -> str:
    rgb = _hex_to_rgb(value, _hex_to_rgb(fallback))
    return f"#{rgb}".lower()


def _relative_luminance(rgb: RGBColor) -> float:
    """WCAG relative luminance, used to pick readable text over a fill."""
    channels = []
    for raw in (rgb[0], rgb[1], rgb[2]):
        c = raw / 255.0
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def readable_text_hex(background_hex: str) -> str:
    """Return black or white — whichever stays legible on the given fill."""
    return "#111111" if _relative_luminance(_hex_to_rgb(background_hex)) > 0.45 else "#ffffff"


def build_custom_theme(
    primary_hex: str,
    secondary_hex: str,
    background_hex: str = "#ffffff",
    font_id: str = DEFAULT_FONT_ID,
    name: str = "Custom Palette",
) -> ColorPalette:
    """
    Build a palette from user-chosen colours.

    Only primary and secondary are asked for in the UI; the remaining roles
    (card fill, body text, muted text) are derived, and text colours are chosen
    by luminance so a dark primary never ends up with black text on it.
    """
    primary = _normalise_hex(primary_hex, "#000000")
    accent = _normalise_hex(secondary_hex, "#ffbd00")
    background = _normalise_hex(background_hex, "#ffffff")

    body_text = readable_text_hex(background)
    card_bg = "#f5f6f8" if _relative_luminance(_hex_to_rgb(background)) > 0.45 else "#1b1d22"
    subtext = "#555555" if body_text == "#111111" else "#bbbbbb"

    font = FONT_CHOICES.get(font_id, FONT_CHOICES[DEFAULT_FONT_ID])

    return ColorPalette(
        id="custom",
        name=name,
        description="User-defined palette.",
        bg_hex=background,      bg_rgb=_hex_to_rgb(background),
        primary_hex=primary,    primary_rgb=_hex_to_rgb(primary),
        accent_hex=accent,      accent_rgb=_hex_to_rgb(accent),
        card_bg_hex=card_bg,    card_bg_rgb=_hex_to_rgb(card_bg),
        text_hex=body_text,     text_rgb=_hex_to_rgb(body_text),
        subtext_hex=subtext,    subtext_rgb=_hex_to_rgb(subtext),
        heading_font=font["heading"],
        body_font=font["body"],
    )


def apply_font(theme: ColorPalette, font_id: str) -> ColorPalette:
    """Return a copy of a preset theme using the chosen font pairing."""
    font = FONT_CHOICES.get(font_id)
    if not font:
        return theme
    return replace(theme, heading_font=font["heading"], body_font=font["body"])


def get_theme(theme_id: str) -> ColorPalette:
    """Retrieve theme color palette by ID, defaulting to the bright default."""
    return THEMES.get(theme_id, THEMES["canva_bright"])

def auto_detect_theme(topic_title: str) -> ColorPalette:
    """Pick a *bright* palette from title keywords (dark themes stay opt-in)."""
    t = (topic_title or "").lower()
    rules = (
        (("medical", "health", "biology", "science", "nature", "green", "environment", "chemistry"), "forest_calm"),
        (("history", "art", "literature", "education", "humanities", "editorial", "marketing", "creative"), "sunrise_pop"),
        (("business", "finance", "corporate", "swiss", "market", "management", "report", "economics"), "swiss_corporate"),
        (("glass", "indigo", "modern", "future", "design", "startup", "product"), "violet_soft"),
        (("nordic", "clean", "slate", "simple", "minimal"), "nordic_slate"),
        (("architecture", "warm", "terracotta", "craft"), "warm_terracotta"),
    )
    for words, tid in rules:
        if any(re.search(r"\b" + re.escape(w), t) for w in words):  # word start: 'art' must not match 'quarterly'
            return THEMES[tid]
    return THEMES["canva_bright"]


def resolve_theme(topic_title: str, theme_id: str = "auto",
                  theme_spec: dict | None = None) -> ColorPalette:
    """
    Turn a theme selection into a ColorPalette.

    ``theme_spec`` carries a user-defined palette from the UI:
    ``{"primary": "#...", "secondary": "#...", "background": "#...",
       "font_id": "anton_poppins"}``. When absent we fall back to the named
    preset (or auto-detection), optionally re-fonted.
    """
    if theme_spec and (theme_spec.get("primary") or theme_spec.get("secondary")):
        return build_custom_theme(
            primary_hex=theme_spec.get("primary", "#000000"),
            secondary_hex=theme_spec.get("secondary", "#ffbd00"),
            background_hex=theme_spec.get("background", "#ffffff"),
            font_id=theme_spec.get("font_id", DEFAULT_FONT_ID),
            name=theme_spec.get("name", "Custom Palette"),
        )

    theme = auto_detect_theme(topic_title) if theme_id == "auto" else get_theme(theme_id)
    if theme_spec and theme_spec.get("font_id"):
        theme = apply_font(theme, theme_spec["font_id"])
    return theme
