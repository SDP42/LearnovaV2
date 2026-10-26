"""
From a short request ("Gradient descent for beginners") to a complete lesson the pipeline can turn into a deck.

A one-line prompt carries no content, so it cannot become a good deck by layout alone. This module writes the
missing source text:

1. **LLM** (any configured provider) with a detailed instructional-design brief — sections with one job each,
   facts only, shaped so the visual engine recognises process / comparison / timeline / numbers / definitions.
2. **Library** — when no model is configured, the closest built-in lesson from the gallery catalogue.
3. **None** — the prompt is kept as written and the caller is told plainly that an AI key would write the rest.

Longer inputs (a syllabus, notes, a document) are never rewritten: ``is_prompt`` says which kind of input this is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from learnova.logging_config import logger

SECTIONS_FOR = {"compact": 6, "balanced": 9, "detailed": 12}

SYSTEM_BRIEF = """You are an expert teacher and instructional designer. You write the SOURCE TEXT for a slide deck: accurate, \
well-structured lesson notes that another program will turn into slides. Output Markdown only — no preamble, no closing remarks.

FORMAT
- First line: "# <Title>" (specific, at most 8 words).
- Then exactly the requested number of sections, each "## <Heading>" (specific, at most 7 words; never just "Introduction").
- Each section is 45–110 words of plain sentences or a short list. No markdown tables, no emojis, no bold, no links.

EACH SECTION HAS ONE JOB — choose the ones that fit the topic, and make the job obvious from the sentences:
- Overview: what it is and why it matters (2–3 sentences).
- Key terms: 4–6 terms, one sentence each, written "Term is …".
- How it works: an ordered procedure written "First, … Then, … Next, … Finally, …" (4–6 steps, one sentence each). If the process repeats, say "and the cycle repeats".
- Timeline: 4–6 dated events, one sentence each, starting "In 1969 …".
- Comparison: two or more things described in parallel sentences ("X is …, whereas Y is …" or "Option A is …. Option B is …. Option C is …").
- Numbers: one sentence listing 3+ comparable figures with units ("A reached $5 million, B $3 million and C $2 million"). Use ONLY well-established figures; if unsure, describe qualitatively and skip the numbers.
- Formula or equation: write it plainly on its own sentence (e.g. "The formula is F = m a."), then explain each symbol.
- Worked example: one concrete case with real values, stepping through it.
- Common mistakes: 3–4 misconceptions and the correction for each.
- Applications: 3–4 real uses, each with a one-line reason.
- Summary: 4–5 takeaways, one sentence each.
Include at least: an overview, key terms, one process or timeline, one comparison, one worked example and a summary.

QUALITY RULES
- Facts only. Never invent statistics, quotations, names, dates or sources. If you are unsure of a fact, leave it out.
- Match the audience and level given. Define jargon the first time it appears.
- No filler ("In this presentation we will…"), no meta commentary, no repetition between sections.
"""


@dataclass
class Expansion:
    markdown: str
    mode: str                  # "llm" | "library" | "none" | "kept"
    message: str = ""
    sections: int = 0
    source: str = ""           # library slug, when mode == "library"

    def to_dict(self) -> Dict[str, object]:
        return {"mode": self.mode, "message": self.message, "sections": self.sections, "source": self.source}


_PROMPT_VERBS = re.compile(r"^(?:please\s+)?(?:make|create|build|generate|write|prepare|give me|explain|teach me|i need|i want|presentation|ppt|slides?)\b", re.I)


def is_prompt(text: str) -> bool:
    """A request rather than content: short, no headings or lists, a sentence or two."""
    t = (text or "").strip()
    if not t:
        return False
    words = len(t.split())
    if re.search(r"(?m)^\s*(?:#{1,6}\s|[-*•]\s|\d+[.)]\s)", t) or "[TABLE DATA]" in t:
        return False
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
    if words <= 25:
        return True
    return words <= 60 and len(sentences) <= 3 and bool(_PROMPT_VERBS.match(t))


def _title_from(prompt: str) -> str:
    t = re.sub(r"^(?:please\s+)?(?:make|create|build|generate|write|prepare|give me|explain|teach me|i need|i want)\s+(?:me\s+)?(?:a|an|the)?\s*(?:presentation|ppt|slides?|deck|lesson|lecture)?\s*(?:on|about|for|of)?\s*", "", prompt.strip(), flags=re.I)
    t = re.split(r"[.!?\n]", t)[0].strip(" ,:;-")
    t = re.sub(r"\s+(?:for|with|in)\s+\d+\s+(?:slides?|minutes?).*$", "", t, flags=re.I)
    return (t[:1].upper() + t[1:])[:70] if t else prompt.strip()[:70]


def _valid(md: str, want: int) -> bool:
    heads = re.findall(r"(?m)^##\s+\S", md)
    if len(heads) < max(4, want - 3):
        return False
    body = re.sub(r"(?m)^#+\s.*$", "", md)
    per = len(body.split()) / max(1, len(heads))
    if per < 28:
        return False
    return not re.search(r"\b(as an ai|i'm sorry|i cannot|i can't help)\b", md, re.I)


def _clean(md: str) -> str:
    md = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", (md or "").strip())
    md = re.sub(r"\*\*(.+?)\*\*", r"\1", md)                       # the engine wants plain sentences, not bold runs
    return md.strip()


def _llm(prompt: str, audience: str, tone: str, detail: str) -> Optional[str]:
    from learnova.ai.assist import llm_available
    from learnova.providers.router import TASK_IMPROVE, get_router

    if not llm_available():
        return None
    n = SECTIONS_FOR.get(detail, 9)
    user = (f"Request: {prompt.strip()[:600]}\nAudience: {audience or 'general learners'}\nTone: {tone or 'clear and friendly'}\n"
            f"Number of sections: {n}\nWrite the lesson now.")
    last = ""
    for attempt in range(2):
        extra = "" if attempt == 0 else "\nYour previous answer was too short or malformed. Follow the FORMAT exactly and make every section 45–110 words."
        try:
            raw = get_router().generate(user + extra, system_prompt=SYSTEM_BRIEF, task=TASK_IMPROVE, temperature=0.4, max_tokens=4200, timeout=90.0)
        except Exception as exc:
            logger.info("lesson_writer: provider failed: %s", exc)
            return None
        last = _clean(raw or "")
        if _valid(last, n):
            return last
    return last if last and len(re.findall(r"(?m)^##\s", last)) >= 3 else None


def _tokens(s: str) -> set:
    stop = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "with", "about", "intro", "introduction", "basics", "basic", "make", "create",
            "presentation", "slides", "slide", "explain", "teach", "me", "lesson", "ppt", "deck", "beginners", "students"}
    return {w for w in re.findall(r"[a-z0-9]{3,}", s.lower()) if w not in stop}


def _library_match(prompt: str):
    try:
        from learnova.gallery.catalog import load_catalog
    except Exception:
        return None
    want = _tokens(prompt)
    if not want:
        return None
    best, best_score = None, 0.0
    for e in load_catalog():
        if not e.outline:
            continue
        title, tags = _tokens(e.title), _tokens(" ".join(e.tags))
        score = 3.0 * len(want & title) + 1.5 * len(want & tags) + 0.15 * len(want & _tokens(e.outline[:1200]))
        if score > best_score:
            best, best_score = e, score
    return best if best is not None and best_score >= 3.0 else None


def expand(prompt: str, *, audience: str = "", tone: str = "", detail: str = "balanced") -> Expansion:
    """Write (or find) the lesson for a short request. Never raises."""
    prompt = (prompt or "").strip()
    md = None
    try:
        md = _llm(prompt, audience, tone, detail)
    except Exception:
        logger.exception("lesson_writer: llm path crashed")
    if md:
        return Expansion(md, "llm", "Written by the AI from your request — review and edit it before generating.", len(re.findall(r"(?m)^##\s", md)))
    hit = _library_match(prompt)
    if hit is not None:
        return Expansion(hit.outline.strip(), "library",
                         f"Built from our “{hit.title}” lesson. Add an AI key (Settings) to write a lesson tailored to your exact request.",
                         len(re.findall(r"(?m)^##\s", hit.outline)), hit.slug)
    title = _title_from(prompt)
    return Expansion(f"# {title}\n\n## Overview\n{prompt.rstrip('.')}.", "none",
                     "Your request is too short to build a full deck on its own. Add an AI key (Settings) and Learnova writes the whole lesson, "
                     "or paste your notes / syllabus instead.", 1)


__all__ = ["Expansion", "expand", "is_prompt", "SYSTEM_BRIEF", "SECTIONS_FOR"]
