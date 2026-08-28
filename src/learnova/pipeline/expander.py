"""
Expansion pass — the anti-summariser.

The layout stage keeps every teachable point but writes each as a compact
bullet. For a lesson that is meant to *teach* (typed notes, a worked example),
a four-word step like "Isolate x" is not enough on its own — the learner needs
"Isolate x by subtracting 3 from both sides, so the variable term stands
alone."

This stage takes the terse bullets and asks the LLM to expand each into one
complete teaching sentence that keeps the original fact and adds the *why* /
*how*, without inventing new facts. Already-full sentences are left alone.

It is:
  * **opt-in** — only runs when ``content_mode == "expand"`` or the density
    profile is ``teaching``;
  * **LLM-backed** — no provider ⇒ the deck is unchanged;
  * **bounded** — one call per slide, first ``max_slides`` only, sequential
    (httpx connection-pool safety on macOS);
  * **safe** — a bad or mismatched response leaves that slide's bullets as they
    were. Numbers, currency and formulae are preserved verbatim by instruction
    and re-checked afterwards.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from learnova.logging_config import logger
from learnova.providers.router import TASK_ENHANCE, get_router

MAX_EXPANDED_SLIDES = 10

# A bullet at or below this many words is a candidate for expansion.
_TERSE_WORDS = 11

_SYSTEM_PROMPT = """\
You are a patient teacher turning terse slide bullets into full teaching points.

For EACH numbered bullet you are given, return one rewritten bullet:
- If the bullet is already a complete explanatory sentence (roughly 14+ words
  that includes the reasoning), return it UNCHANGED.
- If it is terse (a fragment, a bare instruction, a label), expand it into ONE
  complete sentence of about 16-28 words that keeps the original fact and adds
  the WHY or the HOW a teacher would say out loud. Keep ordered-step wording
  ("first", "then", "next", "finally") if present.

HARD RULES:
- Do NOT invent facts, numbers, names or results that are not implied by the
  bullet or the slide title.
- Reproduce every number, currency amount, symbol and formula EXACTLY.
- One sentence per bullet. Plain text — no markdown, no bullet characters.
- Return the SAME NUMBER of bullets, in the SAME ORDER.

Return ONLY a JSON array of strings. Nothing else."""

_NUM = re.compile(r"\d+(?:[.,]\d+)?%?|[$₹€£¥]\s?\d[\d.,]*")


def _resolve_provider():
    try:
        router = get_router()
        return router if router.available else None
    except Exception:
        return None


def _is_terse(bullet: str) -> bool:
    b = bullet.strip()
    if not b:
        return False
    words = b.split()
    if len(words) <= _TERSE_WORDS:
        return True
    # A longer line that is still just a noun phrase (no verb-ish cue, no
    # sentence-ending punctuation) also reads as terse.
    return not b.endswith((".", "!", "?")) and len(words) <= _TERSE_WORDS + 4


def _numbers(text: str) -> set:
    return set(_NUM.findall(text or ""))


def _expand_slide_bullets(title: str, bullets: List[str], provider) -> Optional[List[str]]:
    numbered = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(bullets))
    try:
        raw = provider.generate(
            prompt=f"Slide title: {title}\n\nBullets:\n{numbered}",
            system_prompt=_SYSTEM_PROMPT,
            task=TASK_ENHANCE,
            temperature=0.3,
            max_tokens=200 + 90 * len(bullets),
            timeout=30.0,
            reasoning_effort="medium",
        )
    except Exception as exc:
        msg = str(exc).lower()
        if any(k in msg for k in ("429", "rate", "quota", "tokens per")):
            raise  # let the caller stop expanding rather than grind through 429s
        logger.warning("expander: LLM call failed (%s)", exc)
        return None

    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return None
    try:
        out = json.loads(m.group(0))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(out, list) or len(out) != len(bullets):
        return None

    result: List[str] = []
    for original, expanded in zip(bullets, out):
        expanded = str(expanded).strip().lstrip("-•*").strip()
        # Reject an expansion that dropped or changed a number/currency token,
        # or that came back shorter than the original, or empty.
        if (not expanded
                or len(expanded) < len(original)
                or not _numbers(original) <= _numbers(expanded)):
            result.append(original)
        else:
            result.append(expanded)
    return result


def expand_deck(
    deck: List[dict],
    *,
    density: str = "medium",
    content_mode: str = "compress",
    max_slides: int = MAX_EXPANDED_SLIDES,
) -> int:
    """
    Expand terse bullets across the deck, in place. Returns the number of slides
    whose bullets were changed.
    """
    if content_mode != "expand" and str(density).lower() != "teaching":
        logger.info("expansion skipped: content_mode=%r density=%r", content_mode, density)
        return 0

    provider = _resolve_provider()
    if provider is None:
        logger.info("expansion skipped: no LLM provider available")
        return 0

    changed = 0
    for entry in deck:
        if changed >= max_slides:
            logger.info("expansion capped at %d slide(s)", max_slides)
            break

        improved = entry.get("improved") if isinstance(entry.get("improved"), dict) else None
        if not improved:
            continue
        if str(improved.get("layout_type", "")).upper() == "QUIZ":
            continue
        if improved.get("inline_quiz"):
            pass  # still fine to expand the slide's own bullets

        bullets = [str(b) for b in (improved.get("bullets") or []) if str(b).strip()]
        if len(bullets) < 1 or not any(_is_terse(b) for b in bullets):
            continue

        title = str(improved.get("title") or "")
        try:
            expanded = _expand_slide_bullets(title, bullets, provider)
        except Exception:
            logger.info("expansion stopped early — provider rate-limited")
            break
        if expanded and expanded != bullets:
            improved["bullets"] = expanded
            changed += 1

    logger.info("expansion rewrote bullets on %d slide(s)", changed)
    return changed


__all__ = ["expand_deck", "MAX_EXPANDED_SLIDES"]
