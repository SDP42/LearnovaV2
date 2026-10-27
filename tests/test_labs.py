"""Interactive labs: found by topic, embedded in the web deck, linked from the PowerPoint, served and uploadable via the API."""
import pytest
from fastapi.testclient import TestClient

from learnova import labs
from learnova.parsers.markdown_converter import from_typed_text
from learnova.pipeline.orchestrator import PipelineConfig, generate

_MD = ("# Segmentation\n\n## Region growing\nRegion growing groups pixels into larger regions based on a condition. "
       "We start from a seed pixel and add neighbours while max minus min stays within a threshold T.\n\n"
       "## Thresholding\nA single threshold separates the object from the background by intensity.\n")


def test_lab_is_found_by_topic_only():
    assert labs.find_lab("Region growing")["id"] == "region_growing"
    assert labs.find_lab("Region based segmentation (2/3)")["id"] == "region_growing"
    assert labs.find_lab("Edge detection") is None


def test_deck_embeds_and_links_the_lab():
    res = generate(from_typed_text(_MD, "seg"), PipelineConfig(enable_enhancement=False, enable_vision_ocr=False, enable_quizzes=False))
    html = res.html_bytes.decode("utf-8")
    assert html.count('class="lv-labbtn"') == 1 and 'id="lab-region_growing-doc"' in html
    from io import BytesIO

    from pptx import Presentation

    links = [sh.click_action.hyperlink.address for s in Presentation(BytesIO(res.pptx_bytes)).slides for sh in s.shapes
             if sh.has_text_frame and "interactive lab" in sh.text_frame.text]
    assert links == [labs.lab_url("region_growing")]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import apps.api.main as main

    monkeypatch.setattr(labs, "USER_DIR", tmp_path)
    main.app.dependency_overrides[main.current_user] = lambda: "u1"
    yield TestClient(main.app)
    main.app.dependency_overrides.pop(main.current_user, None)


def test_api_serves_and_accepts_labs(client):
    assert client.get("/api/labs/region_growing").status_code == 200
    assert client.get("/api/labs/../secret").status_code == 404
    r = client.post("/api/labs", json={"id": "otsu", "topics": ["otsu thresholding"], "html": "<html><head><title>Otsu Lab</title></head><body>x</body></html>"})
    assert r.status_code == 201 and r.json()["name"] == "Otsu Lab"
    assert any(l["id"] == "otsu" for l in client.get("/api/labs").json()["labs"])
    assert labs.find_lab("Otsu thresholding")["id"] == "otsu"
    assert client.post("/api/labs", json={"id": "Bad Id!", "topics": ["x"], "html": "<html></html>"}).status_code == 400


def test_new_topic_gets_a_lab_built_from_the_slide(tmp_path, monkeypatch):
    from learnova.labs import auto, slide_lab

    monkeypatch.setattr(auto, "AUTO_DIR", tmp_path)
    monkeypatch.setattr(labs, "USER_DIR", tmp_path.parent)
    imp = {"title": "Stages of mitosis", "bullets": ["Prophase: chromosomes condense", "Metaphase: chromosomes line up", "Anaphase: chromatids separate", "Telophase: two nuclei form"]}
    data = {"stages": [{"label": b.split(":")[0], "detail": b.split(":")[1].strip()} for b in imp["bullets"]]}
    got = slide_lab(imp, "PROCESS_LINEAR", data, labs.new_deck_state())
    assert got and got["auto"] and got["id"].startswith("auto-")
    page = (tmp_path / f"{got['id']}.html").read_text()
    assert "Prophase" in page and "function build" in page and 'name="learnova-topics"' in page
    full = labs.new_deck_state()
    full["auto"] = labs.MAX_AUTO_PER_DECK
    assert slide_lab({**imp, "title": "Cell cycle"}, "PROCESS_LINEAR", data, full) is None          # capped per deck
    assert slide_lab({**imp, "is_summary": True}, "PROCESS_LINEAR", data, labs.new_deck_state()) is None
    st = labs.new_deck_state()
    assert slide_lab({**imp, "title": "Mitosis (1/2)"}, "PROCESS_LINEAR", data, st) and slide_lab({**imp, "title": "Mitosis (2/2)"}, "PROCESS_LINEAR", data, st) is None
    assert slide_lab({**imp, "title": "Module 4"}, "PROCESS_LINEAR", data, labs.new_deck_state()) is None


def test_ai_written_lab_is_used_only_when_its_code_checks_out(tmp_path, monkeypatch):
    import json as _json
    import shutil

    from learnova.ai import assist
    from learnova.labs import auto

    if not shutil.which("node"):
        pytest.skip("node not installed")
    monkeypatch.setattr(auto, "AUTO_DIR", tmp_path)
    good = {"title": "Edit Distance Lab", "lead": "x", "cond": "d(i,j)", "inputs": "<div class=row></div>", "ideas": ["a"],
            "js": "const PRESETS=[{tag:'a',name:'b',desc:'c',input:{}}];function fill(i){}function readInputs(){return {}}function build(i){return [{k:'a',title:'b',explain:'c',view:'d'}]}"}

    class R:
        reply = _json.dumps(good)

        def generate(self, *a, **k):
            return self.reply

    r = R()
    monkeypatch.setattr(assist, "llm_available", lambda: True)
    monkeypatch.setattr("learnova.providers.router.get_router", lambda: r)
    made = auto.lab_for_slide("Edit distance", "Levenshtein distance between strings", "KEY_POINTS", {}, ["a", "b", "c"])
    assert made["name"] == "Edit Distance Lab"
    r.reply = _json.dumps({**good, "js": "function build( { broken"})                    # syntax error → falls back to the slide lab
    made2 = auto.lab_for_slide("Edit distance 2", "x", "KEY_POINTS", {}, ["Insert: add one character", "Delete: remove one character", "Substitute: change one character"])
    assert made2 and "step-through" in made2["name"]
    r.reply = _json.dumps({**good, "js": good["js"] + "fetch('http://x')"})              # network access is refused
    made3 = auto.lab_for_slide("Edit distance 3", "x", "KEY_POINTS", {}, ["Insert: add one character", "Delete: remove one character", "Substitute: change one character"])
    assert "step-through" in made3["name"]
