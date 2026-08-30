"""
Conversation / session context (spec §10).

In-memory, per session id. Holds just enough state for pronoun and ordinal
resolution ("explain this", "the second one", "go back"). Swap the backing
store for Redis if the assistant ever runs multi-worker — the interface is
deliberately tiny.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Turn:
    role: str            # "user" | "assistant"
    text: str
    intent: Optional[str] = None
    at: float = field(default_factory=time.time)


@dataclass
class SessionContext:
    session_id: str
    user_id: str
    current_presentation: Optional[str] = None   # pres_id
    current_deck_id: Optional[str] = None
    current_slide: Optional[int] = None
    previous_slide: Optional[int] = None
    previous_presentation: Optional[str] = None
    current_subject: str = ""
    current_topic: str = ""
    last_user_request: str = ""
    last_referenced_entity: str = ""
    last_result_list: List[Dict[str, Any]] = field(default_factory=list)  # pres dicts
    active_mode: str = "chat"          # chat | presenting | quiz
    quiz_state: Dict[str, Any] = field(default_factory=dict)
    history: List[Turn] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def note_user(self, text: str, intent: Optional[str] = None) -> None:
        self.last_user_request = text
        self.history.append(Turn("user", text, intent))
        self._trim()

    def note_assistant(self, text: str, intent: Optional[str] = None) -> None:
        self.history.append(Turn("assistant", text, intent))
        self.updated_at = time.time()
        self._trim()

    def open_presentation(self, pres_id: str, deck_id: str, slide: int = 1) -> None:
        if self.current_presentation and self.current_presentation != pres_id:
            self.previous_presentation = self.current_presentation
        self.current_presentation = pres_id
        self.current_deck_id = deck_id
        self.previous_slide = self.current_slide
        self.current_slide = slide
        self.active_mode = "presenting"

    def set_slide(self, n: int) -> None:
        self.previous_slide = self.current_slide
        self.current_slide = n

    def _trim(self) -> None:
        if len(self.history) > 40:
            self.history = self.history[-40:]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "current_presentation": self.current_presentation,
            "current_slide": self.current_slide,
            "previous_slide": self.previous_slide,
            "active_mode": self.active_mode,
            "current_subject": self.current_subject,
            "current_topic": self.current_topic,
            "turns": len(self.history),
        }


class SessionStore:
    _TTL = 12 * 3600

    def __init__(self) -> None:
        self._s: Dict[str, SessionContext] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str, user_id: str) -> SessionContext:
        with self._lock:
            self._prune()
            s = self._s.get(session_id)
            if s is None or s.user_id != user_id:
                s = SessionContext(session_id=session_id, user_id=user_id)
                self._s[session_id] = s
            return s

    def _prune(self) -> None:
        now = time.time()
        for k in [k for k, v in self._s.items() if now - v.updated_at > self._TTL]:
            self._s.pop(k, None)


_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


__all__ = ["Turn", "SessionContext", "SessionStore", "get_session_store"]
