"""
Deterministic NLU: intent classification + entity extraction (spec §4, §20,
§38).

This is the fast, offline path — regex/keyword rules over a normalised
utterance. It is intentionally high-precision: when it is not confident it
returns ``Intent.AMBIGUOUS`` / ``Intent.UNKNOWN`` and the orchestrator falls
back to the LLM classifier (``classify_llm``, wired later). The QA dataset in
``data/assistant/`` is the benchmark this path is tuned against.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from learnova.assistant.intents import INTENT_SPEC, Intent

_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
           "twelve": 12, "twenty": 20, "thirty": 30, "fifty": 50}


@dataclass
class NLUResult:
    intent: Intent
    confidence: float
    entities: Dict[str, object] = field(default_factory=dict)
    normalised: str = ""
    matched_rule: str = ""

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "confidence": round(self.confidence, 3),
            "entities": self.entities,
            "category": INTENT_SPEC[self.intent].category.value,
            "action": INTENT_SPEC[self.intent].action.value,
            "matched_rule": self.matched_rule,
        }


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower().strip()
    t = re.sub(r"^(hey|ok|okay|hi|hello|yo)\s+(learnova|assistant)[,!.\s]*", "", t)
    t = re.sub(r"^(learnova|assistant)[,!.\s]+", "", t)
    t = re.sub(r"\b(pls|plz)\b", "please", t)
    t = re.sub(r"\bpresntation\b|\bpresentaton\b|\bpresentaion\b|\bpresntn\b", "presentation", t)
    t = re.sub(r"\bpres\b", "presentation", t)
    t = re.sub(r"\bppt\b", "presentation", t)
    t = re.sub(r"\bslde\b", "slide", t)
    t = re.sub(r"\bnxt\b", "next", t)
    t = re.sub(r"\bopn\b", "open", t)
    t = re.sub(r"\bexplan\b|\bexplian\b", "explain", t)
    t = re.sub(r"\bno\.?\s*(\d)", r"number \1", t)
    t = re.sub(r"\s+", " ", t).strip(" ?!.")
    return t


def _num(text: str) -> Optional[int]:
    m = re.search(r"\b(\d{1,3})\b", text)
    if m:
        return int(m.group(1))
    for w, n in _WORDNUM.items():
        if re.search(rf"\b{w}\b", text):
            return n
    return None


# rule = (name, regex, intent, base_confidence, entity_fn)
def _pref_ref(t: str) -> str:
    """The presentation-reference slice of an utterance."""
    s = t
    m = re.search(r"\b(?:open|show( me)?|launch|start|get|give me|take me to|go to|"
                  r"bring up|pull up|resume|restart|download|delete|i want)\s+(.+)$", s)
    if m:
        s = m.group(m.lastindex).strip()
    # drop a leading "the / of the / me the / the web deck of"
    s = re.sub(r"^(the\s+|me\s+the\s+|of\s+(the\s+)?|web deck of\s+|interactive version of\s+)", "", s)
    s = re.sub(r"^(the\s+)?(web|interactive|html)\s+(deck|version|presentation)\s+(of\s+)?", "", s)
    return s.strip() or t


_RULES = [
    # ── voice control (check first — very short, unambiguous) ───────────────
    ("voice.stop", r"^(stop|shut up|be quiet|quiet|enough)$", Intent.STOP_SPEAKING, 0.97, None),
    ("voice.pause", r"^(pause|hold on|wait)$", Intent.PAUSE, 0.95, None),
    ("voice.resume", r"^(resume|continue|carry on|go on|keep going)$", Intent.RESUME, 0.93, None),
    ("voice.repeat", r"^(repeat|repeat that|say (that|it) again|come again|what)$",
     Intent.REPEAT_LAST, 0.9, None),
    ("voice.cancel", r"^(cancel|never mind|nevermind|forget it|abort)$", Intent.CANCEL, 0.95, None),

    # ── slide navigation ───────────────────────────────────────────────────
    ("slide.next", r"^(next slide|next|next one|okay next|and next|forward|move on|"
     r"advance( the slide)?|go forward|show the next( one| slide)?|"
     r"continue to the next slide)$",
     Intent.NEXT_SLIDE, 0.9, None),
    ("slide.prev", r"^(previous slide|previous( one)?|go back|back|back up( one slide)?|"
     r"prior slide|one back|go back one|back a slide|return to the previous slide|"
     r"back to the previous slide)$", Intent.PREVIOUS_SLIDE, 0.88, None),
    ("slide.first", r"\b(first slide|go to (the )?first slide|slide one|slide 1)\b|"
     r"^(go to the beginning|back to the start|start from the beginning|"
     r"jump to the first slide|to the start)$",
     Intent.FIRST_SLIDE, 0.9, None),
    ("slide.last", r"\b(last slide|final slide)\b|^(go to the end|jump to the end|"
     r"show the last slide|to the end)$",
     Intent.LAST_SLIDE, 0.9, None),
    ("slide.goto", r"\b(go to|goto|show|jump to|open|take me to|start (from|at))\s+"
     r"slide\s+(?:number\s+)?(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten)\b",
     Intent.GO_TO_SLIDE, 0.93, lambda t: {"slide_number": _num(t)}),
    ("slide.goto2", r"\bslide\s+(?:number\s+)?(\d{1,3}|one|two|three|four|five|six|"
     r"seven|eight|nine|ten|eleven|twelve)\b",
     Intent.GO_TO_SLIDE, 0.82, lambda t: {"slide_number": _num(t)}),
    ("slide.section", r"\b(go to|jump to|show me|take me to|open)\s+the\s+(.+?)\s+"
     r"(section|part|slide)\b", Intent.GO_TO_SECTION, 0.82,
     lambda t: {"section_name": (re.search(r"the\s+(.+?)\s+(section|part|slide)", t) or [None, ""])[1]}),
    ("slide.repeat", r"\b(repeat (this|the) slide|show (this|it) again|stay here)\b",
     Intent.REPEAT_SLIDE, 0.85, None),
    ("slide.read", r"\b(read (this|the) slide|read (this|it) (out|aloud)|read it to me)\b",
     Intent.READ_SLIDE, 0.9, None),
    ("slide.explain", r"\b(explain (this|the)( current)? slide|what('?s| is) (on )?this slide|"
     r"what does this slide (say|mean)|what is this slide about|"
     r"break down this slide|help me understand this slide)\b|"
     r"^(explain this|explain it|explain the current slide)$",
     Intent.EXPLAIN_SLIDE, 0.9, None),
    ("visual.explain", r"\b(explain (this|the) (diagram|chart|image|figure|graph|picture)|"
     r"what does this (diagram|chart|image|figure|arrow|box) (mean|show|represent)|"
     r"what('?s| is) (happening )?(here|this)|what is this)\b",
     Intent.EXPLAIN_VISUAL, 0.85, None),

    # ── web deck / open / control presentation ─────────────────────────────
    ("pres.create", r"\b(create|make( me)?|build|generate|turn .* into)\b.*\b(presentation|deck|"
     r"slides|slideshow|web deck)\b",
     Intent.CREATE_PRESENTATION, 0.92,
     lambda t: {"topic": (re.search(r"\b(about|on|for|covering|regarding)\s+(.+)$", t) or [None, None, ""])[2].strip(),
                "source_ref": "this" if re.search(r"\b(this|the) (document|content|text|pdf|notes)\b", t) else ""}),
    ("pres.webdeck", r"\b(web deck|interactive (deck|version|presentation)|"
     r"web (version|presentation)|html (deck|version))\b",
     Intent.GET_WEB_DECK, 0.9, lambda t: {"presentation_reference": _pref_ref(t)}),
    ("pres.start", r"\b(start|play|present|begin|run|kick off)\s+(presenting\s+)?"
     r"(the\s+)?(presentation|deck|slideshow|slide\s?show)\b|"
     r"\bstart presentation\b|\bpresent the\b|\blet'?s present\b",
     Intent.START_PRESENTATION, 0.92, lambda t: {"presentation_reference": _pref_ref(t)}),
    ("pres.stop", r"\b(stop|end|close|exit|quit)\s+(the\s+)?(presentation|deck|slideshow)\b",
     Intent.STOP_PRESENTATION, 0.9, None),
    ("pres.restart", r"\b(restart|start over|from the beginning)\b.*\b(presentation|deck)\b",
     Intent.RESTART_PRESENTATION, 0.85, None),
    ("pres.resume", r"\b(resume|continue|go back to)\s+(the\s+)?(presentation|deck|"
     r"where (i|we) (left off|were))\b", Intent.RESUME_PRESENTATION, 0.8, None),
    ("pres.download", r"\b(download|export|save)\b.*\b(presentation|deck|pptx|"
     r"powerpoint|power point|pdf|file|slides)\b|"
     r"\b(get|give) (me )?the (pptx|powerpoint|power point|pdf|file)\b",
     Intent.DOWNLOAD_PRESENTATION, 0.93,
     lambda t: {"presentation_reference": _pref_ref(t),
                "format": "pptx" if "point" in t or "pptx" in t else ("pdf" if "pdf" in t else "")}),
    ("pres.delete", r"\b(delete|remove|trash|get rid of)\s+(the\s+)?(presentation|deck)\b",
     Intent.DELETE_PRESENTATION, 0.85, lambda t: {"presentation_reference": _pref_ref(t)}),
    ("pres.open", r"\b(open|show( me)?|launch|get|give me|take me to|bring up|pull up|"
     r"i want|can i see|let'?s (see|open))\b.*\b(presentation|deck|lrn-pres-\d+)\b",
     Intent.OPEN_PRESENTATION, 0.85, lambda t: {"presentation_reference": _pref_ref(t)}),
    ("pres.open_id", r"\blrn-pres-\d{3,}\b", Intent.OPEN_PRESENTATION, 0.9,
     lambda t: {"presentation_reference": (re.search(r"lrn-pres-\d{3,}", t) or [""])[0].upper()}),
    ("pres.open_num", r"\b(open|show( me)?|launch|start|go to|bring up|pull up|let'?s (open|see))\s+"
     r"(number\s+)?(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten)\b(?!.*\bslide\b)",
     Intent.OPEN_PRESENTATION, 0.8,
     lambda t: {"presentation_reference": str(_num(t) or "")}),
    ("pres.open_ord", r"\b(open|show( me)?|launch|start|go to|bring up)\s+the\s+"
     r"(first|second|third|fourth|fifth|last|latest|newest|\d+(st|nd|rd|th))\s*(one|deck|presentation)?\b"
     r"(?!.*\bslide\b)",
     Intent.OPEN_PRESENTATION, 0.78,
     lambda t: {"presentation_reference": (re.search(r"the\s+(.+)$", t) or [None, ""])[1].strip()}),

    # ── presentation search ───────────────────────────────────────────────
    ("pres.search", r"\b(find|search( for)?|list|show( me)?( all| my)?|which|do i have)\b"
     r".*\b(presentations?|decks?)\b",
     Intent.SEARCH_PRESENTATION, 0.85,
     lambda t: {"query": re.sub(
         r"^.*?\b(about|on|for|related to|covering)\b\s*|"
         r"\b(find|search( for)?|list|show me all|show all|which|do i have|my|"
         r"presentations?|decks?|all|the)\b", " ", t).strip(" ?")}),
    ("content.where", r"\b(where (is|do you|can i find|are|does)|which (presentation|deck|slide))\b",
     Intent.WHERE_IS_TOPIC, 0.82,
     lambda t: {"topic": re.sub(
         r"^.*?\b(where (is|does|do you|can i find|are))\s+|"
         r"\b(explained?|covered?|discussed?|taught|talk(s)? about)\b.*$|"
         r"\bwhich (presentation|deck|slide)\b|\b(is|are|do you|can i)\b", " ", t).strip(" ?")}),
    ("content.search", r"\b(search( for)?|look up|find (me )?(everything |all )?(about|on)?|"
     r"look for)\b(?!.*\b(presentations?|decks?)\b)",
     Intent.SEARCH_CONTENT, 0.78,
     lambda t: {"query": re.sub(
         r"^.*?\b(search( for)?|look up|find (me )?(everything |all )?|look for|about|on|in my content)\b",
         " ", t).strip(" ?")}),
    ("content.findabout", r"\b(show me all presentations related to|find presentations about|"
     r"which decks are about|list decks covering)\b",
     Intent.FIND_PRESENTATIONS_ABOUT, 0.85,
     lambda t: {"subject": re.sub(r".*\b(about|related to|covering)\b", "", t).strip(" ?")}),

    # ── summarise / explain a presentation (explicit) ─────────────────────
    ("pres.summarise", r"\b(summari[sz]e|give me a summary of|tl;?dr|short version of|"
     r"quick summary of)\b",
     Intent.SUMMARIZE_PRESENTATION, 0.9, lambda t: {"presentation_reference": _pref_ref(t)}),
    ("pres.explain", r"\b(explain|walk me through|what('?s| is) in|give me an overview of|"
     r"what does presentation \d+ cover)\b.*\b(presentation|deck)\b",
     Intent.EXPLAIN_PRESENTATION, 0.86, lambda t: {"presentation_reference": _pref_ref(t)}),

    # ── quiz / learning ──────────────────────────────────────────────────
    ("quiz.start", r"\b(quiz me|test me|give me (a )?quiz|practi[sc]e questions?|"
     r"give me \d+ questions|mcqs?|ask me (some )?questions)\b", Intent.START_QUIZ, 0.9,
     lambda t: {"count": _num(t), "topic": (re.search(r"\bon\s+(.+)$", t) or [None, ""])[1].strip()}),
    ("quiz.next", r"\b(next question|another question|ask me (the )?next|continue the quiz)\b",
     Intent.NEXT_QUIZ_QUESTION, 0.88, None),
    ("quiz.mistake", r"\b(why (is|was) (my answer|that) wrong|explain my mistake|"
     r"why did i get (it|that) wrong)\b", Intent.EXPLAIN_MISTAKE, 0.88, None),
    ("quiz.answer", r"^(the answer is|i think it'?s|my answer is|it'?s|answer:?)\s+(.+)$",
     Intent.SUBMIT_QUIZ_ANSWER, 0.7, lambda t: {"answer": (re.search(r"(?:is|it'?s|answer:?)\s+(.+)$", t) or [None, ""])[1]}),
    ("learn.teach", r"\b(teach me|help me (learn|understand)|i (want|need) to learn|"
     r"start teaching me)\b", Intent.TEACH_TOPIC, 0.9,
     lambda t: {"topic": re.sub(
         r".*\b(teach me|learn|understand)\b\s*(about)?|\bfrom the (beginning|start)\b|"
         r"\bstep by step\b", " ", t).strip(" ?about")}),
    ("learn.exam", r"\b(exam (prep|preparation)|prepare (me )?for (my|the) (exam|test)|"
     r"revision|revise|i have (an|a) (exam|test)|help me (study|revise)|studying for)\b",
     Intent.EXAM_PREP, 0.85,
     lambda t: {"topic": (re.search(r"\b(on|for|about)\s+(.+)$", t) or [None, None, ""])[2].strip()}),
    ("learn.easier", r"\b(easier example|simpler example|give me an easier|too hard|"
     r"i don'?t (get|understand) (it|this))\b", Intent.EASIER_EXAMPLE, 0.8, None),
    ("learn.harder", r"\b(harder example|more (difficult|advanced|challenging)|"
     r"give me a tougher|too easy)\b", Intent.HARDER_EXAMPLE, 0.82, None),

    # ── educational questions ────────────────────────────────────────────
    ("edu.compare", r"\b(compare|difference between|vs\.?|versus|how (does|do) .* differ)\b",
     Intent.COMPARE_CONCEPTS, 0.85, _compare_ents := None),
    ("edu.rwexample", r"\b(real[- ]world example|everyday example|practical example|"
     r"real life example|used in real life|real[- ]world use|where is .* used)\b",
     Intent.REAL_WORLD_EXAMPLE, 0.86,
     lambda t: {"concept": (re.search(r"example of\s+(.+)$|of\s+(.+)$", t) or [None, "", ""])[2] or ""}),
    ("edu.example", r"\b(give me (an|a) example|show me an example|for example|"
     r"an example please|can you demonstrate|give an example|example of)\b",
     Intent.GIVE_EXAMPLE, 0.84,
     lambda t: {"concept": (re.search(r"example of\s+(.+)$", t) or [None, ""])[1]}),
    ("edu.simple", r"\b(explain\b.*\b(simply|in simple( terms)?|in easy|in plain (english|language))|"
     r"like i'?m (a beginner|five|new|10)|make (this|it) (easier|simpler)|dumb it down|"
     r"i don'?t understand( this)?$|simpler please)\b",
     Intent.SIMPLIFY, 0.88,
     lambda t: {"concept": (re.search(r"explain\s+(.+?)\s+(simply|in simple|in easy|in plain)", t) or [None, ""])[1]}),
    ("edu.step", r"\b(step by step|step-by-step|one step at a time|break (it|this) down)\b",
     Intent.STEP_BY_STEP, 0.85, None),
    ("edu.why", r"^why\b|\bwhy (do|does|is|are|did|would|should)\b", Intent.WHY_QUESTION, 0.72, None),
    ("edu.next", r"\b(what (happens|comes) next|then what|and then|what'?s the next step|"
     r"what happens after this)\b", Intent.WHAT_NEXT, 0.86, None),
    ("edu.define", r"^(define|what does .* (mean|stand for)|meaning of)\b",
     Intent.DEFINE_TERM, 0.75, lambda t: {"term": re.sub(r"^(define|what does|meaning of)\s+", "", t).strip(" ?mean stand for")}),
    ("edu.explain", r"^(explain|what (is|are|was)|tell me about|how (does|do|is)|describe)\b",
     Intent.EXPLAIN_CONCEPT, 0.68,
     lambda t: {"concept": re.sub(r"^(explain|what (is|are|was)|tell me about|how (does|do|is)|describe)\s+", "", t).strip(" ?")}),

    # ── visualisation ───────────────────────────────────────────────────
    ("vis.make", r"\b(make (this|it|.{1,20}) (more )?visual|turn (this|it|.{1,30}) into (a )?"
     r"(diagram|visual|animation|flowchart|picture)|show (this|it) as a (diagram|chart|visual|flowchart)|"
     r"visuali[sz]e (this|it|.{1,20})|create a visual (explanation|of)|"
     r"turn (this|the) (paragraph|text|content) into)\b",
     Intent.MAKE_VISUAL, 0.83, None),
    ("vis.anim", r"\b(add (an )?animation|animate (this|it)|make (this|it) animated)\b",
     Intent.ADD_ANIMATION, 0.85, None),
    ("vis.interact", r"\b(make (this|it) interactive|add interactivity|interactive flowchart)\b",
     Intent.MAKE_INTERACTIVE, 0.85, None),

    # ── system / meta ──────────────────────────────────────────────────
    ("sys.help", r"^(help|what can you do|how do (i|you) work|commands|how do i use this)$",
     Intent.HELP, 0.9, None),
    ("sys.translate", r"\b(translate|in (hindi|marathi|spanish|french|german|tamil|telugu)|"
     r"explain (this|that) in )\b", Intent.TRANSLATE, 0.72,
     lambda t: {"target_language": (re.search(r"in (hindi|marathi|spanish|french|german|tamil|telugu|english)", t) or [None, ""])[1]}),
    ("sys.greet", r"^(hi|hello|hey|good (morning|afternoon|evening)|what'?s up|yo)$",
     Intent.GREETING, 0.9, None),
]


def _compare_entities(t: str) -> dict:
    m = re.search(r"(?:compare|difference between|between)\s+(.+?)\s+(?:and|vs\.?|versus|with)\s+(.+)$", t)
    if m:
        return {"concept": m.group(1).strip(" ?"), "concept_b": m.group(2).strip(" ?")}
    m = re.search(r"(.+?)\s+(?:vs\.?|versus)\s+(.+)$", t)
    if m:
        return {"concept": m.group(1).strip(" ?"), "concept_b": m.group(2).strip(" ?")}
    return {}


# patch the compare rule's entity fn (defined after the list for readability)
_RULES = [
    (name, rx, it, cf, (_compare_entities if name == "edu.compare" else fn))
    for (name, rx, it, cf, fn) in _RULES
]

_COMPILED = [(name, re.compile(rx), it, cf, fn) for (name, rx, it, cf, fn) in _RULES]


def classify(utterance: str) -> NLUResult:
    t = normalise(utterance)
    if not t:
        return NLUResult(Intent.UNKNOWN, 0.0, normalised=t)

    best: Optional[NLUResult] = None
    for name, rx, intent, conf, fn in _COMPILED:
        if rx.search(t):
            ents = {}
            if fn:
                try:
                    ents = {k: v for k, v in (fn(t) or {}).items() if v not in (None, "")}
                except Exception:
                    ents = {}
            r = NLUResult(intent, conf, ents, normalised=t, matched_rule=name)
            if best is None or r.confidence > best.confidence:
                best = r

    if best is None:
        # A bare question → educational; a bare imperative with "presentation"
        # → open. Otherwise unknown (LLM fallback).
        if "?" in (utterance or "") or re.match(r"^(what|why|how|when|who|which|is|are|can|does|do)\b", t):
            return NLUResult(Intent.EXPLAIN_CONCEPT, 0.45,
                             {"concept": re.sub(r"^(what|why|how|is|are|does|do|can)\s+(is|are|the)?\s*", "", t).strip(" ?")},
                             normalised=t, matched_rule="fallback.question")
        if "presentation" in t or "deck" in t:
            return NLUResult(Intent.OPEN_PRESENTATION, 0.4,
                             {"presentation_reference": _pref_ref(t)},
                             normalised=t, matched_rule="fallback.presentation")
        return NLUResult(Intent.UNKNOWN, 0.2, normalised=t, matched_rule="none")

    # Ambiguity: a reference like "the security one" with no strong signal.
    return best


__all__ = ["NLUResult", "classify", "normalise"]
