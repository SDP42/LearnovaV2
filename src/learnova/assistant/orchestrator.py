"""
Assistant orchestrator (spec §1, §2, §33–§38).

    utterance + session
        → NLU (deterministic; LLM fallback hook)
        → entity resolution (registry + context)
        → validation / permission
        → structured action
        → AssistantResponse

This module is transport-agnostic — the FastAPI route and the test suite both
call :func:`handle`. It never manipulates arbitrary app state: it returns a
typed action for the frontend to execute.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional

from learnova.assistant import actions as R
from learnova.assistant.intents import INTENT_SPEC, Action, Intent
from learnova.assistant.nlu import classify
from learnova.assistant.registry import PresentationEntry, build_registry
from learnova.assistant.resolver import resolve_presentation_reference
from learnova.assistant.session import SessionContext
from learnova.logging_config import logger

# Optional LLM fallback for low-confidence utterances. Wired later; signature:
#   (utterance: str, context: dict) -> NLUResult | None
classify_llm: Optional[Callable] = None

_LLM_FALLBACK_BELOW = float(os.getenv("LEARNOVA_ASSISTANT_LLM_THRESHOLD", "0.55"))


def _entries(session: SessionContext) -> List[PresentationEntry]:
    try:
        return build_registry(session.user_id)
    except Exception as exc:  # never let a storage hiccup break the assistant
        logger.warning("assistant: registry build failed: %s", exc)
        return []


def _current_entry(session, entries) -> Optional[PresentationEntry]:
    if not session.current_presentation:
        return None
    return next((e for e in entries if e.pres_id == session.current_presentation), None)


def _result_entries(session, entries) -> List[PresentationEntry]:
    ids = {r.get("pres_id") for r in (session.last_result_list or [])}
    return [e for e in entries if e.pres_id in ids] or []


def _resolve(ref: str, session, entries) -> "object":
    return resolve_presentation_reference(
        ref, entries,
        result_list=_result_entries(session, entries) or None,
        current=_current_entry(session, entries),
        previous=next((e for e in entries
                       if e.pres_id == session.previous_presentation), None),
    )


def _clarify_from(candidates: List[PresentationEntry], what: str) -> R.AssistantResponse:
    opts = [{"label": e.title, "pres_id": e.pres_id,
             "display_number": e.display_number} for e in candidates[:5]]
    names = " or ".join(f"'{e.title}'" for e in candidates[:3])
    return R.clarify(f"I found {len(candidates)} matches for {what}. Which one — {names}?",
                     opts, intent=Intent.AMBIGUOUS.value)


# ── per-action handlers ─────────────────────────────────────────────────────
def _act_open(nlu, session, entries, *, web_deck=False):
    ref = str(nlu.entities.get("presentation_reference", "")).strip()
    res = _resolve(ref, session, entries)
    if res.status == "empty":
        return R.error("You don't have any presentations yet. Say "
                       "\"create a presentation about …\" to make one.",
                       "NO_PRESENTATIONS", intent=nlu.intent.value)
    if res.status == "ambiguous":
        return _clarify_from(res.candidates, f"\"{ref}\"")
    if res.status != "resolved" or not res.entry:
        return R.error(f"I couldn't find that presentation ({res.reason}).",
                       "PRESENTATION_NOT_FOUND", intent=nlu.intent.value)
    e = res.entry
    session.open_presentation(e.pres_id, e.deck_id, slide=1)
    session.current_subject = e.subject or session.current_subject
    verb = "the web deck for" if web_deck else "presentation"
    return R.open_presentation(
        e.pres_id,
        f"Opening {verb} {e.title} (presentation {e.display_number}).",
        web_deck=web_deck, url=e.web_deck_url if web_deck else None,
        intent=nlu.intent.value, confidence=res.confidence,
    )


def _act_navigate(nlu, session, entries):
    e = _current_entry(session, entries)
    if not e:
        return R.error("Open a presentation first, then I can move between slides.",
                       "NO_ACTIVE_PRESENTATION", intent=nlu.intent.value)
    n = session.current_slide or 1
    total = max(1, e.slide_count)
    it = nlu.intent
    if it == Intent.NEXT_SLIDE:
        target = min(total, n + 1)
    elif it == Intent.PREVIOUS_SLIDE:
        target = max(1, n - 1)
    elif it == Intent.FIRST_SLIDE:
        target = 1
    elif it == Intent.LAST_SLIDE:
        target = total
    elif it == Intent.REPEAT_SLIDE:
        target = n
    elif it == Intent.GO_TO_SLIDE:
        want = nlu.entities.get("slide_number")
        if want is None:
            return R.clarify("Which slide number?", [], intent=nlu.intent.value)
        if not (1 <= int(want) <= total):
            return R.error(f"That presentation has {total} slides.",
                           "SLIDE_OUT_OF_RANGE", intent=nlu.intent.value)
        target = int(want)
    elif it == Intent.GO_TO_SECTION:
        # Best-effort: the frontend does the actual title search; we just signal.
        section = str(nlu.entities.get("section_name", "")).strip()
        session.set_slide(session.current_slide or 1)
        return R.AssistantResponse(
            R.ResponseType.NAVIGATE, f"Jumping to the {section} section.",
            presentation_id=e.pres_id, payload={"section": section},
            intent=nlu.intent.value, confidence=nlu.confidence,
        )
    else:
        target = n
    session.set_slide(target)
    return R.navigate(e.pres_id, target, f"Slide {target} of {total}.",
                      slide_id=e.slide_ref(target), intent=nlu.intent.value,
                      confidence=nlu.confidence)


def _act_search(nlu, session, entries):
    q = str(nlu.entities.get("query") or nlu.entities.get("topic")
            or nlu.entities.get("subject") or "").strip()
    if not entries:
        return R.error("You have no presentations to search yet.", "NO_PRESENTATIONS",
                       intent=nlu.intent.value)
    if not q:
        results = [e.to_dict() for e in sorted(entries, key=lambda x: x.display_number)]
        session.last_result_list = results
        return R.search_results(f"You have {len(results)} presentations.", results,
                                intent=nlu.intent.value)
    res = _resolve(q, session, entries)
    hits = ([res.entry] if res.resolved else res.candidates) or [
        e for e in entries
        if any(tok in " ".join([e.title.lower(), e.subject, " ".join(e.tags)])
               for tok in q.lower().split())
    ]
    results = [e.to_dict() for e in hits]
    session.last_result_list = results
    if not results:
        return R.text(f"I couldn't find any presentation about \"{q}\".",
                      intent=nlu.intent.value)
    return R.search_results(
        f"Found {len(results)} presentation{'s' if len(results) != 1 else ''} "
        f"about \"{q}\".", results, intent=nlu.intent.value)


def _act_voice_control(nlu, session):
    msg = {
        Intent.STOP_SPEAKING: "Stopped.",
        Intent.PAUSE: "Paused.",
        Intent.RESUME: "Resuming.",
        Intent.CANCEL: "Cancelled.",
        Intent.REPEAT_LAST: None,
    }[nlu.intent]
    if nlu.intent == Intent.REPEAT_LAST:
        last = next((t.text for t in reversed(session.history) if t.role == "assistant"), None)
        return R.AssistantResponse(R.ResponseType.VOICE_CONTROL,
                                   last or "There's nothing to repeat yet.",
                                   payload={"control": "repeat"}, intent=nlu.intent.value)
    return R.AssistantResponse(R.ResponseType.VOICE_CONTROL, msg,
                               payload={"control": nlu.intent.value},
                               intent=nlu.intent.value, confidence=nlu.confidence)


def _act_create(nlu, session):
    topic = str(nlu.entities.get("topic") or "").strip()
    src = str(nlu.entities.get("source_ref") or "").strip()
    return R.AssistantResponse(
        R.ResponseType.CREATE_PRESENTATION,
        (f"Starting a presentation about {topic}." if topic
         else "Starting a new presentation."),
        payload={"topic": topic, "source_ref": src,
                 "note": "routes to the generation pipeline; source content "
                         "is preserved, never auto-summarised"},
        intent=nlu.intent.value, confidence=nlu.confidence,
    )


def _act_explain_or_quiz(nlu, session, entries):
    it, spec = nlu.intent, INTENT_SPEC[nlu.intent]
    if spec.action == Action.START_QUIZ:
        topic = str(nlu.entities.get("topic") or session.current_topic or "").strip()
        ref = str(nlu.entities.get("presentation_reference") or "").strip()
        pid = None
        if ref:
            res = _resolve(ref, session, entries)
            if res.resolved:
                pid = res.entry.pres_id
        pid = pid or session.current_presentation
        session.active_mode = "quiz"
        session.quiz_state = {"topic": topic, "pres_id": pid, "asked": 0,
                              "count": int(nlu.entities.get("count") or 5)}
        return R.AssistantResponse(
            R.ResponseType.START_QUIZ,
            f"Quiz time{f' on {topic}' if topic else ''}. First question coming up.",
            presentation_id=pid, payload=dict(session.quiz_state),
            intent=it.value, confidence=nlu.confidence)
    if spec.action == Action.QUIZ_TURN:
        return R.AssistantResponse(R.ResponseType.QUIZ_QUESTION, "…",
                                   payload={"turn": it.value, **session.quiz_state},
                                   intent=it.value, confidence=nlu.confidence)
    # explain / answer — the actual content retrieval + generation happens in a
    # later phase; for now return a typed EXPLAIN_CONTENT the frontend/LLM fills.
    concept = str(nlu.entities.get("concept") or nlu.entities.get("term")
                  or nlu.entities.get("topic") or "").strip()
    needs_ctx = spec.requires_context and not concept
    if needs_ctx and not (session.current_presentation or session.current_topic):
        return R.clarify("Explain what exactly? Open a slide or name a topic.",
                         [], intent=it.value)
    e = _current_entry(session, entries)
    return R.AssistantResponse(
        R.ResponseType.EXPLAIN_CONTENT,
        f"Here's an explanation of {concept or 'this'}." if concept
        else "Here's what this covers.",
        presentation_id=e.pres_id if e else None,
        slide_number=session.current_slide,
        payload={"intent": it.value, "concept": concept,
                 "style": ("simple" if it == Intent.SIMPLIFY else
                           "step_by_step" if it == Intent.STEP_BY_STEP else "normal"),
                 "target_language": nlu.entities.get("target_language", ""),
                 "answer_type": spec.action.value,
                 "requires_content": spec.action == Action.ANSWER_FROM_CONTENT},
        intent=it.value, confidence=nlu.confidence)


def _act_system(nlu):
    if nlu.intent in (Intent.HELP, Intent.CAPABILITIES):
        return R.text(
            "I can open and present your decks, move between slides, explain "
            "any slide or concept, search your presentations, run quizzes, and "
            "create new decks — just ask naturally.", intent=nlu.intent.value)
    if nlu.intent == Intent.GREETING:
        return R.text("Hi — what would you like to do?", intent=nlu.intent.value)
    return R.text("Opening settings.", intent=nlu.intent.value)


# ── entry point ─────────────────────────────────────────────────────────────
def handle(utterance: str, session: SessionContext) -> R.AssistantResponse:
    session.note_user(utterance)
    nlu = classify(utterance)

    if nlu.confidence < _LLM_FALLBACK_BELOW and classify_llm is not None:
        try:
            better = classify_llm(utterance, session.to_dict())
            if better and better.confidence > nlu.confidence:
                nlu = better
        except Exception as exc:
            logger.warning("assistant: LLM classify fallback failed: %s", exc)

    entries = _entries(session)
    action = INTENT_SPEC[nlu.intent].action
    try:
        if nlu.intent == Intent.OPEN_PRESENTATION or nlu.intent == Intent.DOWNLOAD_PRESENTATION:
            resp = _act_open(nlu, session, entries)
        elif nlu.intent == Intent.GET_WEB_DECK:
            resp = _act_open(nlu, session, entries, web_deck=True)
        elif nlu.intent == Intent.START_PRESENTATION:
            resp = _act_open(nlu, session, entries)
            if resp.type == R.ResponseType.OPEN_PRESENTATION:
                resp.type = R.ResponseType.SHOW_WEB_DECK
                resp.payload["present"] = True
                resp.message = resp.message.replace("Opening", "Starting")
        elif action == Action.NAVIGATE_SLIDE:
            resp = _act_navigate(nlu, session, entries)
        elif action == Action.CONTROL_PRESENTATION:
            resp = R.AssistantResponse(
                R.ResponseType.NAVIGATE, "Done.",
                presentation_id=session.current_presentation,
                payload={"control": nlu.intent.value}, intent=nlu.intent.value,
                confidence=nlu.confidence)
        elif action == Action.SHOW_SEARCH_RESULTS:
            resp = _act_search(nlu, session, entries)
        elif action == Action.CREATE_PRESENTATION:
            resp = _act_create(nlu, session)
        elif action == Action.VOICE_CONTROL:
            resp = _act_voice_control(nlu, session)
        elif action == Action.CREATE_VISUAL:
            resp = R.AssistantResponse(
                R.ResponseType.PLAY_ANIMATION, "Working on that visual.",
                presentation_id=session.current_presentation,
                slide_number=session.current_slide,
                payload={"request": nlu.intent.value,
                         "note": "routes to the visual pipeline"},
                intent=nlu.intent.value, confidence=nlu.confidence)
        elif action == Action.SYSTEM_INFO:
            resp = _act_system(nlu)
        elif action in (Action.EXPLAIN_CONTENT, Action.ANSWER_FROM_CONTENT,
                        Action.ANSWER_GENERAL, Action.START_QUIZ, Action.QUIZ_TURN):
            resp = _act_explain_or_quiz(nlu, session, entries)
        elif action == Action.ASK_CLARIFICATION:
            resp = R.clarify("I'm not sure what you mean — could you rephrase?",
                             [], intent=nlu.intent.value)
        else:
            resp = R.text("I'm not sure how to help with that yet.",
                          intent=nlu.intent.value, confidence=nlu.confidence)
    except Exception as exc:
        logger.error("assistant: handler crashed for %r: %s", utterance, exc, exc_info=True)
        resp = R.error("Something went wrong handling that. Try rephrasing.",
                       "HANDLER_ERROR")

    resp.confidence = resp.confidence or nlu.confidence
    session.note_assistant(resp.message, resp.intent)
    return resp


__all__ = ["handle", "classify_llm"]
