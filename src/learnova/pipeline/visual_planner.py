"""
Deterministic visual planning — the bridge that finally wires the
``intelligence`` and ``visual_specs`` packages into the runtime pipeline.

Given a chunk of text, this decides whether it *should* be a flowchart, a
comparison table, KPI cards, a timeline or an icon grid, and emits a
renderable layout dict. No LLM, no API key, no network.

Why this exists
---------------
The layout router asks an LLM to classify each chunk and falls back to keyword
heuristics when the call fails. Neither path could ever produce a *real*
flowchart: the fallback emitted a hardcoded three-node placeholder.

Meanwhile ``intelligence/`` already extracts steps, comparisons, statistics and
chronology from raw text, and ``visual_specs/`` already turns those into proper
node/edge specifications — but nothing called them.

This module runs that machinery and converts its output into the flat dict
shape the PPTX and HTML builders consume. It matters most for typed syllabus
input, which has no images or charts of its own, so structure is the only
visual richness available.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from learnova.logging_config import logger
from learnova.parsers.schema import SlidePageEntity, TextBlockElement
from learnova.textutils import (
    clean_bullet,
    dedupe_bullets,
    is_redundant,
    strip_inline_markdown,
    truncate_words,
)

# Minimum steps before a sequence is worth drawing as a flowchart.
_MIN_FLOW_STEPS = 3
# Minimum numeric findings before KPI cards beat a bullet list.
_MIN_KPI_METRICS = 2


def _build_slide_entity(title: str, text: str, slide_id: int = 0) -> SlidePageEntity:
    """Adapt a plain text chunk into the entity the intelligence engine wants."""
    blocks: List[TextBlockElement] = []
    order = 0

    if title:
        blocks.append(
            TextBlockElement(
                id=f"s{slide_id}_tb_{order}",
                text=title,
                is_heading=True,
                heading_level=1,
                reading_order=order,
            )
        )
        order += 1

    for line in (text or "").splitlines():
        # Callers may pass raw markdown (list markers intact) or text that has
        # already been through the chunker (markers stripped). Normalise both,
        # otherwise the step extractor misses bulleted procedures entirely.
        stripped = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line).strip()
        if not stripped:
            continue
        blocks.append(
            TextBlockElement(
                id=f"s{slide_id}_tb_{order}",
                text=stripped,
                is_heading=False,
                bullet_level=1,
                reading_order=order,
            )
        )
        order += 1

    return SlidePageEntity(
        id=slide_id,
        unit_number=slide_id + 1,
        title=title or "",
        text_blocks=blocks,
    )


def _clean(label: str, limit: int = 60) -> str:
    """Trim a bullet down to something that fits inside a node box."""
    text = clean_bullet(label).strip(" .;:")
    return truncate_words(text, limit) if len(text) > limit else text


# A quantity as a reader would write it: optional currency, thousands
# separators, optional decimals, optional unit. The old pattern was `\d+` with
# no separator support, so it read "$250,000" as **250** and "₹50,000" as
# **50** — then displayed that as the headline figure of the slide.
_QUANTITY = re.compile(
    r"(?P<currency>[$₹€£¥]\s?)?"
    r"(?P<number>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s?(?P<unit>%|percent|percentage|x|k|bn|mn|m|cr|crore|lakh|"
    r"years?|yrs?|months?|days?)?",
    re.I,
)


def extract_quantity(text: str) -> str:
    """
    Pull the headline figure out of a statistic, keeping it intact.

    Returns "" when the text carries no quantity, which the caller must treat
    as "this is not a metric slide" rather than substituting a placeholder.
    """
    match = _QUANTITY.search(strip_inline_markdown(text or ""))
    if not match:
        return ""
    value = (match.group("currency") or "").strip() + match.group("number")
    unit = match.group("unit") or ""
    if unit:
        value += "" if unit in {"%"} else " "
        value += unit
    return value.strip()


def _mermaid_from_flowchart(spec: Dict[str, Any]) -> str:
    """Render a FlowchartSpec dict as Mermaid for the HTML web deck."""
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    if not nodes:
        return "graph TD\n  A[Start] --> B[End]"

    orientation = spec.get("orientation") or "TD"
    if orientation not in {"TD", "TB", "LR", "RL"}:
        orientation = "TD"

    alias = {node["id"]: f"N{i}" for i, node in enumerate(nodes)}
    lines = [f"graph {orientation}"]

    for node in nodes:
        label = re.sub(r"[\[\]{}()\"|]", "", str(node.get("label", "")))[:48] or "Step"
        shape = node.get("type", "process")
        if shape == "decision":
            lines.append(f"  {alias[node['id']]}{{{label}}}")
        elif shape in {"start", "end"}:
            lines.append(f"  {alias[node['id']]}([{label}])")
        else:
            lines.append(f"  {alias[node['id']]}[{label}]")

    for edge in edges:
        src, dst = alias.get(edge.get("from")), alias.get(edge.get("to"))
        if not src or not dst:
            continue
        condition = re.sub(r"[\[\]{}()\"|]", "", str(edge.get("condition") or ""))[:20]
        lines.append(f"  {src} -->|{condition}| {dst}" if condition else f"  {src} --> {dst}")

    return "\n".join(lines)


def plan_visual(title: str, text: str, slide_id: int = 0) -> Optional[Dict[str, Any]]:
    """
    Analyse one chunk and return a renderable layout dict, or None.

    Returning None means "nothing structural found here" and the caller should
    keep whatever the LLM/heuristic router decided.
    """
    if not (text or "").strip():
        return None

    try:
        from learnova.intelligence.engine import SlideIntelligenceEngine
    except Exception as exc:
        logger.warning("intelligence engine unavailable (%s)", exc)
        return None

    entity = _build_slide_entity(title, text, slide_id)

    try:
        intel = SlideIntelligenceEngine().analyze_slide(entity)
    except Exception as exc:
        logger.warning("slide intelligence failed for %r: %s", title[:40], exc)
        return None

    steps = [s for s in (intel.steps or []) if s.strip()]
    processes = [p for p in (intel.processes or []) if p.strip()]
    sequence = steps or processes
    comparisons = intel.comparisons or []
    stats = intel.numbers_and_statistics or []
    chronology = intel.chronology or []

    # ── 1. Flowchart — an ordered procedure ──────────────────────────────────
    if len(sequence) >= _MIN_FLOW_STEPS:
        try:
            from learnova.visual_specs.flowchart_spec import build_flowchart_spec

            spec = build_flowchart_spec(intel).to_dict()
        except Exception as exc:
            logger.warning("flowchart spec build failed: %s", exc)
            spec = None

        labels = [
            _clean(n.get("label", ""))
            for n in (spec or {}).get("nodes", [])
            if _clean(n.get("label", ""))
        ] or [_clean(s) for s in sequence[:6]]

        result: Dict[str, Any] = {
            "layout_type": "FLOWCHART",
            "title": title or intel.main_topic or "Process",
            "bullets": labels[:6],
            "takeaway": intel.learning_objective or "Follow the steps in order.",
            "mermaid_code": _mermaid_from_flowchart(spec) if spec else "",
            "visual_source": "intelligence",
        }
        if spec:
            result["flowchart_spec"] = spec
        if not result["mermaid_code"]:
            chain = " --> ".join(
                f"N{i}[{re.sub(r'[\\[\\]{}()\"|]', '', lbl)[:40]}]"
                for i, lbl in enumerate(labels[:6])
            )
            result["mermaid_code"] = f"graph TD\n  {chain}"
        return result

    # ── 2. Timeline — dated or chronological events ──────────────────────────
    if len(chronology) >= _MIN_FLOW_STEPS:
        return {
            "layout_type": "FLOWCHART",
            "title": title or "Timeline",
            "bullets": [_clean(c) for c in chronology[:6]],
            "takeaway": intel.learning_objective or "Events in chronological order.",
            "mermaid_code": "graph LR\n  "
            + " --> ".join(
                f"T{i}[{re.sub(r'[\\[\\]{}()\"|]', '', _clean(c))[:32]}]"
                for i, c in enumerate(chronology[:6])
            ),
            "visual_source": "intelligence",
        }

    # ── 3. Comparison table ──────────────────────────────────────────────────
    if comparisons:
        rows: List[List[str]] = []
        for item in comparisons[:6]:
            if isinstance(item, dict):
                left = _clean(str(item.get("item_a") or item.get("left") or ""), 40)
                right = _clean(str(item.get("item_b") or item.get("right") or ""), 40)
                basis = _clean(str(item.get("aspect") or item.get("basis") or ""), 40)
                # Quality gate: a comparison is only worth a table if both
                # sides are present and neither is a truncated run-on. A bare
                # connector ("vs", "versus") is not a real aspect. Shipping a
                # malformed table is worse than shipping a clean bullet list.
                if not left or not right:
                    continue
                if len(left) > 38 or len(right) > 38:
                    continue
                if basis.lower() in {"vs", "versus", "and", "or", "than", "whereas", ""}:
                    basis = "Aspect"
                rows.append([basis, left, right])
        if rows:
            return {
                "layout_type": "TABLE",
                "title": title or "Comparison",
                "table_headers": ["Aspect", "Option A", "Option B"],
                "table_rows": rows,
                "bullets": [],
                "takeaway": intel.learning_objective or "Compare the options side by side.",
                "visual_source": "intelligence",
            }

    # ── 4. KPI / metric callout ──────────────────────────────────────────────
    if len(stats) >= _MIN_KPI_METRICS:
        primary = str(stats[0])
        value = extract_quantity(primary)
        # A metric slide devotes the whole canvas to one number. If no real
        # quantity can be read out, there is nothing to headline — fall through
        # to a bullet layout rather than printing "Key Stat" or "n/a" in 40pt.
        if value:
            return {
                "layout_type": "METRIC",
                "title": title or "Key Metric",
                "metric_value": value[:16],
                "metric_label": title or intel.main_topic or "Metric",
                "metric_desc": _clean(primary, 120),
                "bullets": dedupe_bullets([_clean(s, 80) for s in stats[1:4]]),
                # No filler takeaway: an empty string drops the bar entirely,
                # which reads better than "Note the headline figures."
                "takeaway": intel.learning_objective or "",
                "visual_source": "intelligence",
            }

    # ── 5. Icon grid for a set of distinct concepts ──────────────────────────
    concepts = dedupe_bullets([_clean(c, 70) for c in (intel.key_concepts or [])])
    # Drop concepts that merely restate the slide title — the grid was filling
    # with three paraphrases of its own heading.
    concepts = [c for c in concepts if not is_redundant(c, [title or ""])]
    if len(concepts) >= 3:
        return {
            "layout_type": "CARD_GRID",
            "title": title or intel.main_topic or "Key Concepts",
            "bullets": concepts[:4],
            "takeaway": intel.learning_objective or "",
            "visual_source": "intelligence",
        }

    return None


def enrich_deck(improved: List[dict]) -> int:
    """
    Upgrade slides in place where deterministic analysis beats the router.

    We only override when the router produced nothing structural
    (``MINIMAL_TEXT``) or when it guessed ``FLOWCHART`` without real node data —
    an LLM result that already carries a genuine table or metric is left alone.
    """
    upgraded = 0

    for index, entry in enumerate(improved):
        current = entry.get("improved") or {}
        layout = str(current.get("layout_type", "MINIMAL_TEXT")).upper()

        # The extractive summariser (no-LLM path) already produced clean,
        # scored bullets and a conservative layout — do not re-derive from the
        # raw section text (that reintroduces the title-in-first-bullet bug and
        # over-eager FLOWCHART routing).
        if current.get("visual_source") == "extractive":
            continue

        # The router's fallbacks emit recognisable placeholders: a flowchart
        # with no node data, or a metric literally labelled "Key Stat". Those
        # are worth re-deriving; a genuine LLM result is not.
        placeholder_flow = layout == "FLOWCHART" and not current.get("flowchart_spec")
        placeholder_metric = layout == "METRIC" and str(
            current.get("metric_value", "")
        ).strip().lower() in {"", "key stat", "100%"}

        if (
            layout not in {"MINIMAL_TEXT", "CARD_GRID"}
            and not placeholder_flow
            and not placeholder_metric
        ):
            continue

        original = entry.get("original") or {}
        text = original.get("text") or "\n".join(current.get("bullets") or [])
        title = current.get("title") or original.get("title") or ""

        planned = plan_visual(title, text, slide_id=index)
        if not planned:
            continue

        # Preserve anything the router produced that the planner has no view on.
        for key in ("question", "options", "correct", "explanation"):
            if key in current:
                planned[key] = current[key]

        entry["improved"] = planned
        upgraded += 1

    if upgraded:
        logger.info("visual planner upgraded %d slide(s) to structured visuals", upgraded)
    return upgraded


__all__ = ["plan_visual", "enrich_deck"]
