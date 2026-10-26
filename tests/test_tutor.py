"""Deck Tutor: grounded retrieval, personas, intents, and the no-key fallback."""
from learnova.ai import tutor

SLIDES = [
    {"index": 0, "layout_type": "MINIMAL_TEXT", "title": "Gradient Descent", "bullets": [], "takeaway": "",
     "source_text": "Gradient descent is an optimisation method that repeatedly moves the parameters to reduce the loss. The learning rate controls the size of each step."},
    {"index": 1, "layout_type": "MINIMAL_TEXT", "title": "Bias and Variance", "bullets": [], "takeaway": "",
     "source_text": "Bias is the error from overly simple assumptions. Variance is the error from sensitivity to the training set. High variance causes overfitting."},
    {"index": 2, "layout_type": "MINIMAL_TEXT", "title": "Training Steps", "bullets": [], "takeaway": "",
     "source_text": "First, collect and clean the data. Next, split it into training and validation sets. Then train the model and evaluate it."},
]


def test_retrieval_finds_the_right_slide():
    hits = tutor.retrieve("what does the learning rate do?", tutor.build_passages(SLIDES))
    assert hits and hits[0]["slide"] == 1


def test_own_logic_answer_is_grounded_and_in_persona(monkeypatch):
    monkeypatch.setattr("learnova.ai.assist.llm_available", lambda: False)
    r = tutor.answer("What causes overfitting?", SLIDES, "genz")
    assert r["mode"] == "own-logic" and r["sources"][0]["slide"] == 2 and "variance" in r["answer"].lower()
    r2 = tutor.answer("What causes overfitting?", SLIDES, "brief")
    assert r2["answer"].lstrip().startswith("•") or "• " in r2["answer"]


def test_intents_and_unknown_questions(monkeypatch):
    monkeypatch.setattr("learnova.ai.assist.llm_available", lambda: False)
    assert "Gradient Descent" in tutor.answer("summarise this deck", SLIDES)["answer"]
    assert "Slide 3" in tutor.answer("explain slide 3", SLIDES)["answer"]
    assert "couldn't find" in tutor.answer("what is the capital of France", SLIDES)["answer"]
    assert len(tutor.list_personas()) >= 6


def test_llm_mode_cites_slides(monkeypatch):
    monkeypatch.setattr("learnova.ai.assist.llm_available", lambda: True)

    class R:
        available = True

        def generate(self, *a, **k):
            return "The learning rate sets the step size [S1]."

    monkeypatch.setattr("learnova.providers.router.get_router", lambda: R())
    r = tutor.answer("what is the learning rate?", SLIDES, "teacher")
    assert r["mode"] == "llm" and r["sources"] == [{"slide": 1, "title": "Gradient Descent"}]
