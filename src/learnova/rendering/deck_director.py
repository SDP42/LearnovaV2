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
        vms_source = "\n".join(
            p for p in (str((original or {}).get("text") or "").strip(),
                        "\n".join(bullets)) if p
        ) or text
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

        override_bar = 0.75 if _has_real_data else 0.6
        keep_existing = (
            existing_layout not in {"MINIMAL_TEXT", "", "CARD_GRID"}
            and vd.confidence < override_bar
            and not (vms_has_payload and not hard_layout)
        )
        if keep_existing:
            treatment = existing_layout
            family, variant = TREATMENT_TO_FAMILY.get(existing_layout, (vd.family, vd.variant))
            data = {}
        else:
            treatment, family, variant = vd.treatment, vd.family, vd.variant
            data = vd.data or {}
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

        plan.slides.append(SlidePlan(
            index=i, title=title, treatment=treatment, family=family, variant=variant,
            params={}, data=data,
            animation=animation, transition=transition, transition_reason=reason,
            summary_directive=directive, verbatim=verbatim, speaker_notes=notes,
            est_seconds=est, is_section_start=is_section, confidence=vd.confidence,
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
