# The Deck Director — whole-deck presentation decisions

`src/learnova/rendering/deck_director.py`. Deterministic, tested
(`tests/test_deck_director.py`). Runs after the pipeline, before rendering.

Single-slide stages cannot decide things that depend on a slide's *neighbours*
or on the deck as a whole. The Director does:

| Decision | How |
|---|---|
| **Visual** (family / variant) | VMS (`ai/visual_selector`); keeps a confident existing structural layout, else lets the VMS choose |
| **Animation** | `plan_animation_steps` — the progressive-reveal timeline |
| **Transition** into each slide | §1 — from the *semantic relationship* to the previous slide |
| **Summarisation directive** | §2 — PRESERVE / BALANCED / COMPRESS |
| **Speaker notes** | §3 — assembled for the web presenter view and the PPTX notes pane |
| **Pacing** | section boundaries + estimated running time |

---

## 1. Semantic transition selection

A deck where every slide slides in from the right feels machine-made. A human
presenter varies the transition to signal the *relationship* between slides.
The Director picks the transition **into** slide *s* from its relationship with
*s − 1*:

```
overlap = Jaccard(content_words(s-1), content_words(s))

s is a numbered continuation ("Topic (2/3)")   -> none      (one continuous thought)
s is a quiz / checkpoint                        -> concave   (distinct "test" feel)
s looks like a section head AND overlap < 0.2   -> zoom      (hard break, new section)
overlap >= 0.45                                 -> fade      (closely related)
0.15 <= overlap < 0.45                          -> slide     (next point, same topic)
overlap < 0.15                                  -> convex    (topic shift)
first slide                                     -> slide
```

"Section head" = a short (≤5-word) title with almost no body, or one starting
`Chapter / Unit / Module / Part / Section / Introduction / Overview`.

This reuses the same concept-overlap signal as the PSF `Flow` term (§3.6 of
`PSF_DESIGN.md`), so the metric that *scores* deck cohesion and the logic that
*presents* it agree.

Each choice ships with a `transition_reason` string, so the studio UI can
explain "zoom — new section" per slide and let the user override.

---

## 2. Summarisation directive

Per slide, from two signals already computed elsewhere:

```
verbatim_ratio = VERBATIM sentences / all sentences      (ai/text_policy)
load           = L(slide)                                (scoring/psf.cognitive_load)

verbatim_ratio >= 0.40   -> PRESERVE   (definitions/theorems/quotes dominate — keep wording, slow down)
load >= 0.60             -> COMPRESS   (slide is overloaded — tighten hard, talk don't read)
otherwise                -> BALANCED
```

The directive is advisory metadata today (it drives the speaker-note hint and
will gate a future re-tightening pass); it does not silently rewrite content.

---

## 3. Speaker notes

Assembled per slide so both presenter surfaces are populated:

```
KEY POINT TO LAND: <takeaway>

Reveal, one click at a time:
  1. <step 1 label>
  2. <step 2 label>
  ...

Read these exactly (do not paraphrase):
  - <verbatim sentence>

<directive hint>

~<est seconds>s
```

- **Web deck** → `<aside class="notes">`; Reveal's presenter view (`s` key)
  shows notes + next-slide preview + a timer. Wired in
  `web_deck_builder.build_web_deck(deck_plan=...)` along with the
  `notes` and `highlight` plugins.
- **PPTX** → the slide's notes pane (next: `ppt_builder`).

---

## 4. Running-time estimate

`~12s base + 7s per reveal step + 25s per quiz`, summed, plus 8s for the title.
Rough, but enough for the studio to show "≈ 14 min" and to warn when a deck is
too long for its slot.

---

## 5. Research angle (contribution #3, after PSF and VMS)

**Semantic transition selection** is itself evaluable: show raters decks with
(a) uniform transitions, (b) random transitions, (c) Director transitions, and
measure perceived coherence / professionalism / "did the structure help you
follow it". Costs one extra rating column on the existing corpus. Pairs with
the PSF `Flow` term — same signal, two uses.

---

## 6. Status / next

- Director: **done + tested.**
- Web deck consumes it: transitions, per-bullet fragments, presenter notes — **done.**
- Next: `ppt_builder` reads the plan → per-shape entrance animations + notes pane;
  new SVG family renderers; feed `animation.steps` count into CLASS as the
  realised slide segmentation.
