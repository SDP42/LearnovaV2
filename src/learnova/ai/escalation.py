"""
Offline first, AI only when the offline result is weak.

Every place that can call a language model asks this module first. The rule-based result is always computed; a model is
called only when a check here says that result is not good enough. ``LEARNOVA_AI_MODE`` sets the policy:

* ``auto``   (default) — escalate only on a weak offline result;
* ``always`` — use the model wherever a key exists (the old behaviour);
* ``off``    — never call a model.

Checks, one per place a model can help:

=====================  ======================================================================================
place                  the offline result is weak when …
=====================  ======================================================================================
picture reading        Tesseract's text does not read as language (``textutils.is_readable``)
titles / explanation   the title is a bare topic label, a counter or generic, or the slide is thin (< 60 words)
topic diagram          the slide needs a mechanism drawn (flow, plot, anatomy, comparison), which offline scenes cannot do
lab                    the slide has too little structure for the offline step-through lab
visual choice          the decision engine's confidence is below 0.7 (``pipeline.visual_data_stage``)
explainer              no exact solver recognises the problem (``rendering.deck_director``)
=====================  ======================================================================================
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any, Dict, List

STATS: Counter = Counter()          # escalated / kept-offline counts per place, for the run log and the paper


def mode() -> str:
    m = os.getenv("LEARNOVA_AI_MODE", "auto").strip().lower()
    return m if m in {"auto", "always", "off"} else "auto"


def _note(place: str, escalate: bool) -> bool:
    STATS[f"{place}:{'ai' if escalate else 'offline'}"] += 1
    return escalate


def should_escalate(place: str, weak: bool) -> bool:
    """True when a model should be called for ``place`` given whether the offline result is ``weak``."""
    m = mode()
    if m == "off":
        return _note(place, False)
    return _note(place, True if m == "always" else bool(weak))


# ── checks ──────────────────────────────────────────────────────────────────
def ocr_is_weak(text: str) -> bool:
    from learnova.textutils import is_readable

    return not is_readable(text or "")


_GENERIC = re.compile(r"^(?:introduction|overview|example|examples|summary|contd\.?|continued|notes?|slide \d+|untitled|"
                      r"definition|definitions|types|advantages|disadvantages|applications?|problem|solution)$", re.I)
_VERB = re.compile(r"\b(?:is|are|was|were|has|have|uses?|makes?|gives?|shows?|predicts?|measures?|reduces?|increases?|changes?|"
                   r"depends?|means|keeps?|splits?|finds?|chooses?|learns?|minimi[sz]es|maximi[sz]es|converts?|forms?|causes?|"
                   r"leads?|requires?|balances?|controls?|describes?|represents?|estimates?|works?|helps?)\b", re.I)


def title_is_weak(title: str) -> bool:
    """A topic label ('Linear Regression'), a counter ('(2/3)', 'continued') or a generic heading — not a statement of the point."""
    t = re.sub(r"\s*\((?:\d+/\d+|continued)\)\s*$", "", (title or "").strip(), flags=re.I)
    words = t.split()
    if not words or _GENERIC.match(t) or len(words) < 5:
        return True
    return not _VERB.search(t)


def slide_is_thin(text: str) -> bool:
    return len((text or "").split()) < 60


def polish_needed(title: str, text: str) -> bool:
    return title_is_weak(title) or slide_is_thin(text)


def diagram_needed(title: str, text: str, family: str = "") -> bool:
    """Offline scenes are good generic pictures; a slide about a mechanism, a graph, parts or a contrast needs a real drawing."""
    from learnova.ai.topic_art import art_kind

    return art_kind(title, text, family) in {"FLOW", "PLOT", "ANATOMY", "COMPARE"}


def offline_lab_ok(items: List[Dict[str, Any]], kind: str) -> bool:
    if len(items) < 3:
        return False
    return kind != "concepts" or sum(1 for x in items if x.get("body")) >= 3


def summary() -> Dict[str, int]:
    return dict(STATS)


__all__ = ["mode", "should_escalate", "ocr_is_weak", "title_is_weak", "slide_is_thin", "polish_needed", "diagram_needed",
           "offline_lab_ok", "summary", "STATS"]
