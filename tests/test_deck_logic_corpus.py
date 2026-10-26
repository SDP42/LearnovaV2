"""Visual decisions on realistic lesson text (demo/corpus): each case is a defect that once produced a poor slide."""
import pytest

from learnova.visuals.engine import decide


def fam(title, text):
    return decide(title, text, [], [])


CASES = [
    ("Comparing the algorithms",
     "Bubble sort is O(n^2) and stable, and it is used for teaching. Merge sort is O(n log n) and stable, and it suits linked lists and external sorting. "
     "Quick sort is O(n log n) on average and not stable, and it is usually fastest in practice.", "COMPARE_TABLE"),
    ("The reaction", "The reaction is N2 + 3H2 <-> 2NH3. It is reversible and exothermic, which means it releases 92 kJ of heat per mole of nitrogen converted.", "FORMULA_CALLOUT"),
    ("Revenue by region", "North America generated $5.6 million, Europe $3.9 million, Asia Pacific $2.1 million and the rest of the world $0.8 million.", "CHART_CATEGORICAL"),
    ("Product mix", "Subscriptions provided 62 percent of revenue, services 24 percent and hardware 14 percent.", "CHART_PART_TO_WHOLE"),
    ("Sales funnel", "The team generated 8,000 leads. Of these, 3,200 became qualified prospects. 1,400 reached a demo, 520 received a proposal and 190 signed a contract.", "FUNNEL"),
    ("Key terms", "Equilibrium is the state where forward and reverse reactions occur at the same rate. A catalyst is a substance that speeds up a reaction without being used up. "
                  "Le Chatelier's principle states that a system at equilibrium shifts to oppose any change imposed on it.", "LIST_STRUCTURED"),
    ("Tallest Mountains", "Everest is 8,849 metres high. K2 is 8,611 metres high. Kangchenjunga is 8,586 metres high. Lhotse is 8,516 metres high.", "CHART_CATEGORICAL"),
]


@pytest.mark.parametrize("title,text,want", CASES, ids=[c[0] for c in CASES])
def test_family(title, text, want):
    assert fam(title, text).family == want


def test_process_steps_are_short_phrases_without_ordinals():
    d = fam("Steps", "First, nitrogen is taken from the air and hydrogen is made from natural gas. Second, the gases are mixed and compressed to about 200 atmospheres. "
                     "Third, the mixture passes over an iron catalyst. Fourth, the hot gases are cooled so that ammonia liquefies and is removed. Finally, unreacted gases are recycled.")
    labels = [s["label"] for s in d.data["stages"]]
    assert d.family == "PROCESS_LINEAR" and "Fourth" not in labels and all(len(l.split()) <= 6 for l in labels)
    assert all(labels) and not any(l.split()[-1].lower() in {"is", "are", "gives", "favours"} for l in labels)


def test_stat_labels_sit_beside_their_figures():
    d = fam("Highlights", "Revenue reached $12.4 million in Q3, up 18 percent from Q2. Gross margin improved from 41 percent to 46 percent. "
                          "The company added 1,200 new customers and kept churn at 4 percent.")
    vals = {t["value"]: t["label"] for t in d.data["tiles"]}
    assert d.family == "STAT_TILES" and "$12.4 million" in vals and "18%" in vals and "growth" in vals["18%"].lower()
    assert all("percent" not in v for v in vals)


def test_prose_gets_a_facts_rail_only_for_headline_figures():
    d = fam("Bubble sort", "Bubble sort repeatedly compares neighbouring items and swaps them if they are in the wrong order. After each pass the largest remaining item has moved to the end. "
                           "It is simple but slow, with O(n^2) time in the average and worst case.")
    assert d.family == "PROSE" and any(f["value"] == "O(n²)" for f in d.data.get("facts", []))
    d = fam("Effects on society", "Cities grew quickly because workers moved to factory towns. Manchester's population rose from about 25,000 in 1750 to over 300,000 in 1850. "
                                  "Working conditions were harsh, with 12 to 16 hour days and child labour. However, real wages and life expectancy rose in the long run, and a new middle class emerged.")
    assert d.family != "COMPARE_VISUAL" and not any("hour" in f["value"] for f in d.data.get("facts", []))


def test_head_body_duplicates_are_removed():
    from learnova.visuals.engine import dedupe_head_body

    h, b = dedupe_head_body("A high pressure favours ammonia", "A high pressure favours ammonia because there are fewer gas molecules")
    assert h == "A high pressure favours ammonia" and b.startswith("because")
    assert dedupe_head_body("Stable government protected", "A stable government protected property and patents")[1] == "property and patents"


def test_compare_cells_keep_their_words():
    d = fam("Agricultural versus industrial society",
            "Agricultural societies were rural and tied to the seasons, whereas industrial societies were urban and tied to the clock. "
            "Agricultural output depended on land; industrial output depended on capital and machines.")
    cells = " ".join(" ".join(r) for r in d.data["rows"])
    assert "land" in cells and "Output depended on l" not in cells.replace("land", "")
