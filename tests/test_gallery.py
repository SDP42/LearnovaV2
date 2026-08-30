"""Gallery catalogue, store and API."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from learnova.gallery import catalog as gcat
from learnova.gallery import store as gstore


@pytest.fixture()
def api_client():
    import apps.api.main as main

    return TestClient(main.app)


def test_catalog_loads_and_has_breadth():
    entries = gcat.load_catalog(force=True)
    assert len(entries) >= 1000
    subjects = {e.subject for e in entries}
    assert len(subjects) >= 20
    outlines = [e for e in entries if e.status == "outline"]
    assert len(outlines) >= 15
    # every curated entry carries a real brief with headings
    for e in outlines:
        assert e.outline.strip()
        assert "##" in e.outline


def test_catalog_slugs_are_unique_and_safe():
    entries = gcat.load_catalog()
    slugs = [e.slug for e in entries]
    assert len(slugs) == len(set(slugs))
    assert all(s and s == s.lower() and " " not in s for s in slugs)


def test_subjects_counts_sum_to_total():
    entries = gcat.load_catalog()
    total = sum(s["count"] for s in gcat.subjects())
    assert total == len(entries)


def test_list_entries_filters():
    bio = gcat.list_entries(subject="Biology")
    assert bio and all(e.subject == "Biology" for e in bio)
    hits = gcat.list_entries(query="photosynthesis")
    assert any(e.slug == "photosynthesis" for e in hits)
    assert gcat.list_entries(subject="No Such Subject") == []


def test_entry_to_dict_marks_ready_only_with_a_deck():
    e = gcat.get_entry("photosynthesis")
    assert e is not None
    assert e.to_dict()["status"] in {"outline", "index"}
    assert e.to_dict({"slide_count": 8})["status"] == "ready"
    assert e.to_dict({"slide_count": 8})["has_deck"] is True


def test_gallery_list_endpoint(api_client):
    r = api_client.get("/api/gallery?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1000
    assert len(body["entries"]) == 5
    assert body["subjects"]
    assert body["ready_total"] <= body["total"]


def test_gallery_entry_and_missing(api_client):
    assert api_client.get("/api/gallery/photosynthesis").status_code == 200
    assert api_client.get("/api/gallery/not-a-real-slug").status_code == 404
    # a deck that is only an index entry has no pre-built deck
    r = api_client.get("/api/gallery/mitosis-and-meiosis/deck")
    assert r.status_code == 404


def test_curated_briefs_have_teaching_structure():
    for e in gcat.list_entries(ready_only=True):
        heads = [ln for ln in e.outline.splitlines() if ln.startswith("## ")]
        assert "## The core ideas" in heads
        assert "## How it works, step by step" in heads
        assert "## The takeaway" in heads
        assert "## Why it matters" in heads  # every curated topic explains its relevance


def test_bake_progressive_reveal_flips_the_default():
    from learnova.gallery.builder import _bake_progressive_reveal

    src = b"<script>\n        var LV_BUILD = (function () { return false; })();\n</script>"
    out = _bake_progressive_reveal(src).decode()
    assert "window.__learnovaBuild = true" in out
    # idempotent
    assert _bake_progressive_reveal(out.encode()).decode().count("window.__learnovaBuild = true") == 1
    assert _bake_progressive_reveal(None) is None


def test_assistant_recognises_gallery_check():
    from learnova.assistant.nlu import classify
    from learnova.assistant.intents import Intent

    for utt in [
        "do you have slides on photosynthesis",
        "is there a ready-made deck on binary search",
        "check that the cold war slides are pre built",
        "is bayes theorem pre-built",
    ]:
        r = classify(utt)
        assert r.intent == Intent.CHECK_GALLERY, (utt, r.intent)
        assert r.entities.get("topic"), utt


def test_assistant_confirms_and_offers_a_ready_deck(monkeypatch):
    import learnova.assistant.orchestrator as orch
    from learnova.assistant.session import SessionContext

    monkeypatch.setattr(orch, "classify_llm", None)
    monkeypatch.setattr(orch, "_entries", lambda s: [])

    s = SessionContext(session_id="t", user_id="u")
    r = orch.handle("is there a ready-made deck on photosynthesis", s)
    assert r.type == "SHOW_GALLERY_RESULTS"
    assert "yes" in r.message.lower()
    assert any(row["has_deck"] and row["slug"] == "photosynthesis" for row in r.results)

    r2 = orch.handle("do you have a deck on a topic that does not exist at all", s)
    assert r2.type in ("TEXT_RESPONSE", "SHOW_GALLERY_RESULTS")
    assert "create" in r2.message.lower() or "generate" in r2.message.lower()


def test_search_gallery_tool_ranks_ready_first():
    from learnova.assistant.tools import search_gallery

    res = search_gallery("photosynthesis")
    assert res.ok
    assert res.data["results"][0]["slug"] == "photosynthesis"
    assert res.data["results"][0]["has_deck"] is True
    assert not search_gallery("").ok


def test_clone_to_user_roundtrip(tmp_path, monkeypatch):
    # a fake gallery deck on disk
    from learnova.storage import deck_library as dl

    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    monkeypatch.setattr("learnova.gallery.catalog.DATA_DIR", tmp_path)

    slug = "demo-topic"
    src = tmp_path / "users" / gcat.GALLERY_USER / slug
    src.mkdir(parents=True)
    (src / dl.META_FILE).write_text(json.dumps({
        "id": slug, "user_id": gcat.GALLERY_USER, "title": "Demo Topic",
        "created_at": 1.0, "slide_count": 4, "quiz_count": 0, "overall_score": 70,
    }))
    (src / dl.SLIDES_FILE).write_text(json.dumps({"slides": [{"title": "A"}], "quizzes": []}))

    assert gstore.has_deck(slug)
    new_id = gstore.clone_to_user(slug, "user-42")
    assert new_id and new_id != slug
    cloned = json.loads((tmp_path / "users" / "user-42" / new_id / dl.META_FILE).read_text())
    assert cloned["user_id"] == "user-42"
    assert cloned["id"] == new_id
    assert cloned["from_gallery"] == slug
    assert gstore.clone_to_user("does-not-exist", "user-42") is None
