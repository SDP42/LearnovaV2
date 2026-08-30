# The Gallery — ready-made presentations

A shared catalogue of teaching topics. A user browses by subject, previews a
finished deck and clicks **Use** to drop an editable copy into their own
projects — or clicks **Generate** on any catalogue topic to open Create
pre-filled.

## Pieces

| Piece | Path |
|---|---|
| Catalogue (1000+ topics) | `data/gallery/catalog.json` — built by `scripts/gallery/build_catalog.py` |
| Catalogue loader / query | `src/learnova/gallery/catalog.py` |
| Deck storage + clone-on-use | `src/learnova/gallery/store.py` |
| Batch deck generator | `src/learnova/gallery/builder.py` |
| API | `GET /api/gallery`, `GET /api/gallery/{slug}`, `GET /api/gallery/{slug}/deck`, `POST /api/gallery/{slug}/use` |
| UI | `frontend/src/pages/Gallery.jsx` → `/app/gallery` |

## Catalogue tiers

* **`status: "outline"`** — a curated topic with a real structured teaching
  brief. `builder` turns each into a finished, previewable deck.
* **`status: "index"`** — title + subject + tags only. Shown for breadth;
  "Generate" opens Create with a starter scaffold.

`GET /api/gallery` reports the entry as `"ready"` once a built deck exists on
disk.

## Building the decks

Generated decks live under the synthetic user `__gallery__`, reusing every
`deck_library` primitive. They are **not** committed (`.data/` is gitignored) —
a deployment populates them by running the builder:

```bash
# everything with a brief (currently the ~20 curated topics)
LEARNOVA_NO_LLM=1 PYTHONPATH=src .venv/bin/python -m learnova.gallery.builder --all

# a subset while iterating
PYTHONPATH=src .venv/bin/python -m learnova.gallery.builder --subject Biology --limit 5
```

Re-runs skip existing decks unless `--force`. Each deck is a full pipeline run
(layout, visuals, quizzes, scoring, PPTX + web deck), so it costs LLM calls and
minutes; the batch is resumable.

## Growing past the curated set

To add pre-built decks for the index tier, give those entries a real `outline`
in `build_catalog.py` (or a batch step that expands a title into a brief via an
LLM), rebuild the catalogue, then run the builder. The UI needs no change — it
shows whatever the API reports as ready.
