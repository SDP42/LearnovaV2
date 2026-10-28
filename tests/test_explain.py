"""Step-by-step explainers compute their numbers; they are never guessed."""
import pytest

from learnova.explain import explainer_html, solve_text
from learnova.explain.model import Explainer

CASES = [
    ("Solve 3x + 5 = 20", "linear equation", "x = 5"),
    ("If 7x - 4 = 3x + 12, find x.", "linear equation", "x = 4"),
    ("Solve 2(x - 3) = 4x + 6", "linear equation", "x = -6"),
    ("Find x if 4x + 9 = x + 21", "linear equation", "x = 4"),
    ("Solve for y given 2y + 3 = 11", "linear equation", "y = 4"),
    ("Solve x^2 - 5x + 6 = 0", "quadratic equation", "x = 2 or x = 3"),
    ("2x + 3y = 12 and x - y = 1", "pair of linear equations", "x = 3, y = 2"),
    ("What is 15% of 240?", "percentage", "36"),
    ("Find the mean of 4, 8, 15, 16, 23, 42", "mean", "18"),
    ("Find the median of 3, 9, 1, 7, 5", "median", "5"),
    ("A bag has 3 red and 5 blue balls. What is the probability of drawing a red ball?", "probability", "3/8"),
    ("P(spam)=0.3, P(free|spam)=0.8, P(free)=0.32. Find P(spam|free).", "Bayes' rule", "0.75"),
    ("Invest $1000 at 5% simple interest for 3 years", "simple interest", "1,150"),
    ("A right triangle has legs 3 and 4. Find the hypotenuse.", "Pythagoras", "5"),
    ("A car travels 150 km in 3 hours. What is its speed?", "speed", "50"),
    ("Find the derivative of x^3 + 2x", "derivative", "3x^2 + 2"),
]


@pytest.mark.parametrize("text,kind,ans", CASES, ids=[c[0][:30] for c in CASES])
def test_solves_and_explains(text, kind, ans):
    ex = solve_text(text)
    assert ex is not None and ex.kind == kind
    assert ans in ex.answer.replace("−", "-")
    assert len(ex.steps) >= 3 and all(s.title and s.explain for s in ex.steps), "every step says what and why"


def test_linear_steps_are_balanced_and_checked():
    ex = solve_text("Solve 3x + 5 = 20")
    titles = [s.title for s in ex.steps]
    assert titles == ["Write down the equation", "Subtract 5 from both sides", "Divide both sides by 3", "Check the answer"]
    assert "[[" in ex.steps[1].math[0]                      # the change is marked for highlighting
    assert "20 = 20" in " ".join(ex.steps[-1].math)


def test_cyk_accepts_a_grammatical_sentence():
    ex = solve_text("Grammar: S -> NP VP; NP -> Det N; VP -> V NP; Det -> the; N -> dog | cat; V -> chased. Sentence: the dog chased the cat")
    assert ex and ex.kind == "CYK parsing" and ex.answer.startswith("Accepted")
    assert any(s.grid for s in ex.steps) and ex.steps[-1].focus == [(0, 4)]
    bad = solve_text("Grammar: S -> NP VP; NP -> Det N; VP -> V NP; Det -> the; N -> dog | cat; V -> chased. Sentence: dog the chased cat the")
    assert bad is None or bad.answer.startswith("Rejected")


def test_non_problems_are_left_alone():
    assert solve_text("The Industrial Revolution began in Britain around 1760.") is None
    assert solve_text("Photosynthesis converts light into chemical energy.") is None


def test_html_is_self_contained_and_round_trips():
    ex = solve_text("Solve 3x + 5 = 20")
    page = explainer_html(ex, title="Linear")
    assert "<script>" in page and "Next step" in page and "const EX=" in page and "</script></body>" in page
    back = Explainer.from_dict(ex.to_dict())
    assert [s.title for s in back.steps] == [s.title for s in ex.steps] and back.answer == ex.answer


def test_nlp_solvers_match_textbook_answers():
    from learnova.explain import solve_text

    bi = solve_text("Using a bigram model on the corpus: <s> I am Sam </s> <s> Sam I am </s> <s> I do not like green eggs and ham </s>. Compute P(<s> I am Sam </s>).")
    assert bi and bi.kind == "bigram probability" and bi.answer.startswith("P = 1/9")
    nb = solve_text("Naive Bayes. Training: comedy: fun couple love love; action: fast furious shoot; comedy: couple fly fast fun fun; "
                    "action: furious shoot shoot fun; action: fly fast shoot love. Test: fast couple shoot fly")
    assert nb and nb.answer == "action"
    vit = solve_text("Viterbi for the HMM. States: H, C; Observations: 3 1 3; Start: H=0.8, C=0.2; Transition: H->H=0.6, H->C=0.4, C->H=0.5, "
                     "C->C=0.5; Emission: H:1=0.2, H:2=0.4, H:3=0.4, C:1=0.5, C:2=0.4, C:3=0.1")
    assert vit and vit.answer == "H → C → H" and all(s.explain for s in vit.steps)
