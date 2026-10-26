"""
Deck Tutor — a persona-based study chatbot grounded in one deck.

* Retrieval: every slide is split into passages (source sentences, bullets, takeaway, notes, key terms, table cells);
  a small BM25-style scorer finds the passages that answer the question.
* LLM mode (a Gemini / Groq / NVIDIA key is configured): the persona's style prompt + the retrieved passages go to the model,
  which is told to answer only from the deck, cite slides as [S3], and say so when the deck doesn't cover something.
* Own-logic mode (no key, or the model fails): the best sentences are stitched into an answer in the persona's voice, with
  slide references. Intents handled without any model: "quiz me", "summarise / overview", "explain slide N".

Voice (speech-to-text and text-to-speech) runs in the browser (Web Speech API); each persona carries voice hints
(rate / pitch / language) for the client.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from learnova.logging_config import logger

PERSONAS: Dict[str, Dict[str, Any]] = {
    "teacher": {"name": "Friendly Teacher", "emoji": "🧑‍🏫", "tagline": "Patient, clear, encouraging",
                "style": "You are a warm, patient teacher. Explain simply, use a short everyday example when it helps, and end with a quick check-for-understanding question.",
                "voice": {"rate": 1.0, "pitch": 1.05, "lang": "en-US"},
                "greeting": "Hi! I'm your teacher for this deck. Ask me anything about it.",
                "open": ["Great question!", "Good one —", "Let's work through it."], "close": ["Does that make sense?", "Want me to go deeper on any part?"]},
    "socratic": {"name": "Socratic Coach", "emoji": "🤔", "tagline": "Guides you with questions",
                 "style": "You are a Socratic coach. Give a brief, correct answer from the deck, then ask ONE guiding question that makes the student reason further.",
                 "voice": {"rate": 0.97, "pitch": 0.95, "lang": "en-GB"},
                 "greeting": "I won't just hand you answers — I'll help you find them. What are you curious about?",
                 "open": ["Let's think it through together.", "Here's what the deck says —"], "close": ["What do you think would happen if that changed?", "Can you explain it back to me in your own words?"]},
    "exam": {"name": "Exam Coach", "emoji": "🎯", "tagline": "Crisp, exam-focused answers",
             "style": "You are an exam coach. Answer in crisp exam-ready points, bold nothing, flag what is most likely to be asked, and keep it short.",
             "voice": {"rate": 1.08, "pitch": 1.0, "lang": "en-US"},
             "greeting": "Exam mode on. Ask me a topic and I'll give you the points that score.",
             "open": ["Exam-ready answer:", "Key points to remember:"], "close": ["Likely follow-up: can you state this from memory?", "Tip: practise writing this in 3 lines."]},
    "genz": {"name": "Gen Z Buddy", "emoji": "😎", "tagline": "Casual, meme-aware, no cap",
             "style": "You are a Gen Z study buddy. Keep it casual and short, light slang is fine (no cap, lowkey, fr) but never at the cost of accuracy.",
             "voice": {"rate": 1.1, "pitch": 1.1, "lang": "en-US"},
             "greeting": "yo, I'm your study buddy for this deck. ask away, no cap.",
             "open": ["ok so basically —", "lowkey simple:", "fr, here's the deal:"], "close": ["that make sense or nah?", "want the cheat-sheet version?"]},
    "genx": {"name": "Gen X Mentor", "emoji": "🎸", "tagline": "Dry, direct, to the point",
             "style": "You are a dry, direct Gen X mentor. No fluff, a touch of ironic humour, straight to the substance.",
             "voice": {"rate": 0.98, "pitch": 0.9, "lang": "en-US"},
             "greeting": "Alright. Deck's loaded. What do you need to know?",
             "open": ["Short version:", "Here's the deal:"], "close": ["That's about it.", "Questions? Thought so."]},
    "millennial": {"name": "Millennial Guide", "emoji": "☕", "tagline": "Enthusiastic, relatable, practical",
                   "style": "You are an enthusiastic millennial guide. Friendly, relatable, practical, a light 'adulting' joke is fine.",
                   "voice": {"rate": 1.03, "pitch": 1.08, "lang": "en-US"},
                   "greeting": "Hey! Let's make this deck make sense — what are we tackling?",
                   "open": ["Okay, so —", "Here's the gist:"], "close": ["Hope that helps!", "Want an example to make it stick?"]},
    "story": {"name": "Storyteller", "emoji": "📖", "tagline": "Explains through analogy and story",
              "style": "You are a storyteller. Explain the idea through one vivid analogy or mini-story that stays faithful to the deck, then state the point plainly.",
              "voice": {"rate": 0.95, "pitch": 1.0, "lang": "en-GB"},
              "greeting": "Every idea has a story. Which one shall we explore?",
              "open": ["Picture this:", "Imagine —"], "close": ["And that's the heart of it.", "Shall I tell it another way?"]},
    "brief": {"name": "Executive Brief", "emoji": "💼", "tagline": "Three bullets, then stop",
              "style": "You are an executive briefer. Give at most 3 short bullets and one 'so what'. No preamble.",
              "voice": {"rate": 1.1, "pitch": 0.95, "lang": "en-US"},
              "greeting": "Ask for anything — you'll get the brief.",
              "open": [""], "close": ["So what: act on the first point."]},
}
DEFAULT_PERSONA = "teacher"

_STOP = set("the a an of and or to in on at for by with is are was were be been it its this that these those as from which who what why how when where do does did can could should would will you your i me my we our they them their there here not no yes about into over under than then so such".split())
_TOK = re.compile(r"[a-z0-9][a-z0-9\-']+")


def list_personas() -> List[Dict[str, Any]]:
    return [{"id": k, **{f: v[f] for f in ("name", "emoji", "tagline", "voice", "greeting")}} for k, v in PERSONAS.items()]


def _tokens(s: str) -> List[str]:
    return [t for t in _TOK.findall(s.lower()) if t not in _STOP and len(t) > 1]


def build_passages(slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[{slide, title, text}] — one passage per sentence-ish unit, tagged with its slide number (1-based)."""
    from learnova.visuals.engine import split_sentences

    out: List[Dict[str, Any]] = []
    for s in slides:
        if str(s.get("layout_type", "")).upper() == "QUIZ":
            continue
        n, title = int(s.get("index", 0)) + 1, str(s.get("title") or f"Slide {int(s.get('index', 0)) + 1}")
        seen = set()
        chunks = [str(s.get("source_text") or "")] + [str(b) for b in (s.get("bullets") or [])] + [str(s.get("takeaway") or ""), str(s.get("speaker_notes") or "")]
        for row in (s.get("table_rows") or [])[:20]:
            chunks.append(" — ".join(str(c) for c in row))
        for ch in chunks:
            for sent in split_sentences(re.sub(r"\[TABLE DATA\]|\||^###\s*", " ", ch, flags=re.M)) or ([ch] if ch.strip() else []):
                sent = re.sub(r"\s+", " ", sent).strip()
                key = re.sub(r"\W+", "", sent.lower())[:80]
                if len(sent.split()) >= 4 and key not in seen:
                    seen.add(key)
                    out.append({"slide": n, "title": title, "text": sent})
    return out


def retrieve(question: str, passages: List[Dict[str, Any]], k: int = 6) -> List[Dict[str, Any]]:
    q = _tokens(question)
    if not q or not passages:
        return []
    docs = [Counter(_tokens(p["title"] + " " + p["text"])) for p in passages]
    N = len(docs)
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    avg = sum(sum(d.values()) for d in docs) / max(1, N)
    scored = []
    for p, d in zip(passages, docs):
        L = sum(d.values()) or 1
        sc = 0.0
        for t in set(q):
            if t in d:
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                sc += idf * (d[t] * 2.2) / (d[t] + 1.2 * (0.25 + 0.75 * L / avg))
        if any(t in _tokens(p["title"]) for t in q):
            sc *= 1.25  # a title match is a strong signal
        if sc > 0:
            scored.append((sc, p))
    scored.sort(key=lambda x: -x[0])
    return [dict(p, score=round(sc, 2)) for sc, p in scored[:k]]


def _flavour(persona: str, key: str, i: int = 0) -> str:
    opts = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA]).get(key) or [""]
    return opts[i % len(opts)]


def _sources(passages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for p in passages:
        if p["slide"] not in seen:
            seen.add(p["slide"])
            out.append({"slide": p["slide"], "title": p["title"]})
    return out[:4]


def _intent(msg: str) -> Optional[str]:
    m = msg.lower()
    if re.search(r"\b(quiz me|test me|ask me a question|give me a question|practice question)\b", m):
        return "quiz"
    if re.search(r"\b(summar[iy]s?e|overview|tl;?dr|recap|main points|outline of)\b", m):
        return "summary"
    if re.search(r"\b(explain|walk me through|go through|what is on|what's on|tell me about)\b.*\b(slide|page)\s*(\d+)", m):
        return "slide"
    return None


def _quiz(slides: List[Dict[str, Any]], seed: int) -> Optional[Dict[str, Any]]:
    from learnova.ai.quiz_offline import offline_quizzes

    entries = [{"original": {"text": str(s.get("source_text") or "")}, "improved": {"title": s.get("title", ""), "bullets": s.get("bullets") or [], "layout_type": "MINIMAL_TEXT"}}
               for s in slides if str(s.get("layout_type", "")).upper() != "QUIZ"]
    if not entries:
        return None
    qs = offline_quizzes(entries, frequency=max(1, len(entries) // 5 or 1))
    return qs[seed % len(qs)] if qs else None


def _llm_answer(question: str, persona: str, passages: List[Dict[str, Any]], history: List[Dict[str, str]]) -> Optional[str]:
    from learnova.ai import assist
    from learnova.providers.router import TASK_IMPROVE, get_router

    if not assist.llm_available():
        return None
    ctx = "\n".join(f"[S{p['slide']}] ({p['title']}) {p['text']}" for p in passages)
    system = (PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["style"] +
              " Ground every claim in the DECK CONTEXT below and cite slides like [S3]. If the context does not cover the question, say so briefly, "
              "then give a short, clearly-labelled general explanation. Keep replies under 120 words. Never invent numbers or facts about the deck.\n\nDECK CONTEXT:\n" + ctx)
    convo = "\n".join(f"{'Student' if h.get('role') == 'user' else 'Tutor'}: {str(h.get('content', ''))[:400]}" for h in history[-6:])
    prompt = (convo + "\n" if convo else "") + f"Student: {question}\nTutor:"
    try:
        out = get_router().generate(prompt, system_prompt=system, task=TASK_IMPROVE, temperature=0.5, max_tokens=420, timeout=30.0)
        return out.strip() if out and out.strip() else None
    except Exception as exc:
        logger.info("tutor LLM failed: %s", exc)
        return None


def answer(message: str, slides: List[Dict[str, Any]], persona: str = DEFAULT_PERSONA, history: Optional[List[Dict[str, str]]] = None,
           use_llm: bool = True) -> Dict[str, Any]:
    persona = persona if persona in PERSONAS else DEFAULT_PERSONA
    history = history or []
    message = (message or "").strip()
    if not message:
        return {"answer": PERSONAS[persona]["greeting"], "sources": [], "mode": "greeting", "persona": persona}
    passages = build_passages(slides)
    turn = len(history)
    intent = _intent(message)

    if intent == "quiz":
        q = _quiz(slides, turn)
        if q:
            opts = "\n".join(f"{'ABCD'[i]}. {o}" for i, o in enumerate(q["options"]))
            return {"answer": f"{_flavour(persona, 'open', turn)} {q['question']}\n{opts}".strip(), "quiz": q, "sources": [], "mode": "own-logic", "persona": persona}
    if intent == "summary":
        titled = [(s.get("index", 0) + 1, s.get("title", ""), s.get("takeaway", "")) for s in slides if str(s.get("layout_type", "")).upper() != "QUIZ"]
        lines = [f"• Slide {n}: {t}" + (f" — {tk}" if tk else "") for n, t, tk in titled[:12]]
        return {"answer": f"{_flavour(persona, 'open', turn)} the deck covers:\n" + "\n".join(lines), "sources": [{"slide": n, "title": t} for n, t, _ in titled[:4]], "mode": "own-logic", "persona": persona}
    if intent == "slide":
        n = int(re.search(r"(?:slide|page)\s*(\d+)", message.lower()).group(1))
        mine = [p for p in passages if p["slide"] == n][:6]
        if mine:
            text = " ".join(p["text"] for p in mine)
            return {"answer": f"{_flavour(persona, 'open', turn)} Slide {n} — {mine[0]['title']}: {text}", "sources": [{"slide": n, "title": mine[0]["title"]}], "mode": "own-logic", "persona": persona}

    hits = retrieve(message, passages, k=6)
    if use_llm and hits:
        txt = _llm_answer(message, persona, hits, history)
        if txt:
            cited = {int(x) for x in re.findall(r"\[S(\d+)\]", txt)}
            srcs = [s for s in _sources(hits) if not cited or s["slide"] in cited] or _sources(hits)
            return {"answer": txt, "sources": srcs, "mode": "llm", "persona": persona}
    if not hits:
        titles = ", ".join(f"“{s['title']}”" for s in slides[:4] if s.get("title"))
        return {"answer": f"I couldn't find that in this deck. It covers things like {titles}. Try asking about one of those, or say “summarise”.",
                "sources": [], "mode": "own-logic", "persona": persona}
    best = hits[:3]
    body = " ".join(p["text"] if p["text"].endswith((".", "!", "?")) else p["text"] + "." for p in best)
    if persona == "brief":
        body = "\n".join(f"• {p['text']}" for p in best)
    refs = ", ".join(f"slide {s['slide']}" for s in _sources(best))
    ans = f"{_flavour(persona, 'open', turn)} {body}".strip() + f"\n(See {refs}.) {_flavour(persona, 'close', turn)}".rstrip()
    return {"answer": ans, "sources": _sources(best), "mode": "own-logic", "persona": persona}
