"""
The Learnova master prompt + visual taxonomy.

This drives the layout / structuring LLM call and is the single source of truth
for:

* the **visual library** — ~40 families x ~180 named variants x parametric axes
  (`docs/visual_catalog.yaml`), reaching 1000+ addressable visuals;
* **five decisions** the model makes per chunk: CONTENT, VISUAL
  (`family` / `variant` / `params`), per-sentence TEXT treatment, IMAGE handling,
  and PROGRESSIVE REVEAL (`animation.steps`);
* the strict JSON output schema.

The deterministic selectors — ``ai/visual_selector.py`` (VMS + animation
planner), ``ai/text_policy.py``, ``ai/image_policy.py`` — mirror the same rules
and are the validation / fallback layer: the LLM proposes, they check and can
override.

Design of record: ``docs/research/VISUAL_LIBRARY_MASTER_PROMPT.md``.
Nothing here calls a model — this module only builds strings and loads the
catalog.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

_CATALOG_PATH = Path(__file__).resolve().parents[3] / "docs" / "visual_catalog.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# Catalog loading
# ─────────────────────────────────────────────────────────────────────────────


@functools.lru_cache(maxsize=1)
def load_catalog() -> Dict[str, Any]:
    """Parse ``docs/visual_catalog.yaml``. Returns {} if unavailable."""
    try:
        import yaml

        with _CATALOG_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # pragma: no cover - missing pyyaml or file
        return {}


@functools.lru_cache(maxsize=1)
def _families() -> Dict[str, Dict[str, Any]]:
    return load_catalog().get("families", {}) or {}


FAMILY_KEYS: List[str] = sorted(_families().keys()) or [
    "TEXT", "DEFINITION", "QUOTE", "KPI", "LIST_STRUCTURED", "PROCESS_LINEAR",
    "PROCESS_CYCLIC", "DECISION", "STATE_MACHINE", "TIMELINE", "HIERARCHY_TREE",
    "HIERARCHY_NEST", "MIND_MAP", "COMPARE_TABLE", "COMPARE_VISUAL", "MATRIX_GRID",
    "SET_DIAGRAM", "CHART_CATEGORICAL", "CHART_TREND", "CHART_PART_TO_WHOLE",
    "CHART_DISTRIBUTION", "CHART_RELATIONSHIP", "CHART_RANKING", "CHART_FLOW",
    "CHART_SPATIAL", "CHART_SPECIAL", "FUNCTION_PLOT", "CALCULUS_VIZ",
    "LINEAR_ALGEBRA", "GEOMETRY", "NUMBER_LINE", "PROOF_LADDER", "ML_VIZ",
    "DATA_STRUCTURE", "ALGORITHM_TRACE", "CIRCUIT", "PHYSICS_DIAGRAM",
    "CHEM_DIAGRAM", "BIO_DIAGRAM", "MEDIA", "ANNOTATION_LAYER",
]


def variants_for(family: str) -> List[str]:
    fam = _families().get(family, {})
    return sorted((fam.get("variants") or {}).keys())


def catalog_entry(family: str, variant: str) -> Dict[str, Any]:
    return (_families().get(family, {}).get("variants") or {}).get(variant, {})


def default_variant(family: str) -> str:
    vs = variants_for(family)
    return vs[0] if vs else "default"


# ─────────────────────────────────────────────────────────────────────────────
# Flat "treatment" view — kept for the VMS scorer (ai/visual_selector.py)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Treatment:
    key: str
    family: str
    variant: str
    use_when: str


VISUAL_TREATMENTS: List[Treatment] = [
    Treatment("KEEP_TEXT", "TEXT", "keep",
              "wording is precision-critical (definition, theorem, quote, code, formula)"),
    Treatment("MINIMAL_TEXT", "TEXT", "minimal", "connected explanatory prose, no structure"),
    Treatment("BULLETS", "TEXT", "bullets", "3-8 discrete unrelated facts"),
    Treatment("DEFINITION", "DEFINITION", "term", "one term is introduced and defined"),
    Treatment("QUOTE", "QUOTE", "statement", "a single memorable statement / law / principle"),
    Treatment("METRIC", "KPI", "single", "one headline number is the message"),
    Treatment("FLOWCHART", "PROCESS_LINEAR", "flowchart", "ordered procedure, 3+ steps, may branch"),
    Treatment("CYCLE", "PROCESS_CYCLIC", "cycle", "a repeating process with no start or end"),
    Treatment("WORKED_EXAMPLE", "WORKED_EXAMPLE", "steps",
              "a problem solved step by step (a sum, a derivation, a proof) — "
              "each line follows from the last and every line stays on screen"),
    Treatment("TIMELINE", "TIMELINE", "dated", "3+ dated or strictly chronological events"),
    Treatment("COMPARISON_TABLE", "COMPARE_TABLE", "comparison",
              "two or more named things compared across the same aspects"),
    Treatment("PROS_CONS", "COMPARE_VISUAL", "pros_cons", "advantages vs disadvantages of ONE thing"),
    Treatment("MATRIX_2X2", "MATRIX_GRID", "quadrant_2x2", "items on two independent axes"),
    Treatment("PYRAMID", "HIERARCHY_NEST", "pyramid", "levels that build on or nest inside each other"),
    Treatment("VENN", "SET_DIAGRAM", "venn2", "2-3 sets with shared and unique members"),
    Treatment("MIND_MAP", "MIND_MAP", "radial", "one central concept fanning into loose branches"),
    Treatment("CARD_GRID", "LIST_STRUCTURED", "cards", "3-4 parallel pillars of equal weight"),
    Treatment("BAR_CHART", "CHART_CATEGORICAL", "bar", "quantities compared across categories"),
    Treatment("LINE_CHART", "CHART_TREND", "line", "a quantity changing over an ordered dimension"),
    Treatment("PIE_CHART", "CHART_PART_TO_WHOLE", "pie", "parts of a single whole summing to ~100%"),
    Treatment("IMAGE_FOCUS", "MEDIA", "image_focus", "a supplied figure IS the content"),
    Treatment("FUNCTION_PLOT", "FUNCTION_PLOT", "curve", "a mathematical function y = f(x) to plot"),
    Treatment("ML_VIZ", "ML_VIZ", "regression_fit", "fitting a model to data / residuals / a loss curve"),
    Treatment("ALGORITHM_TRACE", "ALGORITHM_TRACE", "sort_bars", "an algorithm walked step by step over data"),
    Treatment("DATA_STRUCTURE", "DATA_STRUCTURE", "array", "the shape of a data structure (array, list, tree)"),
    Treatment("GEOMETRY", "GEOMETRY", "labelled_figure", "a geometric figure with labelled sides or angles"),
]

TREATMENT_KEYS: List[str] = [t.key for t in VISUAL_TREATMENTS]
TREATMENT_TO_FAMILY: Dict[str, tuple] = {t.key: (t.family, t.variant) for t in VISUAL_TREATMENTS}


# ─────────────────────────────────────────────────────────────────────────────
# Image-handling policy (mirrored in ai/image_policy.py)
# ─────────────────────────────────────────────────────────────────────────────

IMAGE_ACTIONS = {
    "KEEP_AS_IS": "clear, relevant photo/illustration/figure — show unchanged with a caption",
    "SUMMARISE_TO_STRUCTURE": "the picture is really a diagram/table/chart — rebuild it as a "
                              "native Learnova visual and drop the bitmap",
    "ENHANCE": "relevant but low-resolution / noisy — keep, flag for upscaling",
    "REGENERATE": "decorative / stock / watermarked — replace with a generated illustration",
    "CAPTION_ONLY": "cannot show it but its information matters — carry only the extracted text",
    "DROP": "logo / divider / bullet icon / pure decoration — remove it",
    "NONE": "no image on this slide",
}


# ─────────────────────────────────────────────────────────────────────────────
# The master prompt
# ─────────────────────────────────────────────────────────────────────────────


def _family_catalogue_block() -> str:
    fams = _families()
    if not fams:
        return "\n".join(f"- {k}" for k in FAMILY_KEYS)
    lines: List[str] = []
    for name in FAMILY_KEYS:
        fam = fams.get(name, {})
        variants = fam.get("variants") or {}
        vlist = ", ".join(sorted(variants.keys())) or "default"
        domain = fam.get("domain", "")
        lines.append(f"- {name} ({domain}). variants: {vlist}")
    return "\n".join(lines)


FAMILY_CATALOGUE = _family_catalogue_block()


MASTER_SYSTEM_PROMPT = f"""\
You are Learnova's Master Instructional Designer. You convert ONE chunk of raw
lecture material (text, notes, and any OCR of an embedded figure) into ONE
structured, teachable slide with a step-by-step reveal plan.

Return ONE strict JSON object and nothing else. Make FIVE decisions.

================ DECISION 1 - CONTENT (never lose a teachable point) ================
- You are RESTRUCTURING, not summarising. Every distinct fact, definition, figure,
  step, comparison, coordinate and example in the input must survive as its own
  bullet or structural element. Do not cap the list; a later stage paginates
  overflow. Remove ONLY: exact repetition, filler, and the slide's own title.
- Preserve VERBATIM: numbers, currency, dates, units, formulae, proper nouns,
  defined terms, quoted sentences, code.
- Write ONE high-yield "takeaway" sentence, or "" if there is no single lesson.
- PLAIN TEXT ONLY in every string. No markdown, asterisks, or backticks.
- NEVER invent data. If the numbers/dates/coordinates a chart needs are not in
  the source, do not choose that chart.

================ DECISION 2 - VISUAL (family / variant / params) ================
Pick the ONE visual whose STRUCTURE matches the content's structure, not its
keywords. Output "family", "variant", and "params". If nothing structural fits,
use family "TEXT" (variant "keep" for precision-critical wording, else "minimal").
A forced diagram is worse than clean text.

Families and their variants:
{FAMILY_CATALOGUE}

params (include only those that apply):
  orientation: horizontal|vertical|radial|isometric
  cardinality: tiny|small|medium|large|dense
  emphasis: neutral|highlight|ranked|threshold|delta
  data_mode: schematic|data_driven|hybrid
  dimensionality: 1d|2d|2.5d|3d
  highlight: [element ids or labels to call out]
  annotations: [{{"type":"callout_pin|spotlight|magnifier|dimension_line|attention_arrow","anchor":"","text":""}}]

DO NOT choose a visual when: the wording is exact (-> TEXT.keep); <3 structured
elements with no relation (-> TEXT or LIST_STRUCTURED); the chart's data is absent
from the source; a diagram would imply order/loop/causation that is not stated.

Provide the structured data the chosen visual needs in the ONE matching
sub-object of "data" and OMIT all the others.

================ DECISION 3 - TEXT TREATMENT PER SENTENCE ================
For each source sentence: VERBATIM (definition/theorem/quote/legal/code/formula),
TIGHTEN (wordy prose -> punchy bullet), or MERGE (near-duplicates). Put every
verbatim-critical sentence in "verbatim" so later trimming never touches it.

================ DECISION 4 - IMAGE HANDLING ================
Choose one "image_action": KEEP_AS_IS | SUMMARISE_TO_STRUCTURE | ENHANCE |
REGENERATE | CAPTION_ONLY | DROP | NONE. If a diagram/chart image really carries
structured data, choose SUMMARISE_TO_STRUCTURE and re-express it as a native
visual above.

================ DECISION 5 - PROGRESSIVE REVEAL / ANIMATION ================
Build "animation": an ordered "steps" list that walks a presenter through the
slide one click at a time. Each element you draw has a dotted id (axis.x, pt.3,
line.bestfit, eq, row.2, node.n4, bar.1). A step lists the ids it "adds", any
"transforms", ids to "focus" (others dim), ids to "removes", an "effect"
(fade|draw|grow|pop|count-up|trace|slide-left), and "wait_for" ("click" unless
the motion is inherently continuous, then "auto").

Rules:
- One idea per step. A set is one step only if read as a unit (a table header
  row, both halves of a Venn).
- Never reorder content. Steps follow reading order (top->bottom, left->right,
  chronological, base->apex, algorithm order).
- Scaffolding first (axes, containers, skeletons); labels and equations AFTER the
  thing they describe; the takeaway/QED/equation is ALWAYS the final step.
- Indivisible visuals (QUOTE, KPI, single DEFINITION) = exactly one step.
- Max 7 steps. If more are needed, keep the 7 highest-value and put the rest on
  a continuation slide.
- mode: "build" for anything instructional; "animate" only for inherently moving
  things (wave, orbit, pendulum, auto-playing gradient descent); "static" if the
  source implies no walk-through (then one step with everything).
- effect must match meaning: draw for curves/paths, grow for bars, count-up for
  metrics, pop for scatter, trace for pointers/arrows, fade otherwise.

================ OUTPUT - return ONLY this JSON ================
{{
  "title": "Clean, specific slide title",
  "takeaway": "One high-yield sentence or empty string",
  "bullets": ["every teachable point, tightened but complete"],
  "verbatim": ["sentences that must never be edited or trimmed"],

  "family": "<one FAMILY>",
  "variant": "<one variant of that family>",
  "params": {{"orientation":"","cardinality":"","emphasis":"","data_mode":"",
             "dimensionality":"","highlight":[],"annotations":[]}},

  "image_action": "<KEEP_AS_IS|SUMMARISE_TO_STRUCTURE|ENHANCE|REGENERATE|CAPTION_ONLY|DROP|NONE>",
  "image_caption": "Caption if an image is kept, else empty",

  "data": {{
    "flowchart":   {{"nodes":[{{"id":"n1","label":"","type":"start|process|decision|end"}}],"edges":[{{"from":"n1","to":"n2","condition":""}}]}},
    "cycle":       {{"stages":["",""]}},
    "timeline":    {{"events":[{{"date":"","title":"","description":"","is_milestone":false}}]}},
    "table":       {{"headers":["Aspect","A","B"],"rows":[["","",""]],"highlight_cells":[{{"row":0,"col":1}}]}},
    "pros_cons":   {{"pros":[""],"cons":[""]}},
    "matrix":      {{"x_axis":"","y_axis":"","quadrants":{{"q1":[""],"q2":[""],"q3":[""],"q4":[""]}}}},
    "pyramid":     {{"levels":["base","","apex"]}},
    "venn":        {{"sets":["A","B"],"only_a":[""],"only_b":[""],"shared":[""]}},
    "mind_map":    {{"central":"","branches":[{{"name":"","children":[""]}}]}},
    "chart":       {{"chart_type":"bar|line|pie|scatter|area|radar","x_axis":"","y_axis":"","categories":[""],"series":[{{"name":"","values":[0]}}],"points":[{{"x":0,"y":0,"label":""}}]}},
    "metric":      {{"value":"","label":"","description":""}},
    "definition":  {{"term":"","definition":"","examples":[""]}},
    "function_plot":{{"expr":"","domain":[0,10],"key_points":[{{"x":0,"y":0,"label":""}}],"family_param":null,"param_values":[]}},
    "geometry":    {{"kind":"labelled_figure|construction|transformation","shape":"","vertices":[[0,0]],"labels":[{{"on":"edge|angle|vertex","ref":"","text":""}}],"steps":[]}},
    "proof":       {{"kind":"statement_reason|derivation_chain","rows":[{{"statement":"","reason":""}}]}},
    "ml_viz":      {{"kind":"regression_fit|decision_boundary|gradient_descent|loss_curve|kmeans|bias_variance","points":[{{"x":0,"y":0,"class":null}}],"candidate_models":[{{"slope":0,"intercept":0}}],"chosen":{{"slope":0,"intercept":0}},"show_residuals":true,"equation":"","loss":{{"epochs":[],"train":[],"val":[]}}}},
    "data_structure":{{"kind":"array|linked_list|stack_queue|binary_tree|hash_table|graph","cells":[{{"id":"","value":""}}],"links":[{{"from":"","to":""}}],"pointers":[{{"name":"","at":""}}]}},
    "algorithm_trace":{{"kind":"sort_bars|pointer_walk|recursion_tree|dp_table|call_stack","initial":[0],"steps":[{{"op":"compare|swap|mark|recurse|return|fill","args":[0]}}]}},
    "circuit":     {{"components":[{{"id":"","type":"R|L|C|V|diode|npn|gate_and","value":"","nodes":["",""]}}],"wires":[["",""]]}},
    "physics":     {{"kind":"free_body|ray_optics|wave|field_lines|energy_bar","object":"","forces":[{{"label":"","mag":0,"angle_deg":0}}]}},
    "chem":        {{"kind":"molecule_2d|mechanism|energy_profile|titration_curve","atoms":[{{"el":"C","xy":[0,0]}}],"bonds":[{{"a":0,"b":1,"order":1}}],"arrows":[{{"from":"","to":""}}]}},
    "bio":         {{"kind":"anatomy_labelled|punnett|food_web|phylo_tree","labels":[{{"part":"","anchor":""}}],"parent_alleles":["",""]}},
    "list":        {{"style":"checklist|ranked|do_dont|steps|cards","items":[{{"text":"","group":"do|dont|null"}}]}},
    "hierarchy":   {{"kind":"org_chart|taxonomy|pyramid|treemap","root":"","edges":[{{"parent":"","child":""}}],"values":{{}}}}
  }},

  "animation": {{
    "mode": "build|animate|static",
    "steps": [
      {{"id":"s1","label":"what the presenter says","adds":["axis.x","axis.y"],
        "transforms":[],"focus":[],"removes":[],"effect":"fade",
        "duration_ms":400,"stagger_ms":60,"wait_for":"click"}}
    ]
  }}
}}

If you cannot produce valid JSON, retry with the minimal shape:
{{"title":"","takeaway":"","bullets":[""],"verbatim":[],"family":"TEXT",
 "variant":"minimal","params":{{}},"image_action":"NONE","image_caption":"",
 "data":{{}},"animation":{{"mode":"static","steps":[{{"id":"s1","label":"","adds":["all"],"effect":"fade","wait_for":"click"}}]}}}}
"""


MASTER_RETRY_PROMPT = """\
Return ONLY a JSON object, no prose, no code fences:
{"title":"","takeaway":"","bullets":[""],"verbatim":[],"family":"TEXT",
 "variant":"minimal","params":{},"image_action":"NONE","image_caption":"",
 "data":{},"animation":{"mode":"static","steps":[{"id":"s1","label":"","adds":["all"],"effect":"fade","wait_for":"click"}]}}
"""


def build_user_prompt(text: str, title: str = "", image_ocr: str = "") -> str:
    """Assemble the per-chunk user message for the master prompt."""
    parts = [f"SLIDE TITLE: {title or '(none given)'}", "", "SOURCE TEXT:", (text or "").strip()]
    if (image_ocr or "").strip():
        parts += ["", "OCR / DESCRIPTION OF THE EMBEDDED FIGURE:", image_ocr.strip()]
    return "\n".join(parts)


def treatment_help() -> Dict[str, str]:
    """treatment key -> one-line guidance (for docs / the studio UI)."""
    return {t.key: t.use_when for t in VISUAL_TREATMENTS}


__all__ = [
    "Treatment",
    "VISUAL_TREATMENTS",
    "TREATMENT_KEYS",
    "TREATMENT_TO_FAMILY",
    "FAMILY_KEYS",
    "FAMILY_CATALOGUE",
    "IMAGE_ACTIONS",
    "MASTER_SYSTEM_PROMPT",
    "MASTER_RETRY_PROMPT",
    "load_catalog",
    "variants_for",
    "catalog_entry",
    "default_variant",
    "build_user_prompt",
    "treatment_help",
]
