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
