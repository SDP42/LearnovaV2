"""POST /api/explain and the per-deck explainer downloads."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    import apps.api.main as main

    main.app.dependency_overrides[main.current_user] = lambda: "u1"
    yield TestClient(main.app), main
    main.app.dependency_overrides.pop(main.current_user, None)


def test_explain_solves_a_typed_problem(client):
    c, _ = client
    r = c.post("/api/explain", json={"problem": "Solve 3x + 5 = 20"})
    assert r.status_code == 200
    body = r.json()
    assert body["explainer"]["answer"] == "x = 5" and len(body["explainer"]["steps"]) >= 3
    assert all(s["explain"] for s in body["explainer"]["steps"])           # every step says why
    assert body["html"].startswith("<!doctype html>") and "step by step" in body["html"].lower()


def test_explain_rejects_what_it_cannot_solve_with_a_helpful_message(client):
    c, _ = client
    r = c.post("/api/explain", json={"problem": "Write me a poem about autumn leaves"})
    assert r.status_code == 422 and "Solve 3x + 5 = 20" in r.json()["detail"]
    assert c.post("/api/explain", json={"problem": " "}).status_code == 422


def test_deck_explainers_are_listed_and_downloadable(client, monkeypatch):
    c, main = client
    from learnova.explain import solve_text

    ex = solve_text("Solve 3x + 5 = 20").to_dict()
    slides = [{"index": 0, "title": "Intro", "explainer": None}, {"index": 2, "title": "Solving a linear equation", "explainer": ex}]
    monkeypatch.setattr(main.deck_library, "get_deck", lambda u, d: {"title": "Algebra.md"} if d == "d1" else None)
    monkeypatch.setattr(main.deck_library, "read_slides", lambda u, d: {"slides": slides})

    listed = c.get("/api/decks/d1/explainers").json()["explainers"]
    assert listed == [{"slide": 2, "title": "Solving a linear equation", "kind": "linear equation", "problem": ex["problem"], "answer": "x = 5", "steps": len(ex["steps"])}]
    page = c.get("/api/decks/d1/explainers/2")
    assert page.status_code == 200 and "attachment" in page.headers["content-disposition"] and "x = 5" in page.text
    assert c.get("/api/decks/d1/explainers/0").status_code == 404
    assert c.get("/api/decks/nope/explainers").status_code == 404


def test_stepper_slides_carry_their_explainer_in_the_payload():
    from learnova.parsers.markdown_converter import from_typed_text
    from learnova.pipeline.orchestrator import PipelineConfig, generate
    from learnova.rendering.deck_payload import slides_payload

    res = generate(from_typed_text("# Algebra\n\n## Solving a linear equation\nSolve 3x + 5 = 20. Find the value of x.\n\n## Averages\nFind the mean of 4, 8, 15, 16, 23, 42.\n", "a"),
                   PipelineConfig(enable_enhancement=False, enable_vision_ocr=False, enable_quizzes=False, build_pptx=False, build_html=False))
    pay = slides_payload(res.final_deck)
    solved = [s for s in pay if s["explainer"]]
    assert solved and all(s["family"] == "STEPPER" and s["explainer"]["steps"] for s in solved)
