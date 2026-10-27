from learnova.pipeline.polish import merge_thin_parts, polish_deck, retitle


def _e(title, bullets, layout="MINIMAL_TEXT"):
    return {"original": {"text": " ".join(bullets)}, "improved": {"layout_type": layout, "title": title, "bullets": bullets}}


def test_titles_are_cleaned_and_generic_ones_become_claims():
    d = [_e("INTRODUCTION", ["Parsing is the task of recovering the structure of a sentence from its words."]), _e("•POS TAGGING", ["x y z w"]),
         _e("Features Features", ["a b c d"]), _e("Checkpoint 1", ["q"], "QUIZ")]
    retitle(d)
    assert d[0]["improved"]["title"].startswith("Parsing is the task")
    assert d[1]["improved"]["title"] == "POS tagging" and d[2]["improved"]["title"] == "Features" and d[3]["improved"]["title"] == "Checkpoint 1"


def test_thin_continuations_merge_and_renumber():
    d = [_e("Ambiguity (1/3)", ["Some strings have many parses."]), _e("Ambiguity (2/3)", ["Choose the likeliest one."]), _e("Ambiguity (3/3)", ["x " * 40], "MINIMAL_TEXT")]
    d[2]["improved"]["bullets"] = ["word " * 30]
    assert merge_thin_parts(d) == 1 and len(d) == 2
    assert [e["improved"]["title"] for e in d] == ["Ambiguity (1/2)", "Ambiguity (2/2)"]
    assert polish_deck([_e("A", ["one two three four"])])["merged_thin"] == 0
