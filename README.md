# 🎓 Learnova — AI Presentation Transformation Engine

> Transforms text-heavy PPTs and PDFs into modern, visually engaging, presentation-ready decks.
> Flowcharts, timelines, comparison tables, KPI cards, SmartArt and inline checkpoint quizzes —
> fully programmatic, with optional Groq / NVIDIA NIM / Gemini AI integration.

**Run it with no API keys at all** and you still get a deck — layout falls back
to a keyword heuristic. Keys improve the writing; they are not a dependency.

---

## 🚀 What it does

1. **Ingest** a `.pptx`, a `.pdf`, or a typed syllabus.
2. **Convert to Markdown** via AnyDoc — one intermediate representation for all
   three inputs. Images are extracted separately and **anchored back to the
   section that discusses them**.
3. **Review & edit** that markdown before anything expensive runs.
4. **Chunk** on `##` heading boundaries, so slides break at semantic seams.
5. **Classify layout** per chunk (flowchart / table / metric / card grid / minimal text).
6. **Plan visuals deterministically** — detect real flowcharts, comparison
   tables and KPI callouts from the text itself, with no LLM.
7. **Enhance** — examples, analogies and revision points from `enhancement/`.
8. **Apply text density** — low / medium / heavy, paginating overflow onto
   numbered continuation slides so nothing is dropped.
9. **Generate quizzes** and attach them **inline**, as a band at the foot of the
   slide that closes each run — the deck no longer inflates with interruptions.
10. **Score** engagement quality per slide.
11. **Export** an animated `.pptx` and an interactive Reveal.js web deck.

### Where the visuals come from

A typed syllabus has no images or charts, so structure is its only source of
visual richness. `pipeline/visual_planner.py` runs the `intelligence` +
`visual_specs` engines over each chunk and emits a real layout:

| Detected in the text | Becomes |
|---|---|
| 3+ ordered steps / a described process | **Flowchart** with real nodes, edges and start/end shapes |
| 3+ dated or chronological events | **Timeline** flow |
| An explicit A-vs-B comparison | **Comparison table** (skipped if the extraction is low quality) |
| 2+ numeric findings | **Metric callout** using the actual figure, e.g. `47%` |
| 3+ distinct key concepts | **Card grid** |

This only overrides the layout router when the router produced nothing
structural, or produced a recognisable placeholder (a flowchart with no node
data). A genuine LLM result is left alone.

**Nothing is fabricated.** A `TABLE` with no parseable rows and a `METRIC` with
no readable quantity are both downgraded to plain text rather than rendering an
invented `Item / Description` grid or the literal words `Key Stat` at headline
size — both of which used to ship.

---

## 🏗️ Architecture

```
              ┌───────────┐
  PPTX ──┐    │           │
  PDF  ──┼───▶│ Markdown  │──▶ sections ──▶ chunks ──▶ layout ──▶ quizzes ──▶ score
  Typed ─┘    │    IR     │                                                     │
              └───────────┘                                                     ▼
                    ▲                                              PPTX  +  HTML web deck
                    │
              user may edit
```

Everything under `src/learnova/` is **UI-agnostic** — it imports no Streamlit and no FastAPI.
Both frontends call the same `learnova.pipeline.orchestrator`.

---

## 📂 Project structure

```text
learnova/
├── pyproject.toml                 # packaging + pytest config
├── requirements.txt
├── .env.example
│
├── src/learnova/                  # ← the library. No UI imports anywhere.
│   ├── config.py                  # paths, limits, API keys, runtime env flags
│   ├── logging_config.py
│   ├── textutils.py               # ← markdown stripping, word-safe trimming, dedupe
│   ├── parsers/
│   │   ├── schema.py              # 8 structured dataclasses (rich view)
│   │   ├── legacy.py              # SlideData / ParsedDocument (flat view, single definition)
│   │   ├── base.py                # BaseDocumentParser ABC
│   │   ├── ppt_parser.py          # PPTX: tables, SmartArt, charts, equations, notes
│   │   ├── pdf_parser.py          # PDF: PyMuPDF text/tables/images + scanned-page render
│   │   └── markdown_converter.py  # ← Markdown IR (AnyDoc) + image anchoring
│   ├── providers/
│   │   ├── base.py                # LLM / Vision / Embedding ABCs
│   │   ├── groq_provider.py
│   │   ├── nvidia_provider.py     # ← NVIDIA NIM over plain REST (no openai SDK)
│   │   ├── gemini_vision.py
│   │   ├── gemini_embedding.py
│   │   └── router.py              # ← LLMRouter: ordered failover on 429/timeouts
│   ├── pipeline/
│   │   ├── orchestrator.py        # ← the 12-stage pipeline, UI-free
│   │   ├── visual_planner.py      # ← deterministic flowchart/table/KPI detection
│   │   ├── density.py             # ← text density + slide continuity/pagination
│   │   ├── enhancer.py            # ← bridges enhancement/ into the runtime
│   │   └── jobs.py                # in-memory async job store for the API
│   ├── auth/clerk.py              # ← Clerk JWT verification against JWKS
│   ├── storage/deck_library.py    # ← per-user saved decks on disk
│   ├── assistant/                 # ← chat + voice control: NLU, resolver, tools, orchestrator
│   ├── gallery/                   # ← ready-made catalogue: loader, deck store, batch builder
│   ├── ai/                        # improver, layout_router, quiz_gen, image_describer
│   ├── intelligence/              # zero-LLM concept extraction & transformation planning
│   ├── enhancement/               # pedagogical generators (examples, analogies, mnemonics)
│   ├── visual_specs/              # deterministic visual specification builders
│   ├── rag/                       # chunker, retriever, embedder
│   ├── rendering/                 # themes, PPTX builder, web deck, subprocess isolation
│   │   └── layout.py              # ← content-driven geometry: fits fonts, boxes, grids
│   └── scoring/                   # engagement scorer
│
├── apps/
│   ├── streamlit_app/             # Streamlit UI (app.py, styles.py, helpers.py)
│   └── api/main.py                # FastAPI REST backend
│
├── frontend/                      # React + Vite SPA (Clerk auth, routing)
│   ├── .env                       # VITE_CLERK_PUBLISHABLE_KEY
│   └── src/
│       ├── styles.css             # brutalist design system, four accent tokens
│       ├── pages/                 # Landing · AuthPage · Studio · DeckLibrary
│       └── components/            # Navbar · Footer · Marquee · PalettePicker · Cursor · …
│
├── scripts/                       # verify_*.py, generate_sample.py, gallery/build_catalog.py
├── data/gallery/catalog.json      # ← the 1000+ topic catalogue
├── tests/                         # pytest suite + conftest.py + fixtures/
└── docs/
    ├── PPT_RULES.md               # ← every rule applied, in execution order
    ├── GALLERY.md                 # ← the ready-made catalogue + batch builder
    ├── ASSISTANT_ARCHITECTURE.md  # ← the chat/voice assistant layer
    └── PROGRESS_README.md
```

---

## ⚙️ Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in whichever keys you have. **All of them are optional** — with no keys at all the
pipeline still produces a deck using heuristic layout classification.

| Key | Used for | Required? | Notes |
|-----|----------|-----------|-------|
| `GROQ_API_KEY` | Layout, diagrams, enhancement | No | Free tier; `gsk_…`. TPM ceiling is 6 000 — the enhancement stage can trip it |
| `NVIDIA_API_KEY` | Rewriting + quizzes, and 429 failover for everything | No | build.nvidia.com, `nvapi-…` |
| `GEMINI_API_KEY` | Image OCR / vision descriptions | No | Needed for **scanned** PDFs, which are otherwise rejected |
| `VITE_CLERK_PUBLISHABLE_KEY` | Sign-in + per-user deck library | For accounts | `pk_…`, safe in the browser |
| `CLERK_SECRET_KEY` | Server-side Clerk calls | For accounts | `sk_…` — **never** put this in `frontend/.env` |

> A Gemini key that authenticates can still return `429 RESOURCE_EXHAUSTED` on
> every generation call: listing models does not consume `generateContent`
> quota, so a key can look valid and have none. If every call 429s with no
> retry delay, the project needs billing or free-tier quota enabled.

The frontend reads its Clerk key from **`frontend/.env`** (`VITE_` prefix — Vite
does not expose bare or `NEXT_PUBLIC_` names to the browser). The project-root
`.env` holds the backend copy. Without Clerk configured the API runs in
anonymous single-user mode, so local development still works.

### 3. Run

**Streamlit (single process, simplest):**

```bash
streamlit run apps/streamlit_app/app.py
```

**FastAPI + React (two processes):**

```bash
uvicorn apps.api.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Then open <http://localhost:5173>. Vite proxies `/api` to port 8000, so there is no CORS setup.

---

## 🧪 Tests

```bash
python -m pytest -q
```

**295 passed, 2 skipped, 1 failed.** The skips need a PDF fixture. The failure
is `test_live_enhance_photosynthesis`, which calls Groq for real and trips the
free tier's 6 000 tokens-per-minute ceiling — a quota limit, not a defect, but
it does make a full run non-deterministic. Run the credentialed tests
deliberately with `pytest -m live`, and everything else with:

```bash
python -m pytest -q -m "not live"
```

A full run takes ~13 minutes because several tests exercise the live pipeline.
`tests/test_content_fidelity.py` is the fast, offline guard over slide-copy
quality — metric extraction, markdown leakage, restatement, card headings,
pagination balance — and finishes in under a second.

Verification scripts (write JSON into `.cache/`):

```bash
python scripts/verify_day4.py
```

```bash
python scripts/verify_day5.py
```

---

## 🔌 API reference

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Liveness + the canonical stage list |
| `GET` | `/api/themes` | Available design themes |
| `POST` | `/api/jobs` | Upload a document → `job_id`; conversion starts |
| `POST` | `/api/jobs/typed` | Create a job from typed text |
| `GET` | `/api/jobs/{id}` | Poll status, stage, progress |
| `GET` | `/api/jobs/{id}/markdown` | Fetch the editable markdown IR |
| `PUT` | `/api/jobs/{id}/markdown` | Save user edits |
| `POST` | `/api/jobs/{id}/generate` | Run the expensive half |
| `GET` | `/api/jobs/{id}/deck` | Slides + quizzes + scores as JSON |
| `GET` | `/api/jobs/{id}/download/pptx` | Download the PPTX |
| `GET` | `/api/jobs/{id}/download/html` | Download the web deck |
| `GET` | `/api/decks` | The signed-in user's saved deck library |
| `GET` | `/api/gallery` | Browse the ready-made catalogue (subject / search / paging) |
| `GET` | `/api/gallery/{slug}/deck` | Slides + quizzes for one pre-built gallery deck |
| `POST` | `/api/gallery/{slug}/use` | Clone a gallery deck into the caller's library |
| `POST` | `/api/assistant/query` | Natural-language / voice control → typed action |

The pipeline outlives an HTTP request, so uploads return **202** immediately and the
client polls. The 12 stages map directly onto a progress bar.

---

## 🤖 Provider strategy

`LLMRouter` implements `LLMProvider`, so it drops into any call site that already
accepts one. It tries providers in a task-specific order and falls through on
429 / timeout / 5xx:

| Task | Preferred | Fallback | Why |
|------|-----------|----------|-----|
| Layout classification | Groq `llama-3.1-8b-instant` | NVIDIA `meta/llama-3.1-8b-instruct` | Short JSON, one call per chunk — latency dominates |
| Diagram generation | Groq `llama-3.1-8b-instant` | NVIDIA `meta/llama-3.1-8b-instruct` | Same shape |
| Content improvement | NVIDIA `nemotron-3-ultra-550b-a55b` | Groq | Low volume, quality shows |
| Quiz generation | NVIDIA `nemotron-3-ultra-550b-a55b` | Groq | Distractor quality matters |
| Enhancement | Groq `llama-3.1-8b-instant` | NVIDIA | **72 calls per run** — see below |
| Image description | Gemini `gemini-2.5-flash` | native PyMuPDF render | |

**Model choice is a latency budget, not a quality ranking.** Enhancement makes
six sequential calls per slide across up to twelve slides. On Nemotron Ultra
(~13 s a call) that is ~15 minutes of wall clock for one deck, so it takes the
small fast model and leaves NVIDIA as failover. `meta/llama-3.3-70b-instruct`
was measured at **158 s per call** on this endpoint and is not used anywhere.

Call sites choose a timeout suited to Groq's small models, so the router applies
a **per-provider floor** on the way out — without it every failover to a large
NIM model would time out before it could answer.

Gemini's model list is ordered `2.5-flash` first: `2.0-flash` and `1.5-flash`
are absent from the v1beta catalog, so trying them first burned two guaranteed
failures per image.

**No OpenAI dependency.** NVIDIA NIM is reached with plain `requests` against its
OpenAI-compatible endpoint; the `openai` package is not installed or imported.
NIM reasoning models return chain-of-thought in a separate `reasoning_content`
field, which the provider deliberately ignores so JSON parsing stays clean.

---

## 🖼️ How images are handled

AnyDoc produces **text only**: markdown cannot carry bytes, and AnyDoc exposes
no document model for PDF at all (`to_document` is PPTX-only). So the split is:

- **Text** → AnyDoc, which gives cleaner heading/list structure than flattening
  our own parser output.
- **Image bytes** → always the native parsers, which know the slide or page each
  image came from.

Each extracted image is then **anchored** back onto a markdown section by
`markdown_converter.anchor_assets`, in three escalating steps:

1. exact heading match,
2. word-overlap similarity against the section body,
3. positional fallback.

This is why an image stays with its related content even after the user
deletes or reorders sections in the markdown editor — a plain index mapping
breaks the moment the two documents differ in length.

Layouts other than `MINIMAL_TEXT` fill their content area with cards or tables,
so an anchored image there gets its **own figure slide immediately after** the
slide it belongs to, rather than being dropped or overlapped.

AnyDoc marks embedded pictures with a bare `image.png` line; those placeholders
are stripped, otherwise each one becomes a junk slide.

## 📝 Notes & known limits

- **Retrieval is keyword-based, not vector-based.** `rag/retriever.py` is a
  pure-Python keyword-overlap store. There is no FAISS in this project, and no
  embeddings run in the default pipeline. `ChunkRetriever` is currently built
  and discarded — it exists for future retrieval-augmented stages.
- **AnyDoc does no OCR.** If it returns too little text (a scanned page), the
  native PyMuPDF path takes over, which can render and OCR the page. AnyDoc is
  a required dependency but the pipeline still runs without it.
- **Every LLM call now goes through `LLMRouter`.** `layout_router`, `quiz_gen`
  and `diagram_gen` used to construct `GroqProvider()` directly, so NVIDIA was
  unreachable from them and a Groq 429 simply lost the work.
- **Enhancement is LLM-backed**, so it is skipped at `low` density, capped at
  the first 12 slides, and degrades to plain slides with no provider. It is the
  highest-volume stage in the pipeline — six sequential calls per slide, ~72 per
  run — so it deliberately prefers the *fast* model, not the best one.
- **Scanned/image-only PDFs are rejected with a clear message** rather than
  producing a deck whose one content slide reads "Page 1". They need OCR, which
  needs `GEMINI_API_KEY`. Typed input is exempt from the check — a short outline
  is deliberate, not a failed extraction.
- **The job store is in-memory and single-process.** Jobs are lost on restart
  and it will not work across multiple uvicorn workers. Fine for a demo.
- PPTX/HTML builds run in a **separate interpreter** (`rendering/subprocess_builder.py`)
  to isolate C-extension state; this is what fixed the exit-139 segfaults.
- The intelligence / enhancement / visual_specs packages **are** wired into the
  runtime, via `pipeline/visual_planner.py` (deterministic layout detection) and
  `pipeline/enhancer.py` (pedagogical extras). `scripts/verify_day4.py` and
  `verify_day5.py` exercise them standalone.
- **Quantity parsing covers `$ ₹ € £ ¥` with comma separators.** `USD 250,000`
  and European decimal-comma notation (`1.234,56`) are not recognised.

---

## 🔐 Accounts & the deck library

Sign-in is handled by **Clerk**. The React app sends Clerk's session JWT as
`Authorization: Bearer …`; the API verifies its RS256 signature against Clerk's
published JWKS. **The user id is never taken from the client** — otherwise
changing a header would expose someone else's decks.

Every generated deck is written to `.data/users/<user_id>/<deck_id>/`
(markdown + PPTX + HTML + metadata) and listed under **My Decks**. Requests for
a deck you don't own return `404`, not `403`, so ids cannot be probed.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/decks` | Your saved decks, newest first |
| `GET` | `/api/decks/{id}/markdown` | The saved markdown |
| `GET` | `/api/decks/{id}/download/{pptx or html}` | Download a saved artifact |
| `DELETE` | `/api/decks/{id}` | Remove a deck |

## 🎨 Palette & typography

The studio exposes a Canva-style picker: **primary**, **secondary** and
**background** colours plus a font pairing, with eight presets and a live
preview. The chosen values travel as a `theme_spec` through the pipeline and the
build subprocess into *both* the PPTX and the web deck.

Remaining roles (card fill, body text, muted text) are derived, and text colour
is picked by WCAG relative luminance — so a dark primary never ends up with
dark text on it. The **web deck honours the palette too**; it previously
hardcoded a navy `#1e2761` throughout while captioning itself "Theme: Custom
Palette".

PPTX embeds a font *name*, so the viewer needs the font installed; each pairing
therefore names a safe fallback. `Arial` and `Georgia` are the safest choices
for decks you will hand to someone else.

---

## 📐 Slide quality

Geometry is **derived from the content**, not hardcoded. `rendering/layout.py`
measures the text and picks the largest size that fits, stepping down in half
points and stopping at a legibility floor (11 pt body, 9 pt cards) — below that
the content paginates instead of shrinking further. Cards in a row share one
size so the row reads evenly, grids wrap past four per row, and the last row is
balanced (five items become 3+2, not 4+1).

The content band is computed per slide and shrinks for whichever of the takeaway
bar and inline quiz band are present, so nothing overlaps.

Copy is normalised through `textutils.py` before it reaches a slide:

| Rule | Why |
|---|---|
| Markdown emphasis stripped, including **unbalanced** markers | Extraction cuts sentences mid-emphasis; the remnant rendered as `Strategic Growth:*` |
| Trimming lands on a word boundary | Character slicing shipped slides ending "The cost of ca" |
| Restatements dropped | One grid showed a heading and two of its own fragments as three separate cards |
| Quantities kept whole | A bare `\d+` headlined `$250,000` as **250** |
| Card headings taken from the content's own `Label:` prefix | Cards read `PILLAR 1`, `STEP 2` — numbering that tells a reader nothing |

**Content survives the LLM.** The layout router used to cap the model's reply at
`bullets[:4]` while the prompt asked for "only the top 3 to 4 concepts", so
eight points of source became three before the density stage could paginate
them. The cap is gone, the prompt says restructure rather than summarise, and —
because prompting alone does not reliably stop a model summarising — the result
is diffed against the source and any unrepresented sentence is appended
verbatim.

---

## Text density & slide continuity

The studio asks one question — **how much text per slide?** — and every limit
derives from it.

| | Low | Medium (default) | Heavy |
|---|---|---|---|
| Bullets per slide | 3 | 5 | 8 |
| Words per bullet | 12 | 20 | 32 |
| Table rows | 4 | 6 | 10 |
| Flowchart steps | 3 | 4 | 6 |
| Enhancement extras | none | 1 | 3 |

**Content is never dropped.** A lighter setting spreads the same material
across more slides, titled `Topic (2/3)` so the run reads as one continuous
thought. Only the last part carries the takeaway; only the first keeps the
figure. `METRIC` and `QUIZ` slides are never split.

Full rule list: **[docs/PPT_RULES.md](docs/PPT_RULES.md)** — every rule applied
between raw input and finished deck, in execution order.

---

## 🖼️ The Gallery

A shared catalogue of **1000+ teaching topics** across 30+ subjects. A user
browses by subject, previews a finished deck and clicks **Use** to drop an
editable copy into their own projects — or clicks **Generate** on any topic to
open Create pre-filled.

Curated topics ship with a real structured brief and a pre-built deck; the rest
are browsable and generate on demand. `scripts/gallery/build_catalog.py` builds
the catalogue; `learnova.gallery.builder` batch-generates the decks. See
[`docs/GALLERY.md`](docs/GALLERY.md).

## 🗣️ The assistant

A chat + voice assistant (`src/learnova/assistant/`, floating widget in the web
app) that resolves natural language to typed actions — open a deck, jump to a
slide, explain a concept from the deck's own text, search your presentations,
run a quiz. Deterministic NLU (57-intent taxonomy) with an LLM fallback; every
action is validated server-side before it runs. See
[`docs/ASSISTANT_ARCHITECTURE.md`](docs/ASSISTANT_ARCHITECTURE.md).

## 🖥️ The web app

The React app (`frontend/`) pairs a preserved brutalist landing page with a
calm authenticated workspace: a shared page-container / header / empty-state
design system, a Gallery, per-deck analytics, checkpoint-quiz runner and the
assistant widget.

The landing page keeps its brutalist black-and-amber design system:
ultra-condensed display type, hard offset shadows, a dotted grid ground and
dual-direction marquees.

The accent lives in **four tokens** rather than one, because a single value
cannot stay legible both as a fill and as text:

| Token | Role |
|---|---|
| `--accent` | fills and borders |
| `--accent-deep` | hover / pressed |
| `--accent-light` | the accent as text on black panels |
| `--accent-on` | text sitting on an accent fill |

That split is what makes a palette change safe: swapping the accent inverts the
whole site from one place. A flat find-and-replace would leave roughly a third
of the UI unreadable.

`components/Cursor.jsx` replaces the pointer with a dot that swells over
anything clickable. It falls back to the native cursor on touch devices, under
`prefers-reduced-motion`, and **inside Clerk's account portal** — that renders
in its own high-z-index portal where the dot cannot reliably paint, and
suppressing the native cursor there left no pointer at all.
