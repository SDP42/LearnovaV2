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
[`ai/visual_selector.py`](../src/learnova/ai/visual_selector.py) and the taxonomy
in [`ai/master_prompt.py`](../src/learnova/ai/master_prompt.py) are the current
ground truth; this document is the spec they should grow into.

---

## Part A — What the repo has today (20 treatments)

From `VISUAL_TREATMENTS` in `ai/master_prompt.py` and `VisualType.ALL` in
`visual_specs/schema.py`:

| Key | Family | Use when |
|---|---|---|
| KEEP_TEXT | text | wording is precision-critical (definition, theorem, quote, code) |
| MINIMAL_TEXT | text | connected explanatory prose, no structure |
| BULLETS | text | 3–8 unrelated discrete facts |
| DEFINITION | callout | one term introduced + defined |
| QUOTE | callout | one memorable statement / law / principle |
| METRIC | callout | one headline number is the message |
| FLOWCHART | process | ordered procedure with 3+ steps, possible branches |
| CYCLE | process | repeating process, no start/end (PDCA, water cycle) |
| TIMELINE | chronology | 3+ dated / strictly chronological events |
| COMPARISON_TABLE | compare | 2+ named things across the same aspects |
| PROS_CONS | compare | advantages vs disadvantages of ONE thing |
| MATRIX_2X2 | compare | items on two independent binary axes |
| PYRAMID | hierarchy | levels that build on / nest inside each other |
| VENN | set | 2–3 sets with shared + unique members |
| MIND_MAP | hierarchy | one central concept fanning into loose branches |
| CARD_GRID | layout | 3–4 parallel pillars of equal weight |
| BAR_CHART | data | quantities compared across categories |
| LINE_CHART | data | a quantity changing over an ordered dimension |
| PIE_CHART | data | parts of a single whole summing to 100% |
| IMAGE_FOCUS | media | a supplied figure IS the content |

Plus schema-only types not yet in the prompt: `MATRIX`, `HIERARCHY`,
`PROCESS_DIAGRAM`, `DECISION_TREE`, `ORG_CHART`, `SMART_ART`, `ICON_GRID`,
`CHECKLIST`, `AI_IMAGE`, `GRAPH` (scatter/radar).

**Gap:** ~20 treatments cannot cover STEM teaching (no function plots, geometry,
circuits, molecules, algorithm traces, data-structure diagrams, proofs, number
lines, dc/anatomy overlays, maps, etc.), and `reveal_groups` is *planned but not
rendered* — the web deck builder has no fragment output yet.

---

## Part B — The expanded visual taxonomy (1000+ addressable visuals)

You never need 1000 hand-written renderers. You need:

```
VISUAL ID  =  FAMILY . VARIANT . { parametric axes }
```

- **~40 families** (Part B.1)
- **~220 named variants** across them (Part B.2 catalog)
- **8 parametric axes** (Part B.3) — orientation, cardinality, emphasis,
  data-vs-schematic, annotation layers, dimensionality, palette-encoding,
  motion-state — whose legal combinations multiply the 220 variants past 1000
  distinct, meaningfully-different visuals.

Each catalog row carries: **USE WHEN**, **DO NOT USE WHEN**, **NEEDS** (structured
data the renderer requires), **REVEAL UNIT** (the atom a progressive-reveal step
adds — see Part C).

### B.1 The 40 families

| # | Family | One-line domain |
|---|---|---|
| 1 | TEXT | verbatim / prose / bullets / callouts |
| 2 | DEFINITION | term–meaning–example callouts, glossary strips |
| 3 | QUOTE | statements, laws, principles, epigraphs |
| 4 | KPI / METRIC | single or small-multiple headline numbers |
| 5 | LIST_STRUCTURED | checklist, ranked list, do/don't, steps-as-list |
| 6 | PROCESS_LINEAR | flowchart, pipeline, swimlane, funnel, chevron |
| 7 | PROCESS_CYCLIC | cycle, feedback loop, iterative loop, infinity loop |
| 8 | DECISION | decision tree, if/then ladder, truth table, flow w/ branches |
| 9 | STATE_MACHINE | state diagram, lifecycle, phase diagram |
| 10 | TIMELINE | dated timeline, Gantt, roadmap, era band, sequence-of-events |
| 11 | HIERARCHY_TREE | org chart, taxonomy tree, file tree, dendrogram, tournament bracket |
| 12 | HIERARCHY_NEST | pyramid, layered model (OSI), nested boxes, treemap, sunburst |
| 13 | MIND_MAP | radial map, concept map (labelled edges), spider diagram |
| 14 | COMPARE_TABLE | comparison table, feature matrix, spec sheet, rubric |
| 15 | COMPARE_VISUAL | side-by-side, before/after, pros-cons, this-vs-that split |
| 16 | MATRIX_GRID | 2x2 quadrant, 3x3, Eisenhower, BCG, risk matrix, confusion matrix |
| 17 | SET_DIAGRAM | Venn (2/3/4-set), Euler, set-builder, overlap bars |
| 18 | CHART_CATEGORICAL | bar, grouped bar, stacked bar, column, Pareto, lollipop, dot plot |
| 19 | CHART_TREND | line, multi-line, area, stacked area, step, spline, slope chart |
| 20 | CHART_PART_TO_WHOLE | pie, donut, 100% stacked, waffle, treemap, icon array |
| 21 | CHART_DISTRIBUTION | histogram, box plot, violin, density, dot-strip, ECDF |
| 22 | CHART_RELATIONSHIP | scatter, bubble, connected scatter, hexbin, correlation heatmap |
| 23 | CHART_RANKING | ordered bar, bump chart, ranked list, dumbbell, tornado |
| 24 | CHART_FLOW | Sankey, alluvial, chord, network graph, arc diagram |
| 25 | CHART_SPATIAL | choropleth map, dot map, flow map, cartogram, small-multiple maps |
| 26 | CHART_SPECIAL | radar/spider, parallel coordinates, gauge, bullet graph, funnel |
| 27 | FUNCTION_PLOT | y=f(x) curve, family of curves, piecewise, parametric, polar |
| 28 | CALCULUS_VIZ | tangent/secant line, area under curve, Riemann sums, slope field, limit zoom |
| 29 | LINEAR_ALGEBRA | vector diagram, basis/grid transform, matrix as grid, span, projection |
| 30 | GEOMETRY | construction, labelled polygon, circle theorems, transformations, 3D solid net |
| 31 | NUMBER_LINE | number line, inequality ray, interval, fraction bar, place-value chart |
| 32 | PROOF_LADDER | statement–reason table, derivation chain, algebra step stack, proof tree |
| 33 | ML_VIZ | scatter+boundary, regression fit, residuals, loss surface/curve, tree split, gradient-descent path, k-means, bias-variance |
| 34 | DATA_STRUCTURE | array, linked list, stack/queue, binary tree, heap, hash table, graph, matrix |
| 35 | ALGORITHM_TRACE | sorting bars, pointer walkthrough, recursion tree, call stack, DP table fill |
| 36 | CIRCUIT | schematic (R/L/C/diode/transistor), logic gates, block diagram, breadboard |
| 37 | PHYSICS_DIAGRAM | free-body diagram, ray optics, wave, field lines, projectile, energy bar |
| 38 | CHEM_DIAGRAM | molecule (2D skeletal), reaction mechanism arrows, energy profile, orbital, titration curve, periodic-table slice |
| 39 | BIO_DIAGRAM | labelled anatomy, cell, cycle (Krebs), phylogenetic tree, punnett square, food web |
| 40 | ANNOTATION_LAYER | callout pins, magnifier/inset, dimension lines, highlight mask, spotlight, arrows-of-attention (overlays on ANY visual above) |

### B.2 Named-variant catalog (excerpt — the pattern, ~220 rows total)

> Full machine-readable catalog lives in `docs/visual_catalog.yaml` (to be
> generated). Below is the authoring format and a representative slice per family.
> Each row: `FAMILY.VARIANT — USE WHEN | DO NOT USE WHEN | NEEDS | REVEAL UNIT`.

**PROCESS_LINEAR**
- `PROCESS_LINEAR.flowchart` — ordered procedure with branches, 3–12 nodes | it loops with no end (use PROCESS_CYCLIC); >15 nodes (split slide) | nodes[id,label,type], edges[from,to,condition] | node
- `PROCESS_LINEAR.pipeline` — data/material transformed stage by stage, one path | branches exist; stages are not transformations | stages[label, in, out] | stage
- `PROCESS_LINEAR.swimlane` — a process where *who does what* matters | actor is irrelevant; <2 actors | lanes[actor], steps[lane,label,order] | step
- `PROCESS_LINEAR.funnel` — quantity shrinks monotonically through stages | quantities grow or are unordered | stages[label,value] descending | stage
- `PROCESS_LINEAR.chevron` — 3–6 sequential phases, no data, emphasis on direction | there is branching or timing detail | phases[label] | phase

**PROCESS_CYCLIC**
- `PROCESS_CYCLIC.cycle` — 3–8 stages repeating forever, equal weight | there is a true start/end; one stage dominates | stages[label] in order | stage
- `PROCESS_CYCLIC.feedback_loop` — output feeds back to modify input | the return path is not a correction/measurement | nodes, forward_edges, feedback_edge[from,to,sign] | edge
- `PROCESS_CYCLIC.iteration_loop` — repeat-until-converged (training, refinement) | fixed number of non-repeating steps | body_steps[label], exit_condition | step

**DECISION**
- `DECISION.tree` — nested yes/no choices leading to outcomes | choices are independent (use MATRIX_GRID); >4 levels deep | root, nodes[question], branches[label,to], leaves[outcome] | branch
- `DECISION.if_then_ladder` — 3–7 mutually exclusive condition→action rules | conditions overlap or are continuous | rules[condition, action], default | rule
- `DECISION.truth_table` — boolean function of 2–4 inputs | continuous inputs; >4 inputs (16+ rows) | inputs[name], rows[input_values, output] | row

**TIMELINE**
- `TIMELINE.dated` — 3–12 events with real dates | ordinal-only ("first, then"); durations matter more than dates | events[date,title,desc,is_milestone] | event
- `TIMELINE.gantt` — overlapping tasks with start/end and dependencies | instantaneous events; no overlap | tasks[label,start,end,depends_on] | task
- `TIMELINE.roadmap` — future plan grouped into horizons (now/next/later) | precise dates are known and matter | horizons[label], items[horizon,label] | item
- `TIMELINE.era_band` — long history split into named periods | <3 periods; exact events matter more | periods[label,start,end], optional markers | period

**HIERARCHY_TREE / HIERARCHY_NEST**
- `HIERARCHY_TREE.org_chart` — reporting / containment tree | peer relationships or networks (use CHART_FLOW.network) | root, edges[parent,child], node labels | node
- `HIERARCHY_TREE.taxonomy` — is-a classification, 2–4 levels | overlapping categories; membership is fuzzy | levels, nodes, parent links | node
- `HIERARCHY_TREE.bracket` — single-elimination tournament / knockout | non-elimination structure | rounds, matchups[a,b,winner] | matchup
- `HIERARCHY_NEST.pyramid` — 3–6 levels building on a base | levels are independent or same-size | levels[label] base→apex | level
- `HIERARCHY_NEST.layered_model` — stack of abstraction layers (OSI, TCP/IP) | not a stack; lateral flow dominates | layers[name, role] bottom→top | layer
- `HIERARCHY_NEST.treemap` — part-to-whole with nested categories, area = value | <5 items; values unknown | tree[label, value, children] | leaf
- `HIERARCHY_NEST.sunburst` — same as treemap when radial depth reads better | only one level; many tiny leaves | same as treemap | ring segment

**COMPARE**
- `COMPARE_TABLE.comparison` — 2–5 things × 3–8 shared aspects | one thing only (PROS_CONS); aspects differ per thing | headers, rows[aspect, values...] , highlight cells | row
- `COMPARE_TABLE.feature_matrix` — many options × many binary features (✓/✗) | features are graded not binary | options, features, cells[bool] | feature row
- `COMPARE_VISUAL.before_after` — one subject, two states, change is the point | more than two states; states not comparable | before{...}, after{...}, changed[fields] | side
- `COMPARE_VISUAL.split_screen` — two competing approaches shown in parallel | 3+ approaches; they are not opposed | left{title,points}, right{title,points} | point
- `COMPARE_VISUAL.pros_cons` — advantages vs disadvantages of ONE thing | comparing two things | pros[], cons[] | item

**MATRIX_GRID**
- `MATRIX_GRID.quadrant_2x2` — items on two independent binary/continuous axes | one axis; >~12 items | x_axis, y_axis, items[label,x,y] or quadrants{q1..q4} | quadrant then item
- `MATRIX_GRID.eisenhower` — tasks by urgency × importance | non-task content | items[label, urgent:bool, important:bool] | quadrant
- `MATRIX_GRID.confusion_matrix` — classifier TP/FP/FN/TN (or k×k) | non-classification data | classes, counts[actual][predicted] | cell
- `MATRIX_GRID.heatmap_grid` — value across two categorical dimensions, color = value | dimensions are continuous (use CHART_RELATIONSHIP.hexbin) | rows, cols, values[r][c] | cell / row

**CHART families** (each variant: USE WHEN / DO NOT USE WHEN / NEEDS / REVEAL UNIT)
- `CHART_CATEGORICAL.bar` — compare a value across 3–15 nominal categories | parts of a whole (pie); time series (line); >20 bars | categories[], series[{name,values}], axes | series, then bar
- `CHART_CATEGORICAL.grouped_bar` — 2–4 sub-series per category | >4 sub-series; categories >8 | categories, series[2..4] | series
- `CHART_CATEGORICAL.stacked_bar` — category total AND composition both matter | only composition (100% stacked); only total (bar) | categories, segments[{name,values}] | segment
- `CHART_CATEGORICAL.pareto` — few categories drive most of the total (80/20) | no dominant categories | categories sorted desc + cumulative % | bar, then cumulative line
- `CHART_TREND.line` — continuous quantity over ordered/time x, 1–4 series | nominal x (bar); >6 series (spaghetti) | x[], series[{name,values}] | series, then point-by-point
- `CHART_TREND.area` — magnitude of a single series over time, volume matters | multiple crossing series | x[], series[1] | region sweep
- `CHART_TREND.slope` — change between exactly two time points, many items | >2 time points; few items | items[label, t1, t2] | line
- `CHART_PART_TO_WHOLE.pie` — 2–5 parts of one whole summing to ~100% | >5 slices; values not a whole; comparing across pies | slices[label, pct] total≈100 | slice
- `CHART_PART_TO_WHOLE.donut` — pie + a central total/label | same limits as pie | slices + center_label | slice
- `CHART_PART_TO_WHOLE.waffle` / `.icon_array` — proportion made tangible ("13 in 100") | precise multi-part breakdown; >2 categories | total, highlighted, unit_icon | filled cell block
- `CHART_DISTRIBUTION.histogram` — shape of one numeric variable, n large | n < ~20; categorical data | values[] or bins[range,count] | bin
- `CHART_DISTRIBUTION.box_plot` — compare distributions across 2–8 groups | need to see modality (use violin); n tiny | groups[label, min,q1,med,q3,max, outliers] | box
- `CHART_RELATIONSHIP.scatter` — relationship between two numeric variables | one variable; categorical x | points[x,y], optional group | point cloud, then trend
- `CHART_RELATIONSHIP.bubble` — 3rd numeric variable via size | size differences <2×; clutter | points[x,y,size,label] | point
- `CHART_FLOW.sankey` — flow/conservation of quantity through stages | quantity not conserved; <3 nodes | nodes, links[source,target,value] | link
- `CHART_FLOW.network` — entities and their relationships, no hierarchy | it is a tree (use HIERARCHY_TREE); >50 nodes on a slide | nodes[id,label,group], edges[a,b,weight] | node then edge
- `CHART_SPATIAL.choropleth` — a value per region, geography matters | regions vary wildly in size skewing perception; non-spatial data | regions[id,value], scale | region
- `CHART_SPECIAL.radar` — one entity profiled on 3–8 comparable axes | axes not comparable; >8 axes; >3 entities | axes[label], series[{name, values 0..max}] | axis
- `CHART_SPECIAL.gauge` / `.bullet` — one KPI against a target/range | multiple metrics (use KPI grid); no meaningful range | value, target, ranges[] | needle sweep

**FUNCTION_PLOT / CALCULUS_VIZ**
- `FUNCTION_PLOT.curve` — a single y=f(x) over a domain | discrete data (scatter); no closed form | expr or samples, domain, key_points[] | curve draw, then key points
- `FUNCTION_PLOT.family` — how a parameter changes a curve's shape | only one curve matters; >6 curves | base_expr, param, param_values[] | one curve per param value
- `FUNCTION_PLOT.piecewise` — function defined by cases | continuous single expression | pieces[condition, expr], breakpoints | piece
- `CALCULUS_VIZ.secant_to_tangent` — derivative as limit of secant slope | not teaching limits/derivative | curve, point_a, point_b→a sequence | each secant, then tangent
- `CALCULUS_VIZ.riemann` — integral as limit of rectangle sum | not teaching integration | curve, interval, n_values[4,8,16,...] | each rectangle set
- `CALCULUS_VIZ.area_under` — definite integral as signed area | area is not the concept | curve, a, b | shaded region sweep
- `CALCULUS_VIZ.slope_field` — solutions of a 1st-order ODE | no ODE context | dydx expr, grid, sample_solution | field, then solution curve

**GEOMETRY / NUMBER_LINE / PROOF_LADDER**
- `GEOMETRY.construction` — compass-and-straightedge or step-built figure | final figure only matters (use labelled) | steps[primitive, args], final_labels | construction step
- `GEOMETRY.labelled_figure` — a named polygon/solid with sides, angles, marks | the figure must be *built* to be understood | shape, vertices, labels[edge/angle], congruence marks | label group
- `GEOMETRY.transformation` — translate/rotate/reflect/dilate a shape | no transformation; >2 composed | pre_image, transform[type, params] | pre-image, mapping, image
- `GEOMETRY.solid_net` — 3D solid unfolded to 2D net | net is irrelevant | solid, faces, fold_edges | fold
- `NUMBER_LINE.line` — position/order of numbers, integers or reals | 2D relationships; many points cluttering | range, ticks, points[value,label] | point
- `NUMBER_LINE.inequality` — solution set of an inequality | equality; system in 2 vars | boundary, open/closed, direction | boundary then ray
- `NUMBER_LINE.fraction_bar` — fractions / ratios / percentages of one bar | >~8 partitions; non-part-whole | whole, partitions, shaded[] | partition
- `PROOF_LADDER.statement_reason` — two-column geometry / logic proof | one-liner; purely computational | rows[statement, reason] | row
- `PROOF_LADDER.derivation_chain` — algebra/physics: each line follows from the last | steps are independent facts | lines[expr, justification] | line
- `PROOF_LADDER.proof_tree` — natural deduction / recursive structure | linear derivation reads fine | premises, rules, conclusion | inference

**ML_VIZ**
- `ML_VIZ.regression_fit` — fitting a line/curve to points; residuals; "best" | classification; no fitting concept | points[x,y], candidate_models[], chosen, residuals:bool, equation | see Part D worked example
- `ML_VIZ.decision_boundary` — how a classifier partitions feature space | >2 features; regression | points[x,y,class], boundary curve/regions | points, then boundary, then regions
- `ML_VIZ.gradient_descent` — iterative minimisation of a loss | closed-form solution; no optimisation | loss_surface or loss_curve, start, path[params...], lr | each step along path
- `ML_VIZ.loss_curve` — training vs validation loss over epochs | single value; no training loop | epochs, train[], val[], marks[early_stop] | series then epoch sweep
- `ML_VIZ.tree_split` — how a decision tree partitions data at each node | non-tree model | dataset, splits[feature, threshold], resulting_regions | split
- `ML_VIZ.kmeans` — iterative clustering | supervised task; k unknown and unmotivated | points[], k, init_centroids, iterations[assignments, centroids] | iteration
- `ML_VIZ.bias_variance` — under/overfitting tradeoff | not discussing model complexity | complexity axis, train_err, test_err, sweet_spot | curve, then regions
- `ML_VIZ.confusion_matrix` — see MATRIX_GRID.confusion_matrix | — | — | cell

**DATA_STRUCTURE / ALGORITHM_TRACE**
- `DATA_STRUCTURE.array` — indexed contiguous cells; index vs value | linked / hierarchical data | cells[value], indices, pointers[name→index] | cell / pointer move
- `DATA_STRUCTURE.linked_list` — nodes + next pointers, insertion/deletion | random access is the point (use array) | nodes[value], links, head, (tail) | node / pointer
- `DATA_STRUCTURE.stack_queue` — LIFO/FIFO discipline | random access; priority (use heap) | items[], mode, top/front/back | push/pop frame
- `DATA_STRUCTURE.binary_tree` — BST / heap / expression tree | n-ary or graph | nodes[value], left/right, root, highlights | node
- `DATA_STRUCTURE.hash_table` — buckets, hash function, collisions | ordered data; ranges | buckets[], entries[key,hash,bucket], collision_chain | insert
- `DATA_STRUCTURE.graph` — vertices + edges, weighted/directed optional | tree (use binary_tree); flow (Sankey) | nodes[id,label], edges[a,b,w,directed] | node / edge
- `ALGORITHM_TRACE.sort_bars` — comparison/swap-based sorting step by step | non-comparison sort; array huge | array[], steps[{compare:[i,j]}|{swap:[i,j]}|{mark:[...]}], sorted_prefix | step
- `ALGORITHM_TRACE.pointer_walk` — two-pointer / sliding-window / binary search | recursion-heavy algorithm | array, pointers[name], steps[pointer moves, window] | step
- `ALGORITHM_TRACE.recursion_tree` — recursive call structure & return values | iterative algorithm | calls[args→result, children], order | call (pre-order), then returns
- `ALGORITHM_TRACE.dp_table` — filling a 1D/2D DP table cell by cell | greedy / non-DP | table dims, recurrence, fill_order[cells], deps per cell | cell
- `ALGORITHM_TRACE.call_stack` — stack frames pushed/popped during execution | no nesting | frames[func, locals], events[push|pop] | frame

**CIRCUIT / PHYSICS / CHEM / BIO**
- `CIRCUIT.schematic` — components + wiring, analysis target | block-level only (use block_diagram); >~15 components | components[type,id,value,nodes], wires, source | component, then wire, then annotation (V/I)
- `CIRCUIT.logic_gates` — boolean logic from gates | arithmetic circuits at transistor level | gates[type,in,out], inputs, output, (truth table) | gate
- `CIRCUIT.block_diagram` — system as functional blocks + signal flow | you need actual component values | blocks[label], signals[from,to,label] | block
- `PHYSICS_DIAGRAM.free_body` — forces on one object | multi-body without isolating; kinematics only | object, forces[label, magnitude, angle], axes | force vector
- `PHYSICS_DIAGRAM.ray_optics` — lenses/mirrors, image formation | wave optics; no optical elements | elements[type,focal,pos], object, rays[3 principal] | ray
- `PHYSICS_DIAGRAM.wave` — wavelength/amplitude/phase/superposition | not periodic; frequency-domain only | waves[amp,wavelength,phase], sum:bool | wave, then sum
- `PHYSICS_DIAGRAM.field_lines` — E/B/gravitational field around sources | quantitative field values (use heatmap) | sources[charge/pole, pos], line_density | source, then lines
- `PHYSICS_DIAGRAM.energy_bar` — KE/PE/heat at stages of a process | continuous function of time (use line) | stages[label], bars[type,value] | stage
- `CHEM_DIAGRAM.molecule_2d` — skeletal structure, functional groups | 3D geometry is the point (use orbital/VSEPR) | atoms[element,pos], bonds[a,b,order], charges | bond / group
- `CHEM_DIAGRAM.mechanism` — electron-pushing arrows between structures | overall equation only (use reaction) | steps[reactants, arrows[from,to], products] | arrow
- `CHEM_DIAGRAM.energy_profile` — reaction coordinate vs energy, Ea, ΔH | thermodynamics without kinetics context | coordinate, points[label,energy], catalyst_path? | segment
- `CHEM_DIAGRAM.titration_curve` — pH vs volume, equivalence point, buffer region | non-acid-base; single measurement | points or model, equivalence_pt, pKa marks | curve, then region marks
- `BIO_DIAGRAM.anatomy_labelled` — parts of a structure named with leader lines | process/flow (use cycle); molecular scale | image or shape, labels[part, anchor] | label
- `BIO_DIAGRAM.punnett` — Mendelian cross outcomes | polygenic; linkage | parent_alleles, grid cells, phenotype ratios | cell
- `BIO_DIAGRAM.food_web` — feeding relationships in an ecosystem | linear chain (use PROCESS_LINEAR); energy pyramid (use HIERARCHY_NEST) | organisms[name, trophic], arrows[eaten_by] | organism / arrow
- `BIO_DIAGRAM.phylo_tree` — evolutionary relationships | non-evolutionary classification (use taxonomy) | taxa, clades, branch order, (branch lengths) | node

**ANNOTATION_LAYER** (compose on top of any visual above)
- `ANNOTATION_LAYER.callout_pin` — attach a note to a point on any visual | the note applies to the whole visual (use caption) | anchor[x,y or ref], text | pin
- `ANNOTATION_LAYER.spotlight` — dim everything except one region | nothing to isolate | target region/ref, dim_opacity | reveal step (see Part C `focus`)
- `ANNOTATION_LAYER.magnifier_inset` — zoomed detail of a small region | detail is legible at full size | source_region, inset_position, zoom | inset appear
- `ANNOTATION_LAYER.dimension_line` — measured distances/angles on a figure | measurements not relevant | measurements[from,to,label] | measurement
- `ANNOTATION_LAYER.attention_arrow` — direct the eye along a path | the order is obvious | path[points], label | arrow

### B.3 The 8 parametric axes (how 220 → 1000+)

Each named variant accepts a subset of these. A distinct legal combination is a
distinct visual with its own layout, and often its own *use-when*:

| Axis | Values | Notes / when it changes the advice |
|---|---|---|
| **orientation** | horizontal, vertical, radial, isometric | e.g. `TIMELINE.dated` vertical is for mobile / many-events; horizontal for ≤7 |
| **cardinality** | tiny (≤3), small (4–7), medium (8–15), large (16–40), dense (40+) | crossing a band usually *changes the recommended variant* (bar→dot plot, pie→bar, network→matrix) |
| **emphasis** | neutral, single-highlight, ranked, threshold-band, delta (vs baseline) | highlight/threshold/delta each add data fields and a reveal step |
| **data mode** | schematic (illustrative), data-driven (to scale), hybrid | schematic FUNCTION_PLOT for intuition; data-driven for real measurements |
| **annotation layers** | 0…n stacked ANNOTATION_LAYER items | each layer is independently revealable |
| **dimensionality** | 1D, 2D, 2.5D (stacked/iso), 3D (only when the 3rd dim is essential) | 3D only for solids, surfaces, molecular geometry, loss surfaces |
| **encoding** | position, length, angle, area, color-sequential, color-diverging, color-categorical, size, texture | picking an encoding is a sub-choice with its own accessibility rules (see `dataviz` skill) |
| **motion state** | static, build (progressive reveal), animate (continuous), scrub (user-controlled) | Part C |

**Worked count:** 40 families → ~220 named variants → average ~5 legal
parametric combinations that are *materially different* (different layout OR
different use-when) → **~1100 addressable visuals**. The catalog file enumerates
them; the renderer implements ~40 family renderers that each read the
variant + params.

### B.4 Universal "do not use a visual at all" rules

Return `TEXT.minimal` / `TEXT.keep` when:

- the wording is legally/mathematically exact (definitions, theorems, statutes, quotes, code, formulae-in-prose);
- there are fewer than 3 structured elements and no relationship between them;
- the only structure is "these are N things" with no order, hierarchy, comparison, quantity, or process → use `LIST_STRUCTURED` or `CARD_GRID`, not a diagram;
- the data needed for the chart is not actually present in the source (never invent numbers, dates, or coordinates);
- a forced diagram would misrepresent the content (e.g. implying order where there is none, implying a loop where there is none, implying causation from correlation).

---

## Part C — Progressive-reveal & animation grammar

Teachers rarely want the finished slide shown at once. A slide is a **scene**
built from an ordered list of **reveal steps**; each step *adds, transforms, or
focuses* elements. Presenter advances with a click/arrow key; export to `.pptx`
maps each step to a PowerPoint animation entrance; export to Reveal.js maps each
step to a `fragment`.

### C.1 Data model

```jsonc
"animation": {
  "mode": "build",              // static | build | animate | scrub
  "steps": [
    {
      "id": "s1",
      "label": "Raw data points",     // presenter note / what to say
      "adds":    ["pt.0","pt.1","pt.2","pt.3","pt.4"],   // element ids to show
      "transforms": [],                                   // see C.3
      "focus":   [],                                      // ids to spotlight, others dimmed
      "removes": [],                                      // ids to hide again
      "effect":  "fade",           // fade | draw | grow | slide-left | pop | count-up | trace
      "duration_ms": 400,
      "stagger_ms": 60,            // per-child delay when `adds` is a list
      "wait_for": "click"          // click | auto | auto-after:2000
    }
  ],
  "final_state_is_last_step": true
}
```

Every element the renderer draws gets a stable **id** with a dotted namespace so
steps can address it: `axis.x`, `axis.y`, `pt.3`, `line.candidate.2`,
`resid.3`, `line.bestfit`, `eq`, `label.slope`, `region.q2`, `node.n4`,
`edge.n1_n2`, `bar.2`, `rect.riemann.8`, `frame.factorial_3`.

### C.2 Reveal-unit defaults per family (what one click adds)

| Family | Default reveal unit(s), in order |
|---|---|
| TEXT / BULLETS | one bullet per step; takeaway last |
| DEFINITION / QUOTE / METRIC | single step (indivisible) |
| PROCESS_LINEAR | node, then its outgoing edge |
| PROCESS_CYCLIC | stage clockwise; arrows appear with the stage they leave |
| DECISION | root question → each branch → outcome |
| TIMELINE | event in chronological order; milestone gets emphasis effect |
| HIERARCHY_* | breadth-first: root, then each level |
| COMPARE_TABLE | header row (as a set) → one aspect row per step; highlight cells last |
| MATRIX_GRID | axes first → quadrant labels → items into quadrants |
| SET_DIAGRAM | each set outline → unique members → shared region |
| CHART_CATEGORICAL | axes → gridlines → one series → (highlight/threshold) |
| CHART_TREND | axes → each series drawn left-to-right (`effect:"draw"`) → markers → annotation |
| CHART_PART_TO_WHOLE | whole → largest slice → remaining slices → highlight |
| CHART_RELATIONSHIP | axes → point cloud (`effect:"pop"`, staggered) → trend line → annotation |
| FUNCTION_PLOT | axes → curve draw → key points → asymptotes/labels |
| CALCULUS_VIZ | see C.5 (secant→tangent, Riemann n=4→8→16) |
| GEOMETRY.construction | one primitive per step; labels after the figure closes |
| PROOF_LADDER | one row/line per step; QED/box last |
| ML_VIZ | see Part D |
| DATA_STRUCTURE | structure skeleton → values → pointers → per-operation frames |
| ALGORITHM_TRACE | one algorithm step per click (compare, swap, mark, recurse, fill) |
| CIRCUIT | components → wires → source on → V/I annotations |
| PHYSICS.free_body | object → one force vector per step → net force → axes/resolution |
| CHEM.mechanism | one curved arrow per step → resulting intermediate |
| BIO.anatomy | one label per step (or grouped by system) |

### C.3 Transform operations (for `transforms[]`)

```jsonc
{ "target": "line.candidate.2", "op": "move",     "to": {"slope": 1.4, "intercept": 0.2}, "duration_ms": 600 }
{ "target": "line.candidate",   "op": "morph-to", "ref": "line.bestfit" }      // collapse a family into one
{ "target": "pt.3",             "op": "recolor",  "to": "warning" }
{ "target": "region.overfit",   "op": "shade",    "to": 0.15 }
{ "target": "bar.*",            "op": "sort",     "by": "value", "order": "desc" }
{ "target": "camera",           "op": "zoom",     "to": {"x":[0.9,1.1],"y":[0.9,1.1]} }   // limit-zoom
{ "target": "shape.triangle",   "op": "reflect",  "axis": "y" }
```

`op` vocabulary: `move`, `morph-to`, `recolor`, `resize`, `shade`, `sort`,
`zoom`, `pan`, `rotate`, `reflect`, `translate`, `dilate`, `count-up`,
`draw-along` (trace a path), `pulse` (attention), `dim-others`.

### C.4 Rules the LLM must follow when authoring steps

1. **One idea per step.** A step may reveal a *set* only if the audience reads it
   as one unit (a table header row, the two halves of a Venn, the 3 principal
   rays of a lens *only if* the lesson treats them together).
2. **Never reorder content** to make steps; groups are consecutive in reading
   order (top→bottom, left→right, chronological, base→apex, algorithm order).
3. **Scaffold before payload.** Axes/containers/skeletons appear before data.
   Labels and equations appear *after* the thing they describe.
4. **The takeaway / conclusion / QED / equation is always the last step.**
5. **Indivisible visuals get exactly one step** (QUOTE, METRIC, single
   DEFINITION, a single labelled photo with no parts).
6. **Cap at ~7 steps per slide.** More → split into a continuation slide. (CLT:
   working-memory limit; mirrors the PSF/CLASS segmentation goal.)
7. **`focus` beats `remove`.** Prefer dimming other elements to hiding them, so
   context is preserved — unless the slide is genuinely replacing content.
8. **`effect` matches the meaning:** `draw` for curves/paths, `count-up` for
   metrics, `grow` for bars, `pop` for scatter points, `trace` for
   pointers/arrows-of-attention, `fade` as the neutral default.
9. **Continuous animation (`mode:"animate"`) only** for things that are
   inherently moving (a wave, an orbit, a pendulum, gradient descent playing
   automatically); everything instructional is `mode:"build"`.
10. If the source does not imply a walk-through, emit a single step containing
    all elements (`mode:"static"` in effect).

### C.5 Worked examples

**(1) Linear regression — the requested case** (`ML_VIZ.regression_fit`)

Elements: `axis.x`,`axis.y`, `pt.0..pt.n`, `line.candidate.0..k`, `resid.0..n`,
`line.bestfit`, `eq`, `label.slope`, `label.intercept`.

| Step | label (what the teacher says) | adds / transforms | effect |
|---|---|---|---|
| 1 | "Here is our data — hours studied vs exam score." | `axis.x`,`axis.y` | fade |
| 2 | "Each student is one point." | `pt.0..pt.n` | pop, stagger 60ms |
| 3 | "We want a straight line y = mx + c to summarise the trend." | `line.candidate.0` (a poor guess) | draw |
| 4 | "It could be any of these — which is best?" | `line.candidate.1..k` (fan of lines) | draw, stagger 120ms |
| 5 | "For a given line, the error is the vertical gap to each point." | `resid.*` for the current candidate | draw |
| 6 | "'Best' = the line that makes the total squared error smallest." | transform: `line.candidate.*` `morph-to` `line.bestfit`; `resid.*` shrink | move 800ms |
| 7 | "That line is our model." | `eq` ("score = 4.2·hours + 61"), `label.slope`, `label.intercept` | fade |

(Optional step 8, `mode:"animate"` mini-clip: gradient descent walking the
candidate line down the loss curve — only if the lesson covers *how* it's found.)

**(2) Bubble/insertion sort** (`ALGORITHM_TRACE.sort_bars`)
Skeleton bars → step per `{compare:[i,j]}` (pulse both) → step per `{swap:[i,j]}`
(slide-swap) → `{mark:[i]}` greys the settled suffix → final step: all green.

**(3) Derivative as a limit** (`CALCULUS_VIZ.secant_to_tangent`)
axes → curve draw → fix point P → secant PQ with Q far → `transform camera`
none, `transform Q move` closer (steps for Q at h=2,1,0.5,0.25) → secant
`morph-to` tangent → label slope = f′(x).

**(4) Factorial recursion** (`ALGORITHM_TRACE.recursion_tree` + `call_stack`)
One step per call pushed (`frame.factorial_n` slides onto stack, tree node
appears pre-order) → base case highlighted → one step per return (frame pops,
node annotated with value) → root shows final result.

**(5) Titration curve** (`CHEM_DIAGRAM.titration_curve`)
axes (pH vs mL) → curve `draw` left-to-right → mark buffer region (`shade`) →
mark half-equivalence (pKa) → mark equivalence point → final annotation.

---

## Part D — Mapping to existing Learnova code

| This spec | Today | Change needed |
|---|---|---|
| `FAMILY.VARIANT` id | flat `treatment` string | add `variant` + `params` to `SelectedVisual` / master-prompt JSON |
| 1000-visual catalog | 20 `Treatment` rows | generate `docs/visual_catalog.yaml`; `visual_selector._score` reads it |
| `animation.steps` | `reveal_groups: [[int]]` (planned, unrendered) | superset — keep `reveal_groups` as the degenerate case; add `steps[]` |
| step → PPTX | none | `rendering/ppt_builder.py`: map `effect` → `python-pptx` entrance animation |
| step → web | none | `rendering/web_deck_builder.py`: emit `<... class="fragment" data-fragment-index=...>` + a small JS for `transforms` |
| deterministic fallback | `visual_selector.select_visual` | extend `plan_reveal_groups` → `plan_animation_steps` using C.2 defaults |

---

## Part E — The Master Prompt (copy-paste, drop-in for `master_prompt.py`)

> Replaces `MASTER_SYSTEM_PROMPT`. The user message is still built by
> `build_user_prompt(text, title, image_ocr)`. Output is strict JSON.

```
You are Learnova's Master Instructional Designer. You convert ONE chunk of raw
lecture material (text, notes, and any OCR of an embedded figure) into ONE
structured, teachable slide with a step-by-step reveal plan.

Return ONE strict JSON object and nothing else. Make FIVE decisions.

════════ DECISION 1 — CONTENT (never lose a teachable point) ════════
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

════════ DECISION 2 — VISUAL (family.variant + params) ════════
Pick the ONE visual whose STRUCTURE matches the content's structure, not its
keywords. Output "family", "variant", and "params". If nothing structural fits,
use family "TEXT" (variant "keep" for precision-critical wording, else "minimal").
A forced diagram is worse than clean text.

Families and when to use them:
- TEXT: prose or precision-critical wording or <3 unrelated facts.
  variants: keep, minimal, bullets
- DEFINITION / QUOTE / KPI: one term+meaning / one statement / one headline number.
- LIST_STRUCTURED: N items with no order/quantity/relation. variants: checklist,
  ranked, do_dont, steps_list
- PROCESS_LINEAR: ordered procedure, 3–12 steps, maybe branches. variants:
  flowchart, pipeline, swimlane, funnel, chevron
- PROCESS_CYCLIC: repeating process, no start/end. variants: cycle, feedback_loop,
  iteration_loop
- DECISION: nested yes/no choices. variants: tree, if_then_ladder, truth_table
- STATE_MACHINE: states + transitions / lifecycle / phases.
- TIMELINE: 3+ dated or strictly chronological events. variants: dated, gantt,
  roadmap, era_band
- HIERARCHY_TREE: is-a / reports-to / contains tree. variants: org_chart,
  taxonomy, bracket, dendrogram
- HIERARCHY_NEST: levels that build/nest. variants: pyramid, layered_model,
  treemap, sunburst
- MIND_MAP: one centre, loose branches. variants: radial, concept_map, spider
- COMPARE_TABLE: 2–5 things × shared aspects. variants: comparison, feature_matrix,
  rubric
- COMPARE_VISUAL: two opposed things/states. variants: before_after, split_screen,
  pros_cons
- MATRIX_GRID: items on two axes. variants: quadrant_2x2, eisenhower,
  confusion_matrix, heatmap_grid
- SET_DIAGRAM: 2–3 sets, shared + unique. variants: venn2, venn3, euler
- CHART_CATEGORICAL: value across categories. variants: bar, grouped_bar,
  stacked_bar, pareto, lollipop, dot_plot
- CHART_TREND: value over ordered/time x. variants: line, multi_line, area,
  stacked_area, step, slope
- CHART_PART_TO_WHOLE: parts of one whole ≈100%. variants: pie, donut,
  stacked_100, waffle, icon_array
- CHART_DISTRIBUTION: shape of a numeric variable. variants: histogram, box,
  violin, density, ecdf
- CHART_RELATIONSHIP: two numeric variables. variants: scatter, bubble,
  connected_scatter, correlation_heatmap
- CHART_RANKING: order by value. variants: ordered_bar, bump, dumbbell, tornado
- CHART_FLOW: flow / relationships. variants: sankey, alluvial, chord, network,
  arc
- CHART_SPATIAL: value per place. variants: choropleth, dot_map, flow_map
- CHART_SPECIAL: radar, parallel_coordinates, gauge, bullet, funnel
- FUNCTION_PLOT: y=f(x). variants: curve, family, piecewise, parametric, polar
- CALCULUS_VIZ: secant_to_tangent, riemann, area_under, slope_field, limit_zoom
- LINEAR_ALGEBRA: vector, grid_transform, projection, span
- GEOMETRY: construction, labelled_figure, transformation, circle_theorem,
  solid_net
- NUMBER_LINE: line, inequality, interval, fraction_bar
- PROOF_LADDER: statement_reason, derivation_chain, proof_tree
- ML_VIZ: regression_fit, decision_boundary, gradient_descent, loss_curve,
  tree_split, kmeans, bias_variance, confusion_matrix
- DATA_STRUCTURE: array, linked_list, stack_queue, binary_tree, hash_table, graph
- ALGORITHM_TRACE: sort_bars, pointer_walk, recursion_tree, dp_table, call_stack
- CIRCUIT: schematic, logic_gates, block_diagram
- PHYSICS_DIAGRAM: free_body, ray_optics, wave, field_lines, energy_bar,
  projectile
- CHEM_DIAGRAM: molecule_2d, mechanism, energy_profile, titration_curve, orbital
- BIO_DIAGRAM: anatomy_labelled, cell, punnett, food_web, phylo_tree

params (include only those that apply):
  orientation: horizontal|vertical|radial|isometric
  cardinality: tiny|small|medium|large|dense
  emphasis: neutral|highlight|ranked|threshold|delta
  data_mode: schematic|data_driven|hybrid
  dimensionality: 1d|2d|2.5d|3d
  highlight: [element ids or labels to call out]
  annotations: [{type: callout_pin|spotlight|magnifier|dimension_line|attention_arrow,
                 anchor: "...", text: "..."}]

DO NOT choose a visual when: the wording is exact (→ TEXT.keep); <3 structured
elements with no relation (→ TEXT or LIST_STRUCTURED); the chart's data is absent
from the source; a diagram would imply order/loop/causation that is not stated.

Provide the structured data the chosen visual needs in the matching sub-object
(schemas below) and OMIT all the others.

════════ DECISION 3 — TEXT TREATMENT PER SENTENCE ════════
For each source sentence: VERBATIM (definition/theorem/quote/legal/code/formula),
TIGHTEN (wordy prose → punchy bullet), or MERGE (near-duplicates). Put every
verbatim-critical sentence in "verbatim" so later trimming never touches it.

════════ DECISION 4 — IMAGE HANDLING ════════
Choose one "image_action":
KEEP_AS_IS | SUMMARISE_TO_STRUCTURE | ENHANCE | REGENERATE | CAPTION_ONLY | DROP |
NONE. If a diagram/chart image really carries structured data, choose
SUMMARISE_TO_STRUCTURE and re-express it as a native visual above.

════════ DECISION 5 — PROGRESSIVE REVEAL / ANIMATION ════════
Build "animation": an ordered "steps" list that walks a presenter through the
slide one click at a time. Each element you draw has a dotted id
(e.g. axis.x, pt.3, line.bestfit, eq, row.2, node.n4, bar.1). A step lists the
ids it "adds", any "transforms", ids to "focus" (others dim), ids to "removes",
an "effect" (fade|draw|grow|pop|count-up|trace|slide-left), and "wait_for"
("click" unless the motion is inherently continuous, then "auto").

Rules:
- One idea per step. A set is allowed in one step only if read as a unit
  (a table header row, both halves of a Venn).
- Never reorder content. Steps follow reading order (top→bottom, left→right,
  chronological, base→apex, algorithm order).
- Scaffolding first (axes, containers, skeletons); labels and equations AFTER the
  thing they describe; the takeaway/QED/equation is ALWAYS the final step.
- Indivisible visuals (QUOTE, KPI, single DEFINITION) = exactly one step.
- Max 7 steps. If more are needed, keep the 7 highest-value and note the rest
  belong on a continuation slide.
- mode: "build" for anything instructional; "animate" only for inherently moving
  things (wave, orbit, pendulum, auto-playing gradient descent); "static" if the
  source implies no walk-through (then one step with everything).
- effect must match meaning: draw for curves/paths, grow for bars, count-up for
  metrics, pop for scatter, trace for pointers/arrows, fade otherwise.

════════ OUTPUT — return ONLY this JSON ════════
{
  "title": "Clean, specific slide title",
  "takeaway": "One high-yield sentence or empty string",
  "bullets": ["every teachable point, tightened but complete"],
  "verbatim": ["sentences that must never be edited or trimmed"],

  "family": "<one FAMILY>",
  "variant": "<one variant of that family>",
  "params": { "orientation":"", "cardinality":"", "emphasis":"",
              "data_mode":"", "dimensionality":"", "highlight":[], "annotations":[] },

  "image_action": "<KEEP_AS_IS|SUMMARISE_TO_STRUCTURE|ENHANCE|REGENERATE|CAPTION_ONLY|DROP|NONE>",
  "image_caption": "Caption if an image is kept, else empty",

  "data": {
    // include ONLY the one sub-object matching "family"
    "flowchart":   {"nodes":[{"id":"n1","label":"","type":"start|process|decision|end"}],"edges":[{"from":"n1","to":"n2","condition":""}]},
    "cycle":       {"stages":["",""]},
    "timeline":    {"events":[{"date":"","title":"","description":"","is_milestone":false}]},
    "table":       {"headers":["Aspect","A","B"],"rows":[["","",""]],"highlight_cells":[{"row":0,"col":1}]},
    "pros_cons":   {"pros":[""],"cons":[""]},
    "matrix":      {"x_axis":"","y_axis":"","quadrants":{"q1":[""],"q2":[""],"q3":[""],"q4":[""]}},
    "pyramid":     {"levels":["base","","apex"]},
    "venn":        {"sets":["A","B"],"only_a":[""],"only_b":[""],"shared":[""]},
    "mind_map":    {"central":"","branches":[{"name":"","children":[""]}]},
    "chart":       {"chart_type":"bar|line|pie|scatter|area|radar","x_axis":"","y_axis":"","categories":[""],"series":[{"name":"","values":[0]}],"points":[{"x":0,"y":0,"label":""}]},
    "metric":      {"value":"","label":"","description":""},
    "definition":  {"term":"","definition":"","examples":[""]},
    "function_plot":{"expr":"","domain":[0,10],"key_points":[{"x":0,"y":0,"label":""}],"family_param":null,"param_values":[]},
    "geometry":    {"kind":"labelled_figure|construction|transformation","shape":"","vertices":[[0,0]],"labels":[{"on":"edge|angle|vertex","ref":"","text":""}],"steps":[]},
    "proof":       {"kind":"statement_reason|derivation_chain","rows":[{"statement":"","reason":""}]},
    "ml_viz":      {"kind":"regression_fit|decision_boundary|gradient_descent|loss_curve|kmeans|bias_variance",
                    "points":[{"x":0,"y":0,"class":null}],"candidate_models":[{"slope":0,"intercept":0}],
                    "chosen":{"slope":0,"intercept":0},"show_residuals":true,"equation":"","loss":{"epochs":[],"train":[],"val":[]}},
    "data_structure":{"kind":"array|linked_list|stack_queue|binary_tree|hash_table|graph",
                    "cells":[{"id":"","value":""}],"links":[{"from":"","to":""}],"pointers":[{"name":"","at":""}]},
    "algorithm_trace":{"kind":"sort_bars|pointer_walk|recursion_tree|dp_table|call_stack",
                    "initial":[0],"steps":[{"op":"compare|swap|mark|recurse|return|fill","args":[0]}]},
    "circuit":     {"components":[{"id":"","type":"R|L|C|V|diode|npn|gate_and","value":"","nodes":["",""]}],"wires":[["",""]]},
    "physics":     {"kind":"free_body|ray_optics|wave|field_lines|energy_bar","object":"","forces":[{"label":"","mag":0,"angle_deg":0}]},
    "chem":        {"kind":"molecule_2d|mechanism|energy_profile|titration_curve","atoms":[{"el":"C","xy":[0,0]}],"bonds":[{"a":0,"b":1,"order":1}],"arrows":[{"from":"","to":""}]},
    "bio":         {"kind":"anatomy_labelled|punnett|food_web|phylo_tree","labels":[{"part":"","anchor":""}],"parent_alleles":["",""]},
    "list":        {"style":"checklist|ranked|do_dont|steps","items":[{"text":"","group":"do|dont|null"}]},
    "hierarchy":   {"kind":"org_chart|taxonomy|pyramid|treemap","root":"","edges":[{"parent":"","child":""}],"values":{}}
  },

  "animation": {
    "mode": "build|animate|static",
    "steps": [
      {"id":"s1","label":"what the presenter says",
       "adds":["axis.x","axis.y"],"transforms":[],"focus":[],"removes":[],
       "effect":"fade","duration_ms":400,"stagger_ms":60,"wait_for":"click"}
    ]
  }
}

If you cannot produce valid JSON, retry with the minimal shape:
{"title":"","takeaway":"","bullets":[""],"verbatim":[],"family":"TEXT",
 "variant":"minimal","params":{},"image_action":"NONE","image_caption":"",
 "data":{},"animation":{"mode":"static","steps":[{"id":"s1","label":"","adds":["all"],"effect":"fade","wait_for":"click"}]}}
```

---

## Part F — Next implementation steps

1. Generate `docs/visual_catalog.yaml` from Part B (one row per addressable
   visual: `id, family, variant, use_when, avoid_when, needs[], reveal_unit,
   params_allowed[]`).
2. Extend `ai/master_prompt.py`: swap in the Part E prompt; add `variant`,
   `params`, `animation` to the dataclasses and the retry shape.
3. Extend `ai/visual_selector.py`: `plan_animation_steps()` implementing the
   C.2 defaults + C.4 rules as the deterministic fallback / validator.
4. `rendering/web_deck_builder.py`: emit Reveal.js `fragment` markup +
   a `transforms` runtime (small vanilla JS keyed off element ids).
5. `rendering/ppt_builder.py`: map each step to a `python-pptx` entrance
   animation (fade/wipe/grow) — one click = one step.
6. Add ~8–12 new family renderers (FUNCTION_PLOT, ML_VIZ, ALGORITHM_TRACE,
   DATA_STRUCTURE, GEOMETRY, CIRCUIT, PHYSICS_DIAGRAM, CHEM_DIAGRAM) as SVG
   generators that also stamp element ids for the animation layer.
7. Feed `animation.steps` count into PSF/CLASS as the realised segmentation of
   the slide (each step ≈ one cognitive chunk).
