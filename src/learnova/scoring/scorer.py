"""
Engagement Scorer Module for Learnova
Computes a 0-100 engagement score per improved slide based on content quality & visual layout diversity.
"""

def _text_density_score(text: str) -> float:
    word_count = len(text.split())
    if 20 <= word_count <= 80:
        return 20.0
    elif word_count < 20:
        return max(0.0, 20.0 * (word_count / 20))
    elif word_count <= 100:
        return max(0.0, 20.0 * (1 - (word_count - 80) / 20))
    else:
        return 5.0

def _bullet_count_score(bullets: list) -> float:
    n = len(bullets)
    if 2 <= n <= 4:
        return 20.0
    elif n == 5:
        return 16.0
    elif n == 1:
        return 10.0
    else:
        return max(4.0, 20.0 - (n - 4) * 3)

def _title_quality_score(title: str) -> float:
    word_count = len(title.split())
    if 3 <= word_count <= 8:
        return 15.0
    elif word_count < 3:
        return max(0.0, 15.0 * (word_count / 3))
    else:
        return max(3.0, 15.0 * (1 - (word_count - 8) / 4))

def _has_takeaway_score(takeaway: str) -> float:
    if takeaway and len(takeaway.strip()) > 5:
        return 15.0
    return 0.0

def _readability_score(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    avg_len = sum(len(w) for w in words) / len(words)
    if avg_len < 6.5:
        return 15.0
    elif avg_len < 8.5:
        return max(0.0, 15.0 * (1 - (avg_len - 6.5) / 2))
    else:
        return 4.0

def _visual_layout_bonus(improved: dict, has_image: bool = False) -> float:
    """15 pts bonus for dynamic non-text visual layouts or attached image."""
    layout = improved.get("layout_type", "MINIMAL_TEXT").upper()
    bonus = 0.0
    if layout in ["FLOWCHART", "TABLE", "METRIC", "QUIZ"]:
        bonus += 10.0
    elif layout == "CARD_GRID":
        bonus += 7.0
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
