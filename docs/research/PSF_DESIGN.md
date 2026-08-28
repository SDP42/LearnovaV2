# Pedagogical Slide Fitness (PSF) & Cognitive-Load-Aware Slide Segmentation (CLASS)

**Status:** design + reference implementation (`src/learnova/scoring/psf.py`)
**Target venue:** an education-technology / HCI / NLP-for-education venue
(e.g. *L@S*, *AIED*, *EDM*, *IUI*, *CHI LBW*). Also a strong fit for an
information-retrieval "document understanding" track.

---

## 1. Why the current scorer is not publishable

`src/learnova/scoring/scorer.py` assigns a slide a 0–100 score as a fixed
weighted sum of six hand-chosen sub-scores (`text_density 20`, `bullet_count
20`, `title_quality 15`, `has_takeaway 15`, `readability 15`, `visual_bonus
15`). The weights and the piecewise thresholds (`20 <= word_count <= 80`,
`2 <= n <= 4`, …) are asserted, not derived, not fitted, and not validated
against any human judgement of learning quality. There is no theoretical
model behind the choice of terms and no evaluation. It is a reasonable
engineering heuristic and a poor research contribution.

We replace it with two contributions that **are** defensible:

1. **PSF** — a slide-fitness metric with an explicit generative model
   (Cognitive Load Theory + Mayer's Cognitive Theory of Multimedia Learning +
   Shannon information), whose free parameters are *calibrated against human
   ratings* rather than asserted.
2. **CLASS** — an optimal dynamic-programming algorithm that paginates a
   section's content across slides to **minimise total cognitive-load cost**,
   generalising Knuth & Plass's optimal line-breaking to the slide-segmentation
   problem, with a guarantee that no source content is dropped.

---

## 2. Theoretical scaffold

### 2.1 Cognitive Load Theory (CLT)

Working memory is limited (Miller's 7±2 chunks; Cowan's ~4). CLT decomposes
the load a learning artefact imposes into:

| Load type | Driver | Design lever |
|---|---|---|
| **Intrinsic** | element interactivity — how many items must be held simultaneously to understand the material | sequencing, segmenting |
| **Extraneous** | presentation choices that add load without adding learning (wall of text, split attention, redundancy) | layout, trimming, contiguity |
| **Germane** | effort that actually builds schemas | worked examples, signalling |

A good slide **minimises extraneous load, manages intrinsic load by
segmenting, and leaves working-memory headroom for germane processing.**

### 2.2 Mayer's multimedia principles (the ones we can measure)

- **Coherence** — exclude material that does not serve the goal.
- **Signalling** — cue the structure (headings, a stated takeaway).
- **Redundancy** — do not narrate on-screen text verbatim; do not repeat.
- **Spatial contiguity** — put a figure next to the text that refers to it.
- **Segmenting** — deliver in learner-paced segments (this is what CLASS does).

### 2.3 Information theory

The *point* of a slide is to deliver information. We measure delivered
information as the summed inverse-document-frequency of the **newly
introduced** content concepts, saturating (diminishing returns) and
discounted by redundancy. This gives an upside term to trade against the
CLT downside terms — without it, the optimiser would output empty slides.

---

## 3. The PSF metric

### 3.1 Per-slide model

For slide *s* we compute three sub-indices, each in `[0, 1]`:

```
PSF(s) = E(s)^α  ·  (1 − L(s))^β  ·  C(s)^γ ,        α + β + γ = 1
```

A **multiplicative (Cobb–Douglas) form** is a deliberate modelling choice: a
slide that collapses on *any one* dimension (says nothing, or is unreadable,
or is incoherent) should score near zero regardless of the other two. An
additive model lets a beautiful empty slide score 66/100 — which is exactly
the failure mode of the current scorer.

#### E(s) — information efficiency

```
U(s)  = Σ_{c ∈ newconcepts(s)}  idf(c)                # delivered novel information
R(s)  = redundancy ∈ [0,1]  (token overlap of each bullet with the title and
                             with the other bullets, Jaccard, averaged)
E(s)  = ( U(s) / (U(s) + κ_E) ) · (1 − R(s))
```

`U/(U+κ_E)` is a Michaelis–Menten / diminishing-returns saturation: the
first few rare concepts buy most of the score, the tenth buys almost
nothing (matching the intuition that a slide has *one* job).

#### L(s) — cognitive load ∈ [0,1]

Load drivers, each normalised to `[0,1]` by a soft ramp `clip(x / x_ref, 0, 1)`:

```
ê   element interactivity : n_concepts · (1 + relational_density)   / e_ref
t̂   extraneous text load  : (words / CHUNK_SIZE)                    / t_ref     # CHUNK_SIZE≈5 words/chunk, WM≈4 chunks
v̂   visual complexity     : table_rows | flow_nodes | grid_cards    / v_ref
ŝ   split attention       : 1 if a figure is described in text but on another slide, else 0

L(s) = σ( w_e·ê + w_t·t̂ + w_v·v̂ + w_s·ŝ − θ_L )          # logistic squash
```

#### C(s) — multimedia coherence ∈ [0,1]

Mean of four indicators from §2.2:

```
signalling        : has a non-trivial stated takeaway AND a real (non-"Slide 7") title
coherence         : 1 − (fraction of sentences whose similarity to the slide's
                        concept centroid is below τ)      # "seductive detail" detector
non-redundancy    : 1 − 1[image caption ≈ bullet text]
spatial_contiguity: 1 if an anchored image sits on this slide (not the next), else neutral 0.5
```

### 3.2 Deck-level model

```
PSF_deck = ( Π_s PSF(s) )^(1/N)  ·  Flow(deck)
```

`Flow` rewards a **moderate** topic overlap between consecutive slides
(cosine of concept-vectors): near 0 means a jarring jump, near 1 means the
next slide repeats the previous one. Ideal band ≈ `[φ_lo, φ_hi] ≈ [0.2, 0.55]`;
`Flow` is a trapezoid that is 1.0 inside the band and decays outside it.

### 3.3 Free parameters and how they are set

| Params | Meaning | How obtained |
|---|---|---|
| `α, β, γ` | dimension weights | constrained NLS / Dirichlet-reparameterised regression on human ratings |
| `w_e,w_t,w_v,w_s,θ_L` | load model | same fit, jointly |
| `κ_E, e_ref,t_ref,v_ref` | scale constants | fixed from CLT literature (WM capacity) + corpus statistics, **not** fitted (keeps the model identifiable) |
| `φ_lo, φ_hi, τ` | band edges | fixed a priori; reported as sensitivity analysis |

The point for the paper: **the shape of the model is theory; only a
low-dimensional weight vector is learned, and it is learned against human
judgement, with cross-validation and a held-out test set.**

---

## 4. CLASS — optimal slide segmentation

### 4.1 Problem

A section produces an ordered list of atomic content blocks
`b_1 … b_m` (bullets, and for tables/flowcharts their rows/steps). We must
cut this list into consecutive groups (slides) `g_1 … g_k`. Current code
(`pipeline/density.py::_chunk`) uses a fixed per-profile cap and an
even-rebalance. That is a *greedy* choice and it is not optimal for load.

### 4.2 Formulation

Choose cut points `0 = i_0 < i_1 < … < i_k = m` to

```
minimise    Σ_{j=1..k}  cost( b_{i_{j-1}+1 .. i_j} )   +   λ · k
subject to  every b_t assigned to exactly one slide         (no content dropped)
            group size ≤ P_max   (profile hard cap, keeps layout safe)
```

`cost(group)` is the **cognitive-load cost of one slide**, defined directly
from the PSF sub-model:

```
cost(g) =  L(slide(g))              # want low load
         + μ · ( 1 − E(slide(g)) )  # but a near-empty slide is also bad
         + ν · overflow_penalty(g)  # quadratic past the soft target size
```

`λ · k` is the slide-count regulariser (few slides preferred, ties broken
toward fewer). This is **exactly the shape of Knuth–Plass optimal line
breaking** — replace "line" by "slide", "badness of a line" by "cognitive
load of a slide", "hyphenation penalty" by `λ`. We reuse their proof that a
one-dimensional DP over prefix cut points is globally optimal when
`cost` depends only on the contiguous group.

### 4.3 Algorithm

```
CLASS(blocks b[1..m], P_max, λ):
    best[0] = 0 ;  cut[0] = 0
    for i in 1..m:
        best[i] = +inf
        for p in max(0, i - P_max) .. i-1:
            c = best[p] + cost(b[p+1..i]) + λ
            if c < best[i]:
                best[i] = c ;  cut[i] = p
    reconstruct groups by following cut[] back from m
    return groups
```

`O(m · P_max)` time, `O(m)` space. `P_max` is small (≤ 8), so this is linear
in section length and negligible next to the LLM stages.

### 4.4 Guarantees

- **Completeness:** cut points partition `1..m`; every block lands on exactly
  one slide. No `bullets[:4]`-style truncation is possible.
- **Optimality:** global minimum of the objective over all legal segmentations
  (standard DP exchange argument, Knuth–Plass §3).
- **Monotone continuity:** because `cost` includes `1 − E`, the optimiser
  will not emit an orphan one-line continuation slide unless `P_max` forces
  it — fixing the very bug that `density.py::_chunk`'s rebalance hack works
  around today.

### 4.5 Where it plugs in

`pipeline/density.py::paginate_slide` currently calls `_chunk(items, size)`.
CLASS is a drop-in replacement for that call: same input list, same
"list of groups" output, but the split is load-optimal instead of even.
The atomic-layout, table-header-repeat, and figure-on-first-part rules
around it are unchanged.

---

## 5. Evaluation plan (for the paper)

### 5.1 Datasets

1. **Slide corpus** — generate decks from a public set of syllabi / textbook
   chapters / lecture PDFs (e.g. OpenStax chapters, MIT OCW, arXiv survey
   intros). ~150–300 slides.
2. **Human ratings** — 3+ raters per slide on a learning-oriented rubric
   (is the load manageable? is there a clear point? would this help a student?).
   Report inter-rater reliability (Krippendorff's α). This is the ground
   truth `y` for calibrating and testing PSF.

### 5.2 Studies

| # | Question | Method | Metric |
|---|---|---|---|
| E1 | Does PSF predict human-judged slide quality better than the baseline scorer and than strong ablations? | 5-fold CV, held-out test | Spearman ρ, RMSE, ranking NDCG |
| E2 | Which terms matter? | leave-one-term-out ablation of E, L, C and of each load driver | Δρ |
| E3 | Is the multiplicative form justified vs additive? | fit both, compare on test | ΔRMSE, calibration plot |
| E4 | Does CLASS produce measurably better decks than greedy `_chunk`? | within-subjects: same content, CLASS vs greedy, blind human preference + PSF_deck | preference %, ΔPSF_deck, Δslide-count |
| E5 | (stretch) learning outcome | small between-subjects quiz-score study, CLASS deck vs greedy deck | mean quiz score, time-on-task |
| E6 | Cost | wall-clock of CLASS vs `_chunk` across section lengths | ms |

### 5.3 Threats to validity

- Raters judge *perceived* quality, not learning → E5 addresses partially.
- Concept extraction is keyword-based (`intelligence/concept_extractor.py`),
  so `idf` and relational density are noisy → report robustness with an
  embedding-based concept extractor as a second condition.
- Generalisation across domains → stratify corpus by discipline, report
  per-stratum ρ.

---

## 6. Novelty statement

To our knowledge no prior work:

1. defines an **operational, theory-derived, human-calibrated** fitness
   function for an *automatically generated* slide (existing slide-quality
   work is either fully manual rubrics or black-box "engagement" heuristics
   like the one we replace); or
2. casts **slide pagination as optimal segmentation with a cognitive-load
   cost**, i.e. a Knuth–Plass generalisation, with a content-preservation
   guarantee.

The combination — a metric that is also the cost function of the algorithm
that optimises the artefact — is the paper's spine.

---

## 7. Implementation status

- `src/learnova/scoring/psf.py` — PSF sub-indices, deck aggregation, and the
  CLASS DP. Pure-Python, no LLM, deterministic, unit-tested.
- `src/learnova/scoring/scorer.py` — kept; `score_all_slides` gains an
  optional `engine="psf"` path so nothing downstream breaks and the two can
  be compared side by side (needed for E1).
- Calibration harness (`scripts/calibrate_psf.py`) — fits `α,β,γ,w_*` from a
  ratings CSV; ships with literature-derived defaults so the module is
  usable before any data is collected.
