"""
The Deck Director — Learnova's "presentation-generator head".

Given the finished deck (the orchestrator's ``final_deck``), it makes the
whole-deck presentation decisions that no single-slide stage can:

* **Visual** per slide — family / variant / params, via the VMS
  (``ai/visual_selector.py``).
* **Animation** per slide — the progressive-reveal timeline (same source).
* **Transition** *between* consecutive slides — chosen from the *semantic
  relationship* of the two slides (continuation, same-topic step, sub-topic
  shift, new section, checkpoint). This is the piece that makes an exported
  deck feel authored rather than uniform.
* **Summarisation directive** per slide — PRESERVE (keep wording), BALANCED,
  or COMPRESS — from the verbatim ratio (``ai/text_policy.py``) and the
  cognitive load (``scoring/psf.py``).
* **Speaker notes** per slide — takeaway + per-click cues + "read exactly"
  reminders + a time estimate — so the web deck's presenter view and the
  PPTX notes pane are populated.
* **Deck pacing** — section boundaries and an estimated running time.

Deterministic, no LLM, no network. Output is a ``DeckPlan`` that both
``web_deck_builder`` and ``ppt_builder`` consume.

Design notes: ``docs/research/DECK_DIRECTOR.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from learnova.logging_config import logger

_WORD = re.compile(r"[A-Za-z][A-Za-z\-']+")

from learnova.ai.master_prompt import TREATMENT_TO_FAMILY as _T2F

# family → flat treatment key (reverse of the master-prompt table)
_FAMILY_TO_TREATMENT = {fam: key for key, (fam, _v) in _T2F.items()}

# Reveal.js transition names (also mapped to PPTX transitions in ppt_builder).
TRANSITIONS = ("none", "fade", "slide", "convex", "concave", "zoom")

# Rough per-element speaking time (seconds) used for the running-time estimate.
_SEC_BASE = 12.0
_SEC_PER_STEP = 7.0
_SEC_QUIZ = 25.0
_SEC_TITLE = 8.0


@dataclass
class SlidePlan:
    index: int
    title: str
    treatment: str
    family: str
    variant: str
    params: Dict[str, Any]
    data: Dict[str, Any]            # structured data for the chosen family
    animation: Dict[str, Any]
    transition: str
    transition_reason: str
    summary_directive: str          # PRESERVE | BALANCED | COMPRESS
    verbatim: List[str]
    speaker_notes: str
    est_seconds: float
    is_section_start: bool
    confidence: float
    visual_reason: str = ""
    visual_alternatives: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "treatment": self.treatment,
            "family": self.family,
            "variant": self.variant,
            "params": self.params,
            "data": self.data,
            "animation": self.animation,
            "transition": self.transition,
            "transition_reason": self.transition_reason,
            "summary_directive": self.summary_directive,
            "verbatim": self.verbatim,
            "speaker_notes": self.speaker_notes,
            "est_seconds": round(self.est_seconds),
            "is_section_start": self.is_section_start,
            "confidence": round(self.confidence, 3),
            "visual_reason": self.visual_reason,
            "visual_alternatives": self.visual_alternatives,
        }


@dataclass
class DeckPlan:
    slides: List[SlidePlan] = field(default_factory=list)
    est_minutes: float = 0.0
    section_starts: List[int] = field(default_factory=list)

    def by_index(self, i: int) -> SlidePlan | None:
        return self.slides[i] if 0 <= i < len(self.slides) else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "est_minutes": round(self.est_minutes, 1),
            "section_starts": self.section_starts,
            "slides": [s.to_dict() for s in self.slides],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _content_words(text: str) -> set:
    return {w.lower() for w in _WORD.findall(text or "") if len(w) > 3}


def _slide_text(entry: Dict[str, Any]) -> str:
    imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else entry
    imp = imp or {}
    parts = [str(imp.get("title", "")), " ".join(str(b) for b in (imp.get("bullets") or []))]
    parts.append(str(imp.get("takeaway", "")))
    return " ".join(p for p in parts if p)


def _title_stem(title: str) -> str:
    return re.sub(r"\s*\(\d+\s*/\s*\d+\)\s*$", "", title or "").strip().lower()


def _looks_like_section_head(title: str, bullets: List[str]) -> bool:
    """A short, title-cased line with little body reads as a section divider."""
    t = (title or "").strip()
    if not t:
        return False
    few_words = len(t.split()) <= 5
    body_words = sum(len(str(b).split()) for b in (bullets or []))
    starter = bool(re.match(r"(?i)^(chapter|unit|module|part|section|introduction|overview)\b", t))
    return (few_words and body_words < 6) or starter


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ─────────────────────────────────────────────────────────────────────────────
# Transition selection — the semantic bit
# ─────────────────────────────────────────────────────────────────────────────


def choose_transition(
    prev: Dict[str, Any] | None,
    curr: Dict[str, Any],
    prev_words: set,
    curr_words: set,
) -> tuple[str, str, bool]:
    """
    Pick the transition INTO ``curr`` from its relationship with ``prev``.

    Returns ``(transition, reason, is_section_start)``.
    """
    imp = curr.get("improved") if isinstance(curr.get("improved"), dict) else curr
    imp = imp or {}
    layout = str(imp.get("layout_type", "")).upper()
    title = str(imp.get("title", ""))
    bullets = imp.get("bullets") or []

    if prev is None:
        return "slide", "opening slide", True

    prev_imp = prev.get("improved") if isinstance(prev.get("improved"), dict) else prev
    prev_imp = prev_imp or {}

    # Checkpoint / quiz slides get their own distinct feel.
    if layout in {"QUIZ"} or imp.get("inline_quiz") or imp.get("question"):
        return "concave", "checkpoint slide — set it apart", False

    # A numbered continuation of the same topic is one continuous thought.
    if _title_stem(title) and _title_stem(title) == _title_stem(str(prev_imp.get("title", ""))):
        return "none", "continuation of the same topic — no visual break", False

    overlap = _jaccard(prev_words, curr_words)

    if _looks_like_section_head(title, bullets) and overlap < 0.2:
        return "zoom", "new section — strong break", True

    if overlap >= 0.45:
        return "fade", f"closely related to the previous slide (overlap {overlap:.2f})", False
    if overlap >= 0.15:
        return "slide", f"next point in the same topic (overlap {overlap:.2f})", False
    return "convex", f"topic shift (overlap {overlap:.2f})", True


# ─────────────────────────────────────────────────────────────────────────────
# Summarisation directive
# ─────────────────────────────────────────────────────────────────────────────


def choose_summary_directive(text: str, verbatim: List[str], n_sentences: int) -> str:
    from learnova.scoring.psf import SlideFeatures, cognitive_load

    ratio = (len(verbatim) / n_sentences) if n_sentences else 0.0
    if ratio >= 0.4:
        return "PRESERVE"
    load, _ = cognitive_load(SlideFeatures(bullets=[text]))
    if load >= 0.6:
        return "COMPRESS"
    return "BALANCED"


# ─────────────────────────────────────────────────────────────────────────────
# Speaker notes
# ─────────────────────────────────────────────────────────────────────────────


def build_speaker_notes(imp: Dict[str, Any], animation: Dict[str, Any],
                        verbatim: List[str], directive: str, est_seconds: float,
                        source_text: str = "") -> str:
    lines: List[str] = []
    takeaway = str(imp.get("takeaway", "")).strip()
    if takeaway:
        lines.append(f"KEY POINT TO LAND: {takeaway}")
    steps = animation.get("steps") or []
    if len(steps) > 1:
        lines.append("")
        lines.append("Reveal, one click at a time:")
        for i, s in enumerate(steps, 1):
            lines.append(f"  {i}. {s.get('label', '')}")
    if verbatim:
        lines.append("")
        lines.append("Read these exactly (do not paraphrase):")
        for v in verbatim[:4]:
            lines.append(f"  - {v}")

    # The full detail from the source, so the teacher keeps the whole
    # explanation even when the slide bullet is short. Only added when it says
    # meaningfully more than the bullets already on the slide.
    src = re.sub(r"\s+", " ", str(source_text or "")).strip()
    bullets_join = " ".join(str(b) for b in (imp.get("bullets") or []))
    if src and len(src) > len(bullets_join) * 1.25 and len(src) > 120:
        lines.append("")
        lines.append("Full detail (from the source):")
        for sent in re.split(r"(?<=[.!?])\s+", src)[:8]:
            sent = sent.strip()
            if sent:
                lines.append(f"  {sent}")
    kt = imp.get("key_terms") or []
    if kt:
        lines.append("")
        lines.append("Say what these mean, in your own words:")
        for t in kt[:3]:
            lines.append(f"  - {t['term']}: {t['definition']}")
    if not (src and len(src) > len(bullets_join) * 1.25 and len(src) > 120) and str(imp.get("title", "")):
        lines.append("")
        lines.append(f"Pause: ask the class what they already know about “{re.sub(r'\s*\(\d+/\d+\)$', '', str(imp['title']))}” before revealing the slide.")
    hint = {
        "PRESERVE": "Wording matters here — slow down, keep it precise.",
        "COMPRESS": "Dense slide — talk to it, don't read every word.",
        "BALANCED": "",
    }.get(directive, "")
    if hint:
        lines.append("")
        lines.append(hint)
    lines.append("")
    lines.append(f"~{round(est_seconds)}s")
    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def explain_text(imp: Dict[str, Any]) -> str:
    """The plain-words explanation shown in the slide body (not squeezed into the footer), with its example."""
    ex = str(imp.get("explain") or "").strip()
    eg = str(imp.get("example") or "").strip()
    if eg and eg.lower() not in ex.lower():
        ex = (ex + " " if ex else "") + ("For example, " + eg[0].lower() + eg[1:] if not eg.lower().startswith(("for example", "e.g", "example")) else eg)
    return ex


def footer_rows(imp: Dict[str, Any], takeaway: str) -> List[List[str]]:
    """[[label, text], …] shown under a slide: takeaway, key terms from the document's own definitions, an example."""
    rows: List[List[str]] = []
    if takeaway:
        rows.append(["Key takeaway", takeaway])
    kt = imp.get("key_terms") or []
    if kt:
        rows.append(["Key terms", "  ·  ".join(f"{t['term']} — {t['definition']}" for t in kt[:3])])
    for sent in (imp.get("context") or [])[:2]:
        rows.append(["Also in this lecture", str(sent)])
    return rows


def _residual_notes(text: str, data: Dict[str, Any], limit: int = 4) -> List[str]:
    """Sentences the chosen visual does not carry — kept as notes so no fact is lost."""
    from learnova.visuals.engine import split_sentences

    import json as _json

    covered = set(_WORD.findall(_json.dumps(data, default=str).lower()))
    out: List[str] = []
    # table scaffolding and planner markers are not prose
    text = "\n".join(l for l in (text or "").split("\n") if not l.strip().startswith("|") and l.strip() != "[TABLE DATA]" and not l.startswith("###"))
    for s_ in split_sentences(text):
        words = [w for w in _WORD.findall(s_.lower()) if len(w) > 3]
        if not words:
            continue
        if sum(1 for w in words if w in covered) / len(words) < 0.6:
            out.append(s_.strip())
    return out[:limit]


def plan_deck(final_deck: List[Dict[str, Any]]) -> DeckPlan:
    """Produce the full DeckPlan for a finished deck."""
    from learnova.ai.master_prompt import TREATMENT_TO_FAMILY
    from learnova.ai.text_policy import classify_sentences
    from learnova.ai.visual_selector import plan_animation_steps, select_visual

    plan = DeckPlan()
    prev_entry: Dict[str, Any] | None = None
    prev_words: set = set()
    total_seconds = _SEC_TITLE

    for i, entry in enumerate(final_deck):
        imp = entry.get("improved") if isinstance(entry.get("improved"), dict) else entry
        imp = imp or {}
        title = str(imp.get("title", f"Slide {i + 1}"))
        bullets = [str(b) for b in (imp.get("bullets") or [])]
        text = _slide_text(entry)
        curr_words = _content_words(text)

        # 1. Visual + animation via the VMS. Prefer the ORIGINAL section text
        #    (pre-pagination) so a pros/cons or step list split across "(1/2)"
        #    slides is still detected and its data extracted from the whole.
        existing_layout = str(imp.get("layout_type", "MINIMAL_TEXT")).upper()
        original = entry.get("original") if isinstance(entry.get("original"), dict) else {}
        # Feed the VMS BOTH the raw section text (so a step list split across
        # "(1/2)" slides is still detected from the whole) AND the improved
        # bullets (which, after enhancement, can carry structure — a worked
        # example's derivation lines — that the raw chunk did not).
        _otext = str((original or {}).get("text") or "").strip()
        _norm = lambda t: re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()  # noqa: E731
        # the bullets repeat the source text in preserve mode — add them only when they bring something new
        _bl = _norm(" ".join(bullets))
        _dup = bool(_otext) and (_bl in _norm(_otext) or "### " in _otext or "[TABLE DATA]" in _otext)
        vms_source = (_otext if _dup else "\n".join(p for p in (_otext, "\n".join(bullets)) if p)) or text
        vd = select_visual(vms_source, title)

        # The visual_data stage may have already extracted (via LLM) the exact
        # payload this family's renderer needs — a chart's series, a 2x2 matrix,
        # a comparison table. When present and it agrees with the VMS pick (or
        # the VMS only found text), adopt that family + data outright.
        vdata = imp.get("visual_data") if isinstance(imp.get("visual_data"), dict) else None
        if vdata and vdata.get("data"):
            # A user-forced family (from the editor) always wins. Otherwise adopt
            # the extracted data only when it agrees with the VMS or the VMS
            # found nothing structural.
            if (vdata.get("forced")
                    or vd.family in {"TEXT", "MINIMAL_TEXT", ""}
                    or vd.family == vdata.get("family")):
                from learnova.ai.visual_selector import VisualDecision

                vd = VisualDecision(
                    treatment=vd.treatment, family=vdata["family"],
                    variant=vdata.get("variant", vd.variant),
                    confidence=max(vd.confidence, float(vdata.get("confidence", 0.7))),
                    rationale="structured data extracted for the chosen family",
                    scores=vd.scores, bullets=vd.bullets, verbatim=vd.verbatim,
                    reveal_groups=vd.reveal_groups, animation=vd.animation,
                    data=vdata["data"],
                )

        # A layout the pipeline actually populated with data (an LLM table,
        # a real metric, a mermaid flowchart) is authoritative. A bare
        # keyword-heuristic guess (METRIC with no metric_value, etc.) is not —
        # the VMS wins over that whenever it clears a modest bar.
        _has_real_data = (
            (existing_layout == "TABLE" and imp.get("table_rows"))
            or (existing_layout == "METRIC" and str(imp.get("metric_value", "")).strip())
            or (existing_layout == "FLOWCHART" and imp.get("flowchart_spec"))
            or existing_layout == "QUIZ"
        )
        # The VMS produced a concrete structural payload (function expr, array,
        # pros/cons, stages, …) — trust it unless the pipeline has a genuine
        # LLM table or a checkpoint quiz.
        vms_has_payload = bool(vd.data) and vd.confidence >= 0.55
        hard_layout = existing_layout in {"QUIZ"} or (existing_layout == "TABLE" and imp.get("table_rows"))

        # Full-retention guard: a diagram family (process / cycle / mind-map /
        # comparison) *replaces* the bullet list with a handful of node labels.
        # Never do that to a content-heavy teaching slide — its sentences would
        # be lost. Such a slide stays TEXT; the enrich stage can still hang a
        # supporting visual beside it. Chart/table families that carry the data
        # themselves (KPI, real table) are exempt.
        _bwords = sum(len(b.split()) for b in bullets)
        _longest = max((len(b.split()) for b in bullets), default=0)
        _content_heavy = len(bullets) > 7 or _bwords > 110
        _lossy_family = str(vd.family or "").upper() in {
            "PROCESS_LINEAR", "PROCESS_CYCLIC", "DECISION", "STATE_MACHINE",
            "MIND_MAP", "HIERARCHY_TREE", "HIERARCHY_NEST", "TIMELINE",
            "COMPARE_VISUAL", "SET_DIAGRAM", "LIST_STRUCTURED",
        }
        # A diagram family only works when the bullets are genuinely short,
        # parallel node labels. If any bullet is a full teaching sentence, or
        # the slide is content-heavy, the diagram would garble / drop text —
        # keep it as text and hang the visual beside it instead.
        force_text = (
            _lossy_family
            and existing_layout in {"MINIMAL_TEXT", "", "CARD_GRID"}
            and not (vdata and vdata.get("forced"))
            and (_content_heavy or _longest > 12)
        )

        override_bar = 0.75 if _has_real_data else 0.6
        keep_existing = force_text or (
            existing_layout not in {"MINIMAL_TEXT", "", "CARD_GRID"}
            and vd.confidence < override_bar
            and not (vms_has_payload and not hard_layout)
        )
        if force_text:
            treatment, family, variant, data = "MINIMAL_TEXT", "TEXT", "standard", {}
        elif keep_existing:
            treatment = existing_layout
            family, variant = TREATMENT_TO_FAMILY.get(existing_layout, (vd.family, vd.variant))
            data = {}
        else:
            treatment, family, variant = vd.treatment, vd.family, vd.variant
            data = vd.data or {}
        # Content Decision Engine: it reads the slide and chooses the visual *and*
        # builds its data. It overrides plain-text outcomes (every slide gets a
        # visual) and the older selector's guesses, but never an editor-forced
        # family, a real LLM/table payload, or a checkpoint quiz.
        visual_reason, visual_alts, params = "", [], {}
        engine_conf = vd.confidence
        user_forced = bool(vdata and vdata.get("forced"))
        llm_data = bool(vdata and vdata.get("data") and vdata.get("source") == "llm" and vdata.get("family"))
        if llm_data and not user_forced and not hard_layout:
            family, variant, data = vdata["family"], vdata.get("variant", "llm"), vdata["data"]
            treatment = _FAMILY_TO_TREATMENT.get(family, family)
            visual_reason, engine_conf = "chosen by the AI assistant (the rules were unsure)", 0.9
            _tk = str(imp.get("takeaway_llm") or "")
            params = {"notes": _residual_notes(vms_source, data), "takeaway": _tk, "footer": footer_rows(imp, _tk), "explain": explain_text(imp)}
        if not user_forced and not hard_layout and existing_layout != "QUIZ" and not llm_data:
            from learnova.visuals import decide

            dec = decide(title, vms_source, bullets, vms=vd, outline=imp.get("outline"))
            treatment = _FAMILY_TO_TREATMENT.get(dec.family, dec.family)
            family, variant, data = dec.family, dec.variant, dec.data
            visual_reason, visual_alts = dec.reason, dec.alternatives
            engine_conf = max(dec.confidence, 0.66)  # the engine guarantees a drawable payload
            _tk = str(imp.get("takeaway_llm") or dec.takeaway)
            params = {"notes": _residual_notes(vms_source, dec.data), "takeaway": _tk, "footer": footer_rows(imp, _tk), "explain": explain_text(imp)}
        if (imp.get("is_glossary") or re.match(r"^(?:glossary|key terms?)\b", title, re.I)) and family == "LIST_STRUCTURED" and isinstance(data, dict):
            data = {**data, "flip": True}                      # web deck: term on the front, meaning on the back
        # A problem that can be solved on the slide (with numbers or a grammar): show it solved, step by step, with the reasoning.
        if (existing_layout != "QUIZ" and family not in {"FIGURE", "COMPARE_TABLE", "TIMELINE"}
                    and not (imp.get("is_summary") or imp.get("is_glossary") or imp.get("is_activity") or imp.get("is_agenda") or imp.get("is_overview"))):
            try:
                _cue = re.search(r"\b(solve|find|calculate|compute|what is|determine|evaluate|simplify|differentiate|integrate|how (?:much|many)|probability of|derive|parse|example|exercise|problem|numerical|solution|grammar)\b",
                                 f"{title} {vms_source}", re.I)
                if _cue or family == "WORKED_EXAMPLE":
                    from learnova.explain import find_and_solve

                    _ex = find_and_solve(title, vms_source, data if family == "WORKED_EXAMPLE" and isinstance(data, dict) else None)
                    if _ex:
                        treatment, family, variant, data = "STEPPER", "STEPPER", "steps", _ex.to_dict()
                        visual_reason = f"a {_ex.kind} that can be solved on the slide — shown step by step with the reasoning ({_ex.source})"
                        engine_conf = max(engine_conf, 0.92)
                        params = {"notes": [], "takeaway": "", "footer": []}               # the slide already ends with the answer
            except Exception:
                logger.warning("explainer detection failed", exc_info=True)
        # A slide that *is* a picture (a diagram, a table or a chart image from the source deck): keep it as a figure, large and zoomable —
        # never run a text detector on its title.
        _img = (original or {}).get("image") if isinstance(original, dict) else None
        if (_img and _img.get("bytes") and existing_layout != "QUIZ" and len(" ".join(bullets).split()) <= 4 and "[TABLE DATA]" not in _otext):
            from learnova.textutils import is_readable

            desc = re.sub(r"\s+", " ", str(_img.get("description") or "")).strip()
            desc = desc if is_readable(desc) else ""                     # OCR noise is never shown as a caption
            treatment, family, variant = "FIGURE", "FIGURE", "full"
            data = {"caption": desc[:150], "figure": True}
            visual_reason, visual_alts, engine_conf = "the slide is a figure — shown large with zoom instead of being redrawn", [], 0.9
            params = {"notes": [], "takeaway": "", "footer": []}
        animation = plan_animation_steps(
            bullets, treatment, family, takeaway=str(imp.get("takeaway", ""))
        )

        # 2. Transition from the semantic relationship to the previous slide.
        transition, reason, is_section = choose_transition(
            prev_entry, entry, prev_words, curr_words
        )

        # 3. Summarisation directive + verbatim protection.
        sents = classify_sentences(text)
        verbatim = [s.text for s in sents if s.treatment == "VERBATIM"]
        directive = choose_summary_directive(text, verbatim, len(sents))

        # 4. Time estimate + speaker notes.
        is_quiz = existing_layout == "QUIZ" or bool(imp.get("inline_quiz"))
        est = _SEC_BASE + _SEC_PER_STEP * max(1, len(animation.get("steps") or []))
        if is_quiz:
            est += _SEC_QUIZ
        total_seconds += est
        notes = build_speaker_notes(
            imp, animation, verbatim, directive, est,
            source_text=str((original or {}).get("text") or ""),
        )

        if family == "FIGURE" and (original or {}).get("figure_text"):
            notes = (notes + "\n" if notes else "") + "Text in the figure: " + str(original["figure_text"])[:600]
        if imp.get("think"):
            notes = (notes + "\n" if notes else "") + f"Ask the class: {imp['think']}"
        plan.slides.append(SlidePlan(
            index=i, title=title, treatment=treatment, family=family, variant=variant,
            params=params, data=data,
            animation=animation, transition=transition, transition_reason=reason,
            summary_directive=directive, verbatim=verbatim, speaker_notes=notes,
            est_seconds=est, is_section_start=is_section, confidence=engine_conf,
            visual_reason=visual_reason, visual_alternatives=[[f, round(c, 2)] for f, c in visual_alts],
        ))
        if is_section:
            plan.section_starts.append(i)

        prev_entry, prev_words = entry, curr_words

    plan.est_minutes = total_seconds / 60.0
    logger.info(
        "deck director: %d slides, %d section(s), ~%.1f min",
        len(plan.slides), len(plan.section_starts), plan.est_minutes,
    )
    return plan


__all__ = [
    "SlidePlan",
    "DeckPlan",
    "plan_deck",
    "choose_transition",
    "choose_summary_directive",
    "build_speaker_notes",
    "TRANSITIONS",
]
