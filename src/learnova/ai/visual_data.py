"""
LLM structured-data extraction for a chosen visual family.

The VMS (``ai/visual_selector.py``) decides *which* visual a slide should be —
``build_family_data`` then tries to pull the structured payload the renderer
needs straight out of the text with regex heuristics. That works for ~13
families; the rest (charts, a 2x2 matrix, a comparison table, a mind map, a
proper timeline with dates) need a real read of the content.

This module does that read with one compact LLM call: given the slide text and
the target family, return exactly the JSON shape ``rendering/family_blocks``
expects. It is:

  * **used only as a fallback** — the deck director calls it when the heuristic
    extractor came back empty and the family was chosen with real confidence;
  * **degrading** — no provider, a bad parse, or a shape mismatch ⇒ ``{}`` and
    the slide falls back to a bullet list;
  * **bounded** — one call per visual slide, capped by the caller.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from learnova.logging_config import logger
from learnova.providers.router import TASK_VISUAL_DATA, get_router

# family -> (what to extract, a JSON example of the exact shape the renderer wants)
_SCHEMA: Dict[str, tuple[str, str]] = {
    "CHART_CATEGORICAL": (
        "the quantity for each named category",
        '{"points":[{"label":"Coal","value":36},{"label":"Gas","value":23}]}',
    ),
    "CHART_RANKING": (
        "each item and its value, largest first",
        '{"points":[{"label":"Item A","value":80},{"label":"Item B","value":45}]}',
    ),
    "CHART_TREND": (
        "the value at each ordered point in time (keep chronological order)",
        '{"points":[{"label":"2019","value":10},{"label":"2020","value":14}]}',
    ),
    "CHART_PART_TO_WHOLE": (
        "each part and its share of the whole (values should roughly sum to 100)",
        '{"points":[{"label":"Rent","value":40},{"label":"Food","value":25}]}',
    ),
    "MATRIX_GRID": (
        "the two axis labels and the four quadrants",
        '{"x_axis":["Low effort","High effort"],"y_axis":["Low impact","High impact"],'
        '"quadrants":[{"title":"Quick wins","items":["..."]},{"title":"Major projects","items":[]},'
        '{"title":"Fill-ins","items":[]},{"title":"Thankless tasks","items":[]}]}',
    ),
    "COMPARE_TABLE": (
        "the column headers and each row of the comparison",
        '{"headers":["Aspect","Option A","Option B"],"rows":[["Cost","Low","High"],["Speed","Fast","Slow"]]}',
    ),
    "MIND_MAP": (
        "the central concept and its main branches",
        '{"center":"Photosynthesis","branches":["Light reactions","Calvin cycle","Chlorophyll","Products"]}',
    ),
    "TIMELINE": (
        "each dated event in order",
        '{"events":[{"date":"1969","title":"ARPANET goes live"},{"date":"1989","title":"WWW proposed"}]}',
    ),
    "COMPARE_VISUAL": (
        "the advantages and the drawbacks of the one subject",
        '{"pros":["Cheap to run","No emissions"],"cons":["Intermittent","Noisy"]}',
    ),
    "HIERARCHY_NEST": (
        "the levels from top/most-specific to bottom/foundation",
        '{"levels":["Self-actualisation","Esteem","Belonging","Safety","Physiological"]}',
    ),
    "LIST_STRUCTURED": (
        "each pillar as a heading plus a one-line body",
        '{"cards":[{"heading":"Reliability","body":"..."},{"heading":"Scalability","body":"..."}]}',
    ),
    "PROCESS_LINEAR": (
        "the ordered steps, each a short phrase",
        '{"steps":["Gather requirements","Design","Build","Test","Deploy"]}',
    ),
    "PROCESS_CYCLIC": (
        "the repeating stages, each a short phrase",
        '{"stages":["Plan","Do","Check","Act"]}',
    ),
    "WORKED_EXAMPLE": (
        "each line of the solution in order, with the reason for the step",
        '{"rows":[{"step":"2x + 3 = 11","reason":"start"},{"step":"2x = 8","reason":"subtract 3"},'
        '{"step":"x = 4","reason":"divide by 2"}]}',
    ),
    "SET_DIAGRAM": (
        "the members, noting which are shared and which are unique",
        '{"items":["Shared: warm-blooded","Only mammals: fur","Only birds: feathers"]}',
    ),
    "DEFINITION": (
        "the term and its precise definition, plus any clarifying notes",
        '{"term":"Entropy","definition":"a measure of disorder in a system","notes":["Always increases in an isolated system"]}',
    ),
}

# Families whose data extraction is worth an LLM call when the heuristic failed.
LLM_EXTRACTABLE = frozenset(_SCHEMA)

_SYSTEM = """\
You extract structured data for a slide visual. You are given the slide text and
the visual type. Return ONLY a JSON object in exactly the shape shown — same
keys, same nesting. Rules:
- Use ONLY facts present in the slide text. Do not invent numbers or items.
- Numbers must be plain (36 not "36%").
- Keep the original order of steps / events / time points.
- If the text genuinely does not contain what this visual needs, return {}.
No prose, no markdown fences — just the JSON object."""


def _provider():
    try:
        r = get_router()
        return r if r.available else None
    except Exception:
        return None


def _parse(raw: str) -> Optional[dict]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except (ValueError, json.JSONDecodeError):
        return None


def _looks_populated(family: str, data: dict) -> bool:
    if not data:
        return False
    if family.startswith("CHART_"):
        return len(data.get("points") or []) >= 2
    if family == "MATRIX_GRID":
        return len(data.get("quadrants") or []) >= 3
    if family == "COMPARE_TABLE":
        return len(data.get("headers") or []) >= 2 and len(data.get("rows") or []) >= 2
    if family == "MIND_MAP":
        return bool(data.get("center")) and len(data.get("branches") or []) >= 2
    if family == "TIMELINE":
        return len(data.get("events") or []) >= 2
    if family == "COMPARE_VISUAL":
        return bool(data.get("pros")) and bool(data.get("cons"))
    if family == "HIERARCHY_NEST":
        return len(data.get("levels") or []) >= 3
    if family == "LIST_STRUCTURED":
        return len(data.get("cards") or []) >= 3
    if family in {"PROCESS_LINEAR", "PROCESS_CYCLIC"}:
        return len(data.get("steps") or data.get("stages") or []) >= 3
    if family == "WORKED_EXAMPLE":
        return len(data.get("rows") or data.get("steps") or []) >= 2
    if family == "SET_DIAGRAM":
        return len(data.get("items") or []) >= 2
    if family == "DEFINITION":
        return bool(data.get("definition"))
    return bool(data)


def extract_family_data(text: str, title: str, family: str) -> Dict[str, Any]:
    """Return the renderer-ready ``data`` dict for ``family``, or ``{}``."""
    spec = _SCHEMA.get(family)
    if not spec or not (text or "").strip():
        return {}
    provider = _provider()
    if provider is None:
        return {}

    what, example = spec
    prompt = (
        f"Visual type: {family}\n"
        f"Extract: {what}\n"
        f"Exact JSON shape to return:\n{example}\n\n"
        f"Slide title: {title}\n"
        f"Slide text:\n{text[:1400]}"
    )
    try:
        raw = provider.generate(
            prompt=prompt, system_prompt=_SYSTEM,
            task=TASK_VISUAL_DATA, temperature=0.1, max_tokens=500, timeout=25.0,
        )
    except Exception as exc:
        logger.info("visual_data: extraction call failed for %s (%s)", family, exc)
        return {}

    data = _parse(raw) or {}
    if not _looks_populated(family, data):
        return {}
    logger.info("visual_data: LLM filled %s (%d keys)", family, len(data))
    return data


__all__ = ["extract_family_data", "LLM_EXTRACTABLE"]
