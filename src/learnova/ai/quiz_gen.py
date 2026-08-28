"""
Quiz Generator Module for Learnova
Uses Groq to create MCQ quizzes and interleave checkpoint slides.

IMPORTANT: Do NOT use ThreadPoolExecutor here.
httpx.Client has internal keepalive connection pool background threads. When a ThreadPoolExecutor
exits and Python GC destroys the GroqProvider (httpx client), those background threads crash
macOS with exit code 139 (SIGSEGV). Sequential processing with module-level singleton is safe.
"""

import json
import os
import re
import time
from dotenv import load_dotenv
from learnova.providers.base import LLMProvider
from learnova.providers.router import TASK_QUIZ, get_router
from learnova.logging_config import logger

load_dotenv()

DELAY_BETWEEN_CALLS = 0.5

SYSTEM_PROMPT = (
    "You are an educational quiz designer writing ONE multiple-choice question "
    "that checks whether a learner understood the key idea in the content.\n"
    "Rules:\n"
    "- Test understanding, not trivia recall. The stem should require reasoning.\n"
    "- All four options must be plausible to someone who half-learned the "
    "material: distractors are common misconceptions or near-misses on the SAME "
    "concept, never obviously silly.\n"
    "- 'explanation' says why the correct answer is right AND, in one clause each, "
    "why the other three are wrong.\n"
    "- 'difficulty' is one of: recall, apply, analyse.\n"
    "Return ONLY valid JSON:\n"
    '{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], '
    '"correct": "A", "explanation": "...", "difficulty": "apply"}'
)

# Module-level singleton router — created once and reused. Avoids
# creating/destroying httpx pools, which causes macOS segfaults.
#
# Distractor quality is what makes a checkpoint worth answering, so TASK_QUIZ
# prefers Nemotron Ultra and falls back to Groq. Going through the router also
# means a Groq 429 no longer costs the deck its quizzes.
_quiz_provider: LLMProvider | None = None

def _get_quiz_provider() -> LLMProvider | None:
    global _quiz_provider
    if _quiz_provider is None:
        router = get_router()
        if not router.available:
            logger.warning("No LLM provider configured — skipping quiz generation.")
            return None
        _quiz_provider = router
    return _quiz_provider


def _parse_llm_json(raw_response: str) -> dict | None:
    text = raw_response.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def generate_quizzes(improved_results: list[dict]) -> list[dict]:
    """
    Generate MCQs for improved slides.
    Sequential execution — safe on macOS with httpx connection pools.
    """
    provider = _get_quiz_provider()
    if not provider:
        return []

    # Group slides into batches of 3
    batches = []
    for batch_start in range(0, len(improved_results), 3):
        batches.append(improved_results[batch_start : batch_start + 3])

    quizzes = []

    for idx, batch in enumerate(batches):
        combined_parts = []
        source_slides = []

        for entry in batch:
            imp = entry["improved"]
            title = imp.get("title", "")
            bullets = "\n".join(f"- {b}" for b in imp.get("bullets", []))
            takeaway = imp.get("takeaway", "")
            combined_parts.append(f"{title}\n{bullets}\n{takeaway}".strip())
            source_slides.append(entry.get("original", {}).get("source", "?"))

        combined_content = "\n\n".join(combined_parts)

        try:
            raw_content = provider.generate(
                prompt=f"Content:\n{combined_content}",
                system_prompt=SYSTEM_PROMPT,
                task=TASK_QUIZ,          # router picks the model per provider
                temperature=0.3,
                max_tokens=400,
                timeout=20.0,
            )
            parsed = _parse_llm_json(raw_content)

            if parsed and "question" in parsed and "options" in parsed:
                raw_correct = str(parsed.get("correct", "A")).strip()
                match = re.search(r"([A-D])", raw_correct.upper())
                parsed["correct"] = match.group(1) if match else "A"
                parsed["difficulty"] = str(parsed.get("difficulty", "apply")).lower()
                parsed["source_slides"] = source_slides
                quizzes.append(parsed)
        except Exception as e:
            logger.error("Groq quiz call failed: %s", e)

        # Small delay between batches to respect TPM limits
        if idx < len(batches) - 1:
            time.sleep(DELAY_BETWEEN_CALLS)

    logger.info("Generated %d quiz(es)", len(quizzes))
    return quizzes


def _standalone_quiz_slide(q: dict, n: int) -> dict:
    return {
        "original": {"title": "Knowledge Checkpoint", "source": f"Quiz #{n}"},
        "improved": {
            "layout_type": "QUIZ",
            "title": f"Checkpoint {n}",
            "question": q.get("question", "What is the key takeaway so far?"),
            "options": q.get("options", ["Option A", "Option B", "Option C", "Option D"]),
            "correct": q.get("correct", "A"),
            "explanation": q.get("explanation", "Review the previous takeaways."),
            "difficulty": q.get("difficulty", "apply"),
            "takeaway": "Answer, then check your reasoning.",
        },
    }


def interleave_quizzes_into_slides(
    improved_results: list[dict],
    quizzes: list[dict],
    frequency: int = 4,
    inline: bool = True,
    positions: list[int] | None = None,
) -> list[dict]:
    """
    Attach a checkpoint question into the deck.

    Placement:
      * ``positions`` (1-indexed content-slide numbers) — a checkpoint goes in
        immediately AFTER each of those slides. This is the "put a quiz after
        slide 7" case the editor drives.
      * otherwise — one checkpoint after every ``frequency`` slides.

    Style:
      * ``inline=True`` (default) — a band at the foot of the slide that closes
        the run, keeping the slide count honest.
      * ``inline=False`` — a dedicated interactive QUIZ slide inserted after.
        Forced on when ``positions`` is given (a chosen checkpoint deserves its
        own slide).
    """
    if not quizzes:
        return improved_results

    if positions:
        inline = False
        wanted = {p for p in positions if isinstance(p, int) and p >= 1}
        final_deck: list[dict] = []
        quiz_idx = 0
        for pos, item in enumerate(improved_results, 1):
            final_deck.append(item)
            if pos in wanted and quiz_idx < len(quizzes):
                final_deck.append(_standalone_quiz_slide(quizzes[quiz_idx], quiz_idx + 1))
                quiz_idx += 1
        return final_deck

    final_deck: list[dict] = []
    quiz_idx = 0

    for position, slide_item in enumerate(improved_results, 1):
        item = slide_item
        due = position % frequency == 0 and quiz_idx < len(quizzes)

        if due and inline:
            q = quizzes[quiz_idx]
            quiz_idx += 1
            improved = dict(item.get("improved") or {})
            improved["inline_quiz"] = {
                "index": quiz_idx,
                "question": q.get("question", "What was the key idea in this section?"),
                "options": q.get("options", [])[:4],
                "correct": q.get("correct", "A"),
                "explanation": q.get("explanation", ""),
                "difficulty": q.get("difficulty", "apply"),
            }
            item = {**item, "improved": improved}

        final_deck.append(item)

        if due and not inline:
            final_deck.append(_standalone_quiz_slide(quizzes[quiz_idx], quiz_idx + 1))
            quiz_idx += 1

    return final_deck
