"""AI-written slide diagrams are checked before use; split topics get named parts instead of (2/5) counters."""
from learnova.ai import topic_art


GOOD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 720"><rect width="600" height="720" fill="#ffffff"/>'
        '<line x1="40" y1="600" x2="560" y2="600" stroke="#1f2937"/><line x1="40" y1="600" x2="40" y2="80" stroke="#1f2937"/>'
        '<circle cx="120" cy="500" r="8" fill="PRIMARY"/><circle cx="220" cy="420" r="8" fill="PRIMARY"/>'
        '<circle cx="320" cy="350" r="8" fill="PRIMARY"/><line x1="60" y1="560" x2="540" y2="160" stroke="ACCENT" stroke-width="4"/>'
        '<text x="560" y="140" font-size="20" text-anchor="end">Fitted line with a very long label $here$</text></svg>')


def test_clean_svg_accepts_drawing_and_fixes_labels():
    svg = topic_art.clean_svg("Here you go:\n" + GOOD, "#A61E4D", "#22C55E")
    assert svg and "#A61E4D" in svg and "PRIMARY" not in svg and "$" not in svg
    assert 'width="600"' in svg


def test_clean_svg_rejects_unsafe_or_empty():
    assert topic_art.clean_svg(GOOD.replace("<rect", "<script>alert(1)</script><rect"), "#000000", "#111111") is None
    assert topic_art.clean_svg(GOOD.replace('<rect width', '<image href="http://x/y.png"/><rect width'), "#000000", "#111111") is None
    assert topic_art.clean_svg('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>', "#000000", "#111111") is None
    assert topic_art.clean_svg("no svg here", "#000000", "#111111") is None


def test_art_page_only_serves_cached_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(topic_art, "ART_DIR", tmp_path)
    (tmp_path / ("a" * 20 + ".svg")).write_text(GOOD.replace("<rect", "<title>Least squares</title><rect", 1))
    page = topic_art.art_page("a" * 20)
    assert page and "<svg" in page and "Least squares" in page
    assert topic_art.art_page("../etc/passwd") is None and topic_art.art_page("b" * 20) is None


def test_no_ai_means_no_diagram(monkeypatch):
    assert topic_art.available() is False
    assert topic_art.illustrate([{"improved": {"title": "Bias", "bullets": ["High bias means underfitting the data."]}}], ["KEY_POINTS"], "#000000", "#111111") == 0


def test_split_topic_parts_are_named():
    from learnova.pipeline.polish import name_parts

    entries = [{"improved": {"title": "Hypothesis (1/2)", "bullets": ["A hypothesis is a function that describes the target."]}},
               {"improved": {"title": "Hypothesis (2/2)", "bullets": ["Hypothesis space (H): the set of all legal hypotheses."]}}]
    name_parts(entries)
    assert entries[0]["improved"]["title"] == "Hypothesis"
    assert entries[1]["improved"]["title"] == "Hypothesis: Hypothesis space (H)" or "(2/2)" not in entries[1]["improved"]["title"]
