"""
Engagement Scorer Module for Learnova
Computes a 0-100 engagement score per improved slide based on content quality & visual layout diversity.

Calibration note (2026-08-29): the original bands were tuned for keynote-style
slides (20-80 words, 2-4 bullets) and structurally could not score a *lecture*
slide above ~65 no matter how well built. Learnova's job is a teaching deck
that "captures all the thing", so the bands below treat a complete, well-paced
slide — one screen's worth of teaching, a title, a takeaway, plain wording — as
the 100 case, and only penalise slides that are genuinely overloaded (a wall of
9+ bullets, 200+ words) or empty. A slide the density stage has paginated to
~4-6 points should land in the mid-to-high 80s.
"""

def _text_density_score(text: str) -> float:
    # A paginated teaching slide runs ~40-130 words. That is the target, not a
    # penalty zone. Real overload (200+ words on one slide) still tapers to 8.
    word_count = len(text.split())
    if 20 <= word_count <= 130:
        return 20.0
    elif word_count < 20:
        return max(2.0, 20.0 * (word_count / 20))
    elif word_count <= 220:
        return max(8.0, 20.0 * (1 - (word_count - 130) / 130))
    else:
        return 8.0

def _bullet_count_score(bullets: list) -> float:
    n = len(bullets)
    if 2 <= n <= 6:
        return 20.0
    elif n == 7:
        return 17.0
    elif n == 1:
        return 12.0
    else:  # 8+ — a slide that should have been split
        return max(6.0, 20.0 - (n - 6) * 3)

def _title_quality_score(title: str) -> float:
    word_count = len(title.split())
    if 3 <= word_count <= 10:
        return 15.0
    elif word_count < 3:
        return max(2.0, 15.0 * (word_count / 3))
    else:
        return max(5.0, 15.0 * (1 - (word_count - 10) / 6))

def _has_takeaway_score(takeaway: str) -> float:
    if takeaway and len(takeaway.strip()) > 5:
        return 15.0
    return 0.0

def _readability_score(text: str) -> float:
    # Technical decks (NLP, biology, law) carry inherently long terms —
    # "categorization", "morphological", "photophosphorylation". Judge phrasing,
    # not vocabulary: the taper starts at 7.6 (was 6.5) and bottoms out at 4.
    words = text.split()
    if not words:
        return 0.0
    avg_len = sum(len(w) for w in words) / len(words)
    if avg_len < 7.6:
        return 15.0
    elif avg_len < 10.0:
        return max(4.0, 15.0 * (1 - (avg_len - 7.6) / 2.4))
    else:
        return 4.0

def _visual_layout_bonus(improved: dict, has_image: bool = False) -> float:
    """Up to 15 pts for a visual treatment or a well-structured text slide."""
    layout = improved.get("layout_type", "MINIMAL_TEXT").upper()
    bonus = 0.0
    if layout in ["FLOWCHART", "TABLE", "METRIC", "QUIZ", "TIMELINE",
                  "PYRAMID", "VENN", "COMPARISON", "WORKED_EXAMPLE"]:
        bonus += 10.0
    elif layout == "CARD_GRID":
        bonus += 8.0
    else:
        # Structured prose — a real title plus a distilled takeaway — still
        # reads far better than a bare bullet dump, so it is not a zero.
        if (improved.get("title") or "").strip() and \
           len((improved.get("takeaway") or "").strip()) > 5:
            bonus += 4.0
    if has_image:
        bonus += 5.0
    return min(15.0, bonus)

def score_slide(improved: dict, has_image: bool = False) -> dict:
    title = improved.get("title", "")
    bullets = improved.get("bullets", [])
    takeaway = improved.get("takeaway", "")
    full_text = " ".join(bullets)

    breakdown = {
        "text_density": round(_text_density_score(full_text), 1),
        "bullet_count": round(_bullet_count_score(bullets), 1),
        "title_quality": round(_title_quality_score(title), 1),
        "has_takeaway": round(_has_takeaway_score(takeaway), 1),
        "readability": round(_readability_score(full_text), 1),
        "visual_bonus": round(_visual_layout_bonus(improved, has_image), 1),
    }

    total = min(100.0, sum(breakdown.values()))
    return {"score": round(total), "breakdown": breakdown}

def score_all_slides(improved_results: list[dict], engine: str = "heuristic") -> dict:
    """
    Score every slide.

    ``engine="heuristic"`` (default) keeps the original weighted-sum score so
    nothing downstream changes. ``engine="psf"`` uses the research model in
    ``scoring/psf.py`` (Pedagogical Slide Fitness) and additionally returns the
    E/L/C breakdown and a deck-level flow term. Both can run side by side for
    the calibration study in ``docs/research/PSF_DESIGN.md``.
    """
    if not improved_results:
        return {"overall_score": 0, "slide_scores": []}

    if engine == "psf":
        from learnova.scoring.psf import psf_deck

        deck = psf_deck(improved_results)
        return {
            "overall_score": deck["psf_deck_100"],
            "slide_scores": [
                {"score": s["psf_100"], "breakdown": {"E": s["E"], "L": s["L"], "C": s["C"]}}
                for s in deck["slide_scores"]
            ],
            "psf": deck,
        }

    slide_scores = []
    for item in improved_results:
        imp = item.get("improved", {})
        orig = item.get("original", {})
        has_img = bool(orig.get("image") and orig["image"].get("bytes"))
        slide_scores.append(score_slide(imp, has_img))

    avg = sum(s["score"] for s in slide_scores) / len(slide_scores)
    return {"overall_score": round(avg), "slide_scores": slide_scores}
