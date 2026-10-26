"""
Slide templates: the *structure* of a deck, independent of its colours.

A palette answers "what colours?"; a template answers "what does the deck look
like?" — header treatment, title-slide composition, card shape, decoration and
footer. The two are independent, so 240 palettes × 12 templates gives 2,880
distinct looks from one content plan.

Templates are plain data. The PPTX and web builders read the same fields, so a
template looks the same in PowerPoint and in the browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    header: str            # bar | underline | side | ribbon | plain
    title_layout: str      # hero_split | centered | left_band | frame | poster
    card_radius: float     # inches of corner radius on cards
    card_border: bool      # thin outline on cards
    decoration: str        # circles | dots | lines | corner | none
    footer: str            # minimal | rule | pill
    title_case: str = "as_is"     # as_is | upper

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "header": self.header, "title_layout": self.title_layout, "card_radius": self.card_radius,
            "card_border": self.card_border, "decoration": self.decoration, "footer": self.footer,
        }


TEMPLATES: Dict[str, Template] = {t.id: t for t in (
    Template("classic", "Classic Banner", "Solid colour banner, rounded cards, bold hero title slide.",
             "bar", "hero_split", 0.07, True, "circles", "minimal"),
    Template("editorial", "Editorial", "Title above a thin accent rule on white — calm, magazine-like.",
             "underline", "left_band", 0.04, False, "lines", "rule"),
    Template("sidebar", "Side Rail", "A colour rail down the left edge carries the section; roomy content.",
             "side", "left_band", 0.1, True, "none", "minimal"),
    Template("ribbon", "Ribbon", "A ribbon tab holds the title; friendly pill footer.",
             "ribbon", "centered", 0.2, True, "dots", "pill"),
    Template("minimal", "Minimal", "No chrome. Big title, hairline cards, maximum focus.",
             "plain", "centered", 0.03, True, "none", "rule"),
    Template("poster", "Poster", "Huge title slide, confident banner, tight corners.",
             "bar", "poster", 0.0, False, "corner", "minimal", "upper"),
    Template("soft", "Soft Cards", "Generous radius, no outlines — gentle and approachable.",
             "underline", "hero_split", 0.3, False, "circles", "pill"),
    Template("frame", "Framed", "Thin frame around the title slide; clean banner inside.",
             "bar", "frame", 0.08, True, "lines", "rule"),
    Template("academic", "Academic", "Understated, serif-friendly layout for lectures and reports.",
             "underline", "left_band", 0.05, True, "none", "rule"),
    Template("bold", "Bold Block", "Heavy colour blocks and square cards for punchy talks.",
             "bar", "poster", 0.0, False, "corner", "minimal"),
    Template("playful", "Playful", "Round everything, dotted accents — great for school-age decks.",
             "ribbon", "hero_split", 0.35, False, "dots", "pill"),
    Template("slate", "Slate Pro", "Clean business look: side rail, hairline cards, quiet footer.",
             "side", "frame", 0.06, True, "lines", "rule"),
)}

DEFAULT_TEMPLATE_ID = "classic"


def get_template(template_id: str | None) -> Template:
    return TEMPLATES.get(template_id or "", TEMPLATES[DEFAULT_TEMPLATE_ID])


def list_templates() -> List[Dict[str, object]]:
    return [t.to_dict() for t in TEMPLATES.values()]
