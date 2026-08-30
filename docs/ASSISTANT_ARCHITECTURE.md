# Learnova Assistant — Architecture & Roadmap

Companion to `docs/ASSISTANT_MASTER_PROMPT.md`. Records the Phase‑1 inspection,
the Phase‑2 design, and what is built vs pending.

## Phase 1 — inspection (what already exists)

| Concern | Current state |
|---|---|
| Backend | FastAPI (`apps/api/main.py`), 28 pre-existing routes, Clerk-JWT auth, per-user isolation |
| Presentation model | `learnova.storage.deck_library` — one dir per deck under `.data/users/<uid>/<deck_id>/`; `deck_id` = originating job id (`uuid.hex[:16]`), stable but not human-facing; `DeckRecord` has title/slide_count/score/theme/versions |
| Slides | `rendering/deck_payload.slides_payload()` → `{title,bullets,takeaway,layout_type,family,mermaid_code,table_*,question,…}`; **no stable per-slide id** (index only) |
| Content index | `learnova.rag` keyword store (built per-run, not queried by the main path) |
| Visual system | `visual_specs/`, `ai/visual_selector.py`, `family_blocks` renderers, `docs/visual_catalog.yaml` — the "1000+ visuals" |
| Pipeline | `pipeline.orchestrator.generate()` — the deck generator (content-preserving) |
| Voice / chatbot / assistant | **none** — no STT/TTS deps, no intent code |
| Frontend | React 18 + Vite + Clerk, `frontend/src/api.js` client, `AppLayout` shell |

## Phase 2 — design

```
POST /api/assistant/query {text, session_id}
        │
        ▼
  orchestrator.handle(utterance, SessionContext)
        │
        ├─ nlu.classify()            deterministic rules  (→ LLM fallback hook)
        ├─ registry.build_registry() decks + stable ids + aliases
        ├─ resolver.resolve_*()      "presentation 2" / "the RSA deck" / "the 2nd one"
        ├─ validation                exists? in range? permitted?
        └─ actions.*                 typed AssistantResponse
        ▼
  {response: {type, message, presentation_id, slide_number, options, …},
   context: {current_presentation, current_slide, …}}
        ▼
  frontend executes the action (open deck, navigate, speak, show clarification)
```

**Module map** (`src/learnova/assistant/`)

| file | role | spec |
|---|---|---|
| `ids.py` | `LRN-PRES-0007`, `LRN-PRES-0007-S03` scheme | §3, §5, §40 |
| `registry.py` | deck → `PresentationEntry` (pres_id, display_number, subject, tags, aliases); per-user pres_id sequence; backfills `meta.json` | §3, §39 |
| `intents.py` | 57-intent taxonomy + per-intent spec (category, action, entities, requires_context/presentation) | §7 |
| `actions.py` | `AssistantResponse` typed protocol + constructors | §32 |
| `nlu.py` | normalise (wake-word, typos) + ~70 regex rules → intent + entities; ambiguous/unknown → LLM fallback | §4, §18–§20, §38 |
| `resolver.py` | reference → `Resolution{resolved|ambiguous|not_found}` with confidence | §4, §5, §21, §38 |
| `session.py` | in-memory `SessionContext` (current pres/slide, last result list, quiz state, history) | §10 |
| `orchestrator.py` | ties it together; validates before acting; never touches app state directly | §1, §2, §33–§37 |
| `dataset.py` | template × slot generator → `data/assistant/qa_dataset.json`; + hand-curated `gold_examples.json` | §16–§22, §46 |
| `benchmark.py` | intent / action / entity accuracy over the dataset | §43, §47 |

**API** (`apps/api/main.py`)

- `GET  /api/assistant/registry` — the presentation registry
- `GET  /api/assistant/intents` — the taxonomy
- `POST /api/assistant/query` — `{text, session_id}` → typed response + context
- `GET  /api/assistant/session/{id}` — current context

**Data** (`data/assistant/`) — `intents.json`, `qa_templates.json`,
`gold_examples.json`, generated `qa_dataset.json` (~1640 rows).

## Status

| Phase | | Status |
|---|---|---|
| 1 | Inspect | ✅ |
| 2 | Architecture | ✅ |
| 3 | Presentation registry + stable ids | ✅ (registry builds + backfills; `save_deck` still assigns via registry lazily) |
| 4 | Intent + entity system | ✅ 57 intents, deterministic NLU **88.7% intent / 90.6% action** on the 1640-row benchmark |
| 5 | Tool / action layer | ✅ typed protocol + resolver + orchestrator; **tool execution** (openPresentation, goToSlide…) is returned as an action for the frontend, not yet a server-side tool bus |
| 6 | Context / session | ✅ in-memory; multi-turn tested (open → navigate → "explain this" → switch deck) |
| 7 | Chat assistant | 🟡 deterministic path live; **LLM fallback** (`orchestrator.classify_llm`) is a wired hook, not implemented; content-retrieval for `EXPLAIN_CONTENT` returns a typed stub the LLM/frontend fills |
| 8 | Voice (STT / TTS) | �⬜ not started — frontend Web Speech API + a `/api/assistant/voice` passthrough is the plan; `AssistantResponse.speech` field already exists |
| 9 | QA dataset (~1–2k) | ✅ 1640 rows + 40 gold |
| 10 | Automated tests | ✅ `tests/test_assistant.py` — 32 tests, benchmark floors asserted |
| 11 | Edge cases | 🟡 covered: not-found, out-of-range, ambiguous, no-decks, typo, wake-word; pending: transcription error, API failure, unauthorized cross-user |
| 12 | UX polish | ⬜ frontend assistant widget not built |

## Next milestones

1. **LLM fallback + content retrieval** (Phase 7 completion): implement
   `classify_llm` (route through `providers.router`) and an
   `EXPLAIN_CONTENT` handler that pulls the relevant slide/section text from
   the deck (via `deck_library` + the rag store) and answers — the reply may
   be simplified/translated per the user's ask; the deck is never modified.
2. **Frontend assistant widget** (Phase 12): mic button + chat panel in
   `AppLayout`, executes `response.type` actions against the existing
   `api.js` + router.
3. **Voice** (Phase 8): browser `SpeechRecognition` → `/api/assistant/query`
   → `SpeechSynthesis` on `response.speech || response.message`; barge-in.
4. **Server-side tool bus** (Phase 5 completion): so an LLM-planned action is
   validated and executed centrally rather than trusted from the client.
