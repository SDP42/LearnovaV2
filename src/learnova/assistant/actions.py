"""
Structured assistant-response protocol (spec §32).

Every assistant turn returns an :class:`AssistantResponse`. The frontend
switches on ``type`` to decide what to do (open a deck, navigate, speak,
show a clarification prompt, …). ``message`` is always the short spoken /
displayed line; ``speech`` overrides it for TTS when a terser phrasing reads
better aloud.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ResponseType:
    TEXT_RESPONSE = "TEXT_RESPONSE"
    OPEN_PRESENTATION = "OPEN_PRESENTATION"
    OPEN_SLIDE = "OPEN_SLIDE"
    NAVIGATE = "NAVIGATE"
    SHOW_WEB_DECK = "SHOW_WEB_DECK"
    PLAY_ANIMATION = "PLAY_ANIMATION"
    SHOW_VISUAL = "SHOW_VISUAL"
    START_QUIZ = "START_QUIZ"
    QUIZ_QUESTION = "QUIZ_QUESTION"
    SHOW_SEARCH_RESULTS = "SHOW_SEARCH_RESULTS"
    CREATE_PRESENTATION = "CREATE_PRESENTATION"
    SEARCH_CONTENT = "SEARCH_CONTENT"
    EXPLAIN_CONTENT = "EXPLAIN_CONTENT"
    EXPLAIN_AND_NAVIGATE = "EXPLAIN_AND_NAVIGATE"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    VOICE_CONTROL = "VOICE_CONTROL"
    ERROR_RESPONSE = "ERROR_RESPONSE"


@dataclass
class AssistantResponse:
    type: str
    message: str = ""
    speech: Optional[str] = None
    presentation_id: Optional[str] = None
    slide_id: Optional[str] = None
    slide_number: Optional[int] = None
    web_deck_url: Optional[str] = None
    results: List[Dict[str, Any]] = field(default_factory=list)
    options: List[Dict[str, Any]] = field(default_factory=list)  # clarification choices
    payload: Dict[str, Any] = field(default_factory=dict)
    intent: Optional[str] = None
    confidence: float = 0.0
    error_code: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"type": self.type, "message": self.message}
        if self.speech and self.speech != self.message:
            d["speech"] = self.speech
        for k in ("presentation_id", "slide_id", "slide_number", "web_deck_url",
                  "intent", "error_code"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        if self.results:
            d["results"] = self.results
        if self.options:
            d["options"] = self.options
        if self.payload:
            d["payload"] = self.payload
        d["confidence"] = round(self.confidence, 3)
        return d


# ── constructors ────────────────────────────────────────────────────────────
def text(message: str, *, intent=None, confidence=1.0, speech=None) -> AssistantResponse:
    return AssistantResponse(ResponseType.TEXT_RESPONSE, message, speech=speech,
                             intent=intent, confidence=confidence)


def error(message: str, code: str = "GENERIC", *, intent=None) -> AssistantResponse:
    return AssistantResponse(ResponseType.ERROR_RESPONSE, message,
                             error_code=code, intent=intent, confidence=1.0)


def clarify(message: str, options: List[Dict[str, Any]], *, intent=None,
            confidence=0.4) -> AssistantResponse:
    return AssistantResponse(ResponseType.ASK_CLARIFICATION, message,
                             options=options, intent=intent, confidence=confidence)


def open_presentation(pid: str, message: str, *, web_deck=False, intent=None,
                      confidence=1.0, url: Optional[str] = None) -> AssistantResponse:
    return AssistantResponse(
        ResponseType.SHOW_WEB_DECK if web_deck else ResponseType.OPEN_PRESENTATION,
        message, presentation_id=pid, web_deck_url=url, intent=intent,
        confidence=confidence,
    )


def navigate(pid: Optional[str], slide_number: Optional[int], message: str, *,
             slide_id=None, intent=None, confidence=1.0) -> AssistantResponse:
    return AssistantResponse(ResponseType.NAVIGATE, message, presentation_id=pid,
                             slide_number=slide_number, slide_id=slide_id,
                             intent=intent, confidence=confidence)


def search_results(message: str, results: List[Dict[str, Any]], *, intent=None,
                   confidence=1.0) -> AssistantResponse:
    return AssistantResponse(ResponseType.SHOW_SEARCH_RESULTS, message,
                             results=results, intent=intent, confidence=confidence)


__all__ = ["ResponseType", "AssistantResponse", "text", "error", "clarify",
           "open_presentation", "navigate", "search_results"]
