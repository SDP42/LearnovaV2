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
    from learnova.ai.escalation import mode

    if mode() == "off":                     # LEARNOVA_AI_MODE=off: never call a model
        return False
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


def enrich_slides(items: List[Dict[str, str]], max_slides: int = 15) -> Dict[int, Dict[str, Any]]:
    """
    ONE request that adds understanding to thin slides: a short worked example and plain-language definitions of the
    technical terms used. ``items``: [{"id", "title", "text"}]. Returns {id: {"example": str, "terms": [{term, definition}]}}.
    """
    if not items or not llm_available():
        return {}
    system = ("You help students understand lecture slides. For each slide return (a) one concrete example or analogy "
              "(max 28 words) that makes the idea tangible and is consistent with the slide, and (b) up to 2 technical terms "
              "from the slide with a plain-language definition (max 18 words each). Never contradict or replace the slide's "
              "content; if unsure, return an empty example. Reply ONLY with a JSON array "
              "[{\"id\":0,\"example\":\"...\",\"terms\":[{\"term\":\"...\",\"definition\":\"...\"}]}].")
    prompt = "\n\n".join(f"### id={s['id']} · {s['title']}\n{s['text'][:600]}" for s in items[:max_slides])
    try:
        raw = get_router().generate(prompt, system_prompt=system, task=TASK_IMPROVE, temperature=0.3, max_tokens=1800, timeout=45.0)
    except Exception as exc:
        logger.info("assist.enrich_slides failed: %s", exc)
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for item in _json_block(raw) or []:
        try:
            sid = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
        ex = str(item.get("example") or "").strip()
        terms = [{"term": str(t["term"]).strip()[:40], "definition": str(t["definition"]).strip()[:140]}
                 for t in (item.get("terms") or []) if isinstance(t, dict) and t.get("term") and t.get("definition")][:2]
        if (ex and len(ex.split()) <= 45) or terms:
            out[sid] = {"example": ex if len(ex.split()) <= 45 else "", "terms": terms}
    return out


_AI_POLISH_SYSTEM = (
    "You improve lecture slides for students, using ONLY each slide's own content. For every slide return:\n"
    "- title: an assertion title — a full sentence WITH A VERB, 6 to 14 words, sentence case, no trailing period, that states the "
    "slide's main point so a student learns it from the title alone. Good: 'Dijkstra's algorithm finalises the closest unvisited node "
    "at each step', 'Bellman-Ford handles negative weights but runs slower than Dijkstra'. Bad (topic labels): 'Dijkstra's algorithm', "
    "'Shortest paths in a weighted graph', 'Applications of shortest paths'. Also bad (instructions): 'Identify the shortest route', "
    "'Compare Dijkstra and Bellman-Ford'. Write a STATEMENT whose subject is the topic, never a command. Keep technical terms.\n"
    "- explain: ONLY if the slide has fewer than 60 words: 3 or 4 plain sentences (max 85 words) that unpack the slide's own idea "
    "for a beginner (what it is, why it matters, how it works); otherwise an empty string. Never add facts that contradict or go "
    "beyond the slide's topic.\n"
    "- example: one concrete example or analogy (max 30 words) consistent with the slide, or an empty string.\n"
    "- terms: up to 2 technical terms from the slide with plain definitions (max 18 words each).\n"
    "Reply ONLY with a JSON array [{\"id\":0,\"title\":\"...\",\"explain\":\"...\",\"example\":\"...\",\"terms\":[{\"term\":\"...\",\"definition\":\"...\"}]}]."
)


_IMPERATIVE = {"identify", "compare", "apply", "set", "guarantee", "use", "learn", "understand", "explore", "find", "calculate", "discover",
               "define", "explain", "describe", "review", "consider", "examine", "analyse", "analyze", "determine", "recognize", "recognise",
               "implement", "build", "create", "choose", "select", "remember", "note", "know", "see", "look", "let's", "lets", "discuss"}


def _content_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())} - {"this", "that", "with", "from", "they", "have", "which", "their", "there", "these", "those", "into", "about", "what", "when", "where"}


def ai_polish(slides: List[Dict[str, str]], batch: int = 10, max_slides: int = 80) -> Dict[int, Dict[str, Any]]:
    """Assertion titles, a plain-words explanation for thin slides, an example and key terms — in batches, grounded in each
    slide's own words. ``slides``: [{"id", "title", "text"}]. Slides whose answer fails a check (or a batch that fails because a
    quota ran out) are simply left out, so the rule-based version stays."""
    if not slides or not llm_available():
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for start in range(0, min(len(slides), max_slides), batch):
        chunk = slides[start:start + batch]
        prompt = "\n\n".join(f"### id={s['id']} · {s['title']} · {len(s['text'].split())} words\n{s['text'][:900]}" for s in chunk)
        try:
            raw = get_router().generate(prompt, system_prompt=_AI_POLISH_SYSTEM, task=TASK_IMPROVE, temperature=0.3, max_tokens=2600, timeout=60.0)
        except Exception as exc:
            logger.info("assist.ai_polish stopped (%s); remaining slides keep the rule-based version", exc)
            break
        by_id = {s["id"]: s for s in chunk}
        raw = (raw or "").translate({0x2011: "-", 0x2010: "-", 0x2012: "-", 0x00A0: " ", 0x202F: " "})   # glyphs many fonts lack
        for item in _json_block(raw) or []:
            try:
                sid = int(item["id"])
            except (KeyError, TypeError, ValueError):
                continue
            src = by_id.get(sid)
            if not src:
                continue
            words = _content_words(src["title"] + " " + src["text"])
            res: Dict[str, Any] = {}
            title = re.sub(r"[.\s]+$", "", str(item.get("title") or "").strip())
            first = title.split()[0].lower() if title else ""
            if (4 <= len(title.split()) <= 15 and len(title) <= 100 and len(_content_words(title) & words) >= 1
                    and first not in _IMPERATIVE):                  # a command, or a title too long for two lines, keeps the source heading
                res["title"] = title
            ex = str(item.get("explain") or "").strip()
            if ex and len(ex.split()) <= 100 and len(_content_words(ex) & words) >= 2:
                res["explain"] = ex
            eg = str(item.get("example") or "").strip()
            if eg and len(eg.split()) <= 40:
                res["example"] = eg
            terms = [{"term": str(t["term"]).strip()[:40], "definition": str(t["definition"]).strip()[:140]}
                     for t in (item.get("terms") or []) if isinstance(t, dict) and t.get("term") and t.get("definition")][:2]
            if terms:
                res["terms"] = terms
            if res:
                out[sid] = res
    return out
