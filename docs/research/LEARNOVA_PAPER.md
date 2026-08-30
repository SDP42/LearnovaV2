# Content-Preserving, Cognitive-Load-Aware Generation of Educational Slide Decks

*Learnova research track — umbrella paper. Author list TBD.*
*Companion documents: [`PSF_DESIGN.md`](PSF_DESIGN.md) (PSF/CLASS in full), [`VISUAL_INTELLIGENCE.md`](VISUAL_INTELLIGENCE.md) (the decision layer), [`paper_draft.md`](paper_draft.md) (the PSF/CLASS-only submission).*

---

## Abstract

Systems that turn a document, syllabus, or set of notes into a slide deck have
converged on one of two designs: **template filling**, which is rigid and
ignores the shape of the content, or **large-language-model (LLM) generation**,
which silently paraphrases, compresses, drops list items, and occasionally
invents facts, with no way for a user to verify what survived. Neither design
has a principled notion of whether a generated slide is *good for learning*,
and both paginate content with fixed caps that truncate material.

We present **Learnova**, an open-source engine built around three ideas.
**(1) A deterministic decision layer.** Every structural choice — which
sentences are reproduced verbatim, which visual modality a slide takes,
whether a bitmap figure is kept or redrawn, how many ideas go on a slide — is
made by an explicit, inspectable rule with a stated guarantee, not by a
learned model and not by the LLM. The LLM is used only for *rewording within
constraints*, and its output is reconciled against a deterministic extractive
lower bound, giving a **verifiable content-preservation property**: no source
enumeration item is lost and no visual data is fabricated.
**(2) Pedagogical Slide Fitness (PSF)**, a slide-quality metric whose form is
derived from Cognitive Load Theory and Mayer's Cognitive Theory of Multimedia
Learning and whose low-dimensional weight vector is calibrated against human
ratings.
**(3) CLASS**, a dynamic program that paginates a section across slides to
minimise total cognitive-load cost — using PSF's load term as its cost
function — generalising Knuth & Plass optimal line breaking and provably
dropping no content.

The deterministic layer runs in milliseconds with no inference cost; PSF and
CLASS add none. We describe the design, state the guarantees, and give a
pre-registered evaluation plan on open educational material: content-fidelity
against LLM baselines, PSF's agreement with human quality judgements, VMS's
agreement with human "right visual?" judgements, and blind deck preference for
CLASS over even splitting.

---

## 1. Introduction

Automatic "text-to-deck" generation is now a mainstream feature of office
suites and a popular use of general-purpose LLMs ("make me a presentation about
X"). Three problems remain unsolved.

**The fidelity gap.** An LLM asked to "make slides from this chapter" performs
*abstractive* transformation: it rewrites, and in rewriting it under-generates.
A passage that lists "the five stages of X" routinely emerges with two or
three; a two-word list item ("Machine Translation") is dropped as too short to
be a bullet; a definition is loosely paraphrased; occasionally a figure caption
or a statistic is confabulated. Summarisation research names these
*content-selection* and *faithfulness* errors [Maynez et al. 2020; Kryściński
et al. 2020], and for a *study aid* they are disqualifying: the student cannot
tell that the deck is lossy, and the missing item is exactly the one the exam
asks about. Commercial deck tools do not report what they changed.

**The evaluation gap.** Systems optimise for "looks like slides", not for
learning. Where an automatic quality score exists it is an *asserted* additive
sum over surface features — text density, bullet count, presence of a
takeaway — with hand-picked weights and thresholds, no theoretical model
behind the choice of terms, and no validation against any human judgement of
learning quality. Such a score rewards superficial regularity: a beautiful
empty slide can score well.

**The segmentation gap.** How much content goes on each slide is decided by a
fixed per-profile cap plus an even rebalance. A cap silently truncates.
Even splitting ignores that a slide's difficulty is non-linear in its length
and depends on how many of its ideas *interact* — the central claim of
Cognitive Load Theory.

**Our position.** The three gaps are one design problem. If a system can
*measure* the cognitive load a slide imposes, it can also *paginate* to
minimise it — the metric and the planner should be the same model. And the
structural decisions that determine fidelity (what to keep, what to draw, what
to split) should be made by rules that carry guarantees, with the LLM confined
to rewording, so that "nothing was lost" is a property of the system rather
than a hope.

**Contributions.**

1. **A deterministic decision layer** (§4) for document→deck transformation:
   register-protected verbatim text policy, an explainable Visual Modality
   Selector, an image-action policy, enumeration-atomic content preservation,
   a never-fabricate downgrade for visuals, and an extractive reconciliation
   step that lower-bounds the LLM. We state and prove a content-preservation
   property (Guarantee 1) and a no-fabrication property (Guarantee 2).
2. **PSF** (§5): a theory-derived, human-calibrated slide-fitness metric with
   a multiplicative (Cobb–Douglas) form, replacing the asserted engagement
   heuristic.
3. **CLASS** (§6): an optimal, content-preserving slide-segmentation dynamic
   program whose objective is PSF's load term — a Knuth–Plass generalisation.
4. **System** (§7): a web-first render-and-capture pipeline, a shared Gallery
   of pre-built decks, and a grounded conversational assistant, all
   consuming the same typed deck representation.
5. **A pre-registered evaluation plan** (§8) on open educational documents.

Learnova is open source; the decision layer, PSF, and CLASS are pure Python
with no network dependency and are unit-tested, including a brute-force
optimality check for CLASS.

---

## 2. Background and related work

**Cognitive Load Theory (CLT)** [Sweller 1988; Sweller, Ayres & Kalyuga 2011].
Working memory holds ~4 elements [Cowan 2001]. CLT decomposes the load a
learning artefact imposes into *intrinsic* (element interactivity — how many
items must be held simultaneously to understand the material; managed by
sequencing and **segmenting**), *extraneous* (presentation choices that add
load without learning — a wall of text, split attention, redundancy; reduced
by layout), and *germane* (effort that builds schemas). A good slide minimises
extraneous load, manages intrinsic load by segmenting, and leaves
working-memory headroom for germane processing.

**Cognitive Theory of Multimedia Learning (CTML)** [Mayer 2009]. Empirically
grounded principles, several of which are *measurable from slide content*:
**coherence** (exclude material that does not serve the goal), **signalling**
(cue the structure — headings, a stated takeaway), **redundancy** (do not
reproduce on-screen text verbatim in narration; do not repeat),
**spatial contiguity** (put a figure next to its referring text),
**segmenting** (deliver in learner-paced segments).

**Automatic presentation generation.** Doc2ppt-style and template systems
[e.g. Fu et al. 2022; Sefid et al. 2021] and, more recently, LLM deck tools.
To our knowledge none reports a validated quality metric, an optimal
segmentation, or a content-preservation guarantee.

**Faithfulness in summarisation** [Maynez et al. 2020; Kryściński et al. 2020;
Pagnoni et al. 2021]. Establishes that abstractive models drop and hallucinate
content and that the practical mitigation is to treat certain spans as atomic
and to check the output against an extractive reference. We apply both to
list-bearing spans and to whole slides.

**Optimal segmentation / line breaking** [Knuth & Plass 1981]. A
one-dimensional dynamic program over prefix break points is globally optimal
when the cost of a segment depends only on its contents. We reuse this
structure with a cognitive-load cost (§6).

**Information-theoretic content measures.** idf-weighted content and surprisal
as proxies for "how much a span says" [e.g. Peyrard 2019]. PSF uses a
diminishing-returns function of the summed rarity of *newly introduced*
concepts as its upside term (§5.2).

**Readability metrics** (Flesch–Kincaid and relatives) are text-only and say
nothing about layout, visuals, or load interaction; PSF subsumes a readability
signal as one driver among several.

---

## 3. System overview

Learnova is a staged pipeline from a source document to two artefacts (an
animated PowerPoint file and a self-contained interactive web deck). The
stages are: **convert** (PDF/PPTX/typed text → a Markdown intermediate
representation, with figures extracted and re-anchored to the section that
discusses them); **chunk** (split on heading boundaries, merge fragments,
explode enumerations — §4.2); **improve** (per-chunk: LLM reword *or*
deterministic extractive structuring, then extractive reconciliation — §4.6);
**visual plan** (VMS — §4.4 — assigns a treatment and its structured data);
**image policy** (§4.5); **density** (CLASS — §6 — paginates overflow);
**quiz** (checkpoint questions interleaved at run boundaries); **score** (PSF —
§5); **build** (render both artefacts).

Two properties hold across the pipeline by construction:

- The system runs end-to-end **with no LLM key at all** (every LLM stage has a
  deterministic fallback), so all guarantees below are properties of the
  deterministic path and are only *tightened*, never relaxed, by the LLM.
- The deck is carried as a single **typed representation** consumed identically
  by the PPTX builder, the web builder, the Gallery, and the assistant.

---

## 4. The deterministic decision layer

> This is the component that is **not** a statistical model and **not** a
> closed-form mathematical function: it is a set of explicit decision
> procedures, each with a stated guarantee. The LLM is a constrained
> sub-routine, not the decision-maker.

### 4.1 Design principle

For each structural question the pipeline asks — *keep this sentence as
written? draw this as a diagram? which diagram? keep this bitmap? how many
ideas on this slide?* — Learnova commits to three properties:

1. **Explainability.** The decision is a sum of named feature contributions or
   a short rule chain; the Studio UI can display *why* a slide became a pie
   chart.
2. **A conservative default.** When no rule fires with enough evidence, the
   system chooses the option that cannot lose information: keep the text, keep
   the image, do not split.
3. **A guarantee.** Each sub-policy has a property that holds regardless of the
   LLM's behaviour (stated below).

The LLM's role is narrowed to *rewording within constraints* — turning a
retrieved passage into slide-shaped prose without changing which facts, list
items, or defined terms appear.

### 4.2 Enumeration-atomic content preservation

*Module: `ai/enumeration.py`.* The single largest fidelity failure we observed
was content selection on lists. `extract_enumerations(text)` deterministically
pulls every enumeration in a passage:

```
Enumeration(lead="The five phases of NLP", items=[...verbatim...],
            kind="phases", claimed_count=5, style="numbered")
```

It recognises numbered runs, bulleted runs, inline series ("X, Y, and Z"),
header-style item lists, and plain paragraph blocks introduced by a plural
head noun ("phases | stages | methods | applications | advantages | …"). Items
are captured **verbatim**, de-duplicated, order preserved; the claimed count
("five") is parsed and checked against the item count.

Downstream:

- `split_into_item_sections` turns a *definitional* enumeration (each item a
  short heading followed by its own explanation) into an overview slide plus
  one slide per item ("Stage 2 of 5: Syntactic Analysis"), which teaches
  better than a wall of bullets and animates naturally one item per click.
- `missing_items(enum, covered_text)` reports which items the improved slide
  fails to mention; the improver force-appends them.
- Neither scoring, nor length filters, nor the LLM is permitted to alter an
  enumeration's *membership*.

**Guarantee 1 (enumeration preservation).** *For every enumeration `e`
detected in a source section, every item of `e` appears in the generated deck,
verbatim or as a normalisation-equivalent string.* The item set is copied
before any lossy stage and re-checked after; a missing item is re-inserted.
Empirically this raised item retention on a graduate NLP chapter from 1–2 of 5
to 5 of 5 across every enumeration in the document.

### 4.3 Register-protected verbatim text policy

*Module: `ai/text_policy.py`.* `classify_sentences(text)` labels each sentence
**VERBATIM**, **MERGE**, or **TIGHTEN**:

- **VERBATIM** — definitional register (`is defined as`, `X is the measure
  of`, `denoted by`), theorem / law statements, anything in quotation marks or
  following `wrote:`, legal register (`shall`, `pursuant to`, `Section 3`),
  code (`{}`, `=>`, `def`, `SELECT … FROM`), and formula-in-prose
  (`E = mc^2`, `∝`, `≤`).
- **MERGE** — a near-duplicate (string containment or Jaccard ≥ 0.72) of an
  earlier sentence.
- **TIGHTEN** — everything else, and only this class is exposed to the
  trimming / rewording machinery.

`protect_verbatim(text)` marks the VERBATIM spans so the pipeline's
length-based trimming and the LLM prompt both leave them untouched. Precise
wording — the part a student must reproduce on an exam — is never
paraphrased.

### 4.4 Visual Modality Selection (VMS)

*Module: `ai/visual_selector.py`.* VMS is the deterministic answer to "which
visual, when". It scores each of 20 treatments —

`KEEP_TEXT · BULLETS · DEFINITION · QUOTE · FLOWCHART · CYCLE · TIMELINE ·
COMPARISON_TABLE · PROS_CONS · MATRIX_2X2 · PYRAMID · VENN · MIND_MAP ·
CARD_GRID · BAR_CHART · LINE_CHART · PIE_CHART · METRIC · IMAGE_FOCUS ·
MINIMAL_TEXT`

— from *structural features of the content*, not keywords:

| Treatment | Fires on |
|---|---|
| FLOWCHART | ≥3 ordered steps; bonus for decision cues ("if…then", "otherwise") |
| CYCLE | ordered steps **and** loop cues ("repeat", "feedback", "the cycle continues") |
| TIMELINE | ≥2 real dates/years — not ordinal words alone |
| COMPARISON_TABLE | an extracted A-vs-B comparison, or ≥1 "vs / whereas / in contrast" |
| PROS_CONS | ≥2 advantage/disadvantage cues for **one** subject |
| PIE_CHART | ≥3 percentages summing to ≈100 |
| LINE_CHART | a numeric series with time cues |
| BAR_CHART | ≥3 numbers across categories (suppressed if a valid pie exists) |
| METRIC | exactly one figure and <45 words |
| PYRAMID / VENN / MATRIX_2X2 | level cues / shared-set cues / two-axis cues |
| MIND_MAP | ≥4 loosely related concepts and no other structure |

Every treatment carries a `rationale` string and the full per-feature `scores`
map. The winning score must exceed a threshold `τ_vms = 2.5`; **otherwise VMS
returns `KEEP_TEXT` / `MINIMAL_TEXT`.**

**Design property (defer-to-text).** *A forced diagram is worse than clean
text.* VMS emits a non-text treatment only when the content's structure
independently clears `τ_vms`; the null hypothesis is "this is prose".

VMS also serves as a **validation layer** over an LLM that is offered the same
taxonomy: if the LLM proposes FLOWCHART but VMS scores no ordered steps, the
proposal is rejected and the deterministic choice stands.

### 4.5 Image-action policy

*Module: `ai/image_policy.py`.* For each extracted figure,
`decide_image_action(ImageMeta)` chooses from KEEP_AS_IS, CAPTION_ONLY,
ENHANCE, REGENERATE, SUMMARISE_TO_STRUCTURE, or DROP using pixel size, aspect
ratio, OCR word density, structure markers in the OCR (`→`, `step N`,
`| … | … |`, `yes/no`), whether the figure is referenced in the text, and its
topical relevance to the surrounding slide. The consequential case is
**SUMMARISE_TO_STRUCTURE**: a bitmap of a flowchart is re-recognised (its OCR
is run back through VMS) and rendered as a *native* Learnova flowchart, and
the blurry screenshot is dropped.

### 4.6 Extractive reconciliation — a deterministic lower bound on the LLM

*Module: `ai/improver.py`.* Each chunk is structured two ways: by the LLM
(`classify_and_structure_chunk`) and by a deterministic extractive summariser
(`ai/extractive.py`, which performs no length-based sentence cutting and no
per-bullet compression). Let `w_llm` and `w_ext` be the content-word counts of
the two results. If

```
w_llm  <  0.95 · w_ext
```

the LLM under-delivered and its bullets are replaced (or back-filled) from the
extractive result. The threshold `0.95` is a configurable retention floor
(`LEARNOVA_MIN_RETENTION`). This makes the extractive path a *floor*: the
deck is never more lossy than deterministic extraction, and is usually
better-worded than it.

**Guarantee 2 (no fabricated visual data).** *A `COMPARISON_TABLE` with no
parseable rows and a `METRIC` with no readable quantity are downgraded to
plain text rather than rendered with invented cells or the literal words "Key
Stat" at headline size.* The renderer (`rendering/deck_director.py`) refuses to
draw a lossy diagram family over a content-heavy slide or one whose bullets are
full sentences (>12 words); it substitutes `MINIMAL_TEXT`.

### 4.7 Progressive-reveal grammar

*Function: `plan_reveal_groups`.* The build order of a slide's elements is a
deterministic function of its treatment: one idea per step for lists /
flowcharts / timelines; row-by-row for comparison tables; two halves for
pros-cons and Venn; a single step for QUOTE / METRIC / DEFINITION; the
takeaway is always last; groups are **consecutive and never reordered**. The
web deck realises groups as Reveal.js fragments; the PPTX builder as per-shape
entrance animations. Gallery decks ship with reveal enabled by default so a
downloaded deck can be taught one point at a time.

---

## 5. Pedagogical Slide Fitness (PSF)

*Module: `scoring/psf.py`. Full derivation: [`PSF_DESIGN.md`](PSF_DESIGN.md).*

### 5.1 Per-slide model

```
PSF(s) = E(s)^α · (1 − L(s))^β · C(s)^γ ,        α + β + γ = 1
```

A **multiplicative (Cobb–Douglas)** form is deliberate: a slide that collapses
on *any one* dimension — says nothing, is unreadable, or is incoherent —
should score near zero regardless of the other two. An additive model lets a
beautiful empty slide score 66/100, which is the failure mode of the
heuristic PSF replaces.

**E(s) — information efficiency.** With a corpus-free rarity estimate
`îdf(c) ∈ [0.4, 3.0]` (from stop-word membership, a high-frequency-word set,
and token length — technical terms are systematically longer):

```
U(s) = Σ_{c ∈ newconcepts(s)}  îdf(c)                    (delivered novel information)
R(s) = mean_bullets  max( Jaccard(bullet, title), Jaccard(bullet, other bullets) )
E(s) = ( U(s) / (U(s) + κ_E) ) · (1 − R(s))
```

`U/(U+κ_E)` is a Michaelis–Menten saturation: the first few rare concepts earn
most of the score (a slide has *one* job). `newconcepts(s)` excludes concepts
introduced on an earlier slide, so restating does not score.

**L(s) — cognitive load ∈ [0,1].** Four drivers, each soft-clipped by a
reference constant:

| driver | definition | reference |
|---|---|---|
| element interactivity `ê` | `n_concepts · (1 + relational_cue_density) / e_ref` | CLT element interactivity |
| extraneous text load `t̂` | `words / t_ref` | working-memory chunk budget |
| visual complexity `v̂` | `max(table_rows, flow_nodes, grid_cards) / v_ref` | — |
| split attention `ŝ` | 1 if a figure is described in text but placed on another slide | contiguity principle |

```
L(s) = σ( w_e·ê + w_t·t̂ + w_v·v̂ + w_s·ŝ − θ_L )
```

`relational_cue_density` counts connectives ("because", "therefore",
"whereas", "leads to") — a text proxy for how many elements *interact*, which
CLT says drives intrinsic load, not raw count.

**C(s) — multimedia coherence ∈ [0,1].** Mean of four CTML indicators:
signalling (a real title *and* an explicit takeaway); coherence (fraction of
sentences whose overlap with the slide's concept centroid exceeds `τ` — a
"seductive detail" detector); non-redundancy (figure caption ≠ bullet text);
spatial contiguity (figure on the same slide as its referring text).

### 5.2 Deck model

```
PSF_deck = ( Π_s PSF(s) )^{1/N} · Flow(deck)
```

`Flow` is a trapezoidal reward for *moderate* concept overlap between
consecutive slides (Jaccard in `[φ_lo, φ_hi] ≈ [0.18, 0.55]`): near 0 is a
jarring topic jump; near 1 is repetition.

### 5.3 Calibration

Only the low-dimensional vector `(α, β, γ, w_e, w_t, w_v, w_s, θ_L)` is
learned; the scale constants `(κ_E, e_ref, t_ref, v_ref)` are fixed from
theory / corpus statistics to keep the model identifiable. We fit by
constrained non-linear least squares against mean human ratings, with
`(α,β,γ)` Dirichlet-reparameterised onto the simplex, under 5-fold
cross-validation. `scripts/calibrate_psf.py` performs the fit; the module
ships literature-derived priors (Appendix A) so it is usable before any data
is collected.

**The paper's claim about PSF:** the *shape* of the model is theory; only a
weight vector is learned, and it is learned against human judgement with
cross-validation and a held-out test set — in contrast to the asserted
heuristic it replaces.

---

## 6. CLASS — Cognitive-Load-Aware Slide Segmentation

*Function: `scoring/psf.py::segment_blocks`.*

### 6.1 Problem

A section yields an ordered list of atomic content blocks `b_1 … b_m`
(bullets; for tables and flowcharts, rows and steps). Choose cut points
`0 = i_0 < i_1 < … < i_k = m` to

```
minimise    Σ_{j=1..k}  cost( b_{i_{j-1}+1 .. i_j} )  +  λ·k
subject to  group size ≤ P_max          (layout-safety hard cap)
```

with the per-slide cost taken **directly from PSF's load model**:

```
cost(g) = L(slide(g))  +  μ · ( 1 − E(slide(g)) )  +  ν · overflow(g)²
```

`λ·k` regularises slide count (ties break toward fewer slides); `μ·(1−E)` stops
the optimiser emitting near-empty slides; `ν·overflow²` is a soft quadratic
penalty past a target size *below* the hard cap.

This is structurally identical to Knuth–Plass optimal line breaking: "line" →
"slide", "line badness" → "slide cognitive load", "hyphenation penalty" → `λ`.

### 6.2 Algorithm and guarantees

```
CLASS(blocks b[1..m], P_max, λ):
    best[0] = 0 ; cut[0] = 0
    for i in 1..m:
        best[i] = +∞
        for p in max(0, i − P_max) .. i−1:
            c = best[p] + cost(b[p+1..i]) + λ
            if c < best[i]: best[i] = c ; cut[i] = p
    reconstruct groups by following cut[] back from m
```

`O(m · P_max)` time, `O(m)` space; `P_max ≤ 8`, so linear in section length
and negligible beside the LLM stages.

- **Completeness (content preservation).** The cut points partition `1..m`;
  every block lands on exactly one slide. `bullets[:4]`-style truncation is
  structurally impossible.
- **Optimality.** Because `cost` depends only on a contiguous block, the
  standard exchange argument [Knuth & Plass 1981 §3] gives a global minimum of
  the objective over all legal segmentations. `tests/test_psf.py` includes a
  brute-force check against exhaustive enumeration for small `m`.
- **No orphan continuation slides.** Including `μ·(1−E)` in the cost removes
  the one-line-continuation failure mode that even-split code patches with an
  ad-hoc rebalance.

### 6.3 Integration

CLASS is a drop-in replacement for the even-split call inside the density
stage (`LEARNOVA_USE_CLASS=1`); the atomic-layout, table-header-repeat, and
"figure stays on part 1" rules around it are unchanged.

### 6.4 The metric-as-cost-function design

PSF's load term `L` (and its emptiness term `1−E`) is *both* how a finished
slide is judged *and* the cost CLASS minimises while building it. One model
gives the generator a conscience and a planner.

---

## 7. System contributions

### 7.1 Web-first render and capture

Both artefacts are produced from the same typed deck. The web deck is a
self-contained single HTML file (Reveal.js inlined, offline-safe) with
content-adaptive auto-fit (measures rendered height against a reference stage
and scales dense slides down / sparse slides up), entrance animations, a
bullet-hierarchy renderer, and a two-column text+figure layout. Progressive
reveal is a URL/embed toggle, off by default for reading and on for
presenting.

### 7.2 The Gallery

A shared catalogue of ~1,000 teaching topics across ~30 subjects
([`GALLERY.md`](../GALLERY.md)). Curated topics ship a structured teaching
brief and a **pre-built deck**; a user opens it, adapts it, or downloads it
without generating anything. Gallery decks are produced by a batch runner over
the same pipeline with providers disabled, so they are fully deterministic and
reproducible from the catalogue. This turns the fidelity and load machinery
into a directly reusable artefact, and gives an evaluation corpus that is
regenerable byte-for-byte.

### 7.3 Grounded conversational assistant

A chat + voice assistant ([`ASSISTANT_ARCHITECTURE.md`](ASSISTANT_ARCHITECTURE.md))
resolves natural language to typed actions over a deterministic 58-intent
taxonomy with an LLM fallback for low-confidence utterances. Every action is
validated server-side against the real deck library before it runs; an
LLM-supplied identifier is resolved and ownership-checked, never trusted.
Explanations are **grounded** in the retrieved deck/slide text — the reply may
be simplified or translated, but the stored deck is never modified. The
assistant is Gallery-aware: "do you have slides on X?" runs a catalogue search
and, when a pre-built deck exists, confirms and opens it.

---

## 8. Evaluation plan (pre-registered)

### 8.1 Corpus and ratings

- **Documents.** Open educational material stratified by discipline: OpenStax
  chapters, MIT OpenCourseWare notes, arXiv survey introductions. Target
  120–300 slides across 20–40 decks. The Gallery's 39 curated decks are a
  regenerable subset.
- **Slide ratings.** ≥3 raters per slide on a learning-oriented rubric
  (manageable load? clear single point? would it help a student?). Report
  inter-rater reliability (Krippendorff's α). This is the ground truth for
  PSF calibration and testing.
- **VMS ratings.** For a sample of slides, raters judge "is this the right
  visual for this content?" for the VMS choice, an LLM-only choice, and the
  legacy 5-type router.
- **Fidelity annotation.** For a sample of source sections, annotators mark
  every enumeration item and every defined term; we measure recall in the
  generated deck.

### 8.2 Studies

| # | Question | Method | Metric |
|---|---|---|---|
| **E1** | Does PSF predict human slide-quality ratings better than the baseline heuristic and than ablations? | 5-fold CV, held-out test | Spearman ρ, RMSE, NDCG@k |
| **E2** | Which PSF terms matter? | leave-one-out on E, L, C and on each load driver | Δρ |
| **E3** | Multiplicative vs additive aggregation? | fit both, compare on test | ΔRMSE, calibration curves |
| **E4** | Does CLASS beat even-split? | within-subjects, same content, blind deck preference + PSF_deck + slide count | preference %, effect sizes |
| **E5** | Content fidelity vs LLM baselines. | enumeration-item recall and defined-term recall: Learnova (deterministic path), Learnova (LLM path + reconciliation), GPT-class "make me slides", a template tool | recall, hallucinated-fact rate |
| **E6** | VMS agreement with human "right visual?" vs LLM-only and legacy router. | rater agreement | accuracy, Cohen's κ |
| **E7** | (stretch) Learning outcome. | between-subjects quiz after a CLASS deck vs an even-split deck on the same content | mean quiz score, time-on-task |
| **E8** | Cost. | wall-clock of the decision layer, PSF, and CLASS across section lengths | ms |

### 8.3 Hypotheses

- H1: PSF ρ with human ratings > baseline heuristic ρ, on held-out test.
- H4: CLASS decks preferred > 50% and use ≤ even-split slide count.
- H5: Learnova enumeration-item recall ≈ 1.0 and > LLM-baseline recall;
  hallucinated-fact rate ≈ 0.
- H6: VMS agreement ≥ LLM-only agreement, both > legacy router.

---

## 9. Threats to validity

- **Perceived vs actual learning.** Raters judge perceived quality; E7
  addresses this partially with an outcome measure.
- **Noisy concept extraction.** Rarity and relational density come from a
  keyword extractor; we report robustness with true corpus idf and an
  embedding-based extractor as a second condition.
- **Rater pool and rubric.** Learning-quality judgements are subjective; we
  report α and use a pre-registered rubric.
- **Domain generalisation.** We stratify the corpus by discipline and report
  per-stratum ρ.
- **VMS coverage.** The 20-treatment taxonomy is not exhaustive (no maps, no
  music notation); out-of-taxonomy content correctly falls to text, which is
  safe but not always ideal.
- **Guarantee scope.** Guarantee 1 covers *detected* enumerations; an
  enumeration written in an unusual style may be missed by the detector (not
  mis-handled — simply treated as prose). We report detector recall on the
  fidelity-annotated sample.

---

## 10. Reproducibility

- **Decision layer:** `learnova.ai.{enumeration, text_policy, visual_selector,
  image_policy}` and `learnova.ai.improver` — deterministic, stdlib +
  regex, unit-tested (`tests/test_content_fidelity.py`,
  `tests/test_visual_intelligence.py`, `tests/test_visual_planning.py`).
- **PSF / CLASS:** `learnova.scoring.psf` — deterministic, stdlib only;
  `tests/test_psf.py` includes a brute-force optimality check.
- **Calibration:** `scripts/calibrate_psf.py ratings.csv --out params.json`.
- **Deck scoring:** `score_all_slides(deck, engine="psf")`.
- **CLASS in the pipeline:** `LEARNOVA_USE_CLASS=1`.
- **Corpus:** the Gallery catalogue (`data/gallery/catalog.json`) plus the
  batch runner (`python -m learnova.gallery.builder --all`) regenerates the
  curated decks byte-for-byte with no network.
- **No-LLM mode:** `LEARNOVA_NO_LLM=1` forces the deterministic path
  end-to-end; every claimed guarantee holds in this mode.

---

## 11. Discussion and limitations

- **One model, two jobs.** PSF judging and CLASS building from the same load
  term is the paper's spine; it also means a calibration error propagates to
  both. E2/E3 quantify sensitivity.
- **Where the decision layer is weak.** Sarcasm, discipline-specific notation,
  and figures we can only see through OCR/caption. The conservative default
  keeps these *safe* (text is kept) but not always *optimal*.
- **The LLM still matters for prose quality.** Guarantees bound *what* appears,
  not how well it reads; E5 measures fidelity, not fluency, and the
  reconciliation step can make a deck faithful but flat.
- **Extending CLASS.** Two-dimensional layout optimisation, cross-section
  reordering, learner-adaptive `P_max`.

---

## 12. Conclusion

Turning a small amount of learning theory into an objective, and making the
structural decisions with rules that carry guarantees rather than with a model
that might drop things, gives an automatic slide generator a conscience, a
planner, and a fidelity property a user can rely on. The decision layer, PSF,
and CLASS are open source in Learnova, with a pre-registered evaluation on
open educational material.

---

## Appendix A — default parameters

`scoring/psf.py::PSFParams`:
α=0.40, β=0.42, γ=0.18;
w_e=1.10, w_t=1.35, w_v=0.85, w_s=1.60, θ_L=2.30;
κ_E=6.0, e_ref=9.0, t_ref=16.0, v_ref=8.0;
seductive τ=0.08; flow band [0.18, 0.55];
λ=0.35, μ=0.9, ν=0.25.
VMS threshold τ_vms = 2.5. Retention floor `LEARNOVA_MIN_RETENTION` = 0.95.

## Appendix B — notation

| Symbol | Meaning |
|---|---|
| `s`, `N` | a slide; slide count |
| `E, L, C` | PSF sub-indices: information efficiency, cognitive load, coherence |
| `α, β, γ` | Cobb–Douglas exponents (simplex) |
| `U(s), R(s)` | delivered novel information; redundancy |
| `îdf(c)` | corpus-free rarity estimate of concept `c` |
| `ê, t̂, v̂, ŝ` | normalised load drivers |
| `b_1…b_m` | atomic content blocks of a section |
| `P_max`, `λ, μ, ν` | CLASS hard cap; slide-count / emptiness / overflow weights |
| `τ_vms` | VMS minimum winning score to leave plain text |

## References (to be completed)

Cowan 2001 · Fu et al. 2022 · Knuth & Plass 1981 · Kryściński et al. 2020 ·
Mayer 2009 · Maynez et al. 2020 · Pagnoni et al. 2021 · Peyrard 2019 ·
Sefid et al. 2021 · Sweller 1988 · Sweller, Ayres & Kalyuga 2011.
