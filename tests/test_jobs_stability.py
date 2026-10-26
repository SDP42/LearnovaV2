"""Jobs survive a restart, queue instead of piling up, cancel, and never leak server paths."""
import io
import time

import pytest

from learnova.errors import friendly_error
from learnova.parsers import text_inputs as ti
from learnova.pipeline import job_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNOVA_DB_PATH", str(tmp_path / "t.db"))
    job_db._ready_for = None
    yield


def _store():
    from learnova.pipeline.jobs import JobStore

    return JobStore()


def test_friendly_error_hides_paths_and_maps_known_failures():
    msg = friendly_error("Failed to open file '/var/folders/zz/tmp123.pdf'")
    assert "/var/" not in msg and "PDF" in msg
    assert "password" in friendly_error("document is encrypted").lower()
    generic = friendly_error(RuntimeError("boom at /Users/x/secret.py line 3"))
    assert "/Users" not in generic and "ref " in generic


def test_job_survives_restart_and_interrupted_build_is_reported():
    s1 = _store()
    j = s1.create("notes", user_id="u1")
    j.markdown, j.status = "## A\ntext", "awaiting_review"
    job_db.save(j, "typed")
    running = s1.create("deck", user_id="u1")
    running.markdown, running.status = "## B\nmore", "running"
    job_db.save(running, "typed")

    s2 = _store()                      # a fresh process: nothing in memory
    back = s2.get(j.id)
    assert back and back.status == "awaiting_review" and back.markdown.startswith("## A")
    assert back._markdown_doc is not None             # can be generated again without re-uploading
    cut = s2.get(running.id)
    assert cut.status == "failed" and "restarted" in cut.error and cut.markdown
    assert {x.id for x in s2.all("u1")} == {j.id, running.id}
    assert s2.get("nope") is None


def test_cancel_marks_job_cancelled():
    from learnova.pipeline.jobs import Job

    s = _store()
    j = s.create("x", user_id="u")
    j.status = "running"
    assert s.cancel(j.id) is True and j._cancel.is_set()
    j.status = "done"
    assert s.cancel(j.id) is False


def test_text_inputs():
    assert ti.looks_like(b"%PDF-1.7 ...", ".pdf") and not ti.looks_like(b"MZ\x90", ".pdf")
    assert ti.looks_like(b"PK\x03\x04", ".pptx") and not ti.looks_like(b"hello", ".docx")
    md = ti.plain_text_to_markdown("UNIT 1\nIntro text here.\n\n1. Basics of Memory\nStuff.")
    assert "## Unit 1" in md or "## UNIT 1".title() in md
    import docx

    d = docx.Document()
    d.add_heading("Photosynthesis", 1)
    d.add_paragraph("Plants make food.")
    d.add_paragraph("Light", style="List Bullet")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text, t.cell(1, 0).text, t.cell(1, 1).text = "Stage", "Place", "Light", "Thylakoid"
    buf = io.BytesIO()
    d.save(buf)
    out = ti.docx_to_markdown(buf.getvalue())
    assert "## Photosynthesis" in out and "- Light" in out and "| Stage | Place |" in out


def test_upload_formats_through_the_api(tmp_path, monkeypatch):
    import os
    os.environ["LEARNOVA_RATE_LIMIT"] = "off"
    from fastapi.testclient import TestClient
    from apps.api.main import app

    c = TestClient(app)
    ph = "+919000000077"
    otp = c.post("/api/auth/otp/request", json={"phone": ph}).json()["dev_otp"]
    h = {"Authorization": "Bearer " + c.post("/api/auth/otp/verify", json={"phone": ph, "code": otp}).json()["token"]}
    r = c.post("/api/jobs", files={"file": ("n.md", b"# Cells\nCells are the unit of life.\n## Organelles\nMitochondria make energy.", "text/markdown")}, headers=h)
    assert r.status_code == 202 and r.json()["status"] == "awaiting_review"
    r = c.post("/api/jobs", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}, headers=h)
    assert r.status_code == 400
    assert c.post("/api/jobs", files={"file": ("e.txt", b"   ", "text/plain")}, headers=h).status_code == 400
    jobs = c.get("/api/jobs", headers=h).json()["jobs"]
    assert any(j["status"] == "awaiting_review" for j in jobs)
    assert c.post(f"/api/jobs/{jobs[0]['id']}/cancel", headers=h).status_code == 200
    assert c.get("/api/health").json()["database"] is True


def test_short_prompt_is_expanded_into_a_lesson(monkeypatch):
    import os
    os.environ["LEARNOVA_RATE_LIMIT"] = "off"
    from fastapi.testclient import TestClient
    from apps.api.main import app
    from learnova.ai import lesson_writer as lw

    fake = "# Gradient Descent\n\n" + "\n\n".join(
        f"## Section {i}\n" + " ".join(["Gradient descent lowers a loss by stepping downhill."] * 8) for i in range(1, 9))

    monkeypatch.setattr(lw, "_llm", lambda prompt, audience, tone, detail: fake)
    c = TestClient(app)
    ph = "+919000000088"
    otp = c.post("/api/auth/otp/request", json={"phone": ph}).json()["dev_otp"]
    h = {"Authorization": "Bearer " + c.post("/api/auth/otp/verify", json={"phone": ph, "code": otp}).json()["token"]}
    r = c.post("/api/jobs/typed", json={"text": "Gradient descent for beginners", "title": "Typed Syllabus"}, headers=h).json()
    assert r["expansion"]["mode"] == "llm" and r["expansion"]["sections"] == 8
    md = c.get(f"/api/jobs/{r['id']}/markdown", headers=h).json()["markdown"]
    assert md.count("## ") == 8
    assert c.post("/api/jobs/typed", json={"text": "Gradient descent for beginners", "expand": False}, headers=h).json().get("expansion") is None
    assert lw.is_prompt("Gradient descent for beginners") and not lw.is_prompt("# Notes\n- a\n- b")


def test_lesson_validation_rejects_thin_output():
    from learnova.ai import lesson_writer as lw

    assert not lw._valid("# T\n\n## A\nshort\n\n## B\nshort", 9)
    good = "# T\n\n" + "\n\n".join(f"## S{i}\n" + "word " * 50 for i in range(8))
    assert lw._valid(good, 9)
    assert not lw._valid("# T\n\n## A\nAs an AI I cannot do that. " + "word " * 100, 4)


def test_provider_keys_and_image_generation(tmp_path, monkeypatch):
    import base64, io, os
    import httpx
    from PIL import Image
    from learnova.ai import image_providers as ip

    monkeypatch.setattr(ip, "_env_path", lambda: tmp_path / ".env")
    for v in ("GEMINI_API_KEY", "GEMINI_IMAGE_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY", "LEARNOVA_IMAGE_PROVIDER"):
        monkeypatch.delenv(v, raising=False)
    ip.reset()
    assert ip.provider_name() == "" and ip.generate("x") is None            # no key: callers fall back to the vector illustrator

    ip.save_key("gemini", "AIza" + "x" * 30)
    assert "GEMINI_API_KEY" in (tmp_path / ".env").read_text() and ip.provider_name() == "gemini"
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 200)).save(buf, "PNG")
    seen = {}

    def handler(req):
        seen["key"] = req.headers.get("x-goog-api-key")
        seen["body"] = req.content.decode()
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(buf.getvalue()).decode()}}]}}]})

    png = ip.generate(ip.style_prompt("a flask of liquid", "#1D4ED8", "#FFC93C"), client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert png and png[:4] == b"\x89PNG" and seen["key"].startswith("AIza") and "no text" in seen["body"].lower()

    # a rejected key pauses the provider instead of failing every slide
    bad = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"error": "denied"})))
    assert ip.generate("x", client=bad) is None
    assert ip.status()["paused"] is True
    ip.remove_key("gemini")
    assert "GEMINI_API_KEY" not in (tmp_path / ".env").read_text() and ip.provider_name() == ""


def test_providers_api_never_echoes_the_key(tmp_path, monkeypatch):
    import os
    os.environ["LEARNOVA_RATE_LIMIT"] = "off"
    from fastapi.testclient import TestClient
    from apps.api.main import app
    from learnova.ai import image_providers as ip

    monkeypatch.setattr(ip, "_env_path", lambda: tmp_path / ".env")
    monkeypatch.setattr(ip, "verify_key", lambda p, k, client=None: True)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    c = TestClient(app)
    ph = "+919000000099"
    otp = c.post("/api/auth/otp/request", json={"phone": ph}).json()["dev_otp"]
    h = {"Authorization": "Bearer " + c.post("/api/auth/otp/verify", json={"phone": ph, "code": otp}).json()["token"]}
    assert c.post("/api/providers", json={"provider": "groq", "key": "short"}, headers=h).status_code == 400
    secret = "gsk_" + "a1b2" * 10
    r = c.post("/api/providers", json={"provider": "groq", "key": secret}, headers=h)
    assert r.status_code == 200 and secret not in r.text
    assert next(p for p in r.json()["providers"] if p["id"] == "groq")["configured"] is True
    r = c.delete("/api/providers/groq", headers=h)
    assert next(p for p in r.json()["providers"] if p["id"] == "groq")["configured"] is False
