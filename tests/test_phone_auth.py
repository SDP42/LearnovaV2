import importlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNOVA_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LEARNOVA_AUTH", "on")
    monkeypatch.setenv("OTP_DEV_MODE", "1")
    monkeypatch.setenv("LEARNOVA_RATE_LIMIT", "off")
    monkeypatch.delenv("VITE_CLERK_PUBLISHABLE_KEY", raising=False)
    monkeypatch.delenv("CLERK_PUBLISHABLE_KEY", raising=False)
    from learnova.auth import phone

    phone._ready_for = None
    import apps.api.main as main

    return TestClient(main.app), phone


PHONE = "+919876543210"


def _login(c):
    r = c.post("/api/auth/otp/request", json={"phone": PHONE})
    assert r.status_code == 200
    v = c.post("/api/auth/otp/verify", json={"phone": PHONE, "code": r.json()["dev_otp"]})
    assert v.status_code == 200
    return v.json()


def test_full_flow_and_profile(client):
    c, _ = client
    assert c.get("/api/decks").status_code == 401
    data = _login(c)
    assert data["is_new"] and not data["user"]["completed"]
    h = {"Authorization": f"Bearer {data['token']}"}
    assert c.get("/api/auth/me", headers=h).json()["phone"] == PHONE
    r = c.put("/api/auth/profile", headers=h, json={"full_name": "Asha Rao", "role": "educator"})
    assert r.json()["completed"] and r.json()["full_name"] == "Asha Rao"
    assert c.get("/api/decks", headers=h).status_code == 200
    c.post("/api/auth/logout", headers=h)
    assert c.get("/api/auth/me", headers=h).status_code == 401


def test_wrong_code_attempts_and_single_use(client):
    c, phone = client
    r = c.post("/api/auth/otp/request", json={"phone": PHONE}).json()
    bad = "000000" if r["dev_otp"] != "000000" else "111111"
    for _ in range(phone.OTP_MAX_ATTEMPTS):
        assert c.post("/api/auth/otp/verify", json={"phone": PHONE, "code": bad}).status_code == 400
    # locked out even with the right code
    assert c.post("/api/auth/otp/verify", json={"phone": PHONE, "code": r["dev_otp"]}).status_code == 429


def test_code_is_single_use_and_resend_cooldown(client):
    c, _ = client
    r = c.post("/api/auth/otp/request", json={"phone": PHONE}).json()
    assert c.post("/api/auth/otp/request", json={"phone": PHONE}).status_code == 429
    assert c.post("/api/auth/otp/verify", json={"phone": PHONE, "code": r["dev_otp"]}).status_code == 200
    assert c.post("/api/auth/otp/verify", json={"phone": PHONE, "code": r["dev_otp"]}).status_code == 400


def test_invalid_phone_and_normalisation(client):
    c, phone = client
    assert c.post("/api/auth/otp/request", json={"phone": "123"}).status_code == 400
    assert phone.normalize_phone("98765 43210") == "+919876543210"
    assert phone.normalize_phone("0044 7700 900123") == "+447700900123"


def test_delete_account_removes_everything(client, tmp_path, monkeypatch):
    c, phone = client
    monkeypatch.setattr("learnova.config.DATA_DIR", tmp_path)
    data = _login(c)
    h = {"Authorization": f"Bearer {data['token']}"}
    udir = tmp_path / "users" / data["user"]["id"]
    udir.mkdir(parents=True)
    (udir / "x.txt").write_text("deck")
    assert c.delete("/api/auth/account", headers=h).status_code == 204
    assert not udir.exists()
    assert c.get("/api/auth/me", headers=h).status_code == 401
    assert _login(c)["is_new"]  # same number can sign up again, fresh account


def test_events_errors_and_backup(client, tmp_path):
    c, phone = client
    assert c.post("/api/events", json={"name": "landing_view", "path": "/"}).status_code == 204
    assert c.post("/api/errors", json={"message": "boom", "path": "/app"}).status_code == 204
    out = phone.backup(str(tmp_path / "bk"))
    import sqlite3
    assert sqlite3.connect(out).execute("select count(*) from events").fetchone()[0] == 1


def test_decks_are_isolated_between_users(tmp_path, monkeypatch):
    from learnova.storage import deck_library as dl
    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    (tmp_path / "users" / "u_a" / "d1").mkdir(parents=True)
    (tmp_path / "users" / "u_a" / "d1" / dl.META_FILE).write_text('{"id":"d1","user_id":"u_a"}')
    assert dl.get_deck("u_a", "d1") is not None
    assert dl.get_deck("u_b", "d1") is None
    assert dl.list_decks("u_b") == []


def test_rate_limit_and_security_headers(client, monkeypatch):
    c, _ = client
    monkeypatch.setenv("LEARNOVA_RATE_LIMIT", "on")
    r = c.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    for i in range(12):
        last = c.post("/api/auth/otp/request", json={"phone": "123"})
    assert last.status_code == 429


def test_analysis_endpoint_roundtrip(client, tmp_path, monkeypatch):
    """A saved deck exposes its before/after analysis, and only to its owner."""
    from learnova.parsers.markdown_converter import from_typed_text
    from learnova.pipeline.orchestrator import PipelineConfig, generate
    from learnova.analysis import build_analysis
    from learnova.storage import deck_library as dl

    monkeypatch.setattr(dl, "DATA_DIR", tmp_path)
    c, _ = client
    data = _login(c)
    uid = data["user"]["id"]
    doc = from_typed_text("## Layers of the Earth\nThe Earth has four main layers. The crust is the thin outer shell. "
                          "Beneath it lies the mantle. The outer core is liquid iron. The inner core is solid.", "t")
    res = generate(doc, PipelineConfig(build_pptx=False, build_html=False, enable_enhancement=False, enable_vision_ocr=False))
    a = build_analysis(res)
    assert a["summary"]["visual_coverage_after_pct"] == 100 and a["summary"]["fact_retention_pct"] >= 90
    dl.save_deck(uid, res, deck_id="abc123", analysis=a)
    h = {"Authorization": f"Bearer {data['token']}"}
    r = c.get("/api/decks/abc123/analysis", headers=h)
    assert r.status_code == 200 and r.json()["summary"]["slides_after"] >= 1
    assert c.get("/api/decks/abc123/analysis").status_code == 401
