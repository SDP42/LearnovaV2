# Learnova V2 — Project Memory / Handover

_Last updated: 28 Oct 2026. Read this first when continuing on a new account or machine._

## 1. What the project is
Learnova turns lecture notes, PDFs (especially boring lecture-slide PDFs) and PPTs into designed, interactive decks:
an editable **PowerPoint (.pptx)** + an **interactive web deck (Reveal.js HTML)** + study pack + share link.
FastAPI backend (`apps/api/main.py`), pipeline library (`src/learnova/`), React + Vite frontend (`frontend/`).
GitHub: `SDP42/LearnovaV2`, branch `main`. IPD group 1 (Kawaljeet, Jeevesh, Rishit, Swayam), DJSCE AI&DS.

## 2. Rules the user set (follow always)
- Commit and push to `main` regularly. Author: `Swayam Panchal <panchalswayam35@gmail.com>`.
  **Never add a `Co-Authored-By` trailer.**
  `git -c user.name="Swayam Panchal" -c user.email="panchalswayam35@gmail.com" commit -m "..." && git push origin main`
- Stage `src tests apps scripts frontend/src README.md` etc. Never commit `.env`, `demo/output/*` renders, or the user's private report/diary PDFs.
- Bright, light UI only (no dark mode). Illustrations are "very very main". Don't inflate font size to hide whitespace.
- Works with **and** without AI keys: with a key → AI features; key fails/exhausted → offline rule-based logic.
- User is preparing a **live demo** on three real NLP lecture PDFs.

## 3. How to run (and dev-environment gotchas)
- API: `cd LearnovaV2 && /opt/anaconda3/bin/python -m uvicorn apps.api.main:app --port 8000 --host 127.0.0.1`
- Web: `cd LearnovaV2/frontend && npm run dev -- --port 5190 --host 127.0.0.1 --strictPort` → http://127.0.0.1:5190
- Claude desktop launch config: `/Users/swayampanchal/Desktop/LearnovaIPDV2/.claude/launch.json` (`learnova-api`, `learnova-web`).
- Sign in: any mobile number; dev mode shows the OTP on screen (`OTP_DEV_MODE=1`).
- **iCloud problem:** the Desktop is iCloud-synced; offloaded ("dataless") files make Vite hang ("operation timed out").
  `frontend/node_modules` is a symlink → `node_modules.nosync` (iCloud ignores `.nosync`). After `npm ci`, move the new
  `node_modules` into `node_modules.nosync` and re-link (npm ci replaces the link). Find offloaded files:
  `find src frontend -flags +dataless -not -path '*/node_modules*'`; restore tracked ones with `git show HEAD:<path> > <path>`.
- Shell may lack `python` on PATH → use `/opt/anaconda3/bin/python`.
- Tests: `/opt/anaconda3/bin/python -m pytest -q` → **746 passed, 6 skipped** (tests hide AI keys automatically via `tests/conftest.py`).
- E2E: `python scripts/e2e_check.py` (and `E2E_PDF=/path.pdf python scripts/e2e_check.py pdf`).
- Render a deck to images: `python scripts/render_preview.py <file.md|.pdf> auto 12`; contact sheet: `python scripts/contact_sheet.py deck.pdf out.png 1 5 9`.
- Layout audit: `python -m learnova.evaluation.layout_audit deck.pptx` (overflow, sparse, broken words).

## 4. AI keys
- Stored in `LearnovaV2/.env` (git-ignored): `GEMINI_API_KEY`, `GROQ_API_KEY`. Both verified working on 27 Oct 2026.
  (User pasted them in chat → recommend rotating after the demo.) Can also be set in app **Settings → AI keys**.
- Router order Groq → Gemini → NVIDIA (`src/learnova/providers/router.py`). Dead/rejected/exhausted key is switched off
  immediately for 15 min; reset when a new key is saved. Vision OCR stops after 2 failures.
- Gemini **image generation is refused on the free tier (429 quota)** → drawn SVG illustrations are used automatically.
  Real AI pictures need billing on the Gemini key.

## 5. What is DONE (main features, all pushed)
**Pipeline & backend**
- Parsers: PPTX, PDF, DOCX, Markdown/text, typed topic → Markdown IR; slide-deck PDF reader (`parsers/slide_pdf.py`):
  bullet nesting, tables, figures, repeated-logo removal, Tesseract OCR for picture slides, glued-caps title segmentation,
  Unicode/symbol cleanup, credit-line removal, repeated cover images → section dividers, colour DNA → theme.
- Jobs: restart-safe SQLite jobs, queue, cancel, friendly errors; phone OTP auth; deck library with versions; share links;
  study-pack exports (flashcards, Anki, quiz bank, cheat sheet, narration); presenter console; tutor; gallery (1000+ topics).
- Content Decision Engine (`visuals/engine.py`, 20+ visual families) + Deck Director (`rendering/deck_director.py`).
- Builders: `rendering/ppt_builder.py` + `pptx_visuals.py` (native shapes, glyph-measured text fitting so words never break,
  two-level hanging-indent bullets, type-size caps) and `rendering/web_deck_builder.py` (Reveal.js, click-by-click reveals,
  flip cards, match activity, figure zoom, original-slide viewer).
- Polish (`pipeline/polish.py`): sentence-case/cleaned titles, generic titles → claims, thin continuation slides merged,
  one related source sentence on thin slides. Enrich (`pipeline/enrich.py`): agenda, key takeaways, glossary, activity;
  tiny decks padded to ≥5 slides.
- Quizzes (`ai/quiz_offline.py`): definition-based questions, lookup-table questions, shape/word-class matched distractors.
- **With AI key** (`ai/assist.py::ai_polish`): assertion titles (statement with verb, no commands, ≤100 chars),
  "In plain words" explanations, examples, key terms — batched, grounded checks.
- **Illustrations** (`ai/scenes.py`): content-aware SVG scenes on **every topic slide** in web deck (side panel or header
  spot) and PowerPoint (header illustration where no side picture); deck-subject prior; cached rasterisation.
- **Step-by-step explainers** (`explain/`): SymPy/exact solvers — linear, quadratic, systems, percent, interest, stats,
  probability, Bayes, derivative, integral, geometry, CYK, **bigram, Naive Bayes, Viterbi**; STEPPER slides; overlay in web
  deck; `POST /api/explain`, `/api/decks/{id}/explainers[/{slide}]`; AI fallback only for problem-like input (labelled).
- **Interactive labs** (`labs/`): built-in Region Growing (user's own file) + CYK, Viterbi/HMM, bigram, Naive Bayes WSD,
  HMM POS tagging (`scripts/build_labs.py` → `labs/builtin/*.html`, shared engine `labs/engine.py`).
  Auto labs for new topics (`labs/auto.py`): AI-written with key (Node-checked, no network), else built from slide
  structure; one lab per topic, ≤2 same lab, ≤10 auto per deck, weak/garbled titles skipped; parallel prefetch stage `labs`.
  Web deck: overlay (new tab when embedded small); PPT: footer button linking `/api/labs/{id}` (needs server or
  `LEARNOVA_PUBLIC_URL`). `GET/POST /api/labs`.
- Fixes: blank-slide bug (title slide `position:relative`) + stored-deck repair on read; preview shows selected slide in full.

**Frontend**
- Warm landing page (copied design) + dedicated phone layout (<820px) + custom cursor; app pages responsive (bottom tab bar).
- Pages: Create, Generate, Preview, Present, Export (share links + study pack), Settings (AI keys card), **Solve** (explainer),
  Quizzes, Gallery, Analytics, Docs. Installable **PWA** (manifest, icons, service worker in prod build).
- README rewritten with screenshots (`docs/images/`); old README kept as `docs/DEVELOPER_GUIDE.md`.

**Real test material:** `/Users/swayampanchal/Downloads/` → `Syntax analysis_part 2.pdf` (216 pp), `Module 4- Part 1 _ Word.pdf`
(36 pp), `Module 5 lecture slides (2).pdf` (95 pp), `Region_Growing_Lab.html`. Copy to `/tmp/real/{syntax,m4,m5}.pdf` when testing.
Timings: M4 with keys ≈74 s (labs 28 s, vision OCR 19 s); without keys ≈9 s; dead keys ≈28 s.

**IPD diary (done 27–28 Oct):** `LearnovaIPDV2/IPD Diary/` and Downloads → `IPD Diary - Weekly.{docx,pdf}` (51 weeks to
21–27 Oct 2026), `IPD Diary - Monthly.{docx,pdf}` (Oct 2025–Oct 2026). On AI&DS letterhead, Times New Roman 12, justified,
no exam periods, research-paper work added Aug–Oct. Rebuild: `build_diary.py` (entries) + `build_docx.py` (Word/PDF) + `orig.json`.
Two stale Word lock files `~$D Diary - *.docx` may remain in that folder (close the docs in Word).

## 6. What is LEFT (next steps)
1. **Research papers (requested, not started):** one **IEEE** conference format paper and one **Springer LNCS** format paper on
   Learnova's novel parts — Content Decision Engine (visual-family selection with reasons + gold-set accuracy), glyph-measured
   layout fitting / layout audit, slide-PDF reconstruction (OCR, nesting, colour DNA), computed step-by-step explainers,
   auto-generated interactive labs with AI + offline fallback, provider failover. Include architecture figure, evaluation
   (gold-set accuracy, layout audit flags, fact retention, timings above), related work (Gamma, Copilot, Gemini Slides,
   Canva, Presentify, assertion-evidence, Mayer). Deliver .tex (IEEEtran / llncs) + PDF + .docx if wanted.
2. Syntax deck (216 pp): remaining OCR noise on diagram-heavy slides; some sparse slides.
3. Thin slides without a key stay thin (rule-based enrichment adds little); with key it's good.
4. AI titles sometimes still close to headings on very short slides; quiz questions still partly trivia ("figure for X").
5. Frontend: no upload page for teacher labs (API only); quiz-bank export empty for tiny decks; README app screenshots low-res;
   PWA only checked in dev build.
6. Gemini image generation needs billing; `LEARNOVA_PUBLIC_URL` for PPT lab links when deployed.
7. Rotate the API keys after the demo.

## 7. Key file map
`apps/api/main.py` (all routes) · `src/learnova/pipeline/orchestrator.py` (stages incl. `labs`) · `visuals/engine.py` ·
`rendering/{deck_director,ppt_builder,pptx_visuals,pptx_chrome,web_deck_builder,family_blocks,layout}.py` ·
`parsers/slide_pdf.py` · `pipeline/{planner,enrich,polish,density}.py` · `ai/{assist,scenes,image_gen,image_providers,quiz_offline,image_describer}.py` ·
`explain/*` · `labs/{__init__,auto,engine}.py` · `providers/router.py` · `evaluation/layout_audit.py` · `frontend/src/pages/*` ·
`frontend/src/landing/MobileLanding.jsx` · `frontend/public/{manifest.webmanifest,sw.js}` · `tests/*`.
