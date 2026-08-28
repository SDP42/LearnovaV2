"""
Pedagogical Slide Fitness (PSF) and Cognitive-Load-Aware Slide Segmentation
(CLASS).

This module is the research contribution described in
``docs/research/PSF_DESIGN.md``. It replaces the asserted weighted sum in
``scoring/scorer.py`` with:

* **PSF** — a per-slide fitness in ``[0, 1]`` built as a multiplicative model
  of three theory-derived sub-indices (information efficiency ``E``, cognitive
  load ``L``, multimedia coherence ``C``), aggregated to a deck score with a
  topic-flow term.
* **CLASS** — an ``O(m · P_max)`` dynamic program that paginates a list of
  content blocks across slides so as to minimise total cognitive-load cost,
  generalising Knuth & Plass optimal line breaking. It never drops a block.

No LLM calls. Fully deterministic. Pure standard library.

The free parameters (``PSFParams``) ship with literature-derived defaults so
the module is usable before any human ratings are collected;
``scripts/calibrate_psf.py`` fits them from a ratings CSV.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Sequence, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Lexical helpers — deterministic, no external corpora
# ─────────────────────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']+")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")

# A compact closed-class stop list. Content words are everything else.
_STOP = frozenset("""
a an the this that these those there here it its it's they them their we our you your
he she his her him i me my mine ours yours theirs
and or but nor so yet for as if than then thus hence also too very
is are was were be been being am do does did doing done have has had having
will would shall should can could may might must ought
of to in on at by from with about against between into through during before after
above below up down out off over under again further once
not no only own same such can just don't now
which who whom whose what where when why how
each any all both few more most other some
per via etc eg ie
""".split())

# High-frequency non-stop words: common enough that introducing one conveys
# little new information. Keeps pseudo-idf sane without shipping a full corpus.
_COMMON = frozenset("""
use used using make makes made get gets got go goes went come comes came
work works working need needs way ways thing things people time times year years
day days part parts kind type types form forms case cases point points number numbers
example examples show shows shown find finds found give gives given take takes taken
new old good bad big small high low large great different important main key basic
system systems process processes method methods model models data value values result results
group groups level levels area areas problem problems question questions answer answers
""".split())


def _words(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def _content_words(text: str) -> List[str]:
    return [w for w in _words(text) if w not in _STOP and len(w) > 2]


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_RE.split(text or "") if s.strip()]


def pseudo_idf(word: str) -> float:
    """
    Corpus-free estimate of a content word's inverse document frequency.

    Rationale: rarer words carry more information. Without a reference corpus
    we approximate rarity from (a) membership in a small common-word set and
    (b) morphological length — technical terms are systematically longer.
    Bounded to ``[0.4, 3.0]`` so no single term dominates ``U(s)``.
    """
    if word in _COMMON:
        base = 0.5
    elif len(word) <= 4:
        base = 1.0
    elif len(word) <= 7:
        base = 1.6
    elif len(word) <= 11:
        base = 2.2
    else:
        base = 2.8
    # Hyphenated or camel-ish compounds are almost always domain terms.
    if "-" in word:
        base += 0.3
    return max(0.4, min(3.0, base))


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _sigmoid(x: float) -> float:
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


# Relational / connective cues → element interactivity (intrinsic load).
_RELATIONAL_RE = re.compile(
    r"\b(because|therefore|thus|hence|so that|due to|as a result|leads? to|"
    r"causes?|results? in|depends? on|requires?|implies|if\b.+\bthen|"
    r"whereas|unlike|compared|in contrast|however|consequently|"
    r"followed by|then|next|finally|first|second|third)\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Parameters
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PSFParams:
    """
    Free parameters of the PSF model.

    ``alpha/beta/gamma`` are the Cobb-Douglas exponents (sum to 1). The ``w_*``
    and ``theta_l`` define the logistic cognitive-load model. The ``*_ref`` and
    ``kappa_e`` scale constants are fixed from theory / corpus statistics and
    are **not** meant to be fitted (keeps the model identifiable). Defaults
    below are literature-derived priors; refit with ``scripts/calibrate_psf.py``.
    """

    alpha: float = 0.40           # weight on information efficiency
    beta: float = 0.42            # weight on (1 - cognitive load)
    gamma: float = 0.18           # weight on multimedia coherence

    kappa_e: float = 6.0          # half-saturation of delivered information U(s)

    w_elem: float = 1.10          # element interactivity
    w_text: float = 1.35          # extraneous text load
    w_visual: float = 0.85        # visual complexity
    w_split: float = 1.60         # split-attention penalty
    theta_l: float = 2.30         # load logistic bias (higher ⇒ more forgiving)

    e_ref: float = 9.0            # concepts·(1+rel) that counts as "full" intrinsic load
    t_ref: float = 16.0          # working-memory chunks (≈ 4 chunks · 4 slots headroom)
    v_ref: float = 8.0           # table rows / flow nodes / grid cards that is "a lot"

    seductive_tau: float = 0.08   # min sentence↔centroid overlap to not be "off topic"
    flow_lo: float = 0.18         # ideal consecutive-slide concept overlap band
    flow_hi: float = 0.55
    lambda_slide: float = 0.35    # CLASS slide-count regulariser
    mu_empty: float = 0.9         # CLASS weight on (1 - E): discourages empty slides
    nu_overflow: float = 0.25     # CLASS quadratic overflow penalty past soft target

    def normalised(self) -> "PSFParams":
        s = self.alpha + self.beta + self.gamma
        if s <= 0:
            return replace(self, alpha=1 / 3, beta=1 / 3, gamma=1 / 3)
        return replace(self, alpha=self.alpha / s, beta=self.beta / s, gamma=self.gamma / s)


DEFAULT_PARAMS = PSFParams().normalised()


# ─────────────────────────────────────────────────────────────────────────────
# Slide feature extraction
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SlideFeatures:
    title: str = ""
    bullets: List[str] = field(default_factory=list)
    takeaway: str = ""
    layout_type: str = "MINIMAL_TEXT"
    table_rows: int = 0
    flow_nodes: int = 0
    grid_cards: int = 0
    has_image_here: bool = False
    image_desc: str = ""
    image_on_other_slide: bool = False

    @property
    def body_text(self) -> str:
        return " ".join(self.bullets)

    @property
    def concepts(self) -> List[str]:
        return _content_words(f"{self.title} {self.body_text}")


def features_from_slide(entry: Dict[str, Any]) -> SlideFeatures:
    """Adapt a pipeline slide dict (``{"improved": ..., "original": ...}``)."""
    imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else entry
    imp = imp or {}
    orig = entry.get("original", {}) if isinstance(entry, dict) else {}

    layout = str(imp.get("layout_type", "MINIMAL_TEXT")).upper()
    bullets = [str(b).strip() for b in (imp.get("bullets") or []) if str(b).strip()]

    img = orig.get("image") if isinstance(orig, dict) else None
    has_img = bool(img and img.get("bytes"))
    # The density stage sets original.image to None on continuation slides
    # whose figure lives on part 1 — that is the split-attention case.
    img_elsewhere = bool(img is None and (imp.get("continued") or entry.get("_figure_split")))

    mermaid = imp.get("mermaid_code", "") or ""
    return SlideFeatures(
        title=str(imp.get("title", "")),
        bullets=bullets,
        takeaway=str(imp.get("takeaway", "")).strip(),
        layout_type=layout,
        table_rows=len(imp.get("table_rows") or []),
        flow_nodes=mermaid.count("-->") + 1 if mermaid else (len(bullets) if layout == "FLOWCHART" else 0),
        grid_cards=len(bullets) if layout == "CARD_GRID" else 0,
        has_image_here=has_img,
        image_desc=str((img or {}).get("description", "")) if has_img else "",
        image_on_other_slide=img_elsewhere,
    )


# ─────────────────────────────────────────────────────────────────────────────
# The three sub-indices
# ─────────────────────────────────────────────────────────────────────────────


def information_efficiency(
    f: SlideFeatures, prior_concepts: frozenset[str], p: PSFParams = DEFAULT_PARAMS
) -> Tuple[float, Dict[str, float]]:
    """E(s) — delivered novel information, saturating, discounted by redundancy."""
    # A slide with a title but no body / figure delivers nothing, however
    # information-rich the title looks in isolation.
    if not f.bullets and not f.has_image_here and f.table_rows == 0:
        return 0.0, {"U": 0.0, "new_concepts": 0.0, "redundancy": 0.0}

    concs = f.concepts
    new = [c for c in dict.fromkeys(concs) if c not in prior_concepts]
    u = sum(pseudo_idf(c) for c in new)

    title_w = _content_words(f.title)
    overlaps = []
    for i, b in enumerate(f.bullets):
        bw = _content_words(b)
        others = [w for j, bb in enumerate(f.bullets) if j != i for w in _content_words(bb)]
        overlaps.append(max(_jaccard(bw, title_w), _jaccard(bw, others)))
    redundancy = sum(overlaps) / len(overlaps) if overlaps else 0.0

    saturated = u / (u + p.kappa_e)
    e = saturated * (1.0 - redundancy)
    return _clip01(e), {"U": u, "new_concepts": float(len(new)), "redundancy": redundancy}


def cognitive_load(
    f: SlideFeatures, p: PSFParams = DEFAULT_PARAMS
) -> Tuple[float, Dict[str, float]]:
    """L(s) ∈ [0,1] — logistic squash of CLT load drivers."""
    text = f.body_text
    concs = f.concepts
    n_conc = len(set(concs))
    rel_hits = len(_RELATIONAL_RE.findall(text))
    rel_density = rel_hits / max(1, len(f.bullets))

    elem = n_conc * (1.0 + rel_density)
    words = len(_words(text))
    visual = max(f.table_rows, f.flow_nodes, f.grid_cards)
    split = 1.0 if (f.image_on_other_slide and f.image_desc) else 0.0

    e_hat = _clip01(elem / p.e_ref)
    t_hat = _clip01(words / p.t_ref)
    v_hat = _clip01(visual / p.v_ref)

    z = (
        p.w_elem * e_hat
        + p.w_text * t_hat
        + p.w_visual * v_hat
        + p.w_split * split
        - p.theta_l
    )
    load = _sigmoid(z)
    return load, {
        "elem": e_hat, "text": t_hat, "visual": v_hat, "split": split,
        "n_concepts": float(n_conc), "words": float(words),
    }


def multimedia_coherence(
    f: SlideFeatures, p: PSFParams = DEFAULT_PARAMS
) -> Tuple[float, Dict[str, float]]:
    """C(s) ∈ [0,1] — mean of four measurable Mayer indicators."""
    real_title = bool(f.title.strip()) and not re.fullmatch(r"slide\s*\d+", f.title.strip(), re.I)
    signalling = 1.0 if (len(f.takeaway) > 5 and real_title) else (0.5 if real_title else 0.0)

    centroid = set(f.concepts)
    if f.bullets and centroid:
        on_topic = []
        for b in _sentences(f.body_text) or f.bullets:
            bw = _content_words(b)
            sim = _jaccard(bw, centroid) if bw else 1.0
            on_topic.append(1.0 if sim >= p.seductive_tau else 0.0)
        coherence = sum(on_topic) / len(on_topic)
    else:
        coherence = 1.0

    if f.has_image_here and f.image_desc:
        dup = _jaccard(_content_words(f.image_desc), _content_words(f.body_text))
        non_redundant = 1.0 - _clip01((dup - 0.5) / 0.5)
    else:
        non_redundant = 1.0

    contiguity = 1.0 if f.has_image_here else (0.0 if f.image_on_other_slide else 0.5)

    parts = [signalling, coherence, non_redundant, contiguity]
    return sum(parts) / len(parts), {
        "signalling": signalling, "coherence": coherence,
        "non_redundant": non_redundant, "contiguity": contiguity,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PSF — per slide and per deck
# ─────────────────────────────────────────────────────────────────────────────


def psf_slide(
    f: SlideFeatures,
    prior_concepts: frozenset[str] = frozenset(),
    p: PSFParams = DEFAULT_PARAMS,
) -> Dict[str, Any]:
    p = p.normalised()
    e, e_dbg = information_efficiency(f, prior_concepts, p)
    l, l_dbg = cognitive_load(f, p)
    c, c_dbg = multimedia_coherence(f, p)

    score = (max(e, 1e-6) ** p.alpha) * (max(1.0 - l, 1e-6) ** p.beta) * (max(c, 1e-6) ** p.gamma)
    return {
        "psf": round(score, 4),
        "psf_100": round(100.0 * score),
        "E": round(e, 4),
        "L": round(l, 4),
        "C": round(c, 4),
        "breakdown": {"E": e_dbg, "L": l_dbg, "C": c_dbg},
    }


def _flow_term(concept_lists: List[frozenset[str]], p: PSFParams) -> float:
    """Trapezoidal reward for moderate topic overlap between adjacent slides."""
    if len(concept_lists) < 2:
        return 1.0
    vals = []
    for a, b in zip(concept_lists, concept_lists[1:]):
        ov = _jaccard(list(a), list(b))
        if p.flow_lo <= ov <= p.flow_hi:
            vals.append(1.0)
        elif ov < p.flow_lo:
            vals.append(0.6 + 0.4 * (ov / p.flow_lo if p.flow_lo else 1.0))
        else:  # ov > flow_hi  → repetitive
            vals.append(max(0.4, 1.0 - (ov - p.flow_hi) / (1.0 - p.flow_hi)))
    return sum(vals) / len(vals)


def psf_deck(
    slides: List[Dict[str, Any]], p: PSFParams = DEFAULT_PARAMS
) -> Dict[str, Any]:
    """
    Score a whole deck. ``slides`` is the pipeline's ``final_deck`` list
    (each ``{"improved": ..., "original": ...}``). Concepts introduced on an
    earlier slide are "prior" for later slides, so ``E`` rewards genuinely new
    material rather than restating.
    """
    p = p.normalised()
    feats = [features_from_slide(s) for s in slides]
    prior: set[str] = set()
    per_slide = []
    concept_sets: List[frozenset[str]] = []
    for f in feats:
        res = psf_slide(f, frozenset(prior), p)
        per_slide.append(res)
        cs = frozenset(f.concepts)
        concept_sets.append(cs)
        prior |= cs

    if per_slide:
        log_mean = sum(math.log(max(s["psf"], 1e-6)) for s in per_slide) / len(per_slide)
        geo_mean = math.exp(log_mean)
    else:
        geo_mean = 0.0

    flow = _flow_term(concept_sets, p)
    deck_score = geo_mean * flow
    return {
        "psf_deck": round(deck_score, 4),
        "psf_deck_100": round(100.0 * deck_score),
        "geometric_mean": round(geo_mean, 4),
        "flow": round(flow, 4),
        "slide_scores": per_slide,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLASS — Cognitive-Load-Aware Slide Segmentation
# ─────────────────────────────────────────────────────────────────────────────


def _group_cost(
    blocks: Sequence[str],
    p: PSFParams,
    *,
    layout_type: str = "MINIMAL_TEXT",
    soft_target: int,
    prior_concepts: frozenset[str] = frozenset(),
) -> float:
    """Cognitive-load cost of putting ``blocks`` on one slide (CLASS objective)."""
    f = SlideFeatures(bullets=list(blocks), layout_type=layout_type)
    load, _ = cognitive_load(f, p)
    e, _ = information_efficiency(f, prior_concepts, p)
    over = max(0, len(blocks) - soft_target)
    return load + p.mu_empty * (1.0 - e) + p.nu_overflow * (over * over)


def segment_blocks(
    blocks: Sequence[str],
    *,
    max_per_slide: int,
    soft_target: int | None = None,
    layout_type: str = "MINIMAL_TEXT",
    params: PSFParams = DEFAULT_PARAMS,
) -> List[List[str]]:
    """
    CLASS: partition ``blocks`` into consecutive groups (slides) minimising

        Σ_j  cost(group_j)  +  λ · (#groups)

    subject to ``len(group) ≤ max_per_slide``. ``O(m · max_per_slide)``.

    Guarantees every block is placed exactly once (drop-in replacement for
    ``pipeline/density.py::_chunk`` with load-optimal instead of even splits).
    """
    p = params.normalised()
    m = len(blocks)
    if m == 0:
        return []
    if m <= max_per_slide and m <= (soft_target or max_per_slide):
        return [list(blocks)]
    cap = max(1, int(max_per_slide))
    target = int(soft_target) if soft_target else max(1, min(cap, round(cap * 0.75)))

    INF = float("inf")
    best = [INF] * (m + 1)
    cut = [0] * (m + 1)
    best[0] = 0.0
    for i in range(1, m + 1):
        lo = max(0, i - cap)
        for pcut in range(lo, i):
            group = blocks[pcut:i]
            c = best[pcut] + _group_cost(
                group, p, layout_type=layout_type, soft_target=target
            ) + p.lambda_slide
            if c < best[i]:
                best[i] = c
                cut[i] = pcut

    groups: List[List[str]] = []
    idx = m
    while idx > 0:
        pcut = cut[idx]
        groups.append(list(blocks[pcut:idx]))
        idx = pcut
    groups.reverse()
    return groups


__all__ = [
    "PSFParams",
    "DEFAULT_PARAMS",
    "SlideFeatures",
    "features_from_slide",
    "information_efficiency",
    "cognitive_load",
    "multimedia_coherence",
    "psf_slide",
    "psf_deck",
    "segment_blocks",
    "pseudo_idf",
]
