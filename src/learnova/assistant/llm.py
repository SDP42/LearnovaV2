"""
LLM layer for the assistant (spec §7 fallback, §9, §30, §31, §42).

* :func:`classify_intent` — used when the deterministic NLU is not confident.
  Returns an :class:`~learnova.assistant.nlu.NLUResult` validated against the
  real taxonomy, or ``None`` on any failure (the caller keeps the rule result).
* :func:`answer_question` — the conversational answer for EXPLAIN_CONTENT.
  Grounded in the provided deck/slide text when available; may simplify or
  translate the *reply*; must never invent Learnova content it wasn't given.

Both go through ``learnova.providers.router`` (Groq → Gemini → NVIDIA) and
degrade to ``None`` / ``""`` if no provider is available, so the assistant
still works offline on the rule path.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from learnova.assistant.intents import INTENT_SPEC, Intent
from learnova.assistant.nlu import NLUResult, normalise
from learnova.logging_config import logger

_ENABLED = os.getenv("LEARNOVA_ASSISTANT_LLM", "1").lower() in {"1", "true", "yes", "on"}

_INTENT_LIST = ", ".join(i.value for i in Intent if i not in
                         (Intent.AMBIGUOUS, Intent.UNKNOWN))

_CLASSIFY_SYSTEM = f"""You route a user's message to a Learnova assistant intent.
Learnova is an interactive learning platform with presentations / web decks.
Return ONLY compact JSON: {{"intent": "<INTENT>", "entities": {{...}}, "confidence": 0-1}}.
INTENT is exactly one of: {_INTENT_LIST}
Common entities: presentation_reference, slide_number, concept, concept_b,
topic, subject, section_name, target_language, count.
If the message is a general knowledge question about a concept, use
EXPLAIN_CONCEPT. If it asks to open/show/launch a deck, use OPEN_PRESENTATION.
If you cannot tell, use "UNKNOWN" with low confidence. No prose, JSON only."""

_ANSWER_SYSTEM = """You are the Learnova learning assistant.
Answer the user's question clearly and accurately for a student.
RULES:
- If SOURCE MATERIAL is provided, ground your answer in it and do not
  contradict it. If the answer isn't in the material, say what the material
  covers and answer from general knowledge, flagged briefly.
- Never claim Learnova contains something it doesn't.
- Keep it tight: 2-5 sentences unless asked for more. Plain text, no markdown
  headings. Voice-friendly.
- STYLE 'simple' -> short sentences, everyday words, one idea at a time.
  STYLE 'step_by_step' -> a short numbered list of steps.
- If a TARGET LANGUAGE is given, write the whole answer in that language."""


def _router():
    try:
        from learnova.providers.router import get_router
        r = get_router()
        return r if r.available else None
    except Exception:
        return None


def classify_intent(utterance: str, context: Optional[dict] = None) -> Optional[NLUResult]:
    if not _ENABLED:
        return None
    router = _router()
    if not router:
        return None
    ctx = context or {}
    hint = ""
    if ctx.get("current_presentation"):
        hint = (f"\n(Context: a presentation is open at slide "
                f"{ctx.get('current_slide')}. 'this'/'here'/'go back' likely "
                f"refer to it.)")
    try:
        raw = router.generate(
            f"Message: {utterance!r}{hint}\nJSON:",
            system_prompt=_CLASSIFY_SYSTEM, task="layout",
            max_tokens=200, temperature=0.0, timeout=12.0,
        )
    except Exception as exc:
        logger.warning("assistant.llm: classify call failed: %s", exc)
        return None
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None
    name = str(data.get("intent", "")).strip().upper()
    try:
        intent = Intent(name)
    except ValueError:
        return None
    if intent not in INTENT_SPEC:
        return None
    ents = data.get("entities") or {}
    if not isinstance(ents, dict):
        ents = {}
    # coerce slide_number
    if "slide_number" in ents:
        try:
            ents["slide_number"] = int(re.sub(r"\D", "", str(ents["slide_number"])) or 0) or None
        except Exception:
            ents.pop("slide_number", None)
    conf = float(data.get("confidence", 0.6) or 0.6)
    return NLUResult(intent, min(max(conf, 0.5), 0.9),
                     {k: v for k, v in ents.items() if v not in (None, "", [])},
                     normalised=normalise(utterance), matched_rule="llm")


def answer_question(*, question: str, context: str = "", style: str = "normal",
                    target_language: str = "") -> str:
    if not _ENABLED:
        return ""
    router = _router()
    if not router:
        return ""
    parts = [f"QUESTION: {question}"]
    if context:
        parts.append("SOURCE MATERIAL:\n" + context[:6000])
    if style and style != "normal":
        parts.append(f"STYLE: {style}")
    if target_language:
        parts.append(f"TARGET LANGUAGE: {target_language}")
    try:
        out = router.generate("\n\n".join(parts), system_prompt=_ANSWER_SYSTEM,
                               task="improve", max_tokens=550, temperature=0.3,
                               timeout=20.0)
    except Exception as exc:
        logger.warning("assistant.llm: answer call failed: %s", exc)
        return ""
    return re.sub(r"\s+\n", "\n", (out or "").strip())[:2000]


def _extract_json(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


__all__ = ["classify_intent", "answer_question"]
