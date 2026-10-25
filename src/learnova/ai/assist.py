"""
LLM assist layer — optional, batched, cached, validated.

The deterministic engine decides every slide on its own. When a provider is configured this layer
*improves* it, using as few requests as possible:

* ``refine_visuals``  — ONE request for all slides the engine is unsure about: the model picks the
  visual family and returns the data; the answer is validated against the renderers and discarded if
  it does not draw.
* ``polish_takeaways`` — ONE request that writes a sharp one-line takeaway per slide.
* ``improve_slide``   — per-click helper behind the app's "Improve with AI" button.

Identical requests are answered from the router's disk cache. With no provider every function
returns ``{}`` / the input unchanged, so nothing here can break a build.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from learnova.logging_config import logger
from learnova.providers.router import TASK_IMPROVE, TASK_VISUAL_DATA, get_router

# family → the exact data shape its renderer reads
FAMILY_SHAPES: Dict[str, str] = {
    "PROCESS_LINEAR": '{"stages":[{"label":"","detail":""}]}',
    "PROCESS_CYCLIC": '{"stages":[{"label":"","detail":""}]}',
    "TIMELINE": '{"events":[{"date":"","title":""}]}',
    "COMPARE_TABLE": '{"headers":["A","B"],"rows":[["",""]]}',
    "COMPARE_VISUAL": '{"pros":[""],"cons":[""]}',
    "MATRIX_GRID": '{"quadrants":[{"title":"","items":[""]}],"x_axis":["",""],"y_axis":["",""]}',
    "LAYERS": '{"levels":[{"label":"","detail":""}]}',
    "FUNNEL": '{"stages":[{"label":"","value":""}]}',
    "STAT_TILES": '{"tiles":[{"value":"","label":"","detail":""}]}',
    "CHART_CATEGORICAL": '{"points":[{"label":"","value":0}]}',
    "CHART_TREND": '{"points":[{"label":"","value":0}]}',
    "CHART_PART_TO_WHOLE": '{"points":[{"label":"","value":0}]}',
    "DEFINITION": '{"term":"","definition":"","notes":[""]}',
    "FORMULA_CALLOUT": '{"term":"","statement":"","formula":"","notes":[""]}',
    "CAUSE_EFFECT": '{"nodes":[{"label":"","detail":""}],"loop":false}',
    "CHECKLIST": '{"items":[{"text":""}]}',
    "KEY_POINTS": '{"cards":[{"heading":"","body":""}]}',
    "SET_DIAGRAM": '{"items":[""]}',
}
_STUB_THEME = SimpleNamespace(primary_hex="#2563EB", accent_hex="#FFC93C", card_bg_hex="#FFFFFF", text_hex="#0F172A",
                              subtext_hex="#475569", bg_hex="#F7FAFF")


def llm_available() -> bool:
    try:
        return bool(get_router().available)
    except Exception:
        return False


def _json_block(raw: str) -> Any:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    m = re.search(r"[\[{][\s\S]*[\]}]", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def _draws(family: str, data: Dict[str, Any]) -> bool:
    from learnova.rendering.family_blocks import render_family_block

    try:
        return bool(data) and render_family_block(family, data, _STUB_THEME) is not None
    except Exception:
        return False


def refine_visuals(slides: List[Dict[str, str]], max_slides: int = 12) -> Dict[int, Dict[str, Any]]:
    """
    ``slides``: [{"id": int, "title": str, "text": str}] the engine was unsure about.
    Returns {id: {"family", "variant", "data"}} for the answers that validate.
    """
    if not slides or not llm_available():
        return {}
    batch = slides[:max_slides]
    shapes = "\n".join(f"- {f}: {s}" for f, s in FAMILY_SHAPES.items())
    system = ("You design presentation slides. For each slide pick the ONE visual family that best fits its content "
              "and return the data to draw it, using ONLY facts in the slide text (never invent numbers). "
              "Never choose plain text. Families and their exact JSON shapes:\n" + shapes +
              "\nReply with ONLY a JSON array: [{\"id\":0,\"family\":\"...\",\"data\":{...}}]. No prose, no fences.")
    prompt = "\n\n".join(f"### id={s['id']} · {s['title']}\n{s['text'][:900]}" for s in batch)
    try:
        raw = get_router().generate(prompt, system_prompt=system, task=TASK_VISUAL_DATA, temperature=0.1, max_tokens=1800, timeout=40.0)
    except Exception as exc:
        logger.info("assist.refine_visuals failed: %s", exc)
        return {}
    arr = _json_block(raw)
    out: Dict[int, Dict[str, Any]] = {}
    for item in arr if isinstance(arr, list) else []:
        try:
            fam, data, sid = str(item["family"]).upper(), item["data"], int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if fam in FAMILY_SHAPES and isinstance(data, dict) and _draws(fam, data):
            out[sid] = {"family": fam, "variant": "llm", "data": data}
    logger.info("assist.refine_visuals: %d/%d answers validated", len(out), len(batch))
    return out


def polish_takeaways(slides: List[Dict[str, str]]) -> Dict[int, str]:
    """One request: a sharp takeaway (≤ 18 words) for each slide."""
    if not slides or not llm_available():
        return {}
    system = ("Write ONE takeaway sentence (max 18 words) per slide: the single thing the audience should remember, "
              "specific and concrete, not a restatement of the title. Use only the slide's own facts. "
              "Reply ONLY with a JSON array [{\"id\":0,\"takeaway\":\"...\"}].")
    prompt = "\n\n".join(f"### id={s['id']} · {s['title']}\n{s['text'][:700]}" for s in slides[:40])
    try:
        raw = get_router().generate(prompt, system_prompt=system, task=TASK_IMPROVE, temperature=0.3, max_tokens=1500, timeout=40.0)
    except Exception as exc:
        logger.info("assist.polish_takeaways failed: %s", exc)
        return {}
    out: Dict[int, str] = {}
    for item in _json_block(raw) or []:
        try:
            t = str(item["takeaway"]).strip()
            if 3 <= len(t.split()) <= 30:
                out[int(item["id"])] = t
        except (KeyError, TypeError, ValueError):
            continue
    return out


def improve_slide(title: str, bullets: List[str], instruction: str = "Make it clearer and more concise.",
                  audience: str = "") -> Optional[Dict[str, Any]]:
    """Rewrite one slide on request. Returns {"title", "bullets"} or None (no provider / bad answer)."""
    if not llm_available():
        return None
    system = ("You rewrite one presentation slide. Keep every fact, number, date and formula; change only wording and structure "
              "as instructed. Reply ONLY with JSON {\"title\":\"...\",\"bullets\":[\"...\"]} — 3 to 6 bullets of at most 22 words.")
    prompt = f"Instruction: {instruction}\nAudience: {audience or 'general'}\nTitle: {title}\nBullets:\n" + "\n".join(f"- {b}" for b in bullets)
    try:
        raw = get_router().generate(prompt, system_prompt=system, task=TASK_IMPROVE, temperature=0.4, max_tokens=700, timeout=30.0)
    except Exception as exc:
        logger.info("assist.improve_slide failed: %s", exc)
        return None
    obj = _json_block(raw)
    if isinstance(obj, dict) and obj.get("bullets"):
        return {"title": str(obj.get("title") or title)[:120], "bullets": [str(b)[:200] for b in obj["bullets"]][:8]}
    return None


def improve_prompt(text: str) -> Dict[str, Any]:
    """Turn a rough topic/prompt into a well-specified one. LLM when available, otherwise a rule-based nudge."""
    text = (text or "").strip()
    if not text:
        return {"text": "", "llm": False, "hints": ["Paste a syllabus, a topic, or upload a file."]}
    if llm_available():
        system = ("Rewrite the user's request for an AI presentation maker. Keep their topic and every fact; add the likely audience, "
                  "level, and the 5-8 sections a good deck on it needs, as a short outline. Reply with plain text only.")
        try:
            raw = get_router().generate(text[:1500], system_prompt=system, task=TASK_IMPROVE, temperature=0.4, max_tokens=500, timeout=30.0)
            if raw and raw.strip():
                return {"text": raw.strip(), "llm": True, "hints": []}
        except Exception as exc:
            logger.info("assist.improve_prompt failed: %s", exc)
    hints = []
    if len(text.split()) < 8:
        hints.append("Add the audience (e.g. 'for first-year engineering students').")
    if not re.search(r"\b(slides?|sections?|lecture|minutes?)\b", text, re.I):
        hints.append("Say how long it should be (e.g. '10 slides' or 'a 30-minute lecture').")
    if "\n" not in text and len(text) < 120:
        hints.append("A bulleted list of topics gives the best structure.")
    return {"text": text, "llm": False, "hints": hints}
