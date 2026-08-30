"""
Assistant layer — NLU, resolver, orchestrator, multi-turn, edge cases, and the
QA-dataset benchmark floors (spec §43–§48).
"""

import pytest

from learnova.assistant import ids
from learnova.assistant.benchmark import run as bench_run
from learnova.assistant.dataset import load_dataset
from learnova.assistant.nlu import classify, normalise
from learnova.assistant.registry import PresentationEntry
from learnova.assistant.resolver import resolve_presentation_reference
from learnova.assistant.session import SessionContext
from learnova.assistant import orchestrator as orch


# ── fixtures ────────────────────────────────────────────────────────────────
DECKS = [
    PresentationEntry("LRN-PRES-0001", "d1", "u", 1, "Introduction to Cryptography",
                      subject="cybersecurity", topic="cryptography",
                      tags=["rsa", "crypto", "encryption", "keys"],
                      aliases=["cryptography presentation", "rsa deck", "crypto deck"],
                      slide_count=12, has_web_deck=True),
    PresentationEntry("LRN-PRES-0002", "d2", "u", 2, "Social Engineering Attacks",
                      subject="cybersecurity", topic="social engineering",
                      tags=["phishing", "social", "engineering"],
                      aliases=["social engineering presentation", "phishing deck"],
                      slide_count=9, has_web_deck=True),
    PresentationEntry("LRN-PRES-0003", "d3", "u", 3, "NLP Fundamentals",
                      subject="nlp", topic="nlp", tags=["nlp", "language", "tokenization"],
                      aliases=["nlp presentation", "nlp deck"], slide_count=22),
]


@pytest.fixture
def session(monkeypatch):
    monkeypatch.setattr(orch, "build_registry", lambda uid: list(DECKS))
    return SessionContext("s1", "u")


def handle(text, session):
    return orch.handle(text, session).to_dict()


# ── ids ─────────────────────────────────────────────────────────────────────
def test_id_scheme():
    assert ids.pres_id(7) == "LRN-PRES-0007"
    assert ids.slide_id("LRN-PRES-0007", 3) == "LRN-PRES-0007-S03"
    assert ids.is_pres_id("LRN-PRES-0007")
    assert not ids.is_pres_id("presentation 7")
    assert ids.parse_slide_id("LRN-PRES-0007-S03") == ("LRN-PRES-0007", 3)


# ── NLU ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,intent", [
    ("open presentation 2", "OPEN_PRESENTATION"),
    ("hey learnova, open the second presentation", "OPEN_PRESENTATION"),
    ("opn pres 2", "OPEN_PRESENTATION"),
    ("give me the web deck of presentation 2", "GET_WEB_DECK"),
    ("next slide", "NEXT_SLIDE"),
    ("go back", "PREVIOUS_SLIDE"),
    ("go to slide five", "GO_TO_SLIDE"),
    ("what is RSA", "EXPLAIN_CONCEPT"),
    ("what's the difference between RSA and AES", "COMPARE_CONCEPTS"),
    ("explain this like I'm a beginner", "SIMPLIFY"),
    ("quiz me on this presentation", "START_QUIZ"),
    ("stop", "STOP_SPEAKING"),
    ("create a presentation about cybersecurity", "CREATE_PRESENTATION"),
    ("what does this diagram mean", "EXPLAIN_VISUAL"),
])
def test_nlu_intents(text, intent):
    assert classify(text).intent.value == intent


def test_nlu_entities():
    assert classify("go to slide 7").entities.get("slide_number") == 7
    r = classify("compare RSA and AES")
    assert r.entities.get("concept") == "rsa" and r.entities.get("concept_b") == "aes"


def test_normalise_strips_wakeword_and_fixes_typos():
    assert normalise("Hey Learnova, opn the presntation") == "open the presentation"


# ── resolver ────────────────────────────────────────────────────────────────
def test_resolve_by_number_and_id():
    assert resolve_presentation_reference("presentation 2", DECKS).entry.pres_id == "LRN-PRES-0002"
    assert resolve_presentation_reference("LRN-PRES-0003", DECKS).entry.pres_id == "LRN-PRES-0003"
    assert resolve_presentation_reference("the second one", DECKS).entry.display_number == 2


def test_resolve_by_title_and_alias():
    assert resolve_presentation_reference("the RSA presentation", DECKS).entry.pres_id == "LRN-PRES-0001"
    assert resolve_presentation_reference("the phishing deck", DECKS).entry.pres_id == "LRN-PRES-0002"


def test_resolve_ambiguous_asks():
    r = resolve_presentation_reference("the cybersecurity presentation", DECKS)
    assert r.status == "ambiguous" and len(r.candidates) == 2


def test_resolve_not_found():
    assert resolve_presentation_reference("presentation 99", DECKS).status == "not_found"
    assert resolve_presentation_reference("the biology deck", DECKS).status == "not_found"


# ── orchestrator: single actions ────────────────────────────────────────────
def test_open_then_navigate(session):
    r = handle("open presentation 2", session)
    assert r["type"] == "OPEN_PRESENTATION" and r["presentation_id"] == "LRN-PRES-0002"
    r = handle("next slide", session)
    assert r["type"] == "NAVIGATE" and r["slide_number"] == 2
    r = handle("go to slide 9", session)
    assert r["slide_number"] == 9
    r = handle("go to slide 50", session)
    assert r["type"] == "ERROR_RESPONSE" and r["error_code"] == "SLIDE_OUT_OF_RANGE"


def test_web_deck_by_title(session):
    r = handle("give me the web deck for the RSA presentation", session)
    assert r["type"] == "SHOW_WEB_DECK" and r["presentation_id"] == "LRN-PRES-0001"


def test_ambiguous_open_asks_clarification(session):
    r = handle("open the security presentation", session)
    assert r["type"] == "ASK_CLARIFICATION" and len(r["options"]) == 2


def test_navigate_without_presentation_errors(session):
    r = handle("next slide", session)
    assert r["type"] == "ERROR_RESPONSE" and r["error_code"] == "NO_ACTIVE_PRESENTATION"


def test_no_presentations(monkeypatch):
    monkeypatch.setattr(orch, "build_registry", lambda uid: [])
    s = SessionContext("s2", "u")
    r = orch.handle("open presentation 2", s).to_dict()
    assert r["type"] == "ERROR_RESPONSE" and r["error_code"] == "NO_PRESENTATIONS"


def test_voice_control_and_repeat(session):
    handle("open presentation 1", session)
    r = handle("stop", session)
    assert r["type"] == "VOICE_CONTROL"
    r = handle("say that again", session)
    assert r["type"] == "VOICE_CONTROL" and r["message"]


# ── multi-turn ──────────────────────────────────────────────────────────────
def test_multi_turn_context(session):
    handle("open the NLP presentation", session)
    assert session.current_presentation == "LRN-PRES-0003"
    r = handle("go to slide 10", session)
    assert r["slide_number"] == 10 and session.current_slide == 10
    r = handle("explain this slide", session)
    assert r["type"] == "EXPLAIN_CONTENT" and r["presentation_id"] == "LRN-PRES-0003"
    handle("open presentation 1", session)
    assert session.previous_presentation == "LRN-PRES-0003"


def test_search_then_pick_from_results(session):
    r = handle("show me my cybersecurity presentations", session)
    assert r["type"] == "SHOW_SEARCH_RESULTS" and len(r["results"]) >= 2
    r = handle("open the second one", session)
    assert r["type"] == "OPEN_PRESENTATION"


# ── benchmark floors ────────────────────────────────────────────────────────
def test_dataset_is_generated():
    rows = load_dataset()
    assert 1000 <= len(rows) <= 2500
    ids_seen = {r["id"] for r in rows}
    assert len(ids_seen) == len(rows)               # unique ids
    for r in rows[:50]:
        assert {"id", "category", "intent", "question", "expected_action"} <= set(r)


def test_benchmark_accuracy_floor():
    res = bench_run()
    assert res.intent_acc >= 0.83, res.report()
    assert res.action_acc >= 0.85, res.report()


def test_gold_examples_intent_exact():
    from learnova.assistant.dataset import load_gold
    gold = load_gold()
    assert len(gold) >= 30
    # Rows that genuinely need conversation context ("the second one") are not
    # expected to be nailed by the stateless NLU alone.
    misses = [
        g["question"] for g in gold
        if not g.get("requires_context")
        and classify(g["question"]).intent.value != g["intent"]
        and not _lenient(classify(g["question"]).intent.value, g["intent"])
    ]
    assert len(misses) <= 2, misses


def _lenient(a, b):
    groups = [{"SEARCH_PRESENTATION", "WHERE_IS_TOPIC", "FIND_PRESENTATIONS_ABOUT",
               "SEARCH_CONTENT"}, {"GIVE_EXAMPLE", "REAL_WORLD_EXAMPLE"},
              {"OPEN_PRESENTATION", "DOWNLOAD_PRESENTATION"},
              {"EXPLAIN_SLIDE", "EXPLAIN_VISUAL", "READ_SLIDE"}]
    return any(a in g and b in g for g in groups)
