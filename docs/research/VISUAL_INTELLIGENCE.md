# Visual Intelligence layer — design & status

Answers the three questions raised on the deck:

1. **"Why only flowchart?"** — the LLM prompt only offered 5 layouts and the
   renderers only drew 5, even though `visual_specs/` already builds charts,
   timelines, mind maps, pyramids, SmartArt, etc. This layer opens all of them.
2. **When to keep text as-is vs restructure.**
3. **When to summarise / keep / enhance an image.**

Plus a fourth capability the lecturer asked for: **progressive reveal** —
showing a slide one idea at a time.

---

## 1. Components (this session)

| Module | Role | Tests |
|---|---|---|
| `ai/master_prompt.py` | The single engineered system prompt. 20-treatment taxonomy, verbatim rules, image actions, `reveal_groups`, rich JSON schema. | `test_visual_intelligence.py` |
| `ai/visual_selector.py` | **VMS** — deterministic "which visual, when". Scores every treatment from text features, returns treatment + confidence + rationale + reveal segmentation. Validation layer + full fallback for the LLM. | ✓ |
| `ai/text_policy.py` | Per-sentence VERBATIM / TIGHTEN / MERGE. Protects definitions, theorems, quotes, legal wording, code, formulas-in-prose. | ✓ |
| `ai/image_policy.py` | Per-figure KEEP_AS_IS / SUMMARISE_TO_STRUCTURE / ENHANCE / REGENERATE / CAPTION_ONLY / DROP, from pixel size, aspect, OCR density, structure markers, relevance. | ✓ |

All four are pure-Python, deterministic, no network — same contract as the
rest of the pipeline's decision code.

---

## 2. The treatment taxonomy (`VISUAL_TREATMENTS`)

20 treatments, each with an explicit *use-when* and the structured data its
renderer needs:

`KEEP_TEXT · BULLETS · DEFINITION · QUOTE · FLOWCHART · CYCLE · TIMELINE ·
COMPARISON_TABLE · PROS_CONS · MATRIX_2X2 · PYRAMID · VENN · MIND_MAP ·
CARD_GRID · BAR_CHART · LINE_CHART · PIE_CHART · METRIC · IMAGE_FOCUS ·
MINIMAL_TEXT`

Selection principle: **match the *shape* of the information, not keywords.**
A forced diagram is worse than clean text — hence `KEEP_TEXT` / `MINIMAL_TEXT`
win whenever nothing structural clears the score threshold (2.5).

### How VMS scores (excerpt)

| Treatment | Fires on |
|---|---|
| FLOWCHART | ≥3 ordered steps; +decision cues ("if…then", "otherwise") |
| CYCLE | ordered steps **and** loop cues ("repeat", "feedback", "the cycle continues") |
| TIMELINE | ≥2 real dates/years — *not* ordinal words alone |
| COMPARISON_TABLE | intelligence-engine comparisons, or ≥1 "vs / whereas / in contrast" |
| PROS_CONS | ≥2 advantage/disadvantage cues for **one** subject |
| PIE_CHART | ≥3 percentages that sum to ~100 |
| LINE_CHART | numeric series + time cues |
| BAR_CHART | ≥3 numbers across categories (suppressed if a valid pie exists) |
| METRIC | exactly one figure and <45 words |
| PYRAMID / VENN / MATRIX_2X2 | level cues / shared-set cues / two-axis cues |
| MIND_MAP | ≥4 loosely related concepts and no other structure |

Every decision carries a `rationale` string and the full `scores` map, so the
studio UI can show *why* a slide became a pie chart.

---

## 3. Text policy

`classify_sentences(text)` → per sentence:

- **VERBATIM** — `is defined as`, `X is the measure of`, `denoted by`; law /
  theorem statements; anything in quotation marks or after `wrote:`; legal
  register (`shall`, `pursuant to`, `Section 3`); code (`{}`, `=>`, `def`,
  `SELECT … FROM`); formula-in-prose (`E = mc^2`, `∝`, `≤`).
- **MERGE** — near-duplicate (containment or Jaccard ≥ 0.72) of an earlier one.
- **TIGHTEN** — everything else.

`protect_verbatim(text)` feeds the pipeline's existing trimming so those
sentences are never word-clipped.

---

## 4. Image policy

`decide_image_action(ImageMeta)` where `ImageMeta` carries pixel size, ext,
`ocr_text` (already produced by `image_describer`), `referenced_in_text`, and
the surrounding `slide_text`.

| Signal | Action |
|---|---|
| tiny (<0.02 MP) or banner aspect, no text | **DROP** |
| decorative/stock/logo cues + low relevance | **DROP** |
| ≥2 structure markers (`→`, `step N`, `\|…\|…\|`, `yes/no`) + ≥8 words | **SUMMARISE_TO_STRUCTURE** |
| ≥40 OCR words closely tied to the slide | **SUMMARISE_TO_STRUCTURE** |
| low-res but relevant / referenced | **ENHANCE** |
| decorative but on-topic slot | **REGENERATE** (generated illustration) |
| clear + relevant | **KEEP_AS_IS** (+ caption) |
| low relevance but real text inside | **CAPTION_ONLY** |

"Summarise to structure" is the key one: a bitmap of a flowchart becomes a
*real* Learnova flowchart (via the same VMS run over its OCR), and the image
is dropped — no more blurry screenshots of diagrams.

---

## 5. Progressive reveal

New schema field `reveal_groups`: an ordered list of index groups into the
slide's elements. Group *k* appears on the *k*-th presenter click.

`plan_reveal_groups(bullets, treatment, has_takeaway)`:

- one idea per step for lists / flowcharts / timelines;
- row-by-row for comparison tables;
- two halves for pros/cons and Venn;
- single step for QUOTE / METRIC / DEFINITION;
- the takeaway is always the last group;
- **never reorders** — groups are consecutive.

Rendering targets (next session):

- **Web deck** — Reveal.js `class="fragment" data-fragment-index="k"` on each
  group; the existing deck already loads Reveal.js.
- **PPTX** — per-shape entrance animation (`p:animEffect` / `p:par` timing
  nodes) built in `ppt_builder.py`; one build group per click.
- **Presenter mode** — arrow keys advance groups then slides.

---

## 6. Wiring plan (NOT done this session)

The decision layer is complete and tested. Remaining, in order:

1. `layout_router.py` → call `master_prompt` + parse the richer JSON; on any
   failure fall back to `visual_selector.select_visual`.
2. `pipeline/visual_planner.py` → stop collapsing everything to 5 legacy
   `layout_type` values; carry the full treatment + its spec sub-object.
3. `rendering/web_deck_builder.py` → renderers for CYCLE, TIMELINE,
   COMPARISON_TABLE (native), PROS_CONS, MATRIX_2X2, PYRAMID, VENN, MIND_MAP,
   BAR/LINE/PIE (SVG or Chart.js), DEFINITION, QUOTE, IMAGE_FOCUS; apply
   `reveal_groups` as fragments.
4. `rendering/ppt_builder.py` → same treatments as native PPTX shapes +
   SmartArt-style layouts + entrance animations.
5. `pipeline/orchestrator.py` → run `image_policy` in the `vision_ocr` stage;
   route SUMMARISE_TO_STRUCTURE images back through the selector.
6. Studio UI → show the chosen treatment + rationale per slide; let the user
   override it.

---

## 7. Research angle (optional, pairs with PSF)

The VMS is a second contribution: **Visual Modality Selection for generated
slides** — a deterministic, explainable classifier over 20 treatments, with a
threshold that defers to text when no structure is strong. Evaluate the same
way as PSF: human agreement on "is this the right visual for this content?",
against an LLM-only baseline and against the old 5-type router. Add a
`treatment` column to the deck corpus and it costs almost no extra annotation.
