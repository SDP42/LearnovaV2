"""
Text-treatment policy: decide, per sentence, whether the wording must be kept
verbatim or may be tightened / restructured.

The pipeline already preserves numbers and proper nouns. This adds the harder
cases where the *sentence itself* is the content and paraphrasing it would be
wrong: definitions, theorem / law statements, direct quotations, legal or
regulatory wording, code, and formulas expressed in prose.

No LLM. Deterministic. Mirrors DECISION 3 of ``ai/master_prompt.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_SENT = re.compile(r"(?<=[.!?][\"'”’)\]])\s+|(?<=[.!?])\s+")

# Cues that a sentence is precision-critical.
_DEFINITION = re.compile(
    r"\b(is|are)\s+defined\s+as\b|\bis\s+the\s+(?:process|measure|study|ratio|"
    r"rate|amount|degree)\s+of\b|\brefers?\s+to\b|\bmeans\s+that\b|"
    r"\bis\s+a\s+term\s+(?:for|used)\b|\bdenoted\s+by\b|\bis\s+known\s+as\b",
    re.I,
)
_LAW = re.compile(
    r"\b(law|theorem|lemma|axiom|principle|postulate|corollary|rule)\s+(of|states|:)"
    r"|\bstates\s+that\b|\bif\s+and\s+only\s+if\b|\bfor\s+all\b|\bthere\s+exists\b",
    re.I,
)
_QUOTE = re.compile(r"[\"“][^\"”]{12,}[\"”]|(?:wrote|said|stated|remarked|argued)\s*[:,]\s*[\"“]")
_LEGAL = re.compile(
    r"\b(shall|must not|is prohibited|is required to|pursuant to|"
    r"in accordance with|subject to|notwithstanding|hereby|thereof|"
    r"Section\s+\d|Article\s+\d|Clause\s+\d)\b",
)
_CODE = re.compile(r"[{}();]|=>|::|\bdef \b|\breturn \b|\bimport \b|`[^`]+`|\bSELECT\b.+\bFROM\b")
_FORMULA = re.compile(
    r"[A-Za-z]\s?=\s?[A-Za-z0-9]|[=≈≤≥±×÷√∑∫∂πΔ]|"
    r"\b\d+\s?[+\-*/^]\s?\d+\b|\bproportional to\b|\bequals\b(?!\s+the\s+number)",
)

_TREATMENTS = ("VERBATIM", "TIGHTEN", "MERGE")


@dataclass(frozen=True)
class SentenceTreatment:
    text: str
    treatment: str          # one of _TREATMENTS
    reason: str


def _reason_for(sent: str) -> str | None:
    if _QUOTE.search(sent):
        return "direct quotation"
    if _DEFINITION.search(sent):
        return "definition — exact wording carries the meaning"
    if _LAW.search(sent):
        return "law / theorem statement"
    if _LEGAL.search(sent):
        return "legal / regulatory wording"
    if _CODE.search(sent):
        return "code"
    if _FORMULA.search(sent):
        return "formula in prose"
    return None


def classify_sentences(text: str) -> List[SentenceTreatment]:
    """Label every sentence VERBATIM / TIGHTEN / MERGE."""
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return []
    sentences = [s.strip() for s in _SENT.split(raw) if s.strip()]

    out: List[SentenceTreatment] = []
    seen_norm: dict[str, int] = {}
    for s in sentences:
        norm = re.sub(r"[^a-z0-9 ]", "", s.lower())
        reason = _reason_for(s)
        if reason:
            out.append(SentenceTreatment(s, "VERBATIM", reason))
        elif norm in seen_norm or _near_dup(norm, seen_norm):
            out.append(SentenceTreatment(s, "MERGE", "near-duplicate of an earlier sentence"))
        else:
            out.append(SentenceTreatment(s, "TIGHTEN", "explanatory prose"))
        seen_norm[norm] = len(out) - 1
    return out


def _near_dup(norm: str, seen: dict[str, int]) -> bool:
    words = set(norm.split())
    if len(words) < 4:
        return False
    for prev in seen:
        pw = set(prev.split())
        if len(pw) < 4:
            continue
        # containment (one sentence is the other plus a few words) or high overlap
        if words <= pw or pw <= words:
            return True
        if len(words & pw) / len(words | pw) >= 0.72:
            return True
    return False


def protect_verbatim(text: str) -> List[str]:
    """Return just the sentences that must not be edited or trimmed."""
    return [t.text for t in classify_sentences(text) if t.treatment == "VERBATIM"]


def treatment_summary(text: str) -> dict:
    """Counts by treatment — handy for logging and the studio UI."""
    counts = {t: 0 for t in _TREATMENTS}
    for t in classify_sentences(text):
        counts[t.treatment] += 1
    return counts


__all__ = [
    "SentenceTreatment",
    "classify_sentences",
    "protect_verbatim",
    "treatment_summary",
]
