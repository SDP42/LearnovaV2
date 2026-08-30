"""
Server-side tool bus (spec §5, §34, §35).

Every side-effecting or data-reading capability the assistant has is a
function here. The orchestrator (and, later, an LLM planner) chooses a tool
by name and passes structured args; the tool **validates existence,
range and ownership** against the real deck library before returning. An
LLM-supplied id is never trusted — it is resolved and checked here.

Each tool returns a :class:`ToolResult` (ok / error + data). Tools never
raise for expected failures (missing deck, slide out of range); they return
``ok=False`` with a ``code`` the orchestrator turns into a friendly message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from learnova.assistant import registry as _reg
from learnova.assistant.registry import PresentationEntry
from learnova.assistant.resolver import resolve_presentation_reference
from learnova.logging_config import logger


@dataclass
class ToolResult:
    ok: bool
    code: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def fail(cls, code: str, message: str) -> "ToolResult":
        return cls(False, code, message)

    @classmethod
    def done(cls, message: str = "", **data) -> "ToolResult":
        return cls(True, "", message, data)


# ── helpers ────────────────────────────────────────────────────────────────
def _registry(user_id: str) -> List[PresentationEntry]:
    try:
        return _reg.build_registry(user_id)
    except Exception as exc:
        logger.warning("assistant.tools: registry failed: %s", exc)
        return []


def _resolve(user_id: str, ref: str, *, result_ids=None, current=None,
             previous=None) -> ToolResult:
    entries = _registry(user_id)
    if not entries:
        return ToolResult.fail("NO_PRESENTATIONS", "You have no presentations yet.")
    rlist = [e for e in entries if e.pres_id in (result_ids or set())] or None
    cur = next((e for e in entries if e.pres_id == current), None)
    prev = next((e for e in entries if e.pres_id == previous), None)
    res = resolve_presentation_reference(ref, entries, result_list=rlist,
                                        current=cur, previous=prev)
    if res.status == "resolved":
        return ToolResult.done(entry=res.entry, confidence=res.confidence)
    if res.status == "ambiguous":
        return ToolResult(False, "AMBIGUOUS", res.reason,
                          {"candidates": [e.to_dict() for e in res.candidates]})
    return ToolResult.fail("PRESENTATION_NOT_FOUND", res.reason)


# ── tools ──────────────────────────────────────────────────────────────────
def search_presentations(user_id: str, query: str = "") -> ToolResult:
    entries = _registry(user_id)
    if not entries:
        return ToolResult.fail("NO_PRESENTATIONS", "You have no presentations yet.")
    q = (query or "").strip().lower()
    if not q:
        hits = sorted(entries, key=lambda e: e.display_number)
    else:
        toks = [t for t in q.split() if len(t) > 1]
        def match(e):
            hay = " ".join([e.title.lower(), e.subject, e.topic, " ".join(e.tags),
                            " ".join(e.aliases)])
            return sum(t in hay for t in toks)
        scored = sorted(((match(e), e) for e in entries), key=lambda x: -x[0])
        hits = [e for s, e in scored if s > 0] or []
    return ToolResult.done(f"{len(hits)} result(s).",
                           results=[e.to_dict() for e in hits])


def get_presentation(user_id: str, reference: str, **ctx) -> ToolResult:
    r = _resolve(user_id, reference, **ctx)
    if not r.ok:
        return r
    return ToolResult.done(presentation=r.data["entry"].to_dict(),
                           entry=r.data["entry"], confidence=r.data["confidence"])


def open_presentation(user_id: str, reference: str, *, web_deck=False, **ctx) -> ToolResult:
    r = _resolve(user_id, reference, **ctx)
    if not r.ok:
        return r
    e: PresentationEntry = r.data["entry"]
    return ToolResult.done(
        f"Opening {e.title} (presentation {e.display_number}).",
        presentation_id=e.pres_id, deck_id=e.deck_id, slide_count=e.slide_count,
        web_deck_url=e.web_deck_url if (web_deck or e.has_web_deck) else None,
        entry=e, confidence=r.data["confidence"])


def get_web_deck(user_id: str, reference: str, **ctx) -> ToolResult:
    return open_presentation(user_id, reference, web_deck=True, **ctx)


def go_to_slide(user_id: str, presentation_id: str, slide_number: int) -> ToolResult:
    e = next((x for x in _registry(user_id) if x.pres_id == presentation_id), None)
    if not e:
        return ToolResult.fail("NO_ACTIVE_PRESENTATION",
                               "Open a presentation first.")
    total = max(1, e.slide_count)
    n = int(slide_number)
    if not (1 <= n <= total):
        return ToolResult.fail("SLIDE_OUT_OF_RANGE",
                               f"That presentation has {total} slides.")
    return ToolResult.done(f"Slide {n} of {total}.",
                           presentation_id=e.pres_id, slide_number=n,
                           slide_id=e.slide_ref(n), slide_count=total)


def get_slide_content(user_id: str, deck_id: str,
                      slide_number: Optional[int] = None) -> ToolResult:
    """Read slide text from the saved deck — for EXPLAIN_CONTENT retrieval."""
    from learnova.storage import deck_library

    stored = deck_library.read_slides(user_id, deck_id) or {}
    slides = stored.get("slides") or []
    if not slides:
        md = deck_library.read_markdown(user_id, deck_id) or ""
        return ToolResult.done(source="markdown", text=md[:8000], slides=[])
    if slide_number is not None:
        i = int(slide_number) - 1
        if not (0 <= i < len(slides)):
            return ToolResult.fail("SLIDE_OUT_OF_RANGE",
                                   f"That deck has {len(slides)} slides.")
        s = slides[i]
        return ToolResult.done(
            source="slide", slide_number=slide_number,
            title=s.get("title", ""),
            text=_slide_text(s), speaker_notes=s.get("speaker_notes", ""),
            layout=s.get("layout_type"))
    # whole deck
    return ToolResult.done(
        source="deck",
        text="\n\n".join(f"## {s.get('title','')}\n{_slide_text(s)}" for s in slides)[:12000],
        slide_count=len(slides))


def _slide_text(s: dict) -> str:
    parts = [str(b) for b in (s.get("bullets") or [])]
    if s.get("takeaway"):
        parts.append(f"Key takeaway: {s['takeaway']}")
    if s.get("table_rows"):
        for row in s["table_rows"]:
            parts.append(" | ".join(str(c) for c in row))
    if not parts and s.get("source_text"):
        parts.append(str(s["source_text"]))
    return "\n".join(parts)


def search_content(user_id: str, query: str) -> ToolResult:
    """Where is a topic taught? Scans each deck's markdown for the query."""
    from learnova.storage import deck_library

    q = (query or "").strip().lower()
    if not q:
        return ToolResult.fail("EMPTY_QUERY", "Search for what?")
    toks = [t for t in q.split() if len(t) > 2]
    hits = []
    for e in _registry(user_id):
        md = (deck_library.read_markdown(user_id, e.deck_id) or "").lower()
        score = sum(md.count(t) for t in toks)
        if score:
            # first matching line as a snippet
            snippet = next((ln.strip() for ln in md.splitlines()
                            if any(t in ln for t in toks)), "")
            hits.append({**e.to_dict(), "match_score": score, "snippet": snippet[:160]})
    hits.sort(key=lambda h: -h["match_score"])
    return ToolResult.done(f"{len(hits)} presentation(s) mention that.", results=hits)


def explain_content(user_id: str, *, deck_id: Optional[str] = None,
                    slide_number: Optional[int] = None, concept: str = "",
                    style: str = "normal", target_language: str = "",
                    from_content: bool = True) -> ToolResult:
    """Answer an educational question. Retrieves deck/slide text when a deck is
    active, then asks the LLM. The reply may be simplified / translated; the
    stored deck is NEVER modified (docs/MASTER_PROMPT.md)."""
    context_text = ""
    source = "general"
    if deck_id and from_content:
        got = get_slide_content(user_id, deck_id, slide_number)
        if got.ok:
            context_text = got.data.get("text", "")
            source = got.data.get("source", "deck")

    try:
        from learnova.assistant.llm import answer_question

        answer = answer_question(question=concept or "Explain this.",
                                 context=context_text, style=style,
                                 target_language=target_language)
    except Exception as exc:
        logger.warning("assistant.tools: LLM answer failed: %s", exc)
        answer = ""

    if not answer:
        if context_text:
            answer = ("Here's what the material says:\n\n"
                      + context_text[:1200])
        else:
            return ToolResult.fail(
                "NO_CONTENT",
                f"I couldn't find \"{concept}\" in your Learnova content. "
                f"I can explain it generally, or you can add the relevant deck.")
    return ToolResult.done(answer, answer=answer, source=source,
                           grounded=bool(context_text))


TOOLS = {
    "searchPresentations": search_presentations,
    "getPresentation": get_presentation,
    "openPresentation": open_presentation,
    "getWebDeck": get_web_deck,
    "goToSlide": go_to_slide,
    "getSlideContent": get_slide_content,
    "searchContent": search_content,
    "explainContent": explain_content,
}


__all__ = ["ToolResult", "TOOLS", *TOOLS.keys()]
