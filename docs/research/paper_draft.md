# Cognitive-Load-Aware Generation of Educational Slide Decks: A Calibrated Fitness Metric and an Optimal Segmentation Algorithm

*Working draft — Learnova research track. Author list TBD.*

---

## Abstract

Automatic "text-to-deck" systems turn documents and syllabi into slide
presentations, but they have no principled notion of whether a generated
slide is *good for learning*, and they paginate content with ad-hoc rules
that either truncate material or produce ragged, uneven slides. We contribute
(1) **Pedagogical Slide Fitness (PSF)**, a slide-quality metric derived from
Cognitive Load Theory and Mayer's Cognitive Theory of Multimedia Learning and
calibrated against human ratings, and (2) **CLASS**, a dynamic-programming
algorithm that paginates a section's content across slides so as to minimise
total cognitive-load cost, generalising Knuth & Plass's optimal line-breaking
and guaranteeing that no source content is dropped. On a corpus of *N* decks
generated from open educational documents, PSF predicts human quality
judgements substantially better than the engagement heuristic it replaces
(Spearman ρ = _tbd_ vs _tbd_), and decks paginated by CLASS are preferred by
human raters _tbd_ % of the time over an even-split baseline while using
_tbd_ % fewer slides. Both components run in milliseconds and add no
model-inference cost. We release the implementation inside the open-source
Learnova engine.

---

## 1. Introduction

- The rise of automatic slide generation (LLM "make me a deck", commercial
  tools, and open pipelines such as Learnova).
- Two unsolved problems:
  - **Evaluation gap.** Systems optimise for "looks like slides", not for
    learning. Existing automatic scores (e.g. an additive "engagement" score
    over text density, bullet count, presence of a takeaway) are asserted,
    not validated, and reward superficial regularity.
  - **Segmentation gap.** Deciding how much content goes on each slide is done
    with fixed caps and even splitting. Caps silently drop content; even
    splitting ignores that a slide's difficulty is non-linear in its length
    and depends on how many ideas *interact*.
- Our position: the metric and the segmentation algorithm should be **the same
  model**. If we can score a slide's cognitive load, we can also paginate to
  minimise it.
- Contributions:
  1. PSF — a theory-derived, human-calibrated slide-fitness metric (§3).
  2. CLASS — an optimal, content-preserving slide-segmentation DP whose cost
     function is PSF's load term (§4).
  3. An evaluation on open educational material: PSF vs baseline vs ablations;
     CLASS vs even-split; cost analysis (§5–6).
  4. Open-source reference implementation in Learnova.

---

## 2. Background and related work

- **Cognitive Load Theory** (Sweller; Sweller, Ayres & Kalyuga): intrinsic /
  extraneous / germane load; element interactivity; the segmenting and
  worked-example effects.
- **Cognitive Theory of Multimedia Learning** (Mayer): coherence, signalling,
  redundancy, spatial contiguity, segmenting principles — each with an
  empirical effect size and each, we argue, *measurable* from slide content.
- **Automatic presentation generation**: doc2ppt / slide-generation systems,
  LLM deck tools, template-based approaches. None reports a validated quality
  metric or an optimal segmentation.
- **Slide / document quality assessment**: readability metrics
  (Flesch–Kincaid etc.), text-only; presentation-quality rubrics, manual.
- **Optimal segmentation / line breaking**: Knuth & Plass (1981) optimal
  paragraph breaking; its use in typography and in text summarisation
  segmentation. We reuse its DP structure with a cognitive cost.
- **Information-theoretic text measures**: surprisal, idf-weighted content,
  used here as the "upside" term the optimiser trades against load.

---

## 3. Pedagogical Slide Fitness

### 3.1 Overview and design rationale

PSF scores a slide *s* in `[0,1]` as a multiplicative model of three
sub-indices:

    PSF(s) = E(s)^α · (1 − L(s))^β · C(s)^γ,     α + β + γ = 1

- **E(s)** — *information efficiency*: how much genuinely new content the
  slide delivers, with diminishing returns and a redundancy discount.
- **L(s)** — *cognitive load*: a logistic function of CLT load drivers.
- **C(s)** — *multimedia coherence*: the mean of four measurable Mayer
  indicators.

We choose a **Cobb–Douglas (multiplicative)** form deliberately: a slide that
fails on any single dimension — says nothing, overloads the reader, or is
incoherent — should score near zero regardless of the other two. §5 (E3)
tests this choice against an additive model.

### 3.2 Information efficiency E(s)

Let `newconcepts(s)` be the content words (closed-class words removed) that
appear on *s* and on no earlier slide. With a corpus-free rarity estimate
`idf̂(c)` (§3.5):

    U(s) = Σ_{c ∈ newconcepts(s)} idf̂(c)
    R(s) = mean over bullets of max(Jaccard(bullet, title), Jaccard(bullet, other bullets))
    E(s) = ( U(s) / (U(s) + κ_E) ) · (1 − R(s))

`U/(U+κ_E)` is a saturating (Michaelis–Menten) response: the first few rare
concepts earn most of the score, matching the heuristic that "a slide has one
job". A slide with a title but no body or figure delivers nothing: `E = 0`.

### 3.3 Cognitive load L(s)

Four load drivers, each soft-clipped to `[0,1]` by a reference constant:

| driver | definition | reference |
|---|---|---|
| element interactivity ê | `n_concepts · (1 + relational_cue_density) / e_ref` | CLT element interactivity |
| extraneous text load t̂ | `words / t_ref` | working-memory chunk budget |
| visual complexity v̂ | `max(table_rows, flow_nodes, grid_cards) / v_ref` | — |
| split attention ŝ | 1 if a figure is described in the text but placed on another slide | contiguity principle |

    L(s) = σ( w_e·ê + w_t·t̂ + w_v·v̂ + w_s·ŝ − θ_L )

`relational_cue_density` counts connectives ("because", "therefore",
"whereas", "leads to", …) — a text proxy for how many elements *interact*,
which CLT says is what drives intrinsic load, not raw count.

### 3.4 Multimedia coherence C(s)

Mean of four indicators in `[0,1]`:

- **signalling** — a real (non-placeholder) title *and* an explicit takeaway.
- **coherence** — 1 − fraction of sentences whose overlap with the slide's
  concept centroid is below τ (a "seductive detail" detector).
- **non-redundancy** — penalise a figure caption that duplicates the bullet text.
- **spatial contiguity** — figure on the same slide as its referring text.

### 3.5 Corpus-free rarity estimate

To keep the metric dependency-free and deterministic we estimate `idf̂(c)`
from (a) membership in a small high-frequency word set and (b) token length
(technical terms are systematically longer), bounded to `[0.4, 3.0]`. §5
reports robustness when `idf̂` is replaced by true corpus idf and by an
embedding-based concept extractor.

### 3.6 Deck aggregation

    PSF_deck = ( Π_s PSF(s) )^{1/N} · Flow(deck)

`Flow` is a trapezoidal reward for *moderate* concept overlap between
consecutive slides (cosine/Jaccard in `[φ_lo, φ_hi]`): near 0 is a jarring
topic jump, near 1 is repetition.

### 3.7 Parameter calibration

Only a low-dimensional weight vector `(α, β, γ, w_e, w_t, w_v, w_s, θ_L)` is
learned; scale constants are fixed from theory. We fit by constrained
non-linear least squares against mean human ratings, with `(α,β,γ)`
Dirichlet-reparameterised to enforce the simplex constraint, under 5-fold
cross-validation. Defaults shipped in the implementation are literature-derived
priors usable before any data collection.

---

## 4. CLASS: Cognitive-Load-Aware Slide Segmentation

### 4.1 Problem

A section yields an ordered list of atomic content blocks `b_1 … b_m`
(bullets; for tables and flowcharts, rows and steps). We must cut it into
consecutive groups (slides).

### 4.2 Objective

Choose cut points `0 = i_0 < … < i_k = m` to

    minimise  Σ_{j=1..k} cost(b_{i_{j-1}+1 .. i_j})  +  λ·k
    s.t.      group size ≤ P_max  (layout-safety cap)

with the per-slide cost taken directly from PSF's load model:

    cost(g) = L(slide(g)) + μ·(1 − E(slide(g))) + ν·overflow(g)²

`λ·k` regularises slide count; `μ·(1−E)` stops the optimiser from emitting
near-empty slides; `ν·overflow²` is a soft quadratic penalty past a target
size below the hard cap.

This is structurally identical to Knuth–Plass optimal line breaking: "line" →
"slide", "line badness" → "slide cognitive load", "hyphenation penalty" → λ.

### 4.3 Algorithm and guarantees

A one-dimensional DP over prefix cut points (pseudocode in the design doc)
runs in `O(m · P_max)` time and `O(m)` space. Because `cost` depends only on
a contiguous block, the standard exchange argument gives a **global optimum**.
The cut points partition `1..m`, so **every block is placed exactly once** —
truncation is structurally impossible. Including `μ·(1−E)` in the cost
removes the orphan-continuation-slide failure mode that even-split code
patches with an ad-hoc rebalance.

### 4.4 Integration

CLASS is a drop-in replacement for the even-split call inside Learnova's
density stage; atomic layouts (metric, quiz), table-header repetition, and
"figure stays on part 1" rules are unchanged.

---

## 5. Evaluation

### 5.1 Corpus and ratings

- **Decks**: generated from open educational documents (OpenStax chapters,
  MIT OCW notes, arXiv survey introductions), _N_ decks / _M_ slides,
  stratified by discipline.
- **Human ratings**: ≥3 raters/slide on a learning-oriented rubric
  (manageable load? clear point? would it help a student?), plus deck-level
  pairwise preference. Report Krippendorff's α.

### 5.2 Research questions and results (to be filled)

| RQ | Result |
|---|---|
| **E1** PSF vs baseline engagement score vs ablations — do they predict human ratings? | ρ, RMSE, NDCG@k on held-out test |
| **E2** term ablation (drop E / L / C; drop each load driver) | Δρ table |
| **E3** multiplicative vs additive aggregation | ΔRMSE, calibration curves |
| **E4** CLASS vs even-split: blind deck preference, ΔPSF_deck, Δslide-count | preference %, effect sizes |
| **E5** (stretch) learning study: quiz score after CLASS deck vs even-split deck | mean score, time-on-task |
| **E6** runtime of CLASS vs even-split across section lengths | ms curve |

### 5.3 Threats to validity

Perceived vs actual learning (E5 partly addresses); noisy keyword concept
extraction (robustness condition with embeddings); domain generalisation
(per-stratum ρ).

---

## 6. Discussion

- The metric-as-cost-function design: one model both *judges* and *builds*.
- Where PSF is weak: sarcasm/nuance, discipline-specific notation, figures we
  can only see through a caption.
- Extending CLASS: 2-D layout optimisation, cross-section reordering,
  learner-adaptive `P_max`.

## 7. Conclusion

A small amount of learning theory, turned into a differentiable-enough
objective, gives an automatic slide generator both a conscience and a
planner. Implementation and evaluation harness are open source in Learnova.

---

## Appendix A — default parameters

See `src/learnova/scoring/psf.py::PSFParams`. Priors:
α=0.40, β=0.42, γ=0.18; w_e=1.10, w_t=1.35, w_v=0.85, w_s=1.60, θ_L=2.30;
κ_E=6.0, e_ref=9.0, t_ref=16.0, v_ref=8.0; λ=0.35, μ=0.9, ν=0.25;
flow band [0.18, 0.55].

## Appendix B — reproducibility

- Metric: `learnova.scoring.psf` (deterministic, stdlib only).
- Calibration: `scripts/calibrate_psf.py` (ratings CSV → fitted `PSFParams`).
- Deck scoring: `score_all_slides(deck, engine="psf")`.
- CLASS in the pipeline: env `LEARNOVA_USE_CLASS=1`.
- Tests: `tests/test_psf.py` (includes a brute-force optimality check).
