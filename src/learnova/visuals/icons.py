"""
Icon library (Lucide, ISC licence) + keyword → icon matching + SVG/PNG rendering.

Used by the illustration engine and by the cards/diagrams in both the web deck
(inline SVG) and the PowerPoint (PNG pictures), so every concept gets a fitting
glyph instead of a bare number.
"""

from __future__ import annotations

import functools
import json
import pathlib
import re
from typing import Dict, List, Sequence

_ICON_FILE = pathlib.Path(__file__).with_name("icons.json")

# icon → trigger words (matched on word prefixes, case-insensitive)
_KEYWORDS: Dict[str, str] = {
    "book-open": "book read reading literature learn lesson textbook chapter study syllabus course curriculum",
    "lightbulb": "idea insight concept innovation creative thinking solution inspire",
    "brain": "brain memory cognitive mind neural learning psychology intelligence mental",
    "atom": "atom physics quantum particle molecule nuclear electron proton energy matter",
    "leaf": "plant leaf photosynthesis ecology environment nature green botany organic sustainab",
    "globe": "world global earth international geography country planet continent climate",
    "settings": "process system mechanism engine configure setting machine operation",
    "chart-column": "data statistic chart graph metric analytics revenue growth sales market result figure",
    "rocket": "launch startup space rocket mission growth boost accelerate",
    "clock": "time history timeline schedule duration deadline period age era",
    "heart": "heart health care cardio love wellbeing emotion mood",
    "shield-check": "security safe protect privacy safety compliance trust risk defence",
    "laptop": "computer software digital online technology laptop web app program coding",
    "flask-conical": "chemistry experiment laboratory lab reaction chemical hypothesis",
    "users": "people team group community society social audience customer student human population",
    "cloud": "cloud weather rain storage network internet hosting atmosphere",
    "search": "research search find discover investigate analysis explore inquiry",
    "target": "goal target objective aim focus strategy mission outcome",
    "calendar": "calendar date month year schedule annual event",
    "dollar-sign": "money cost price finance budget revenue profit economic dollar payment",
    "trophy": "win success achievement champion award competition result best",
    "trees": "forest tree wildlife habitat biodiversity ecosystem",
    "droplets": "water rain liquid ocean river hydro fluid moisture drop",
    "sun": "sun solar light day energy bright summer heat",
    "zap": "electric power voltage current energy fast lightning charge",
    "puzzle": "puzzle problem piece integrate component module fit logic",
    "key": "key access password unlock critical essential secret",
    "map-pin": "location place map site region address position",
    "smartphone": "mobile phone smartphone app device sms",
    "mail": "email mail message letter newsletter inbox",
    "graduation-cap": "education university degree graduate academic school college learning teaching",
    "microscope": "microscope cell biology bacteria virus specimen lab medical research",
    "dna": "dna gene genetic genome heredity evolution biology chromosome",
    "calculator": "calculate math arithmetic number equation compute algebra",
    "code": "code programming software developer algorithm script function syntax",
    "database": "database data storage sql record table query dataset",
    "network": "network connection internet protocol node link topology graph",
    "lock": "lock secure encryption private confidential authentication",
    "award": "award prize certificate honor merit recognition",
    "flag": "flag milestone goal nation country finish checkpoint",
    "compass": "direction navigation guide explore strategy orientation",
    "layers": "layer stack level tier architecture structure hierarchy foundation",
    "git-branch": "branch version decision fork pathway workflow option",
    "factory": "factory industry manufacture production industrial plant supply",
    "truck": "transport delivery logistics shipping freight supply chain",
    "building-2": "building company organization enterprise office city corporate",
    "landmark": "government bank institution law constitution politics democracy monument",
    "scale": "justice balance law legal fair ethic compare weigh",
    "gavel": "court judge legal law legislation verdict trial",
    "stethoscope": "doctor medical clinical patient diagnosis medicine hospital health",
    "pill": "drug pharma medicine treatment dose vaccine therapy",
    "activity": "pulse heartbeat activity monitor vital rhythm fitness signal",
    "apple": "nutrition food diet fruit eat healthy meal",
    "dumbbell": "exercise fitness workout muscle strength gym training sport",
    "bed": "sleep rest bed night recovery insomnia",
    "music": "music sound song audio rhythm melody acoustic",
    "palette": "art design color creative painting aesthetic visual",
    "camera": "photo camera image photograph picture capture",
    "film": "film movie video cinema media animation",
    "plane": "flight aviation aircraft airport travel aerospace",
    "car": "car vehicle automobile driving traffic automotive electric",
    "wifi": "wireless wifi signal connectivity broadcast",
    "cpu": "cpu processor hardware chip computing silicon architecture",
    "bot": "ai robot automation machine learning artificial chatbot agent",
    "sparkles": "ai generate magic new feature highlight quality",
    "message-circle": "communication conversation discussion feedback chat talk dialogue language",
    "megaphone": "marketing announce campaign advertise promote broadcast publicity",
    "handshake": "partnership agreement deal negotiation cooperation collaboration trade",
    "trending-up": "trend growth increase rise improvement progress profit upward",
    "chart-pie": "share proportion percentage portion distribution segment pie market-share",
    "coins": "coin economy currency saving cash income wealth",
    "wallet": "wallet payment budget spending personal-finance expense",
    "shopping-cart": "shopping retail purchase commerce ecommerce buy consumer",
    "store": "shop store retail market vendor business merchant",
    "house": "home house housing residential family property real-estate",
    "pencil": "write writing edit draft note author essay composition",
    "ruler": "measure measurement geometry length dimension scale unit",
    "telescope": "astronomy telescope star galaxy universe space observe",
    "magnet": "magnet magnetic attract force field pole",
    "thermometer": "temperature thermal heat fever degree warming climate",
    "mountain": "mountain geology terrain landscape peak altitude",
    "waves": "wave ocean sea tide frequency oscillation",
    "flame": "fire flame combustion burn heat fuel",
    "snowflake": "snow ice cold freeze winter cryo",
    "wind": "wind air breeze turbine aerodynamic",
    "recycle": "recycle waste reuse circular renewable sustainability",
    "battery-charging": "battery charge storage electric-vehicle power-bank",
    "circuit-board": "circuit electronics board electrical hardware engineering",
    "file-text": "document report paper file text record contract article",
    "clipboard-list": "checklist plan task survey audit inventory form",
    "list-checks": "checklist steps procedure requirement criteria tasks done",
    "bookmark": "bookmark save remember reference favorite",
    "eye": "vision see observe perception visual eye watch",
    "ear": "hearing listen sound audio ear",
    "hand-heart": "charity donate volunteer help support nonprofit care",
    "baby": "child infant baby development growth early",
    "scissors": "cut edit trim split divide",
    "wrench": "repair tool fix maintain maintenance engineering mechanic",
    "hammer": "build construct construction tool craft forge",
    "hourglass": "wait duration deadline patience delay timer",
    "infinity": "infinite endless loop continuous unlimited limit",
    "sigma": "sum summation statistics total sigma series",
    "triangle": "triangle geometry shape pythagoras angle trigonometry",
    "star": "star rating favorite top featured excellent",
    "moon": "moon night lunar orbit tide",
    "bell": "alert notification reminder alarm notice",
    "gift": "gift reward bonus present incentive",
    "languages": "language translation linguistic english grammar vocabulary",
    "map": "map route atlas geography territory",
    "route": "route path journey roadmap itinerary pipeline",
    "anchor": "anchor maritime stable foundation port",
    "ship": "ship vessel maritime shipping naval boat cargo",
    "bike": "bicycle cycling transport commute",
    "footprints": "footprint walk step trace trail carbon-footprint",
    "newspaper": "news media journalism press headline publication",
    "presentation": "presentation slide lecture talk keynote deck",
    "school": "school classroom teacher class pupil primary education",
    "library": "library archive collection reference books",
    "notebook-pen": "notes notebook journal study diary",
    "test-tube-diagonal": "test-tube sample assay experiment titration",
    "bug": "bug defect error debug insect pest",
    "alert-triangle": "warning danger caution hazard alert risk issue",
    "check-circle": "correct complete verified success approved valid",
    "arrow-right-left": "exchange swap compare trade transfer convert",
    "refresh-cw": "cycle refresh update renew iterate repeat",
    "repeat": "repeat loop iteration recurring again",
    "workflow": "workflow pipeline process flow automation sequence",
    "funnel": "funnel filter conversion pipeline screening narrowing",
    "gauge": "speed performance gauge benchmark efficiency level",
    "percent": "percent percentage rate discount ratio interest",
    "receipt": "invoice receipt bill expense accounting tax",
    "banknote": "cash banknote salary wage payment currency",
    "piggy-bank": "saving savings invest budget frugal",
    "building": "building structure architecture construction tower",
    "briefcase": "job career work business professional employment",
    "user-round": "person individual user profile identity customer",
    "crown": "leader king monarchy royal premium top rank",
    "medal": "medal rank honor second place podium",
}
_FALLBACK = ["lightbulb", "layers", "target", "sparkles", "book-open", "puzzle"]


@functools.lru_cache(maxsize=1)
def _icons() -> Dict[str, list]:
    try:
        return json.loads(_ICON_FILE.read_text())["icons"]
    except Exception:
        return {}


def has_icon(name: str) -> bool:
    return name in _icons()


@functools.lru_cache(maxsize=1)
def _index() -> List[tuple]:
    out = []
    for icon, words in _KEYWORDS.items():
        if icon in _icons():
            out.append((icon, [w.replace("-", "") for w in words.split()]))
    return out


def pick_icons(text: str, n: int = 4) -> List[str]:
    """The ``n`` best-fitting icon names for ``text`` (keyword prefix match, ties → rarer keyword)."""
    toks = [t.replace("-", "") for t in re.findall(r"[a-z][a-z\-]+", (text or "").lower())]
    score: Dict[str, float] = {}
    for icon, words in _index():
        for t in toks:
            for w in words:
                if len(t) >= 4 and (t.startswith(w[:max(4, len(w) - 2)]) or w.startswith(t[:max(4, len(t) - 2)])):
                    score[icon] = score.get(icon, 0.0) + 1.0 + (0.2 if t == w else 0.0)
                    break
    ranked = [i for i, _ in sorted(score.items(), key=lambda kv: -kv[1])]
    for f in _FALLBACK:
        if f in _icons() and f not in ranked:
            ranked.append(f)
    return ranked[:n]


def icon_group(name: str, x: float, y: float, size: float, stroke: str = "#1D4ED8", sw: float = 1.9) -> str:
    """An SVG <g> drawing icon ``name`` in a ``size``×``size`` box at (x, y)."""
    els = _icons().get(name) or _icons().get("lightbulb", [])
    s = size / 24.0
    body = []
    for tag, attrs in els:
        a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        body.append(f"<{tag} {a}/>")
    return (f'<g transform="translate({x:.2f} {y:.2f}) scale({s:.4f})" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{"".join(body)}</g>')


def svg_to_png(svg: str, width_px: int, height_px: int, alpha: bool = False) -> bytes:
    """Rasterise an SVG string with PyMuPDF (already a dependency)."""
    import fitz

    doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    page = doc[0]
    zoom = max(width_px / page.rect.width, 0.1)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=alpha)
    return pix.tobytes("png")


@functools.lru_cache(maxsize=512)
def icon_png(name: str, color: str = "#1D4ED8", px: int = 192) -> bytes:
    """A transparent PNG of one icon, for PowerPoint pictures."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 {px} {px}">'
           f'{icon_group(name, px * 0.08, px * 0.08, px * 0.84, color, 1.9)}</svg>')
    return svg_to_png(svg, px, px, alpha=True)


def icon_svg_inline(name: str, color: str, size: int = 28) -> str:
    """Self-contained <svg> for inlining in the web deck."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24">'
            f'{icon_group(name, 0, 0, 24, color, 1.9)}</svg>')


__all__ = ["pick_icons", "icon_group", "icon_png", "icon_svg_inline", "svg_to_png", "has_icon"]
