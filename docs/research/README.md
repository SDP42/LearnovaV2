# Learnova research track

| File | What it is |
|---|---|
| [`LEARNOVA_PAPER.md`](LEARNOVA_PAPER.md) | **Umbrella paper.** The deterministic decision layer (content preservation, VMS, image/text policy — the *non-model* contribution) + PSF + CLASS + system, with guarantees and a pre-registered evaluation plan (E1–E8). |
| [`PSF_DESIGN.md`](PSF_DESIGN.md) | Full design of the PSF metric (math) and the CLASS algorithm, with the novelty statement |
| [`paper_draft.md`](paper_draft.md) | Narrower PSF/CLASS-only submission draft — abstract, sections, RQ table |
| [`VISUAL_INTELLIGENCE.md`](VISUAL_INTELLIGENCE.md) | Design + status of the deterministic decision layer (VMS, text policy, image policy, progressive reveal) |

## Code

| Path | Role |
|---|---|
| `src/learnova/scoring/psf.py` | PSF sub-indices (`E`, `L`, `C`), deck aggregation with topic-flow term, and the `segment_blocks` CLASS dynamic program. Pure stdlib, deterministic. |
| `src/learnova/scoring/scorer.py` | `score_all_slides(deck, engine="psf")` — opt-in PSF path alongside the original heuristic |
| `src/learnova/pipeline/density.py` | `LEARNOVA_USE_CLASS=1` switches pagination from even-split to load-optimal CLASS |
| `scripts/calibrate_psf.py` | Fit `PSFParams` from a human-ratings CSV |
| `tests/test_psf.py` | Unit tests incl. a brute-force optimality check for CLASS |

## Quick start

```bash
# score an existing deck two ways
python -c "from learnova.scoring.scorer import score_all_slides; ..."

# run the pipeline with load-optimal pagination
LEARNOVA_USE_CLASS=1 python -m learnova ...

# calibrate once you have ratings
python scripts/calibrate_psf.py ratings.csv --out fitted_psf_params.json
```

## Next steps to publication

1. Collect the deck corpus (open educational docs) and human ratings (§5.1).
2. Run `calibrate_psf.py`; report 5-fold CV numbers (E1).
3. Ablations E2/E3; CLASS study E4; optional learning study E5; runtime E6.
4. Fill the RQ table in `paper_draft.md`, add references, submit.
