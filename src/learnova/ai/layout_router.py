"""
AI Layout Router Module for Learnova
Analyzes educational text chunks to classify content into dynamic visual layout types
and extracts visual attributes (Mermaid diagrams, Tables, Metric Stat Cards).

Hardened for production:
  - Extracts JSON from any model response (handles markdown fences, extra prose)
  - Retries once on parse failure with a tighter prompt
  - Falls back deterministically to a heuristic layout — never raises
"""

import json
import os
import re
import time
from typing import Optional

from dotenv import load_dotenv

from learnova.ai.diagram_gen import generate_mermaid_diagram
from learnova.logging_config import logger
from learnova.providers.base import LLMProvider
from learnova.providers.router import TASK_LAYOUT, get_router
from learnova.textutils import (
    clean_bullet,
    dedupe_bullets,
    is_redundant,
    strip_inline_markdown,
    strip_ocr_block,
    truncate_words,
)

load_dotenv()

# ── Module-level singleton ────────────────────────────────────────────────────
# Avoids creating/destroying httpx connection pools per chunk (macOS segfault
# fix). The router keeps Groq first for this task — classification runs once per
# chunk, so latency dominates — and falls through to NVIDIA NIM on a 429.
_llm_provider: Optional[LLMProvider] = None


def _get_llm_provider() -> Optional[LLMProvider]:
    """Return the cached router, or None when no API key is configured."""
    global _llm_provider
    if _llm_provider is None:
        router = get_router()
        if not router.available:
            logger.warning("No LLM provider configured — using heuristic layouts.")
            return None
        _llm_provider = router
    return _llm_provider


# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a Senior Master Instructional Designer and Educational Content Editor.
Your job is to transform raw presentation text, lecture notes, and OCR diagram \
descriptions into structured, visually engaging teaching material.

CRITICAL INSTRUCTIONS FOR CONTENT IMPROVEMENT:
1. KEEP EVERY TEACHABLE POINT. You are RESTRUCTURING, not summarising. Each distinct
   fact, definition, figure, step or example in the input MUST survive as its own
   bullet. Do NOT cap the list — emit as many bullets as the input has points.
   A later stage decides how many fit on a slide and moves the rest onto a
   continuation slide, so anything you drop here is lost from the deck entirely.
   You may only remove: exact repetition, filler words, and the slide's own title.
2. WRITE FULL TEACHING SENTENCES, NOT HEADLINES. Each bullet is one complete
   thought a teacher would say out loud — typically 15 to 30 words — and it KEEPS
   ITS REASONING: the "because ...", "so that ...", "which means ..." clause that
   explains WHY, and connectives like "first / then / next / finally" that show
   order. Do not strip a sentence down to a noun phrase. For a worked example or
   a derivation, keep every intermediate step as its own bullet in order — never
   jump from step 1 to the final answer.
   Preserve concrete numbers, currency amounts, formulas and proper nouns VERBATIM.
   Keep any "Label: detail" prefix intact — it becomes the card heading.
3. HIGH-YIELD TAKEAWAY: Formulate a single, high-yield summary sentence ("takeaway")
   that captures the core lesson. Leave it "" if the content has no single lesson.
4. DIAGRAM SYNTHESIS: If the input text contains visual diagram OCR (e.g., arrows, steps, flowcharts, architectures), extract the step-by-step node sequence accurately.
5. PLAIN TEXT ONLY: never emit markdown emphasis (**bold**, _italics_) inside a
   bullet, title or takeaway — it renders literally on the slide.

SELECT THE BEST VISUAL LAYOUT TYPE:
- "FLOWCHART": For process steps, workflows, cycles, algorithms, chemical/biological mechanisms.
- "TABLE": For comparisons, feature vs feature breakdowns, pros & cons, vs lists.
- "METRIC": For statistical callouts, numerical performance data, percentages, key metrics.
- "CARD_GRID": For 3 to 4 distinct conceptual pillars, key categories, or core principles.
- "MINIMAL_TEXT": For general descriptive text.

The layout choice does NOT limit how many bullets you return. Return them all.

Return ONLY valid JSON — no markdown fences, no extra text, nothing else.
Exact schema:
{
  "layout_type": "FLOWCHART" | "TABLE" | "METRIC" | "CARD_GRID" | "MINIMAL_TEXT",
  "title": "Clean High-Impact Slide Title",
  "takeaway": "Single high-yield key takeaway sentence.",
  "bullets": ["Point 1", "Point 2", "Point 3"],
  "table_data": {
    "headers": ["Feature / Aspect", "Category A", "Category B"],
    "rows": [
      ["Aspect 1", "Detail A1", "Detail B1"],
      ["Aspect 2", "Detail A2", "Detail B2"]
    ]
  },
  "metric_data": {
    "value": "95%",
    "label": "Key Benchmark Metric",
    "description": "Short explanation of why this metric matters."
  }
}
"""

RETRY_SYSTEM_PROMPT = """\
You must respond with ONLY a valid JSON object. No explanation, no markdown, no code fences.
Just the raw JSON starting with { and ending with }.

Schema:
{"layout_type":"MINIMAL_TEXT","title":"string","takeaway":"string","bullets":["string"]}
"""

# ── Valid layout types ─────────────────────────────────────────────────────────
_VALID_LAYOUTS = frozenset(["FLOWCHART", "TABLE", "METRIC", "CARD_GRID", "MINIMAL_TEXT"])

# ── Rate-limit circuit breaker ─────────────────────────────────────────────────
_groq_rate_limited = False


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(raw: str) -> Optional[dict]:
    """
    Robustly extract the first valid JSON object from a model response.

    Strategy (in order):
      1. Try raw string as-is (model returned clean JSON)
      2. Strip markdown fences (``` / ```json) and try again
      3. Regex scan for the outermost { … } block (handles extra prose)
      4. Return None if nothing works
    """
    if not raw or not raw.strip():
        return None

    attempts: list[str] = []

    # 1 — raw
    attempts.append(raw.strip())

    # 2 — strip markdown code fences (handles multiline ``` blocks)
    stripped = re.sub(r"```(?:json)?\s*", "", raw, flags=re.DOTALL | re.IGNORECASE)
    stripped = stripped.strip()
    attempts.append(stripped)

    # 3 — grab outermost { … } block via regex (handles extra prose before/after)
    brace_match = re.search(r"\{[\s\S]*\}", raw, re.DOTALL)
    if brace_match:
        attempts.append(brace_match.group(0))

    seen: set[str] = set()
    for candidate in attempts:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            continue

    return None


# ── Heuristic fallback ────────────────────────────────────────────────────────

# Abbreviations whose trailing period does not end a sentence. Splitting on a
# bare "." turned "Total no. of observations" into "Total no" / "of
# observations" — two meaningless bullets from one clear statement.
_ABBREVIATIONS = (
    "no", "nos", "fig", "eq", "vs", "etc", "approx", "e.g", "i.e", "cf",
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "vol", "ch", "sec",
    "min", "max", "avg", "std", "dept", "univ", "inc", "ltd", "co",
)

_ABBREV_SET = {a.replace(".", "") for a in _ABBREVIATIONS}

# Candidate sentence end: terminal punctuation followed by whitespace. Whether
# it is a *real* end is decided per match, because Python's `re` only supports
# fixed-width look-behind and the abbreviation list is variable width.
_SENTENCE_CANDIDATE = re.compile(r"[.!?](?=\s)")

_TRAILING_TOKEN = re.compile(r"([A-Za-z0-9.]+)$")


def _is_real_sentence_end(text: str, position: int) -> bool:
    before = text[:position]
    after = text[position + 1:].lstrip()

    # A new sentence does not start with a lowercase letter.
    if after and after[0].islower():
        return False

    match = _TRAILING_TOKEN.search(before)
    if not match:
        return True
    token = match.group(1)

    # Decimal number: "3.14" or a numbered label like "n1."
    if token and token[-1].isdigit():
        return False
    # Single capital initial: "J. Smith"
    if len(token) == 1 and token.isupper():
        return False
    # Known abbreviation: "no.", "fig.", "vs."
    if token.replace(".", "").lower() in _ABBREV_SET:
        return False
    return True


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences without breaking abbreviations or decimals."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []

    sentences, start = [], 0
    for match in _SENTENCE_CANDIDATE.finditer(cleaned):
        if not _is_real_sentence_end(cleaned, match.start()):
            continue
        piece = cleaned[start:match.start() + 1].strip(" .;:")
        if piece:
            sentences.append(piece)
        start = match.end()

    tail = cleaned[start:].strip(" .;:")
    if tail:
        sentences.append(tail)
    return sentences


def parse_pipe_table(text: str) -> tuple[list, list]:
    """
    Extract a real ``| a | b |`` table from text. Returns ([], []) if absent.

    Only genuine tabular rows qualify. Previously any mention of "table" or
    "vs" routed a slide to the TABLE layout, which then fabricated a one-row
    placeholder — a fake table is worse than a plain bullet list.
    """
    rows = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.count("|") < 2:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        # Markdown separator row (---|---).
        if all(set(c) <= set("-: ") and c for c in cells):
            continue
        if any(cells):
            rows.append(cells)

    if len(rows) < 2:
        return [], []

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return rows[0], rows[1:]


def _heuristic_layout_type(text: str) -> str:
    lower = text.lower()

    process_kw = [
        r"step\s*1", r"\bfirst,", r"\bsecond,", r"\bprocess\b", r"\bworkflow\b",
        r"\bcycle\b", r"\balgorithm\b", r"\bsequence\b", r"\bpipeline\b",
        r"\bstage\b", r"\bmechanism\b", r"\bworkflow\b",
    ]
    if any(re.search(kw, lower) for kw in process_kw):
        return "FLOWCHART"

    # A table needs real rows, or an explicit whole-word comparison cue —
    # not a stray "vs" inside another word or a passing mention of "table".
    if parse_pipe_table(text)[1]:
        return "TABLE"
    table_kw = [
        r"\bvs\.?\b", r"\bversus\b", r"\bcomparison\b", r"\bcompared?\b",
        r"\bpros and cons\b", r"\bdifference between\b",
        r"\badvantages and disadvantages\b",
    ]
    if any(re.search(kw, lower) for kw in table_kw):
        return "TABLE"
    if re.search(r"\b\d+(?:\.\d+)?%|\b\d+\s*(?:percent|million|billion|k|x)\b", lower):
        return "METRIC"
    return "MINIMAL_TEXT"


def _build_fallback(text: str, current_title: str, layout_type: str) -> dict:
    """Build a fully-populated fallback result dict for the given layout_type."""
    # Prefer explicit line structure (a markdown list survives chunking as
    # newline-separated items); only fall back to sentence splitting for prose.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        items = lines
    else:
        items = split_sentences(text)

    # Do NOT cap here. The density stage owns per-slide budgets and moves any
    # overflow onto continuation slides; truncating at this point would delete
    # the user's content before it ever reaches that logic. The generous
    # ceiling only guards against a pathological chunk.
    result: dict = {
        "layout_type": layout_type,
        "title": current_title or "Overview",
        # No LLM here to write a real takeaway; a repeated filler line on every
        # slide is worse than none. Leave it blank.
        "takeaway": "",
        "bullets": items[:60],
    }
    if layout_type == "FLOWCHART":
        safe_t = re.sub(r"[^\w\s]", "", (current_title or "Process")[:30]) or "Start"
        nodes = [re.sub(r"[^\w\s]", "", i)[:24].strip() or "Step" for i in items[:4]]
        if len(nodes) > 1:
            chain = " --> ".join(
                f"{chr(65 + i)}[{label}]" for i, label in enumerate(nodes)
            )
            result["mermaid_code"] = f"graph TD\n  {chain}"
        else:
            result["mermaid_code"] = (
                f"graph TD\n  A[{safe_t}] --> B[Execute Steps] --> C[Key Outcome]"
            )
    elif layout_type == "TABLE":
        headers, rows = parse_pipe_table(text)
        if rows:
            result["table_headers"] = headers
            result["table_rows"] = rows
        else:
            # No real table in the text. A fabricated one-row "Item /
            # Description" table looks broken on a slide, so present the
            # content as ordinary bullets instead.
            result["layout_type"] = "MINIMAL_TEXT"
    elif layout_type == "METRIC":
        # Same principle as the table rule above: a metric slide is one huge
        # number, so without a real quantity there is nothing to show. It used
        # to print the literal words "Key Stat" at headline size.
        from learnova.pipeline.visual_planner import extract_quantity

        value = extract_quantity(text)
        if value:
            result["metric_value"] = value[:16]
            result["metric_label"] = current_title or "Metric"
            result["metric_desc"] = truncate_words(text, 120)
        else:
            result["layout_type"] = "MINIMAL_TEXT"
    return result


# ── LLM call helper ───────────────────────────────────────────────────────────

def _call_llm(
    prompt: str,
    system_prompt: str,
    max_tokens: int = 300,
    timeout: float = 8.0,
    reasoning_effort: str = "medium",
) -> Optional[str]:
    """
    Single classification call through the router. Returns the raw response
    string or None on failure.

    Raises ValueError with 'rate_limit' only when *every* provider is
    exhausted — the router fails over first, so a Groq 429 alone no longer
    trips the circuit breaker and drops the whole deck to heuristics.
    """
    global _groq_rate_limited
    provider = _get_llm_provider()
    if provider is None:
        raise ValueError("No LLM provider available")

    try:
        raw = provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            task=TASK_LAYOUT,        # router picks the model per provider
            temperature=0.2,
            max_tokens=max_tokens,
            timeout=timeout,
            # Full teaching-sentence bullets need the model to actually reason
            # about what to keep; "low" produced clipped noun phrases.
            reasoning_effort=reasoning_effort,
        )
        return raw
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("429", "rate_limit", "quota", "tokens per")):
            _groq_rate_limited = True
            logger.warning(
                "All providers rate-limited — switching to local heuristic for "
                "all remaining chunks"
            )
            raise ValueError("rate_limit")
        raise


def _restore_dropped_points(bullets: list[str], source: str) -> list[str]:
    """
    Put back source points the model omitted.

    Prompting alone does not reliably stop a model summarising: told to keep
    every point, it still returned 3 bullets for 8 sentences of input. So the
    result is checked against the source and anything unrepresented is appended
    verbatim. Rephrasing is kept where the model did the work; coverage is
    guaranteed regardless.
    """
    candidates = [s for s in split_sentences(source) if len(s.split()) >= 4]
    if not candidates:
        return bullets

    _STOP = {"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is",
             "are", "was", "were", "be", "as", "at", "by", "it", "its", "this",
             "that", "these", "those", "with", "from", "which", "such"}

    def _content_words(s: str) -> set:
        return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) > 2}

    covered = [_content_words(b) for b in bullets]

    def _already_said(cw: set) -> bool:
        if not cw:
            return True
        for other in covered:
            if not other:
                continue
            # Either this sentence is mostly covered by an existing bullet, or
            # an existing bullet is mostly a subset of this sentence (the model
            # paraphrased it shorter). Both mean "no new point here".
            if len(cw & other) >= 0.5 * len(cw):
                return True
            if len(cw & other) >= 0.6 * len(other):
                return True
        return False

    # Don't let restoration balloon a slide — past this the model clearly kept
    # the gist and the extras are mostly re-statements the density stage would
    # just paginate into filler.
    cap = max(len(bullets) + 6, 14)

    restored = list(bullets)
    for sentence in candidates:
        if len(restored) >= cap:
            break
        cleaned = clean_bullet(sentence)
        if not cleaned or is_redundant(cleaned, restored):
            continue
        cw = _content_words(cleaned)
        if _already_said(cw):
            continue
        restored.append(cleaned)
        covered.append(cw)

    if len(restored) > len(bullets):
        logger.info(
            "[layout_router] restored %d point(s) the model dropped (%d -> %d)",
            len(restored) - len(bullets), len(bullets), len(restored),
        )
    return restored


# ── Master-prompt path (opt-in via LEARNOVA_MASTER_PROMPT=1) ──────────────────

# Catalog family -> the legacy layout_type the current renderers understand.
_FAMILY_TO_LEGACY = {
    "PROCESS_LINEAR": "FLOWCHART", "PROCESS_CYCLIC": "FLOWCHART",
    "DECISION": "FLOWCHART", "STATE_MACHINE": "FLOWCHART",
    "COMPARE_TABLE": "TABLE", "MATRIX_GRID": "TABLE",
    "KPI": "METRIC",
    "LIST_STRUCTURED": "CARD_GRID", "MIND_MAP": "CARD_GRID",
    "HIERARCHY_NEST": "CARD_GRID", "HIERARCHY_TREE": "CARD_GRID",
}


def _classify_with_master_prompt(text: str, current_title: str) -> Optional[dict]:
    """Structure one chunk with the master prompt. Returns None to fall back."""
    from learnova.ai.master_prompt import (
        MASTER_RETRY_PROMPT,
        MASTER_SYSTEM_PROMPT,
        build_user_prompt,
    )

    ocr = ""
    m = re.search(r"<<FIGURE_TEXT>>(.*?)<<END_FIGURE_TEXT>>", text, re.S)
    if m:
        ocr = m.group(1).strip()
    elif "[Extracted OCR" in text:  # legacy marker
        ocr = text.split("[Extracted OCR", 1)[1].split(":", 1)[-1].rsplit("]", 1)[0]
    text = strip_ocr_block(text)  # never let the marker reach the bulletiser

    raw = _call_llm(build_user_prompt(text[:1600], current_title, ocr),
                    MASTER_SYSTEM_PROMPT, max_tokens=900, timeout=14.0)
    data = _extract_json(raw) if raw else None
    if data is None:
        raw = _call_llm(f"Text: {text[:600]}\n{current_title}", MASTER_RETRY_PROMPT, max_tokens=250)
        data = _extract_json(raw) if raw else None
    if data is None:
        return None

    family = str(data.get("family", "TEXT")).upper()
    legacy = _FAMILY_TO_LEGACY.get(family, "MINIMAL_TEXT")
    bullets = dedupe_bullets([str(b) for b in data.get("bullets", []) if str(b).strip()])
    bullets = _restore_dropped_points(bullets, text)

    result: dict = {
        "layout_type": legacy,
        "title": str(data.get("title", current_title or "Key Concept")).strip(),
        "takeaway": str(data.get("takeaway", "")).strip(),
        "bullets": bullets,
        # carried through for the Deck Director + expanded renderers
        "family": family,
        "variant": str(data.get("variant", "")),
        "params": data.get("params") or {},
        "verbatim": [str(v) for v in (data.get("verbatim") or [])],
        "animation": data.get("animation") or {},
        "visual_data": data.get("data") or {},
        "image_action": str(data.get("image_action", "NONE")),
        "visual_source": "master_prompt",
    }

    d = result["visual_data"]
    if legacy == "FLOWCHART":
        nodes = d.get("flowchart", {}).get("nodes") or []
        labels = [str(n.get("label", "")) for n in nodes if isinstance(n, dict)]
        if not labels:
            labels = [str(s) for s in (d.get("cycle", {}).get("stages") or [])]
        if not labels:
            labels = bullets[:6]
        clean = [re.sub(r'[\[\]{}()"|]', "", lbl)[:36].strip() or "Step" for lbl in labels[:6]]
        chain = " --> ".join(f"N{i}[{lbl}]" for i, lbl in enumerate(clean))
        result["mermaid_code"] = f"graph TD\n  {chain}" if chain else "graph TD\n  A[Start] --> B[End]"
    elif legacy == "TABLE":
        tbl = d.get("table", {})
        result["table_headers"] = [str(h) for h in tbl.get("headers", ["Aspect", "A", "B"])]
        result["table_rows"] = [[str(c) for c in r] for r in tbl.get("rows", []) if isinstance(r, (list, tuple))]
        if not result["table_rows"]:
            result["layout_type"] = "MINIMAL_TEXT"
    elif legacy == "METRIC":
        met = d.get("metric", {})
        from learnova.pipeline.visual_planner import extract_quantity

        val = extract_quantity(str(met.get("value", ""))) or extract_quantity(text)
        if val:
            result["metric_value"] = val[:16]
            result["metric_label"] = strip_inline_markdown(str(met.get("label", result["title"])))
            result["metric_desc"] = truncate_words(str(met.get("description") or result["takeaway"]), 120)
        else:
            result["layout_type"] = "MINIMAL_TEXT"

    logger.info("[layout_router] master prompt -> %s/%s (legacy %s)",
                family, result["variant"], result["layout_type"])
    return result


# ── Main public function ──────────────────────────────────────────────────────

def classify_and_structure_chunk(text: str, current_title: str = "") -> dict:
    """
    Classify a content chunk into a layout type with full visual attributes.

    Robustness guarantees
    ---------------------
    • JSON is extracted from raw model output via multi-strategy parser
    • One automatic retry with a stricter prompt if first parse fails
    • Falls back to a deterministic heuristic layout — never raises
    • Rate-limit circuit breaker skips all API calls once quota is exceeded
    """
    global _groq_rate_limited

    # The figure-OCR block informs classification but must never be bulletised.
    # _classify_with_master_prompt handles it itself; every other path here
    # works on the stripped text.
    ocr_hint = ""
    _m = re.search(r"<<FIGURE_TEXT>>(.*?)<<END_FIGURE_TEXT>>", text, re.S)
    if _m:
        ocr_hint = _m.group(1).strip()

    # Opt-in: drive the structuring call with the full master prompt
    # (ai/master_prompt.py) — 40-family taxonomy, per-sentence verbatim, and an
    # animation timeline. Falls back to the classic 5-type path on any failure.
    if os.getenv("LEARNOVA_MASTER_PROMPT", "").lower() in {"1", "true", "yes", "on"}:
        try:
            result = _classify_with_master_prompt(text, current_title)
            if result:
                return result
        except Exception as exc:  # never let the new path break structuring
            logger.warning("[layout_router] master prompt path failed: %s", exc)

    t_start = time.monotonic()
    stage = "layout_router"
    text = strip_ocr_block(text)

    try:
        # ── Circuit breaker ───────────────────────────────────────────────────
        if _groq_rate_limited:
            raise ValueError("Groq TPM quota previously exhausted; using local fallback")

        # ── Attempt 1: full prompt ────────────────────────────────────────────
        logger.info("[%s] START — title=%r", stage, current_title[:40] if current_title else "")
        user_prompt = f"Title: {current_title}\nText:\n{text[:3500]}"
        if ocr_hint:
            user_prompt += f"\n\n(A figure on this slide reads: {ocr_hint[:300]})"
        raw1: Optional[str] = None

        try:
            # Room for a full set of teaching-sentence bullets plus the visual
            # payload; 300 tokens truncated the JSON on content-rich slides.
            raw1 = _call_llm(user_prompt, SYSTEM_PROMPT, max_tokens=750)
        except ValueError as ve:
            if "rate_limit" in str(ve):
                raise  # propagate to outer except → heuristic fallback
            raise
        except Exception as e:
            logger.warning("[%s] Attempt 1 API error: %s", stage, e)

        data: Optional[dict] = None
        if raw1:
            data = _extract_json(raw1)

        # ── Attempt 2: retry with minimal prompt ──────────────────────────────
        if data is None:
            logger.warning(
                "[%s] Attempt 1 JSON parse failed — retrying with strict prompt", stage
            )
            retry_prompt = (
                f"Classify this educational text into one of: "
                f"FLOWCHART, TABLE, METRIC, CARD_GRID, MINIMAL_TEXT.\n"
                f"Text: {text[:1500]}\n"
                f"Return ONLY JSON, nothing else."
            )
            raw2: Optional[str] = None
            try:
                raw2 = _call_llm(retry_prompt, RETRY_SYSTEM_PROMPT, max_tokens=200)
            except Exception as e:
                logger.warning("[%s] Attempt 2 API error: %s", stage, e)

            if raw2:
                data = _extract_json(raw2)

            if data is None:
                logger.warning("[%s] Both attempts failed — using heuristic fallback", stage)
                raise ValueError("JSON parse failed after retry")

        # ── Validate parsed data ──────────────────────────────────────────────
        layout_type = str(data.get("layout_type", "")).upper()
        if layout_type not in _VALID_LAYOUTS:
            layout_type = _heuristic_layout_type(text)
            logger.warning(
                "[%s] Invalid layout_type %r from LLM — heuristic chose %r",
                stage, data.get("layout_type"), layout_type,
            )

        # Ensure all string fields are actually strings
        title = str(data.get("title", current_title or "Key Concept")).strip()
        takeaway = str(data.get("takeaway", "")).strip()
        if re.fullmatch(r"(review\b.*|n/?a|none|-)?\.?", takeaway, re.I):
            takeaway = ""  # generic filler is worse than an empty bar
        # No cap here. This used to be `[:4]`, which silently deleted every
        # point past the fourth before the density stage ever saw them — the
        # continuity contract in docs/PPT_RULES.md says overflow moves to a
        # continuation slide, and it cannot if the content is already gone.
        bullets = dedupe_bullets([str(b) for b in data.get("bullets", [])])
        _llm_bullets_raw = list(bullets)  # before restoration inflates the count
        bullets = _restore_dropped_points(bullets, text)

        result: dict = {
            "layout_type": layout_type,
            "title": title,
            "takeaway": takeaway,
            "bullets": bullets,
            # What the model itself produced, so the improver can tell whether it
            # over-summarised (and swap in extractive bullets) even after the
            # restore pass padded the list back out.
            "_llm_bullets_raw": _llm_bullets_raw,
        }

        # gpt-oss-20b loves to call definitional prose a FLOWCHART. Only keep
        # that verdict when the text actually reads like an ordered process.
        if layout_type == "FLOWCHART":
            _low = text.lower()
            _proc = (
                bool(re.search(r"^\s*(?:step\s*\d|\d+[.)]\s)", text, re.M))
                or len(re.findall(r"\b(?:then|next|after that|finally|first|second|third)\b", _low)) >= 2
                or len(re.findall(r"->|→|⟶|=>", text)) >= 1
                or len(re.findall(r"\b(?:phase|stage)s?\b", _low)) >= 2
            )
            if not _proc:
                fallback = _heuristic_layout_type(text)
                logger.info(
                    "[%s] LLM said FLOWCHART but no process cues — using %r", stage, fallback,
                )
                layout_type = fallback if fallback != "FLOWCHART" else "MINIMAL_TEXT"
                result["layout_type"] = layout_type

        # ── Layout-specific extras ────────────────────────────────────────────
        if layout_type == "FLOWCHART":
            try:
                diag = generate_mermaid_diagram(text, title)
                result["mermaid_code"] = str(diag.get("mermaid_code", ""))
            except Exception as e:
                logger.warning("[%s] Mermaid generation failed: %s", stage, e)
                safe_t = re.sub(r"[^\w\s]", "", title[:30]) or "Start"
                result["mermaid_code"] = (
                    f"graph TD\n  A[{safe_t}] --> B[Execute] --> C[Outcome]"
                )

        elif layout_type == "TABLE":
            tbl = data.get("table_data", {})
            if not isinstance(tbl, dict):
                tbl = {}
            headers = tbl.get("headers", ["Category", "Details"])
            rows = tbl.get("rows", [["Aspect 1", "Detail 1"]])
            # Sanitise: ensure all cells are strings
            result["table_headers"] = [str(h) for h in headers]
            result["table_rows"] = [
                [str(cell) for cell in row]
                for row in rows
                if isinstance(row, (list, tuple))
            ]

        elif layout_type == "METRIC":
            from learnova.pipeline.visual_planner import extract_quantity

            met = data.get("metric_data", {})
            if not isinstance(met, dict):
                met = {}
            # Trust the model's figure only if it really is one. It returned
            # "n/a" for IRR, which rendered as the slide's headline number.
            value = extract_quantity(str(met.get("value", ""))) or extract_quantity(text)
            if value:
                result["metric_value"] = value[:16]
                result["metric_label"] = strip_inline_markdown(str(met.get("label", title)))
                result["metric_desc"] = truncate_words(
                    str(met.get("description") or takeaway), 120
                )
            else:
                result["layout_type"] = "MINIMAL_TEXT"

        elapsed = time.monotonic() - t_start
        logger.info("[%s] SUCCESS layout=%s title=%r (%.2fs)", stage, layout_type, title[:40], elapsed)
        return result

    except Exception as exc:
        elapsed = time.monotonic() - t_start
        logger.error("[%s] FAILURE after %.2fs: %s", stage, elapsed, exc)

        # Fully deterministic heuristic fallback — guaranteed no exceptions
        h_layout = _heuristic_layout_type(text)
        return _build_fallback(text, current_title, h_layout)
