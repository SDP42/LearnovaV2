"""
Scores the visual-selection stack against a labelled gold set.

Each gold case lists the *acceptable* director families for a piece of content.
Reported metrics:

* ``fit``       — chosen family is in the acceptable set
* ``coverage``  — chosen family renders as a real visual (not plain TEXT)
* ``data``      — the renderer actually received data (so it will draw)
* ``strict``    — all three at once: right family, drawn, with data

Run:  python -m learnova.evaluation.visual_accuracy
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List

GOLD = pathlib.Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "gold_visuals.json"


def load_gold() -> List[Dict[str, Any]]:
    return json.loads(GOLD.read_text())


def _one_slide_plan(case: Dict[str, Any]):
    from learnova.rendering.deck_director import plan_deck

    text = case["text"]
    sents = [s.strip() for s in text.replace("? ", ". ").split(". ") if s.strip()]
    bullets = [s if s.endswith(".") else s + "." for s in sents]
    deck = [{"original": {"text": text, "title": case["title"]},
             "improved": {"title": case["title"], "bullets": bullets, "layout_type": "MINIMAL_TEXT"}}]
    return plan_deck(deck).slides[0]


def evaluate(verbose: bool = False) -> Dict[str, Any]:
    gold = load_gold()
    rows = []
    for c in gold:
        sp = _one_slide_plan(c)
        fit = sp.family in c["ok"]
        cov = sp.family not in {"TEXT", "MINIMAL_TEXT", ""}
        has = bool(sp.data)
        rows.append({"id": c["id"], "got": sp.family, "ok": c["ok"], "fit": fit, "coverage": cov,
                     "data": has, "strict": fit and cov and has})
    n = len(rows)
    out = {k: round(sum(r[k] for r in rows) / n, 3) for k in ("fit", "coverage", "data", "strict")}
    out["n"] = n
    out["distinct_families"] = len({r["got"] for r in rows})
    if verbose:
        for r in rows:
            mark = "OK " if r["strict"] else "-- "
            print(f"{mark}{r['id']:<10} got={r['got']:<18} want={'/'.join(r['ok'])}  data={'Y' if r['data'] else 'N'}")
    out["rows"] = rows
    return out


if __name__ == "__main__":
    import sys

    res = evaluate(verbose=True)
    print({k: v for k, v in res.items() if k != "rows"})
    sys.exit(0)
