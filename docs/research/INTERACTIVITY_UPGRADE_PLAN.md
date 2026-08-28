# Learnova — Interactivity & Fidelity Upgrade Plan

**Goal (user's words):** *"make boring only-text slides into interactive ones — not fully
summarising. If there are 5 phases, explain each one; don't jump to phase 5. If someone
explained something, don't delete it. Reach the level of how Claude makes slides."*

This is the research + to-do list. We solve items **one by one**, top to bottom.
Each task names the exact files to touch.

---

## Part 0 — What's actually wrong today (root-cause findings)

### A. Images disappear in the web deck / presenter view

| # | Finding | File |
|---|---------|------|
| A1 | `decide_image_action` returns **`SUMMARISE_TO_STRUCTURE`** or **`DROP`** for anything with ≥2 "structure markers" (arrows, "step 1", "phase") or ≥40 OCR words. A photo of a worked example or a labelled diagram trips this instantly. | `ai/image_policy.py:154-161` |
| A2 | When the action is `SUMMARISE_TO_STRUCTURE`, `_image_html` returns `""` — **and nothing rebuilds the figure as a native visual.** The "redraw it" half was never implemented. The image is just gone. | `rendering/web_deck_builder.py:73-74` |
| A3 | The **PPTX always embeds the picture** (`slide.shapes.add_picture`) and never consults `image_policy`. So web deck and PPTX disagree on every single image. | `rendering/ppt_builder.py:561-607` |
| A4 | Continuation slides null the image on purpose (`"image": None`) so it isn't duplicated — correct, but means multi-part topics only show the figure on part 1. | `pipeline/density.py:291,343` |
| A5 | The `deck.json` payload the React presenter reads for the filmstrip/next-slide has **no image data**, so thumbnails can't preview figures. | `storage/deck_library.py`, `apps/api/main.py` `_slides_payload` |

### B. Progressive reveal doesn't work / "jumps to phase 5"

| # | Finding | File |
|---|---------|------|
| B1 | `data-build` → Reveal fragment conversion **only happens in "present mode"** (`?build` in URL, or the parent calling `__enableBuilds()`). A teacher who downloads the `.html` and double-clicks it sees every bullet at once — by design, but not what they expect. | `rendering/web_deck_builder.py:366-398` |
| B2 | The **FLOWCHART layout renders the whole Mermaid diagram at once.** Only the bullet list *beside* it stages. So a 5-step process shows all 5 nodes immediately. | `rendering/web_deck_builder.py:268-287` |
| B3 | Expanded **family visuals** (`_stages`, `_timeline`, `_pyramid`…) *do* carry `data-build` on each chip, so they stage correctly — but only in present mode (see B1), and only when `sp.confidence ≥ 0.62`. Below that it falls back to Mermaid or plain text. | `rendering/family_blocks.py`, `rendering/web_deck_builder.py:195-205` |
| B4 | **PPTX progressive reveal is OFF by default** (`LEARNOVA_PPTX_ANIM=1` required). Exported PPT is a static wall of text even when the web deck stages nicely. | `rendering/ppt_builder.py:629-645`, `rendering/pptx_animation.py` |
| B5 | There is **no "worked example" family** — step-by-step math ("solve this sum") becomes MINIMAL_TEXT or FLOWCHART. No running-derivation visual, no "reveal one line, keep the previous lines" mode. | `ai/master_prompt.py` catalog, `rendering/family_blocks.py` |
| B6 | The web deck depends on **CDN Reveal.js / Mermaid** (cloudflare). Offline, or under a strict CSP, Reveal never initialises and *nothing* works — no slides, no fragments. | `rendering/web_deck_builder.py:334-365` |
| B7 | `plan_reveal_groups` collapses PROS_CONS / VENN to 2 steps and comparison tables to row-by-row; fine, but a 6-item list with a takeaway = 7 steps and hits the hard cap, silently dropping step 8+ from the animation. | `ai/visual_selector.py:501-519`, `:350` |

### C. Over-summarisation — "you deleted the explanation"

| # | Finding | File |
|---|---------|------|
| C1 | `trim_bullet` **hard-truncates** every bullet to `max_words_per_bullet` (low=12, medium=20, heavy=32) and clips at a clause break. The second half of an explanation is discarded, not moved. | `pipeline/density.py:132-157` |
| C2 | The layout LLM prompt says "aim 12-20 words" **and** runs at `reasoning_effort=low` → terse, clipped bullets before density even touches them. | `ai/layout_router.py:66-70`, `providers/groq_provider.py` |
| C3 | `text_policy` only marks **definitions / laws / quotes / code / formulae** as VERBATIM. Ordinary teaching prose ("First we isolate x, because…") is `TIGHTEN` → shortened. | `ai/text_policy.py:55-68` |
| C4 | The Deck Director computes a `summary_directive` (PRESERVE / BALANCED / COMPRESS) **but never applies it to the bullet text** — it only changes the wording of the speaker notes. | `rendering/deck_director.py:196-205,324` |
| C5 | `content_mode` defaults to `"compress"` even for a short typed syllabus that should be **expanded** into teaching detail. Not wired to any expansion pass. | `pipeline/orchestrator.py:79`, nothing consumes it |
| C6 | No **"explain each step" expansion**. The enhancement engine adds side material (examples, analogies) but never turns a 4-word step into a full teaching sentence with the *why*. | `pipeline/enhancer.py`, `enhancement/` |

### D. Web deck ≠ PPTX, and the 1000+ visuals are mostly unused

| # | Finding | File |
|---|---------|------|
| D1 | **Two separate rendering engines.** Web = `family_blocks` (18 renderers) + Mermaid. PPTX = 5 hand-coded layouts (TABLE/METRIC/QUIZ/FLOWCHART/text) + partial `visual_specs/`. They share only the slide model, not the visual logic. | `rendering/web_deck_builder.py` vs `rendering/ppt_builder.py` |
| D2 | Catalog = **41 families / 169 named variants / "1000+ addressable"**. Wired: ~18 web, ~5 PPTX. `build_family_data` only extracts data (no-LLM) for ~8 families; the rest can never render. | `docs/visual_catalog.yaml`, `ai/visual_selector.py:387`, `rendering/family_blocks.py:452-469` |
| D3 | No design decision on **which surface is richer.** Intended: web deck = the interactive, animated, SVG-heavy surface; PPTX = the portable fallback. Today PPTX wins on images, web wins on families — inconsistent both ways. | — |
| D4 | The VMS (`select_visual`) picks a family from text, but with no LLM data-extraction the "data" is often `{}` → renderer returns `None` → falls back to bullets. The 1000+ number is theoretical. | `ai/visual_selector.py:527+` |

### E. Quizzes

| # | Finding | File |
|---|---------|------|
| E1 | Quizzes are interleaved **inline** (a small band at the foot of the slide that closes each run). `inline=False` gives a full QUIZ slide — not currently reachable from the UI. | `ai/quiz_gen.py:118-176` |
| E2 | Placement is **every-N only** (`config.quiz_frequency`). No way to say "put a quiz after slide 7". | `ai/quiz_gen.py:143` |
| E3 | Web-deck quiz is **interactive** (click, colour feedback, explanation). PPTX quiz is **static text**. | `web_deck_builder.py:240-266` vs `ppt_builder.py:197-266` |
| E4 | The Settings "Quiz every N" control writes only `localStorage` — need to confirm it's forwarded to `POST /api/jobs`. | `frontend/src/pages/Settings.jsx`, `frontend/src/api.js`, `apps/api/main.py` |

---

## Part 1 — The to-do list (ordered; do one at a time)

### PHASE 1 — Stop losing content (highest priority: correctness)

- [x] **1.1 — Kill silent image loss.**
  In `web_deck_builder._image_html`, when the policy says `SUMMARISE_TO_STRUCTURE`
  but no native rebuild exists, **fall back to `KEEP_AS_IS`** (show the bitmap +
  caption) instead of returning `""`. Only truly `DROP` (logos/dividers) should
  vanish. Add a `LEARNOVA_IMAGE_KEEP_ALL=1` escape hatch that forces every figure
  to render.
  *Files:* `rendering/web_deck_builder.py`, `ai/image_policy.py`

- [x] **1.2 — Make PPTX and web deck agree on images.**
  Route `ppt_builder`'s image decision through the same `decide_image_action`.
  Keep `KEEP_AS_IS` / `ENHANCE`, caption `CAPTION_ONLY`, skip `DROP`. Same input →
  same figures in both outputs.
  *Files:* `rendering/ppt_builder.py`

- [x] **1.3 — Stop truncating explanations.**
  `trim_bullet`: when a bullet exceeds the word budget, **split it onto a
  sub-bullet / continuation** instead of clipping. Nothing gets an ellipsis and
  vanishes. Raise `max_words_per_bullet` for `medium` to ~28 and add a
  `LEARNOVA_VERBOSE_BULLETS=1`.
  *Files:* `pipeline/density.py`

- [x] **1.4 — Enforce the summary directive.**
  In the density stage, read `deck_plan`'s `summary_directive` per slide:
  `PRESERVE` → skip `trim_bullet` entirely; `BALANCED` → current behaviour;
  `COMPRESS` → current + tighter. Right now the directive is computed and ignored.
  *Files:* `pipeline/density.py`, `pipeline/orchestrator.py` (pass `deck_plan` into `apply_density`)

- [x] **1.5 — Loosen the layout prompt.**
  Change "aim 12-20 words" → "one complete teaching sentence per point, ~15-30
  words, keep the reasoning ('because…', 'so that…')". Bump quiz/layout calls off
  `reasoning_effort=low` for the layout task specifically.
  *Files:* `ai/layout_router.py`, `providers/groq_provider.py`, `providers/router.py`

### PHASE 2 — Real progressive reveal (the "explain phase by phase" fix)

- [x] **2.1 — Stage the Mermaid flowchart.**
  Replace the single all-at-once Mermaid block with a **native step chip flow**
  (reuse `family_blocks._stages`) so each step is a `data-build` element, OR
  post-process the rendered Mermaid SVG to tag each node with a
  `data-fragment-index`. Each phase appears on its own click; earlier phases stay
  visible.
  *Files:* `rendering/web_deck_builder.py`, `rendering/family_blocks.py`

- [x] **2.2 — Add the `WORKED_EXAMPLE` family.**
  New catalog entry + renderer: a vertical list of derivation lines where each
  click reveals the next line **and keeps all previous lines** (accumulating, not
  replacing). Sub-variant `WORKED_EXAMPLE_TWO_COL` = "step | reason". This is the
  "teacher solving a sum" case.
  *Files:* `docs/visual_catalog.yaml`, `ai/master_prompt.py`, `ai/visual_selector.py`
  (detection: numbered lines with `=`, "step", "substitute", "therefore"),
  `rendering/family_blocks.py`, `rendering/ppt_builder.py`

- [x] **2.3 — Progressive reveal in the raw web deck too.**
  Add a small on-slide "▶ step 1 / 5" control (and Space/→ still works) so the
  staging plays even when the file is opened directly, not only via the presenter
  console. Keep an "expand all" toggle for study mode.
  *Files:* `rendering/web_deck_builder.py`

- [x] **2.4 — Turn on PPTX click-builds by default.**
  Flip `LEARNOVA_PPTX_ANIM` default to on. Wire `deck_plan.animation.steps` →
  `apply_click_builds` for every layout, not just text. Verify in real PowerPoint
  + Keynote + Google Slides.
  *Files:* `rendering/ppt_builder.py`, `rendering/pptx_animation.py`

- [x] **2.5 — Raise / handle the 7-step cap.**
  When a slide's reveal groups > 7, **paginate the visual** (steps 1-4 on slide
  A, 5-8 on slide B with 1-4 recapped dim) instead of dropping steps 8+ from the
  animation.
  *Files:* `ai/visual_selector.py`, `pipeline/density.py`

- [ ] **2.6 — Self-host Reveal.js + Mermaid (offline-safe).**
  Inline (or bundle as data-URI) Reveal core + notes + highlight + Mermaid so the
  web deck works with no network and under any CSP. This currently silently
  breaks everything when cloudflare is unreachable.
  *Files:* `rendering/web_deck_builder.py`, add `assets/vendor/` (build step to fetch+pin)

### PHASE 3 — "Explain each thing in detail" (anti-summariser)

- [x] **3.1 — Add an expansion pass.**
  New stage between `layout` and `density`: for each terse step/bullet, if
  `content_mode == "expand"` (default it to expand for typed input < N chars),
  call the LLM to turn "Isolate x" → "Isolate x by subtracting 3 from both sides,
  so the variable term stands alone." Keep the original as the headline, the
  expansion as a reveal sub-line.
  *Files:* new `pipeline/expander.py`, `pipeline/orchestrator.py`, `ai/master_prompt.py`

- [x] **3.2 — Protect more teaching prose as VERBATIM-ish.**
  Add a `KEEP_REASONING` treatment to `text_policy`: sentences containing
  causal/procedural cues ("because", "so that", "which means", "first / then /
  next / finally", "note that") are kept in full, only lightly cleaned.
  *Files:* `ai/text_policy.py`, `pipeline/density.py`

- [x] **3.3 — Speaker notes carry the full explanation.**
  Even when the slide bullet is short, the speaker-notes pane (web presenter +
  PPTX notes) should hold the complete sentence the source had, so the teacher
  never loses the detail.
  *Files:* `rendering/deck_director.py` (`build_speaker_notes`)

- [x] **3.4 — "Density = teaching" profile.**
  Add a 4th density profile `teaching` (between medium and heavy): full-sentence
  bullets, every step kept, expansion pass on, reveal one-per-click. Make it the
  default for typed input.
  *Files:* `pipeline/density.py`, `frontend/src/pages/Settings.jsx` + `Create.jsx`

### PHASE 4 — Unify the two outputs + light up the visual library

- [x] **4.1 — One visual spec, two renderers.**
  Define a single `VisualSpec` (family + variant + data + animation) as the
  contract. `web_deck_builder` and `ppt_builder` each become a *renderer* of that
  spec. The Deck Director already produces most of it — formalise it.
  *Files:* new `rendering/visual_spec.py`, refactor both builders, `rendering/deck_director.py`

- [x] **4.2 — Web deck = the rich surface.**
  Decision: the web deck renders the full family set as SVG/HTML with animation;
  the PPTX renders the best static approximation of the same spec (native shapes,
  no JS). Document this in `DECK_DIRECTOR.md`.

- [x] **4.3 — LLM data-extraction for families.**
  `build_family_data` is text-only heuristics for ~8 families. Add an LLM
  extraction path (`TASK_VISUAL_DATA`) that, given the slide text + chosen family,
  returns the structured `data` the renderer needs (timeline events with dates,
  pyramid levels, matrix cells, cycle stages, tree nodes…). This is what unlocks
  the other 30 families.
  *Files:* `ai/visual_selector.py`, new prompt in `ai/master_prompt.py`, `providers/router.py`

- [x] **4.4 — Fill in the missing renderers.**
  Prioritised by frequency in real lecture content: `MATRIX_2x2`, `CYCLE` (proper
  ring, not chips), `TREE` / `ORG_CHART`, `MIND_MAP`, `GANTT` / `ROADMAP`,
  `FUNNEL`, `COMPARISON_MATRIX` (n×m), `LABELLED_DIAGRAM` (image + callout pins),
  `NUMBER_LINE`, `STAT_CALLOUT_GRID`.
  *Files:* `rendering/family_blocks.py` (+ PPTX equivalents)

- [ ] **4.5 — Variant selection.** _(deferred — polish)_
  Once families render, use the catalog's `params` axes (density, orientation,
  emphasis) to pick a *variant* per slide from PSF signals — this is where the
  "1000+" actually materialises.
  *Files:* `ai/visual_selector.py`, `rendering/deck_director.py`

### PHASE 5 — Quizzes

- [ ] **5.1 — Full interactive quiz slide, placement of choice.**
  Let the user mark "insert a checkpoint after slide N" (multiple allowed) in the
  editor. Generate a **standalone interactive** QUIZ slide there (not the inline
  band). Web = clickable; PPTX = the question on the slide with the answer +
  explanation on the next (or in the notes).
  *Files:* `ai/quiz_gen.py`, `pipeline/orchestrator.py`, `apps/api/main.py`,
  `frontend/src/pages/Create.jsx` / `Preview.jsx`

- [ ] **5.2 — Confirm `quiz_frequency` reaches the backend.**
  Trace Settings → `api.js` → `POST /api/jobs` → `PipelineConfig.quiz_frequency`.
  Add it to the Create form, not just Settings.
  *Files:* `frontend/src/api.js`, `frontend/src/pages/Create.jsx`, `apps/api/main.py`

- [ ] **5.3 — Better PPTX quiz.**
  Question slide → reveal options on click → reveal correct + explanation on final
  click (using the same `apply_click_builds`). No more static wall.
  *Files:* `rendering/ppt_builder.py`, `rendering/pptx_animation.py`

- [ ] **5.4 — Quiz quality.**
  One MCQ per 3 slides is thin. Generate 1 per *concept*, tag difficulty, ensure
  distractors are plausible (near-miss on the same concept), add a short "why the
  others are wrong" line.
  *Files:* `ai/quiz_gen.py`, `ai/master_prompt.py`

### PHASE 6 — Frontend UI features (user: "frontend is good, add more")

- [ ] **6.1 — Slide-by-slide editor in Preview.**
  Per-slide: edit title/bullets, change the visual family (dropdown of the
  catalog), reorder, delete, "insert quiz after this", "split into two". Re-render
  that slide live.
  *Files:* `frontend/src/pages/Preview.jsx`, new `components/app/SlideEditor.jsx`, API `PATCH /api/decks/:id/slides/:i`

- [ ] **6.2 — Visual family picker with previews.**
  A gallery modal showing the 40 families as thumbnails; click to apply to the
  current slide. (The engine still auto-picks by default — this is an override.)
  *Files:* `frontend/src/components/app/VisualLayoutPicker.jsx` (revive + expand)

- [ ] **6.3 — Reveal-step timeline scrubber** in the presenter console — drag to
  any build step, not just next/prev.
  *Files:* `frontend/src/pages/Present.jsx`

- [ ] **6.4 — Live generation pipeline view** with per-stage timing, retry a
  failed stage, see which provider answered each LLM call.
  *Files:* `frontend/src/components/app/GenerationPipeline.jsx`, `Create.jsx`

- [ ] **6.5 — Deck diff / version history** — regenerate keeps the previous
  version; show what changed.
  *Files:* `storage/deck_library.py`, `frontend/src/pages/Projects.jsx`

- [ ] **6.6 — In-browser figure re-crop / annotate** before it goes on the slide.
  *Files:* new `components/app/ImageEditor.jsx`, `DiagramView.jsx` pattern

- [ ] **6.7 — Theme studio** — live palette + font preview against a real slide,
  not just the two light/dark radios.
  *Files:* `frontend/src/pages/Settings.jsx`, `rendering/theme_engine.py` (expose presets via API)

- [ ] **6.8 — Export options dialog** — density, animation on/off, quiz
  placement, which format(s), speaker-notes verbosity — before generating.
  *Files:* `frontend/src/pages/Create.jsx`, `Export.jsx`

---

## Part 2 — Suggested order of attack

1. **Phase 1** (1.1 → 1.5) — stop losing images and text. Small, safe, high impact.
2. **Phase 2.1 + 2.2 + 2.3** — the flowchart staging + worked-example family + raw-deck controls. This is the visible "it explains phase by phase now" win.
3. **Phase 3.1 + 3.4** — expansion pass + teaching density. "It explains in detail now."
4. **Phase 2.4** — PPTX animations on.
5. **Phase 5.1 / 5.2** — quiz-after-slide-N.
6. **Phase 4** — the big refactor; unify renderers, light up the visual library.
7. **Phase 6** — frontend features, interleaved with the above.

Each task is independently shippable and testable. We check off boxes as we go.
