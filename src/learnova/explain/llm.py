"""Fallback explainer written by a language model, for problems no rule-based solver recognises.

Only used when a provider key is configured. The result is marked ``source="llm"`` so the page can say the numbers were
not computed by Learnova itself.
"""

from __future__ import annotations

from typing import Optional

from learnova.explain.model import Explainer, Step
from learnova.logging_config import logger

_SYSTEM = ("You are a patient tutor. Solve the problem for a complete beginner, one small step at a time. "
           "Reply ONLY with JSON: {\"kind\":\"short name of the problem type\",\"steps\":[{\"title\":\"short action\",\"math\":[\"working line\"],"
           "\"explain\":\"one or two plain sentences: why this step\",\"tip\":\"the rule behind it, optional\"}],\"answer\":\"final answer\","
           "\"recap\":[\"3 short reminders\"]}. 3 to 8 steps. Check your arithmetic.")


def llm_explain(problem: str) -> Optional[Explainer]:
    from learnova.ai import assist

    if not assist.llm_available():
        return None
    try:
        from learnova.ai.assist import TASK_IMPROVE, get_router

        raw = get_router().generate(f"Problem: {problem}", system_prompt=_SYSTEM, task=TASK_IMPROVE, temperature=0.2, max_tokens=1400, timeout=45.0)
    except Exception as exc:
        logger.info("explain.llm failed: %s", exc)
        return None
    obj = assist._json_block(raw)                                   # noqa: SLF001
    if not isinstance(obj, dict) or not obj.get("steps") or not obj.get("answer"):
        return None
    steps = [Step(str(s.get("title", ""))[:90], [str(m)[:160] for m in (s.get("math") or [])][:4], str(s.get("explain", ""))[:400], str(s.get("tip", ""))[:120])
             for s in obj["steps"][:8] if isinstance(s, dict) and s.get("title")]
    if len(steps) < 3:
        return None
    return Explainer(str(obj.get("kind") or "problem")[:40], problem, steps, str(obj["answer"])[:120], [str(r)[:100] for r in (obj.get("recap") or [])][:3], "llm")
