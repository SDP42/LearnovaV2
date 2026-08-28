# Learnova — Visual Library & Animation Master Prompt

**Purpose of this document**

1. Record what visual treatments the repo ships **today** (small set).
2. Define an **expanded visual taxonomy** that reaches **1000+ addressable visuals**
   through families → named variants → parametric axes, each with explicit
   *use-when / do-not-use-when* rules.
3. Define a **progressive-reveal / animation grammar** so a single slide can be
   walked through one step at a time (e.g. linear regression: points → scatter →
   candidate lines → residuals → best-fit line → equation).
4. Ship one **copy-paste master prompt** (Part E) that an LLM uses to pick a
   visual, populate its data, and produce an animation timeline as strict JSON.

The deterministic selector in
[`ai/visual_selector.py`](../../src/learnova/ai/visual_selector.py) and the
taxonomy in [`ai/master_prompt.py`](../../src/learnova/ai/master_prompt.py) are
the implementation; the machine-readable catalog is
[`docs/visual_catalog.yaml`](../visual_catalog.yaml).

---

## Part A — What the repo has today (20 flat treatments)

| Key | Family | Use when |
|---|---|---|
| KEEP_TEXT | TEXT | wording is precision-critical (definition, theorem, quote, code) |
| MINIMAL_TEXT | TEXT | connected explanatory prose, no structure |
| BULLETS | TEXT | 3–8 unrelated discrete facts |
| DEFINITION | DEFINITION | one term introduced + defined |
| QUOTE | QUOTE | one memorable statement / law / principle |
| METRIC | KPI | one headline number is the message |
| FLOWCHART | PROCESS_LINEAR | ordered procedure with 3+ steps, possible branches |
| CYCLE | PROCESS_CYCLIC | repeating process, no start/end |
| TIMELINE | TIMELINE | 3+ dated / strictly chronological events |
| COMPARISON_TABLE | COMPARE_TABLE | 2+ named things across the same aspects |
| PROS_CONS | COMPARE_VISUAL | advantages vs disadvantages of ONE thing |
| MATRIX_2X2 | MATRIX_GRID | items on two independent binary axes |
| PYRAMID | HIERARCHY_NEST | levels that build on / nest inside each other |
| VENN | SET_DIAGRAM | 2–3 sets with shared + unique members |
| MIND_MAP | MIND_MAP | one central concept fanning into loose branches |
| CARD_GRID | LIST_STRUCTURED | 3–4 parallel pillars of equal weight |
| BAR_CHART | CHART_CATEGORICAL | quantities compared across categories |
| LINE_CHART | CHART_TREND | a quantity changing over an ordered dimension |
| PIE_CHART | CHART_PART_TO_WHOLE | parts of a single whole summing to 100% |
| IMAGE_FOCUS | MEDIA | a supplied figure IS the content |

**Gap:** ~20 treatments cannot cover STEM teaching (no function plots, geometry,
circuits, molecules, algorithm traces, data-structure diagrams, proofs, number
lines, anatomy overlays, maps, etc.), and `reveal_groups` is *planned but not
rendered*.

---

## Part B — The expanded visual taxonomy (1000+ addressable visuals)

```
VISUAL ID  =  FAMILY . VARIANT . { parametric axes }
```

- **~40 families** (B.1)
- **~200 named variants** across them (full list: `docs/visual_catalog.yaml`)
- **8 parametric axes** (B.3) whose legal combinations multiply the variants
  past 1000 distinct, meaningfully different visuals.

Each catalog row carries: **use_when**, **avoid_when**, **needs** (structured
data the renderer requires), **reveal_unit** (the atom a progressive-reveal step
adds — see Part C), **params_allowed**.

### B.1 The 40 families

| # | Family | Domain |
|---|---|---|
| 1 | TEXT | verbatim / prose / bullets |
| 2 | DEFINITION | term–meaning–example callouts, glossary strips |
| 3 | QUOTE | statements, laws, principles, epigraphs |
| 4 | KPI | single or small-multiple headline numbers |
| 5 | LIST_STRUCTURED | checklist, ranked list, do/don't, cards, steps-as-list |
| 6 | PROCESS_LINEAR | flowchart, pipeline, swimlane, funnel, chevron |
| 7 | PROCESS_CYCLIC | cycle, feedback loop, iteration loop, infinity loop |
| 8 | DECISION | decision tree, if/then ladder, truth table |
| 9 | STATE_MACHINE | state diagram, lifecycle, phase diagram |
| 10 | TIMELINE | dated timeline, Gantt, roadmap, era band |
| 11 | HIERARCHY_TREE | org chart, taxonomy tree, file tree, dendrogram, bracket |
| 12 | HIERARCHY_NEST | pyramid, layered model (OSI), treemap, sunburst |
| 13 | MIND_MAP | radial map, concept map (labelled edges), spider diagram |
| 14 | COMPARE_TABLE | comparison table, feature matrix, spec sheet, rubric |
| 15 | COMPARE_VISUAL | side-by-side, before/after, pros-cons, this-vs-that split |
| 16 | MATRIX_GRID | 2x2 quadrant, Eisenhower, BCG, risk matrix, confusion matrix |
| 17 | SET_DIAGRAM | Venn (2/3-set), Euler, set-builder |
| 18 | CHART_CATEGORICAL | bar, grouped bar, stacked bar, Pareto, lollipop, dot plot |
| 19 | CHART_TREND | line, multi-line, area, stacked area, step, slope chart |
| 20 | CHART_PART_TO_WHOLE | pie, donut, 100% stacked, waffle, icon array |
| 21 | CHART_DISTRIBUTION | histogram, box plot, violin, density, ECDF |
| 22 | CHART_RELATIONSHIP | scatter, bubble, connected scatter, correlation heatmap |
| 23 | CHART_RANKING | ordered bar, bump chart, dumbbell, tornado |
| 24 | CHART_FLOW | Sankey, alluvial, chord, network graph, arc diagram |
| 25 | CHART_SPATIAL | choropleth map, dot map, flow map, cartogram |
| 26 | CHART_SPECIAL | radar/spider, parallel coordinates, gauge, bullet graph, funnel |
| 27 | FUNCTION_PLOT | y=f(x) curve, family of curves, piecewise, parametric, polar |
| 28 | CALCULUS_VIZ | tangent/secant, area under curve, Riemann sums, slope field, limit zoom |
| 29 | LINEAR_ALGEBRA | vector diagram, basis/grid transform, matrix as grid, span, projection |
| 30 | GEOMETRY | construction, labelled polygon, circle theorems, transformations, solid net |
| 31 | NUMBER_LINE | number line, inequality ray, interval, fraction bar, place-value chart |
| 32 | PROOF_LADDER | statement–reason table, derivation chain, algebra step stack, proof tree |
| 33 | ML_VIZ | scatter+boundary, regression fit, residuals, loss curve, tree split, gradient descent, k-means, bias-variance |
| 34 | DATA_STRUCTURE | array, linked list, stack/queue, binary tree, heap, hash table, graph |
| 35 | ALGORITHM_TRACE | sorting bars, pointer walkthrough, recursion tree, call stack, DP table fill |
| 36 | CIRCUIT | schematic (R/L/C/diode/transistor), logic gates, block diagram |
| 37 | PHYSICS_DIAGRAM | free-body diagram, ray optics, wave, field lines, projectile, energy bar |
| 38 | CHEM_DIAGRAM | molecule (2D skeletal), reaction mechanism arrows, energy profile, orbital, titration curve |
| 39 | BIO_DIAGRAM | labelled anatomy, cell, cycle (Krebs), phylogenetic tree, punnett square, food web |
| 40 | ANNOTATION_LAYER | callout pins, magnifier/inset, dimension lines, spotlight, attention arrows (overlays on ANY visual) |

### B.3 The 8 parametric axes (how ~200 → 1000+)

| Axis | Values | When it changes the advice |
|---|---|---|
| **orientation** | horizontal, vertical, radial, isometric | vertical timeline for many events / mobile; horizontal for ≤7 |
| **cardinality** | tiny (≤3), small (4–7), medium (8–15), large (16–40), dense (40+) | crossing a band changes the recommended variant (bar→dot plot, pie→bar, network→matrix) |
| **emphasis** | neutral, single-highlight, ranked, threshold-band, delta | highlight/threshold/delta each add data fields and a reveal step |
| **data_mode** | schematic (illustrative), data-driven (to scale), hybrid | schematic FUNCTION_PLOT for intuition; data-driven for real measurements |
| **annotation layers** | 0…n stacked ANNOTATION_LAYER items | each layer is independently revealable |
| **dimensionality** | 1D, 2D, 2.5D, 3D | 3D only for solids, surfaces, molecular geometry, loss surfaces |
| **encoding** | position, length, angle, area, colour (seq/div/cat), size, texture | each encoding has its own accessibility rules |
| **motion state** | static, build, animate, scrub | Part C |

**Count:** 40 families → ~200 named variants → avg ~5 materially different
parametric combinations → **~1000 addressable visuals**. The catalog enumerates
variants; the renderer implements ~40 family renderers that read variant + params.

### B.4 Universal "do not use a visual at all" rules

Return `TEXT.keep` / `TEXT.minimal` when:

- the wording is legally/mathematically exact (definitions, theorems, statutes, quotes, code, formulae-in-prose);
- there are fewer than 3 structured elements with no relationship between them;
- the only structure is "these are N things" with no order, hierarchy, comparison, quantity, or process → `LIST_STRUCTURED`, not a diagram;
- the data the chart needs is not actually present in the source (never invent numbers, dates, coordinates);
- a forced diagram would misrepresent the content (implying order / a loop / causation that is not stated).

---

## Part C — Progressive-reveal & animation grammar

A slide is a **scene** built from an ordered list of **reveal steps**; each step
*adds, transforms, or focuses* elements. Presenter advances with a click; export
to `.pptx` maps each step to an entrance animation; export to Reveal.js maps each
step to a `fragment`.

### C.1 Data model

```jsonc
"animation": {
  "mode": "build",              // static | build | animate | scrub
  "steps": [
    {
      "id": "s1",
      "label": "Raw data points",          // presenter note
      "adds":    ["pt.0","pt.1","pt.2"],    // element ids to show
      "transforms": [],                     // see C.3
      "focus":   [],                        // ids to spotlight, others dimmed
      "removes": [],                        // ids to hide again
      "effect":  "fade",                    // fade|draw|grow|slide-left|pop|count-up|trace
      "duration_ms": 400,
      "stagger_ms": 60,
      "wait_for": "click"                   // click | auto | auto-after:2000
    }
  ]
}
```

Every drawn element gets a stable dotted **id**: `axis.x`, `pt.3`,
`line.candidate.2`, `resid.3`, `line.bestfit`, `eq`, `region.q2`, `node.n4`,
`edge.n1_n2`, `bar.2`, `rect.riemann.8`, `frame.factorial_3`.

### C.2 Reveal-unit defaults per family (what one click adds)

| Family | Default reveal unit(s), in order |
|---|---|
| TEXT / LIST_STRUCTURED | one bullet per step; takeaway last |
| DEFINITION / QUOTE / KPI | single step (indivisible) |
| PROCESS_LINEAR | node, then its outgoing edge |
| PROCESS_CYCLIC | stage clockwise; arrows with the stage they leave |
| DECISION | root question → each branch → outcome |
| TIMELINE | event in chronological order; milestone gets emphasis |
| HIERARCHY_* | breadth-first: root, then each level |
| COMPARE_TABLE | header row (as a set) → one aspect row per step → highlight cells last |
| MATRIX_GRID | axes → quadrant labels → items into quadrants |
| SET_DIAGRAM | each set outline → unique members → shared region |
| CHART_CATEGORICAL | axes → gridlines → one series → highlight/threshold |
| CHART_TREND | axes → each series drawn left-to-right → markers → annotation |
| CHART_PART_TO_WHOLE | whole → largest slice → remaining → highlight |
| CHART_RELATIONSHIP | axes → point cloud (staggered) → trend line → annotation |
| FUNCTION_PLOT | axes → curve draw → key points → asymptotes/labels |
| CALCULUS_VIZ | secant→tangent; Riemann n=4→8→16 |
| GEOMETRY.construction | one primitive per step; labels after the figure closes |
| PROOF_LADDER | one row/line per step; QED last |
| ML_VIZ | see Part C.5 |
| DATA_STRUCTURE | skeleton → values → pointers → per-operation frames |
| ALGORITHM_TRACE | one algorithm step per click (compare, swap, mark, recurse, fill) |
| CIRCUIT | components → wires → source on → V/I annotations |
| PHYSICS.free_body | object → one force vector per step → net force → resolution |
| CHEM.mechanism | one curved arrow per step → resulting intermediate |
| BIO.anatomy | one label per step (or grouped by system) |

### C.3 Transform operations (for `transforms[]`)

`op` vocabulary: `move`, `morph-to`, `recolor`, `resize`, `shade`, `sort`,
`zoom`, `pan`, `rotate`, `reflect`, `translate`, `dilate`, `count-up`,
`draw-along`, `pulse`, `dim-others`.

### C.4 Rules the LLM must follow when authoring steps

1. **One idea per step.** A set is one step only if read as a unit (a table
   header row, both halves of a Venn).
2. **Never reorder content.** Steps follow reading order (top→bottom, left→right,
   chronological, base→apex, algorithm order).
3. **Scaffold before payload.** Axes / containers / skeletons first; labels and
   equations *after* the thing they describe.
4. **The takeaway / conclusion / QED / equation is always the last step.**
5. **Indivisible visuals get exactly one step** (QUOTE, KPI, single DEFINITION).
6. **Cap at ~7 steps per slide.** More → continuation slide (CLT working-memory
   limit; mirrors PSF/CLASS segmentation).
7. **`focus` beats `remove`.** Prefer dimming to hiding, unless genuinely
   replacing content.
8. **`effect` matches meaning:** `draw` for curves/paths, `count-up` for metrics,
   `grow` for bars, `pop` for scatter, `trace` for pointers/arrows, `fade` default.
9. **Continuous animation (`mode:"animate"`) only** for inherently moving things
   (wave, orbit, pendulum, auto-playing gradient descent).
10. If the source implies no walk-through, emit a single step containing all
    elements (`mode:"static"`).

### C.5 Worked example — linear regression (`ML_VIZ.regression_fit`)

| Step | label | adds / transforms | effect |
|---|---|---|---|
| 1 | "Here is our data — hours studied vs exam score." | `axis.x`,`axis.y` | fade |
| 2 | "Each student is one point." | `pt.0..pt.n` | pop, stagger 60ms |
| 3 | "We want a line y = mx + c to summarise the trend." | `line.candidate.0` | draw |
| 4 | "It could be any of these — which is best?" | `line.candidate.1..k` | draw, stagger 120ms |
| 5 | "The error is the vertical gap to each point." | `resid.*` | draw |
| 6 | "'Best' = smallest total squared error." | `line.candidate.*` morph-to `line.bestfit`; `resid.*` shrink | move 800ms |
| 7 | "That line is our model." | `eq`, `label.slope`, `label.intercept` | fade |

---

## Part D — Mapping to existing Learnova code

| This spec | Today | Change |
|---|---|---|
| `FAMILY.VARIANT` id | flat `treatment` string | `family` + `variant` + `params` in `VisualDecision` and master-prompt JSON — **done** |
| 1000-visual catalog | 20 `Treatment` rows | `docs/visual_catalog.yaml` — **done**; `visual_selector` reads it |
| `animation.steps` | `reveal_groups: [[int]]` | superset — `plan_animation_steps()` — **done** |
| step → PPTX | none | `rendering/ppt_builder.py`: `effect` → entrance animation — **next** |
| step → web | none | `rendering/web_deck_builder.py`: `fragment` markup + transforms JS — **next** |
| family renderers | 5 | +~12 SVG family renderers that stamp element ids — **next** |

---

## Part E — The master prompt

Lives verbatim in `ai/master_prompt.py::MASTER_SYSTEM_PROMPT`. Output is one
strict JSON object with five decisions: CONTENT, VISUAL (`family` / `variant` /
`params`), TEXT-treatment-per-sentence, IMAGE handling, and PROGRESSIVE-REVEAL
(`animation.steps`).

---

## Part F — Next implementation steps

1. ~~Generate `docs/visual_catalog.yaml`.~~ **done**
2. ~~Extend `ai/master_prompt.py`: family/variant/params/animation.~~ **done**
3. ~~Extend `ai/visual_selector.py`: `plan_animation_steps()`.~~ **done**
4. `rendering/web_deck_builder.py`: Reveal.js `fragment` markup + `transforms` JS runtime.
5. `rendering/ppt_builder.py`: map each step to a `python-pptx` entrance animation.
6. Add ~8–12 new family renderers (FUNCTION_PLOT, ML_VIZ, ALGORITHM_TRACE,
   DATA_STRUCTURE, GEOMETRY, CIRCUIT, PHYSICS_DIAGRAM, CHEM_DIAGRAM) as SVG
   generators that stamp element ids for the animation layer.
7. Feed `animation.steps` count into PSF/CLASS as the realised slide segmentation.
