# Learnova — Master Prompt

**Content-Preserving Interactive Learning & Visualization Engine**

> This is the governing document for every Learnova implementation decision.
> When it conflicts with a smaller design note, this wins.

## The one rule

**Never summarize the educational content.**

`CONTENT → VISUALIZATION + INTERACTION + ANIMATION`
not
`CONTENT → SUMMARY`

The source content is the knowledge. The UI, visuals, animations, diagrams,
interactions and simulations are the *delivery mechanism*. Do not reduce the
knowledge — improve the way it is experienced.

Never:

- remove sentences because they are long
- combine multiple sentences into one
- shorten explanations / replace them with terse bullets
- remove examples, terminology, exceptions, notes, supporting detail
- paraphrase unnecessarily or change meaning
- decide some content is "less important" and delete it
- reduce information just to make the UI cleaner

If the original is 500 words, present the 500 words better — progressive
reveal, highlighted keywords, multiple scenes, expandable sections, a
supporting diagram — do **not** cut it to 100.

## Content vs presentation

| Transformation | Verdict |
|---|---|
| Changing *what the material says* (content transformation) | ❌ avoid |
| Changing *how the material is experienced* (presentation transformation) | ✅ the goal |

Acceptable presentation transformations: paragraph → animated scene;
sentence → text + illustration; explanation → interactive diagram; process →
animated flowchart; classification → expandable tree; comparison →
interactive comparison; example → interactive scenario; long section →
multiple presentation states. **The information stays intact.**

## Per-content-block decision

For every paragraph / concept / example / formula / process, decide the
presentation method:

`TEXT · ILLUSTRATION · DIAGRAM · FLOWCHART · TIMELINE · COMPARISON ·
TREE/HIERARCHY · PROCESS_ANIMATION · SIMULATION · INTERACTIVE_CARDS ·
TOOLTIP/HOTSPOT · CHART/GRAPH · FORMULA_VISUALIZATION · IMAGE/ICON · MIXED_MODE`

- **Visual-first ≠ text-free.** Use the minimum visual text needed for
  comprehension while preserving the complete content wherever it carries
  meaning. Text and visuals coexist when both contribute.
- A visual must **not replace** important explanatory content unless the
  content is genuinely redundant. Keep necessary text alongside the visual.
- Visuals **explain**, they don't decorate. Every visual has a purpose.

## Animation & interaction

- Animation communicates something: object A→B for data flow, layers appear
  to build an architecture, steps activate one by one, keywords highlight as
  they're explained, branches expand, before/after transitions, cause →
  effect, formula components appear progressively.
- No decorative bouncing / spinning / particles / distracting motion.
- Every interaction answers: *"what does the learner understand better
  because of this?"* — click-to-reveal, hover-to-explain, drag & drop,
  expandable diagrams, interactive timelines, step-by-step exploration,
  before/after, simulations, zoom, layer toggles, scenario exploration.
- Respect `prefers-reduced-motion`.

## Multi-scene is encouraged

If one concept has too much for a screen, split the **presentation** into
scenes (intro · detailed explanation · visual demo · example · notes ·
interactive exploration). This is not summarizing — it is reorganizing the
experience while preserving the information. Readable content beats
fitting everything on one screen.

## Reuse the visual system

Learnova has a 1000+ visual database/spec system (`docs/visual_catalog.yaml`,
`src/learnova/visual_specs/`, `src/learnova/ai/visual_selector.py`, the
`family_blocks` renderers). For every concept: search the DB → reuse/modify
an existing visual → only design a new spec if nothing fits. Each visual
carries semantic metadata (concept, category, visual type, subjects,
keywords, learning objective, animation type, interaction type, difficulty)
so selection is intelligent, not random.

Reusable component targets: `AnimatedProcess · InteractiveTimeline ·
ConceptDiagram · ComparisonView · ExpandableTree · FormulaVisualizer ·
StepByStepExplanation · InteractiveScenario · VisualCard · HotspotDiagram ·
DataFlowDiagram · BeforeAfterView · ConceptMap · InteractiveSimulation`.

## Content-to-visual mapping layer (core capability)

```
Input content → content analysis → concept detection →
visual-opportunity detection → existing-visual search →
(reuse existing) OR (generate visual spec) →
select layout → select animation → select interaction → render experience
```

## Working on the codebase

- Inspect the actual architecture first — content storage, rendering,
  visual storage/selection, existing components, animation & interaction
  capabilities. Do not assume.
- Reuse existing infrastructure. Don't duplicate components. Don't break
  working functionality. Don't redesign the whole app for one feature.
- Preserve the existing design system unless there's a clear reason.
- Make changes modular and reusable — the goal is a system for thousands of
  concepts, not one beautiful page.
- **When you find summarization logic**: don't rip the feature out — find
  out why it exists, then make content preservation the default. If a
  specific UI element needs a short form, it is a *secondary* representation;
  the complete source content stays accessible.

## Quality gate before "done"

- **Content**: original information preserved? nothing important removed? no
  meaning changed? examples & technical detail kept?
- **Visuals**: each major concept has an appropriate visual opportunity?
  meaningful? existing DB reused? missing visuals specified?
- **Animation**: explains something? smooth? not distracting?
- **Interaction**: improves learning? intuitive? reveals useful info?
- **UX**: readable text? uncluttered? discoverable? clear flow?
- **Technical**: existing functionality still works? components reusable?
  scalable? no unnecessary duplicates?

## The core principle

> **Content preservation first. Visualization second. Interaction third.
> Animation with purpose. No unnecessary summarization.**

When given content or asked to improve a presentation, never start with
"how can I summarize this?" — ask *"what is the learner being told, what
must remain intact, and what is the best visual / animation / interaction /
layout through which they can experience it?"*
