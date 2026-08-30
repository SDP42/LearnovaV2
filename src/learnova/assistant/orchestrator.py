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
from learnova.assistant import tools as T
from learnova.assistant.intents import INTENT_SPEC, Action, Intent
from learnova.assistant.nlu import classify
from learnova.assistant.registry import PresentationEntry, build_registry
from learnova.assistant.resolver import resolve_presentation_reference
from learnova.assistant.session import SessionContext
from learnova.logging_config import logger


def _default_llm_classify(utterance: str, context: dict):
    try:
        from learnova.assistant.llm import classify_intent
        return classify_intent(utterance, context)
    except Exception as exc:  # pragma: no cover
        logger.warning("assistant: llm import failed: %s", exc)
        return None


# LLM fallback for low-confidence utterances. Overridable for tests.
#   (utterance: str, context: dict) -> NLUResult | None
classify_llm: Optional[Callable] = _default_llm_classify

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
    tool = T.open_presentation if not web_deck else T.get_web_deck
    res = tool(session.user_id, ref, **_ctx_kwargs(session))
    if not res.ok:
        if res.code == "AMBIGUOUS":
            cands = res.data.get("candidates", [])
            opts = [{"label": c["title"], "pres_id": c["pres_id"],
                     "display_number": c["display_number"]} for c in cands[:5]]
            names = " or ".join(f"'{c['title']}'" for c in cands[:3])
            return R.clarify(f"I found {len(cands)} matches for \"{ref}\". "
                             f"Which one — {names}?", opts, intent=Intent.AMBIGUOUS.value)
        return R.error(res.message or f"I couldn't find that presentation.",
                       res.code or "PRESENTATION_NOT_FOUND", intent=nlu.intent.value)
    e: PresentationEntry = res.data["entry"]
    session.open_presentation(e.pres_id, e.deck_id, slide=1)
    session.current_subject = e.subject or session.current_subject
    session.current_topic = e.topic or session.current_topic
    verb = "the web deck for" if web_deck else "presentation"
    return R.open_presentation(
        e.pres_id,
        f"Opening {verb} {e.title} (presentation {e.display_number}).",
        web_deck=web_deck, url=res.data.get("web_deck_url"), deck_id=e.deck_id,
        intent=nlu.intent.value, confidence=res.data.get("confidence", nlu.confidence),
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
                      slide_id=e.slide_ref(target), deck_id=e.deck_id,
                      intent=nlu.intent.value, confidence=nlu.confidence)


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


def _act_gallery(nlu, session):
    """Is there a ready-made deck on this topic? Answer yes/no and, when yes,
    hand back the matches so the frontend can open the Gallery."""
    topic = str(nlu.entities.get("topic") or nlu.entities.get("concept")
                or nlu.entities.get("query") or "").strip()
    if not topic:
        return R.clarify("Which topic should I check the Gallery for?", [],
                         intent=nlu.intent.value)

    res = T.search_gallery(topic)
    if not res.ok:
        return R.error(res.message, res.code, intent=nlu.intent.value)

    rows = res.data.get("results", [])
    ready = [r for r in rows if r["has_deck"]]
    session.last_result_list = [{"pres_id": f"gallery:{r['slug']}", **r} for r in rows]

    if ready:
        top = ready[0]
        others = [r["title"] for r in ready[1:3]]
        msg = (f"Yes — there's a ready-made deck on \"{top['title']}\" "
               f"({top['slide_count']} slides) in the Gallery. "
               f"Opening it for you now.")
        if others:
            msg += f" (Also ready: {', '.join(others)}.)"
        return R.gallery_results(msg, ready + [r for r in rows if not r["has_deck"]][:2],
                                 intent=nlu.intent.value,
                                 speech=f"Yes, a ready-made deck on {top['title']} is available. Opening it.")
    if rows:
        names = ", ".join(r["title"] for r in rows[:3])
        return R.gallery_results(
            f"Not pre-built yet, but the Gallery has the topic{'s' if len(rows) > 1 else ''} "
            f"{names}. I can generate a deck from it in about a minute.",
            rows, intent=nlu.intent.value)
    return R.text(
        f"There's no ready-made deck on \"{topic}\" in the Gallery yet. "
        f"I can create one for you — just say \"create a presentation on {topic}\".",
        intent=nlu.intent.value)


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


def _ctx_kwargs(session):
    return {
        "result_ids": {r.get("pres_id") for r in (session.last_result_list or [])},
        "current": session.current_presentation,
        "previous": session.previous_presentation,
    }


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
    # explain / answer — retrieve the relevant deck/slide text and answer via
    # the LLM. The reply may be simplified / translated; the deck is untouched.
    concept = str(nlu.entities.get("concept") or nlu.entities.get("term")
                  or nlu.entities.get("topic") or "").strip()
    needs_ctx = spec.requires_context and not concept
    if needs_ctx and not (session.current_presentation or session.current_topic):
        return R.clarify("Explain what exactly? Open a slide or name a topic.",
                         [], intent=it.value)
    e = _current_entry(session, entries)
    style = ("simple" if it == Intent.SIMPLIFY else
             "step_by_step" if it == Intent.STEP_BY_STEP else "normal")
    q = concept
    if it in (Intent.EXPLAIN_SLIDE, Intent.EXPLAIN_VISUAL, Intent.READ_SLIDE):
        q = concept or "Explain this slide."
    elif it == Intent.WHY_QUESTION:
        q = f"Why: {concept}" if concept else session.last_user_request
    elif it == Intent.WHAT_NEXT:
        q = "What comes next, based on this slide?"
    elif it in (Intent.GIVE_EXAMPLE, Intent.REAL_WORLD_EXAMPLE):
        q = f"Give a{'real-world ' if it == Intent.REAL_WORLD_EXAMPLE else ' '}" \
            f"example of {concept or session.current_topic or 'this'}."
    elif it in (Intent.EASIER_EXAMPLE, Intent.HARDER_EXAMPLE):
        q = f"Give a {'simpler' if it == Intent.EASIER_EXAMPLE else 'harder'} " \
            f"example of {session.current_topic or 'this'}."
    elif it == Intent.TRANSLATE:
        q = session.last_user_request

    res = T.explain_content(
        session.user_id, deck_id=(e.deck_id if e else None),
        slide_number=session.current_slide, concept=q or "Explain this.",
        style=style, target_language=str(nlu.entities.get("target_language", "")),
        from_content=(spec.action == Action.ANSWER_FROM_CONTENT or bool(e)),
    )
    if not res.ok:
        return R.error(res.message, res.code, intent=it.value)
    return R.AssistantResponse(
        R.ResponseType.EXPLAIN_CONTENT, res.message,
        presentation_id=e.pres_id if e else None,
        slide_number=session.current_slide,
        payload={"intent": it.value, "concept": concept, "style": style,
                 "grounded": res.data.get("grounded", False),
                 "source": res.data.get("source", "general")},
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
        elif nlu.intent == Intent.CHECK_GALLERY:
            resp = _act_gallery(nlu, session)
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
