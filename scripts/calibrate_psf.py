"""
Calibrate PSF parameters against human slide ratings.

Input CSV (one row per rated slide), columns:

    deck_id,slide_index,title,bullets,takeaway,layout_type,human_score

  * ``bullets``     — bullets joined by ``" || "``
  * ``human_score`` — mean rater score, any scale (rescaled to [0,1] here)

Usage:

    python scripts/calibrate_psf.py ratings.csv --out fitted_params.json

With no SciPy available it runs a coarse random search so the script still
produces a usable fit. Results are written as JSON matching ``PSFParams``.

See docs/research/PSF_DESIGN.md §3.7 and paper_draft.md §5.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from typing import List, Tuple

from learnova.scoring.psf import (
    PSFParams,
    SlideFeatures,
    cognitive_load,
    information_efficiency,
    multimedia_coherence,
)


def _load_rows(path: str) -> List[Tuple[SlideFeatures, float]]:
    rows: List[Tuple[SlideFeatures, float]] = []
    raw_scores: List[float] = []
    parsed: List[Tuple[SlideFeatures, float]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            bullets = [b.strip() for b in (r.get("bullets") or "").split("||") if b.strip()]
            f = SlideFeatures(
                title=r.get("title", ""),
                bullets=bullets,
                takeaway=r.get("takeaway", ""),
                layout_type=(r.get("layout_type") or "MINIMAL_TEXT").upper(),
            )
            y = float(r["human_score"])
            parsed.append((f, y))
            raw_scores.append(y)
    lo, hi = min(raw_scores), max(raw_scores)
    span = (hi - lo) or 1.0
    for f, y in parsed:
        rows.append((f, (y - lo) / span))
    return rows


def _predict(f: SlideFeatures, p: PSFParams) -> float:
    e, _ = information_efficiency(f, frozenset(), p)
    l, _ = cognitive_load(f, p)
    c, _ = multimedia_coherence(f, p)
    return (max(e, 1e-6) ** p.alpha) * (max(1 - l, 1e-6) ** p.beta) * (max(c, 1e-6) ** p.gamma)


def _rmse(rows, p: PSFParams) -> float:
    p = p.normalised()
    return math.sqrt(sum((_predict(f, p) - y) ** 2 for f, y in rows) / len(rows))


def _spearman(rows, p: PSFParams) -> float:
    p = p.normalised()
    preds = [_predict(f, p) for f, _ in rows]
    ys = [y for _, y in rows]

    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        rr = [0.0] * len(xs)
        for pos, i in enumerate(order):
            rr[i] = pos
        return rr

    rp, ry = rank(preds), rank(ys)
    n = len(rows)
    d2 = sum((rp[i] - ry[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1)) if n > 1 else 0.0


def calibrate(rows, iterations: int = 4000, seed: int = 0) -> PSFParams:
    rng = random.Random(seed)
    best = PSFParams()
    best_loss = _rmse(rows, best)
    for _ in range(iterations):
        cand = PSFParams(
            alpha=rng.uniform(0.1, 0.6),
            beta=rng.uniform(0.1, 0.7),
            gamma=rng.uniform(0.05, 0.4),
            w_elem=rng.uniform(0.4, 2.0),
            w_text=rng.uniform(0.4, 2.2),
            w_visual=rng.uniform(0.2, 1.6),
            w_split=rng.uniform(0.6, 2.4),
            theta_l=rng.uniform(1.0, 3.5),
        )
        loss = _rmse(rows, cand)
        if loss < best_loss:
            best, best_loss = cand, loss
    return best.normalised()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ratings_csv")
    ap.add_argument("--out", default="fitted_psf_params.json")
    ap.add_argument("--iterations", type=int, default=4000)
    args = ap.parse_args()

    rows = _load_rows(args.ratings_csv)
    print(f"loaded {len(rows)} rated slides")
    print(f"prior   RMSE={_rmse(rows, PSFParams()):.4f}  ρ={_spearman(rows, PSFParams()):+.3f}")

    fitted = calibrate(rows, iterations=args.iterations)
    print(f"fitted  RMSE={_rmse(rows, fitted):.4f}  ρ={_spearman(rows, fitted):+.3f}")

    Path(args.out).write_text(json.dumps(asdict(fitted), indent=2), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
