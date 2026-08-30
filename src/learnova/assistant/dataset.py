"""
QA / intent dataset (spec §16–§22, §46, §47).

Two layers:

* **templates** (``data/assistant/qa_templates.json``) — phrasing templates ×
  slot fillers. ``generate()`` expands them into the ~1–2k benchmark set
  written to ``data/assistant/qa_dataset.json``. Regenerate after editing
  templates:  ``python -m learnova.assistant.dataset``
* **gold** (``data/assistant/gold_examples.json``) — hand-curated tricky
  cases: ambiguity, typos, voice-like phrasing, multi-turn, edge cases.

Each row:  ``{id, category, intent, question, variants[], entities,
expected_action, requires_context, requires_presentation}``.
"""

from __future__ import annotations

import itertools
import json
import pathlib
import random
from typing import Dict, List

from learnova.assistant.intents import INTENT_SPEC, Intent

_DATA = pathlib.Path(__file__).resolve().parents[3] / "data" / "assistant"


def _load(name: str) -> object:
    p = _DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


# ── slot fillers ────────────────────────────────────────────────────────────
_SLOTS: Dict[str, List[str]] = {
    "num": ["1", "2", "3", "4", "5", "one", "two", "three", "seven"],
    "ordinal": ["first", "second", "third", "last", "latest"],
    "concept": ["RSA", "AES", "phishing", "social engineering", "TCP handshake",
                "public key cryptography", "gradient descent", "tokenization",
                "the OSI model", "deadlock", "normalization", "backpropagation",
                "a digital signature", "symmetric encryption"],
    "concept_b": ["AES", "DES", "spear phishing", "asymmetric encryption",
                  "UDP", "SGD", "stemming"],
    "topic": ["cryptography", "network security", "machine learning",
              "social engineering", "NLP", "operating systems", "databases"],
    "subject": ["cybersecurity", "networking", "machine learning", "NLP"],
    "slide_no": ["3", "5", "10", "12", "one", "five"],
    "section": ["examples", "RSA", "introduction", "summary", "diagram",
                "conclusion", "attack flow"],
    "lang": ["Hindi", "Marathi", "simple English", "Spanish"],
    "count": ["3", "5", "10"],
}


def _fill(template: str, rng: random.Random) -> tuple[str, Dict[str, str]]:
    ents: Dict[str, str] = {}
    out = template
    for slot in list(_SLOTS):
        token = "{" + slot + "}"
        while token in out:
            val = rng.choice(_SLOTS[slot])
            ents.setdefault(slot, val)
            out = out.replace(token, val, 1)
    return out, ents


_SLOT_TO_ENTITY = {
    "num": "presentation_reference", "ordinal": "presentation_reference",
    "concept": "concept", "concept_b": "concept_b", "topic": "topic",
    "subject": "subject", "slide_no": "slide_number", "section": "section_name",
    "lang": "target_language", "count": "count",
}


def generate(seed: int = 7) -> List[dict]:
    templates = _load("qa_templates.json") or _default_templates()
    rng = random.Random(seed)
    rows: List[dict] = []
    counter = itertools.count(1)
    for group in templates:
        intent = Intent(group["intent"])
        spec = INTENT_SPEC[intent]
        want = int(group.get("expand", 12))
        seen: set = set()
        tries = 0
        while len([r for r in rows if r["intent"] == intent.value]) < want and tries < want * 12:
            tries += 1
            tmpl = rng.choice(group["templates"])
            text, slot_ents = _fill(tmpl, rng)
            if text.lower() in seen:
                continue
            seen.add(text.lower())
            entities = {}
            for slot, val in slot_ents.items():
                if slot in _SLOT_TO_ENTITY and ("{" + slot + "}") in tmpl:
                    entities[_SLOT_TO_ENTITY[slot]] = val
            rows.append({
                "id": f"QA-{next(counter):04d}",
                "category": spec.category.value,
                "intent": intent.value,
                "question": text,
                "variants": [],
                "entities": entities,
                "expected_action": spec.action.value,
                "requires_context": spec.requires_context,
                "requires_presentation": spec.requires_presentation,
            })
    # merge the hand-curated gold rows
    gold = _load("gold_examples.json") or []
    for g in gold:
        g.setdefault("id", f"GOLD-{next(counter):04d}")
        rows.append(g)
    return rows


def write_dataset(seed: int = 7) -> pathlib.Path:
    rows = generate(seed)
    out = _DATA / "qa_dataset.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def load_dataset() -> List[dict]:
    return _load("qa_dataset.json") or generate()


def load_gold() -> List[dict]:
    return _load("gold_examples.json") or []


def _default_templates() -> List[dict]:
    """Fallback if the JSON file is missing — kept small; the real set is JSON."""
    return [
        {"intent": "OPEN_PRESENTATION", "expand": 20, "templates": [
            "open presentation {num}", "show presentation {num}",
            "launch the {ordinal} presentation", "take me to presentation {num}",
            "can I see presentation {num}", "bring up the {ordinal} deck",
            "open the {topic} presentation", "pull up the deck about {topic}",
            "open LRN-PRES-000{num}", "let's open number {num}"]},
        {"intent": "GET_WEB_DECK", "expand": 12, "templates": [
            "give me the web deck of presentation {num}",
            "open the interactive version of the {topic} presentation",
            "show me presentation {num} as a web deck",
            "I want the interactive deck for {topic}"]},
        {"intent": "NEXT_SLIDE", "expand": 6, "templates": [
            "next slide", "next", "move on", "go forward", "advance"]},
        {"intent": "GO_TO_SLIDE", "expand": 10, "templates": [
            "go to slide {slide_no}", "show slide {slide_no}",
            "jump to slide {slide_no}", "take me to slide {slide_no}"]},
        {"intent": "EXPLAIN_CONCEPT", "expand": 20, "templates": [
            "explain {concept}", "what is {concept}", "tell me about {concept}",
            "how does {concept} work", "describe {concept}"]},
        {"intent": "COMPARE_CONCEPTS", "expand": 8, "templates": [
            "compare {concept} and {concept_b}",
            "what's the difference between {concept} and {concept_b}",
            "{concept} vs {concept_b}"]},
        {"intent": "START_QUIZ", "expand": 8, "templates": [
            "quiz me", "quiz me on {topic}", "give me {count} questions",
            "test me on this chapter"]},
    ]


if __name__ == "__main__":
    path = write_dataset()
    data = json.loads(path.read_text())
    print(f"wrote {len(data)} rows -> {path}")


__all__ = ["generate", "write_dataset", "load_dataset", "load_gold"]
