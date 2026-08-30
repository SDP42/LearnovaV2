"""
Intent taxonomy for the Learnova assistant (spec §7).

Each intent is a member of :class:`Intent`. :data:`INTENT_SPEC` describes,
per intent, the category, the entities it expects, the structured action it
produces, and whether it needs conversation context or an active
presentation. The JSON mirror lives at ``data/assistant/intents.json`` and is
generated from here by ``dump_intents_json()``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import List


class Intent(str, enum.Enum):
    # ── Presentation ────────────────────────────────────────────────────────
    CREATE_PRESENTATION = "CREATE_PRESENTATION"
    OPEN_PRESENTATION = "OPEN_PRESENTATION"
    GET_WEB_DECK = "GET_WEB_DECK"
    START_PRESENTATION = "START_PRESENTATION"
    STOP_PRESENTATION = "STOP_PRESENTATION"
    RESUME_PRESENTATION = "RESUME_PRESENTATION"
    RESTART_PRESENTATION = "RESTART_PRESENTATION"
    SEARCH_PRESENTATION = "SEARCH_PRESENTATION"
    SUMMARIZE_PRESENTATION = "SUMMARIZE_PRESENTATION"   # only on explicit ask
    EXPLAIN_PRESENTATION = "EXPLAIN_PRESENTATION"
    DOWNLOAD_PRESENTATION = "DOWNLOAD_PRESENTATION"
    DELETE_PRESENTATION = "DELETE_PRESENTATION"
    # ── Slide navigation ───────────────────────────────────────────────────
    NEXT_SLIDE = "NEXT_SLIDE"
    PREVIOUS_SLIDE = "PREVIOUS_SLIDE"
    GO_TO_SLIDE = "GO_TO_SLIDE"
    FIRST_SLIDE = "FIRST_SLIDE"
    LAST_SLIDE = "LAST_SLIDE"
    GO_TO_SECTION = "GO_TO_SECTION"
    REPEAT_SLIDE = "REPEAT_SLIDE"
    READ_SLIDE = "READ_SLIDE"
    EXPLAIN_SLIDE = "EXPLAIN_SLIDE"
    EXPLAIN_VISUAL = "EXPLAIN_VISUAL"
    # ── Educational Q&A ────────────────────────────────────────────────────
    EXPLAIN_CONCEPT = "EXPLAIN_CONCEPT"
    COMPARE_CONCEPTS = "COMPARE_CONCEPTS"
    GIVE_EXAMPLE = "GIVE_EXAMPLE"
    REAL_WORLD_EXAMPLE = "REAL_WORLD_EXAMPLE"
    SIMPLIFY = "SIMPLIFY"
    STEP_BY_STEP = "STEP_BY_STEP"
    WHY_QUESTION = "WHY_QUESTION"
    WHAT_NEXT = "WHAT_NEXT"
    DEFINE_TERM = "DEFINE_TERM"
    # ── Learning assistance ────────────────────────────────────────────────
    TEACH_TOPIC = "TEACH_TOPIC"
    START_QUIZ = "START_QUIZ"
    NEXT_QUIZ_QUESTION = "NEXT_QUIZ_QUESTION"
    SUBMIT_QUIZ_ANSWER = "SUBMIT_QUIZ_ANSWER"
    EXPLAIN_MISTAKE = "EXPLAIN_MISTAKE"
    EASIER_EXAMPLE = "EASIER_EXAMPLE"
    HARDER_EXAMPLE = "HARDER_EXAMPLE"
    EXAM_PREP = "EXAM_PREP"
    # ── Content search ─────────────────────────────────────────────────────
    SEARCH_CONTENT = "SEARCH_CONTENT"
    WHERE_IS_TOPIC = "WHERE_IS_TOPIC"
    FIND_PRESENTATIONS_ABOUT = "FIND_PRESENTATIONS_ABOUT"
    # ── Visualisation ──────────────────────────────────────────────────────
    MAKE_VISUAL = "MAKE_VISUAL"
    ADD_ANIMATION = "ADD_ANIMATION"
    MAKE_INTERACTIVE = "MAKE_INTERACTIVE"
    # ── Voice control ──────────────────────────────────────────────────────
    STOP_SPEAKING = "STOP_SPEAKING"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    REPEAT_LAST = "REPEAT_LAST"
    CANCEL = "CANCEL"
    # ── System / meta ──────────────────────────────────────────────────────
    HELP = "HELP"
    CAPABILITIES = "CAPABILITIES"
    SETTINGS = "SETTINGS"
    TRANSLATE = "TRANSLATE"
    GREETING = "GREETING"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class Category(str, enum.Enum):
    PRESENTATION_NAV = "presentation_navigation"
    PRESENTATION_SEARCH = "presentation_search"
    PRESENTATION_CREATE = "presentation_creation"
    WEB_DECK = "web_deck"
    SLIDE_NAV = "slide_navigation"
    EDUCATIONAL = "educational_question"
    EXPLANATION = "explanation_request"
    VISUAL_QUESTION = "visual_diagram_question"
    VOICE = "voice_command"
    LEARNING = "learning_assistance"
    CONTENT_SEARCH = "content_search"
    COMPARISON = "comparison_question"
    EXAMPLE = "examples_analogies"
    QUIZ = "quizzes_practice"
    PERSONALISED = "personalised_learning"
    SYSTEM = "system_platform"
    ERROR = "error_failure"
    AMBIGUOUS = "ambiguous_request"


class Action(str, enum.Enum):
    ANSWER_FROM_CONTENT = "ANSWER_FROM_CONTENT"
    ANSWER_GENERAL = "ANSWER_GENERAL"
    OPEN_PRESENTATION = "OPEN_PRESENTATION"
    OPEN_WEB_DECK = "OPEN_WEB_DECK"
    START_PRESENTATION = "START_PRESENTATION"
    CONTROL_PRESENTATION = "CONTROL_PRESENTATION"
    NAVIGATE_SLIDE = "NAVIGATE_SLIDE"
    SHOW_SEARCH_RESULTS = "SHOW_SEARCH_RESULTS"
    CREATE_PRESENTATION = "CREATE_PRESENTATION"
    START_QUIZ = "START_QUIZ"
    QUIZ_TURN = "QUIZ_TURN"
    EXPLAIN_CONTENT = "EXPLAIN_CONTENT"
    CREATE_VISUAL = "CREATE_VISUAL"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    VOICE_CONTROL = "VOICE_CONTROL"
    SYSTEM_INFO = "SYSTEM_INFO"
    ERROR = "ERROR"
    NONE = "NONE"


@dataclass(frozen=True)
class IntentSpec:
    intent: Intent
    category: Category
    action: Action
    entities: List[str] = field(default_factory=list)
    requires_context: bool = False
    requires_presentation: bool = False
    summary_only_on_request: bool = False
    description: str = ""


def _s(*a, **k) -> IntentSpec:
    return IntentSpec(*a, **k)

I = Intent
C = Category
A = Action

INTENT_SPEC: dict[Intent, IntentSpec] = {s.intent: s for s in [
    _s(I.CREATE_PRESENTATION, C.PRESENTATION_CREATE, A.CREATE_PRESENTATION,
       ["topic", "subject", "source_ref", "format"],
       description="Generate a new Learnova deck. Routes to the pipeline; "
                   "content preservation applies (never auto-summarise)."),
    _s(I.OPEN_PRESENTATION, C.PRESENTATION_NAV, A.OPEN_PRESENTATION,
       ["presentation_reference"]),
    _s(I.GET_WEB_DECK, C.WEB_DECK, A.OPEN_WEB_DECK, ["presentation_reference"]),
    _s(I.START_PRESENTATION, C.PRESENTATION_NAV, A.START_PRESENTATION,
       ["presentation_reference"]),
    _s(I.STOP_PRESENTATION, C.PRESENTATION_NAV, A.CONTROL_PRESENTATION,
       requires_presentation=True),
    _s(I.RESUME_PRESENTATION, C.PRESENTATION_NAV, A.CONTROL_PRESENTATION,
       requires_context=True),
    _s(I.RESTART_PRESENTATION, C.PRESENTATION_NAV, A.CONTROL_PRESENTATION,
       requires_presentation=True),
    _s(I.SEARCH_PRESENTATION, C.PRESENTATION_SEARCH, A.SHOW_SEARCH_RESULTS,
       ["query", "subject", "topic"]),
    _s(I.SUMMARIZE_PRESENTATION, C.EXPLANATION, A.EXPLAIN_CONTENT,
       ["presentation_reference"], requires_presentation=True,
       summary_only_on_request=True,
       description="Summarise only because the USER asked; source deck "
                   "content is untouched."),
    _s(I.EXPLAIN_PRESENTATION, C.EXPLANATION, A.EXPLAIN_CONTENT,
       ["presentation_reference"], requires_presentation=True),
    _s(I.DOWNLOAD_PRESENTATION, C.PRESENTATION_NAV, A.OPEN_PRESENTATION,
       ["presentation_reference", "format"]),
    _s(I.DELETE_PRESENTATION, C.PRESENTATION_NAV, A.CONTROL_PRESENTATION,
       ["presentation_reference"],
       description="Destructive — always confirm before executing."),

    _s(I.NEXT_SLIDE, C.SLIDE_NAV, A.NAVIGATE_SLIDE, requires_presentation=True),
    _s(I.PREVIOUS_SLIDE, C.SLIDE_NAV, A.NAVIGATE_SLIDE, requires_presentation=True),
    _s(I.GO_TO_SLIDE, C.SLIDE_NAV, A.NAVIGATE_SLIDE, ["slide_number"],
       requires_presentation=True),
    _s(I.FIRST_SLIDE, C.SLIDE_NAV, A.NAVIGATE_SLIDE, requires_presentation=True),
    _s(I.LAST_SLIDE, C.SLIDE_NAV, A.NAVIGATE_SLIDE, requires_presentation=True),
    _s(I.GO_TO_SECTION, C.SLIDE_NAV, A.NAVIGATE_SLIDE, ["section_name", "topic"],
       requires_presentation=True),
    _s(I.REPEAT_SLIDE, C.SLIDE_NAV, A.NAVIGATE_SLIDE, requires_context=True),
    _s(I.READ_SLIDE, C.SLIDE_NAV, A.EXPLAIN_CONTENT, requires_presentation=True),
    _s(I.EXPLAIN_SLIDE, C.EXPLANATION, A.EXPLAIN_CONTENT, requires_presentation=True),
    _s(I.EXPLAIN_VISUAL, C.VISUAL_QUESTION, A.EXPLAIN_CONTENT,
       ["visual_reference"], requires_presentation=True),

    _s(I.EXPLAIN_CONCEPT, C.EDUCATIONAL, A.ANSWER_FROM_CONTENT, ["concept"]),
    _s(I.COMPARE_CONCEPTS, C.COMPARISON, A.ANSWER_FROM_CONTENT, ["concept", "concept_b"]),
    _s(I.GIVE_EXAMPLE, C.EXAMPLE, A.ANSWER_FROM_CONTENT, ["concept"], requires_context=True),
    _s(I.REAL_WORLD_EXAMPLE, C.EXAMPLE, A.ANSWER_FROM_CONTENT, ["concept"], requires_context=True),
    _s(I.SIMPLIFY, C.EXPLANATION, A.ANSWER_FROM_CONTENT, ["concept"], requires_context=True,
       description="Simplify the REPLY, not the stored content."),
    _s(I.STEP_BY_STEP, C.EXPLANATION, A.ANSWER_FROM_CONTENT, ["concept"], requires_context=True),
    _s(I.WHY_QUESTION, C.EDUCATIONAL, A.ANSWER_FROM_CONTENT, ["concept"], requires_context=True),
    _s(I.WHAT_NEXT, C.EDUCATIONAL, A.ANSWER_FROM_CONTENT, requires_context=True),
    _s(I.DEFINE_TERM, C.EDUCATIONAL, A.ANSWER_FROM_CONTENT, ["term"]),

    _s(I.TEACH_TOPIC, C.LEARNING, A.EXPLAIN_CONTENT, ["topic"]),
    _s(I.START_QUIZ, C.QUIZ, A.START_QUIZ, ["topic", "presentation_reference", "count"]),
    _s(I.NEXT_QUIZ_QUESTION, C.QUIZ, A.QUIZ_TURN, requires_context=True),
    _s(I.SUBMIT_QUIZ_ANSWER, C.QUIZ, A.QUIZ_TURN, ["answer"], requires_context=True),
    _s(I.EXPLAIN_MISTAKE, C.QUIZ, A.QUIZ_TURN, requires_context=True),
    _s(I.EASIER_EXAMPLE, C.PERSONALISED, A.ANSWER_FROM_CONTENT, requires_context=True),
    _s(I.HARDER_EXAMPLE, C.PERSONALISED, A.ANSWER_FROM_CONTENT, requires_context=True),
    _s(I.EXAM_PREP, C.PERSONALISED, A.EXPLAIN_CONTENT, ["topic", "subject"]),

    _s(I.SEARCH_CONTENT, C.CONTENT_SEARCH, A.SHOW_SEARCH_RESULTS, ["query"]),
    _s(I.WHERE_IS_TOPIC, C.CONTENT_SEARCH, A.SHOW_SEARCH_RESULTS, ["topic"]),
    _s(I.FIND_PRESENTATIONS_ABOUT, C.CONTENT_SEARCH, A.SHOW_SEARCH_RESULTS, ["subject", "topic"]),

    _s(I.MAKE_VISUAL, C.SYSTEM, A.CREATE_VISUAL, ["concept", "slide_number"], requires_context=True),
    _s(I.ADD_ANIMATION, C.SYSTEM, A.CREATE_VISUAL, ["slide_number"], requires_context=True),
    _s(I.MAKE_INTERACTIVE, C.SYSTEM, A.CREATE_VISUAL, ["slide_number"], requires_context=True),

    _s(I.STOP_SPEAKING, C.VOICE, A.VOICE_CONTROL),
    _s(I.PAUSE, C.VOICE, A.VOICE_CONTROL),
    _s(I.RESUME, C.VOICE, A.VOICE_CONTROL),
    _s(I.REPEAT_LAST, C.VOICE, A.VOICE_CONTROL, requires_context=True),
    _s(I.CANCEL, C.VOICE, A.VOICE_CONTROL),

    _s(I.HELP, C.SYSTEM, A.SYSTEM_INFO),
    _s(I.CAPABILITIES, C.SYSTEM, A.SYSTEM_INFO),
    _s(I.SETTINGS, C.SYSTEM, A.SYSTEM_INFO),
    _s(I.TRANSLATE, C.SYSTEM, A.ANSWER_FROM_CONTENT, ["target_language"], requires_context=True),
    _s(I.GREETING, C.SYSTEM, A.SYSTEM_INFO),
    _s(I.AMBIGUOUS, C.AMBIGUOUS, A.ASK_CLARIFICATION),
    _s(I.UNKNOWN, C.AMBIGUOUS, A.ANSWER_GENERAL),
]}


def dump_intents_json() -> list[dict]:
    return [
        {
            "intent": s.intent.value,
            "category": s.category.value,
            "action": s.action.value,
            "entities": s.entities,
            "requires_context": s.requires_context,
            "requires_presentation": s.requires_presentation,
            "summary_only_on_request": s.summary_only_on_request,
            "description": s.description,
        }
        for s in INTENT_SPEC.values()
    ]


__all__ = ["Intent", "Category", "Action", "IntentSpec", "INTENT_SPEC",
           "dump_intents_json"]
