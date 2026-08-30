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
| 5 | Tool / action layer | ✅ `tools.py` — server-side tool bus (`openPresentation`, `getWebDeck`, `goToSlide`, `getSlideContent`, `searchContent`, `explainContent`, …); each validates existence / range / ownership; an LLM-supplied id is resolved + checked here, never trusted |
| 6 | Context / session | ✅ in-memory; multi-turn tested (open → navigate → "explain this" → switch deck) |
| 7 | Chat assistant | ✅ `llm.py` — `classify_intent` (LLM fallback for confidence < 0.55, validated against the taxonomy) + `answer_question` (grounded in retrieved deck/slide text; may simplify / translate the *reply*; deck untouched). Both route through `providers.router`; degrade to the rule path with no provider. |
| 8 | Voice (STT / TTS) | ✅ `frontend/src/lib/useVoice.js` — `SpeechRecognition` in, `speechSynthesis` out, barge-in (new listen / stop cancels speech). Wired into the widget. Degrades to text-only where the APIs are absent. |
| 9 | QA dataset (~1–2k) | ✅ 1640 rows + 40 gold |
| 10 | Automated tests | ✅ `tests/test_assistant.py` — 36 tests (ids, NLU, resolver, orchestrator, multi-turn, edge cases, tool bus, LLM fallback, grounded explain) + benchmark floors |
| 11 | Edge cases | 🟡 covered: not-found, out-of-range, ambiguous (clarify), no-decks, typo, wake-word, low-confidence→LLM, no-content; pending: transcription error surfacing, unauthorized cross-user |
| 12 | UX polish | ✅ `frontend/src/components/app/AssistantWidget.jsx` — floating chat + mic panel in `AppLayout`; executes the typed response (route to deck, `?slide=N`, clarification chips, search-result cards, speak). |

## Gallery awareness

The assistant knows the shared Gallery (`docs/GALLERY.md`). The
`CHECK_GALLERY` intent ("do you have slides on X", "is X pre-built",
"check that the cold war slides are ready-made") runs the `searchGallery`
tool and replies:

- **ready deck exists** → `SHOW_GALLERY_RESULTS` — "Yes, there's a ready-made
  deck on X (7 slides). Opening it." The widget routes to
  `/app/gallery?topic=<slug>`, which auto-opens that deck's preview.
- **topic in catalogue, not built** → offers to generate it.
- **nothing** → suggests `create a presentation on X`.

## Remaining

- Harden edge cases: surface STT errors in the widget; cross-user auth test
  on the API routes.
- `create_presentation` from the assistant currently returns a
  `CREATE_PRESENTATION` action that routes to `/app/create` prefilled — a
  direct "generate now" path (job creation) is a follow-up.
- Quiz turns (`NEXT_QUIZ_QUESTION`, `SUBMIT_QUIZ_ANSWER`) return typed stubs;
  wire them to `ai/quiz_gen` for a live quiz loop.
- Persist sessions (Redis) if the API ever runs multi-worker.
