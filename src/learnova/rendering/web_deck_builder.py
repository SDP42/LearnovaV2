"""
Learnova Web Deck Builder Module
Generates a standalone, responsive 60fps HTML5 presentation powered by Reveal.js and Mermaid.js.
Supports live interactive quizzes, flowcharts, tables, metric cards, and smooth slide transitions.
"""

import functools
import html
import os
import re
import json
from pathlib import Path
from learnova.rendering.theme_engine import (
    get_theme, auto_detect_theme, select_slide_layout, resolve_theme,
    readable_text_hex, THEMES,
)

_VENDOR = Path(__file__).parent / "vendor"


@functools.lru_cache(maxsize=8)
def _vendor(name: str) -> str:
    """Read a bundled Reveal.js asset. Returns '' if it is missing, so the
    builder can fall back to the CDN <script>/<link>."""
    try:
        return (_VENDOR / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _head_assets(font_query: str) -> str:
    """Inline the Reveal CSS (offline-safe); keep Google Fonts on its host,
    which the artifact CSP allows. Falls back to the CDN if a bundle is missing."""
    css = _vendor("reveal.min.css")
    theme_css = _vendor("theme-white.min.css")
    if css and theme_css:
        return (
            f"<style>{css}</style>\n<style>{theme_css}</style>\n"
            f'<link href="https://fonts.googleapis.com/css2?family={font_query}&display=swap" rel="stylesheet">'
        )
    return (
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/reveal.min.css" crossorigin="anonymous">\n'
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/theme/white.min.css" crossorigin="anonymous">\n'
        f'<link href="https://fonts.googleapis.com/css2?family={font_query}&display=swap" rel="stylesheet">'
    )


def _body_scripts() -> str:
    """Inline Reveal + the notes plugin so the deck runs with no network.
    Mermaid stays on the CDN (700 KB, and the native step flow rarely needs it)."""
    reveal = _vendor("reveal.min.js")
    notes = _vendor("notes.js")
    if reveal:
        parts = [f"<script>{reveal}</script>"]
        if notes:
            parts.append(f"<script>{notes}</script>")
        parts.append(
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.6.1/mermaid.min.js" crossorigin="anonymous"></script>'
        )
        return "\n".join(parts)
    return (
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/reveal.js" crossorigin="anonymous"></script>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/plugin/notes/notes.js" crossorigin="anonymous"></script>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.6.1/mermaid.min.js" crossorigin="anonymous"></script>'
    )


def _inline_quiz_html(quiz: dict, theme) -> str:
    """
    Render a checkpoint question as an interactive band at the foot of a slide:
    click an option, get right/wrong feedback and the explanation. Same
    ``lvQuizPick`` handler as the standalone QUIZ slide.
    """
    if not quiz:
        return ""
    options = [str(o).strip() for o in (quiz.get("options") or []) if str(o).strip()][:4]
    letters = "ABCD"
    correct = str(quiz.get("correct", "A")).strip()[:1].upper()
    explanation = html.escape(str(quiz.get("explanation", "")))
    difficulty = html.escape(str(quiz.get("difficulty", "")).upper())
    btns = "".join(
        f'<button onclick="lvQuizPick(this,{str(letters[i] == correct).lower()})" '
        f'style="flex:1 1 0;min-width:0;border:1px solid {theme.primary_hex};'
        f'background:{theme.bg_hex};color:{theme.text_hex};padding:7px 10px;'
        f'font-size:0.62em;border-radius:6px;cursor:pointer;text-align:left;">'
        f'<b>{letters[i]}.</b> {html.escape(re.sub(r"^\s*[A-Da-d][).:]\s*", "", opt))}</button>'
        for i, opt in enumerate(options)
    )
    diff = (f'<span style="float:right;font-size:0.55em;color:{theme.subtext_hex};">{difficulty}</span>'
            if difficulty else "")
    return f"""
    <div class="lv-quiz" style="margin-top:18px;border:2px solid {theme.accent_hex};
                background:{theme.card_bg_hex};border-radius:10px;padding:12px 14px;">
      <div style="color:{theme.text_hex};font-weight:700;font-size:0.72em;margin-bottom:8px;">
        Q{quiz.get('index', 1)}. {html.escape(str(quiz.get('question', '')))}{diff}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">{btns}</div>
      <div class="lv-quiz-exp" style="display:none;margin-top:10px;font-size:0.6em;
           color:{theme.text_hex};line-height:1.4;">{explanation}</div>
    </div>"""


def _font_query(theme) -> str:
    """Build the Google Fonts family query for the theme's chosen typefaces."""
    families = []
    for name in (theme.heading_font, theme.body_font):
        if not name or name in families:
            continue
        families.append(name)
    return "&family=".join(f.replace(" ", "+") + ":wght@400;600;800" for f in families)


# Only a figure the policy is *confident* is pure chrome (logo, divider, bullet
# icon) is hidden. Everything else is shown — a figure the source author put in
# the document is content until proven otherwise. SUMMARISE_TO_STRUCTURE used to
# hide the bitmap on the promise of a native redraw that was never built, so the
# figure just vanished; now we keep it. Set LEARNOVA_IMAGE_KEEP_ALL=1 to show
# even the DROP cases.
_IMAGE_KEEP_ALL = os.getenv("LEARNOVA_IMAGE_KEEP_ALL", "").lower() in {"1", "true", "yes", "on"}


def _image_html(orig: dict, theme) -> str:
    """
    Render an extracted figure as an inline data-URI <img>. The image policy can
    only *hide* a figure it is confident is decoration (DROP); a redraw-as-
    structure verdict still shows the bitmap, because losing it silently is worse
    than showing a slightly redundant picture. Never raises.
    """
    try:
        import base64

        img = orig.get("image") if isinstance(orig, dict) else None
        if not img or not img.get("bytes"):
            return ""
        raw = img["bytes"]
        ext = str(img.get("ext", "png")).lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "webp": "webp", "gif": "gif"}.get(ext, "png")

        from learnova.ai.image_policy import ImageMeta, decide_image_action, meta_from_bytes

        slide_text = " ".join(str(x) for x in (orig.get("text"),))
        try:
            meta = meta_from_bytes(raw, ext=ext, ocr_text=str(img.get("description", "")),
                                   slide_text=slide_text)
        except Exception:
            meta = ImageMeta(ext=ext, ocr_text=str(img.get("description", "")), slide_text=slide_text)
        action = decide_image_action(meta)

        # DROP = logo / divider / bullet icon. Hidden unless KEEP_ALL. Every
        # other verdict (KEEP_AS_IS, ENHANCE, SUMMARISE_TO_STRUCTURE, REGENERATE,
        # CAPTION_ONLY) renders the bitmap — we cannot generate a replacement, so
        # the real figure is the best available option.
        if action.action == "DROP" and not _IMAGE_KEEP_ALL:
            return ""
        b64 = base64.b64encode(raw).decode("ascii")
        cap = html.escape(action.caption or str(img.get("description", ""))[:120])
        cap_html = (f'<figcaption style="font-size:0.72rem;color:{theme.subtext_hex};'
                    f'margin-top:6px;text-align:center;">{cap}</figcaption>') if cap else ""
        badge = ' · low-res, flagged for cleanup' if action.action == "ENHANCE" else ""
        return (
            f'<figure style="margin:6px auto 0;max-width:100%;text-align:center;">'
            f'<img src="data:image/{mime};base64,{b64}" '
            f'style="max-width:100%;max-height:300px;border-radius:8px;'
            f'border:1px solid {theme.primary_hex}33;" alt="figure{badge}"/>'
            f'{cap_html}</figure>'
        )
    except Exception:
        return ""


def _family_block(family, data, theme):
    """Cached wrapper around family_blocks.render_family_block."""
    try:
        from learnova.rendering.family_blocks import render_family_block

        return render_family_block(family, data, theme)
    except Exception:
        return None


def _fragment_index_for(idx0: int, animation: dict | None) -> dict:
    """Map a bullet index -> reveal step number, from a deck-director animation."""
    if not animation:
        return {}
    out: dict = {}
    for step_no, step in enumerate(animation.get("steps") or []):
        for el in step.get("adds") or []:
            m = str(el)
            if m.startswith("el."):
                try:
                    out[int(m[3:])] = step_no
                except ValueError:
                    pass
    return out


def _staged_flow_html(steps: list[str], frag_map: dict, theme, *, cyclic: bool = False) -> str:
    """
    A vertical numbered process flow where each step is its own reveal element.

    Every step carries ``data-build`` (mapped from the deck-director animation, or
    its own ordinal) so present mode reveals them **one click at a time, keeping
    the earlier steps visible** — the fix for "it jumps straight to phase 5".
    """
    steps = [str(s).strip() for s in steps if str(s).strip()]
    if not steps:
        return ""
    on = readable_text_hex(theme.primary_hex)
    rows = []
    for i, step in enumerate(steps):
        build = frag_map.get(i, i)
        # The connector line is always visible — only the step cards are reveal
        # elements, so the step counter reads "3 / 5" not "3 / 9".
        connector = (
            f'<div style="width:2px;height:16px;margin:2px 0 2px 17px;'
            f'background:{theme.primary_hex}55;"></div>' if i > 0 else ""
        )
        rows.append(
            connector +
            f'<div data-el="el.{i}" data-build="{build}" '
            f'style="display:flex;gap:12px;align-items:flex-start;">'
            f'<span style="flex-shrink:0;width:34px;height:34px;border-radius:50%;'
            f'background:{theme.primary_hex};color:{on};font-weight:800;'
            f'display:flex;align-items:center;justify-content:center;font-size:0.95rem;">'
            f'{("↻" if cyclic and i == len(steps) - 1 else str(i + 1))}</span>'
            f'<div style="flex:1;background:{theme.card_bg_hex};border:1px solid {theme.primary_hex}33;'
            f'border-left:4px solid {theme.primary_hex};border-radius:8px;padding:12px 14px;'
            f'font-size:1rem;line-height:1.45;color:{theme.text_hex};">{html.escape(step)}</div></div>'
        )
    return (
        f'<div style="margin-top:20px;display:flex;flex-direction:column;'
        f'max-width:760px;">{"".join(rows)}</div>'
    )


def build_web_deck(slides_data: list[dict], topic_title: str = "Learnova Interactive Deck",
                   theme_id: str = "auto", theme_spec: dict | None = None,
                   deck_plan=None) -> str:
    """
    Constructs standalone HTML presentation with Reveal.js and Mermaid.js.

    When ``deck_plan`` (a ``rendering.deck_director.DeckPlan``) is supplied, each
    slide also gets: its director-chosen ``data-transition``, per-bullet
    progressive-reveal ``fragment`` markup, and a populated speaker-notes pane
    (Reveal's presenter view, opened with the ``s`` key).
    """
    theme = resolve_theme(topic_title, theme_id, theme_spec)
    # Text drawn on top of the primary fill. Hardcoding white broke every
    # light-primary palette; luminance picks the readable one.
    on_primary = readable_text_hex(theme.primary_hex)

    if deck_plan is None:
        try:
            from learnova.rendering.deck_director import plan_deck

            deck_plan = plan_deck(slides_data)
        except Exception:  # director must never break the render
            deck_plan = None

    slides_html_list = []

    # Title slide
    slides_html_list.append(f"""
    <section data-background-color="{theme.bg_hex}" class="title-slide">
        <h1 style="color: {theme.accent_hex}; font-family: '{theme.heading_font}', sans-serif; font-size: 3.8rem; text-transform: uppercase;">
            {html.escape(topic_title)}
        </h1>
        <div style="width: 100%; height: 6px; background-color: {theme.accent_hex}; margin: 20px 0;"></div>
        <h3 style="color: {theme.text_hex}; font-size: 1.5rem;">Generated by Learnova AI Engine • Theme: {html.escape(theme.name)}</h3>
        <p style="color: {theme.subtext_hex}; font-size: 1rem; margin-top: 30px;">Press <strong>Space</strong> or <strong>Right Arrow</strong> to Navigate</p>
    </section>
    """)

    prev_style = None
    for idx, data in enumerate(slides_data, 1):
        orig = data.get("original", {})
        imp = data.get("improved", {})
        if not isinstance(imp, dict):
            imp = {}

        layout_type = imp.get("layout_type", "MINIMAL_TEXT").upper()
        style_pattern = select_slide_layout(idx, layout_type, prev_style)
        prev_style = style_pattern
        title_text = html.escape(imp.get("title", orig.get("title", f"Slide {idx}")))
        takeaway_text = html.escape(imp.get("takeaway", "").strip())

        sp = deck_plan.by_index(idx - 1) if deck_plan is not None else None
        image_block = _image_html(orig, theme)
        slide_transition = sp.transition if sp else "slide"
        frag_map = _fragment_index_for(idx - 1, sp.animation if sp else None)
        notes_html = (
            f'<aside class="notes">{html.escape(sp.speaker_notes)}</aside>' if sp and sp.speaker_notes else ""
        )

        def _bullets_html(items, li_style=""):
            # Emit the reveal-step as data-build only. Bullets stay fully visible
            # in normal view (Canva/PowerPoint behaviour); the deck's script
            # promotes [data-build] to real Reveal fragments *only* in present
            # mode, so the Preview embed and a plain double-click never show a
            # slide of hidden text.
            #
            # Hierarchy: a short Title-Case label ("Semantic Analysis", "Rule-
            # Based MT") acts as a sub-heading and the ordinary sentences after
            # it are indented under it; a "↳ " prefix is an explicit sub-point.
            def _is_label(s: str) -> bool:
                s = s.strip().rstrip(":")
                if not (1 <= len(s.split()) <= 6):
                    return False
                if s.endswith((".", "!", "?")):
                    return False
                letters = [c for c in s if c.isalpha()]
                return bool(letters) and s[:1].isupper() and not s.islower()

            out = []
            for bi, b in enumerate(items):
                raw = str(b)
                db = f' data-build="{frag_map[bi]}"' if bi in frag_map else ""
                sub = raw.lstrip().startswith(("↳", "-", "•"))
                text = raw.lstrip("↳-• ").strip()
                if _is_label(text):
                    cls = "lv-blabel"
                elif sub:
                    cls = "lv-bsub"
                else:
                    cls = "lv-bmain"
                out.append(
                    f"<li{db} class='{cls}' style='{li_style}'>{html.escape(text)}</li>"
                )
            return "".join(out)

        slide_body = ""

        # ── 0. EXPANDED FAMILY — the Deck Director confidently chose one and
        #      carried its data. This wins over a stale heuristic layout_type
        #      (e.g. the router guessed METRIC for "y = 2x + 1", the VMS knows
        #      it is a FUNCTION_PLOT).
        _fam_block = None
        if (
            sp
            and getattr(sp, "family", None)
            and getattr(sp, "data", None)
            and getattr(sp, "confidence", 0) >= 0.62
            and layout_type not in {"QUIZ"}
        ):
            _fam_block = _family_block(sp.family, sp.data, theme)

        if _fam_block:
            slide_body = _fam_block

        # ── 1. TABLE LAYOUT ──────────────────────────────────────────────────
        elif layout_type == "TABLE" and "table_headers" in imp:
            headers = imp.get("table_headers", [])
            rows = imp.get("table_rows", [])
            th_cells = "".join(f"<th style='background-color:{theme.primary_hex}; color:{on_primary}; padding:12px;'>{html.escape(str(h))}</th>" for h in headers)
            tr_rows = ""
            for r in rows:
                tds = "".join(f"<td style='padding:10px; border-bottom:1px solid #ddd;'>{html.escape(str(val))}</td>" for val in r)
                tr_rows += f"<tr>{tds}</tr>"

            slide_body = f"""
            <div style="overflow-x:auto; margin-top:20px;">
                <table style="width:100%; border-collapse:collapse; background:#fff; box-shadow:0 4px 10px rgba(0,0,0,0.1); font-size:0.85rem;">
                    <thead><tr>{th_cells}</tr></thead>
                    <tbody>{tr_rows}</tbody>
                </table>
            </div>
            """

        # ── 2. METRIC LAYOUT ──────────────────────────────────────────────────
        elif layout_type == "METRIC":
            metric_val = html.escape(str(imp.get("metric_value", "100%")))
            metric_lbl = html.escape(str(imp.get("metric_label", title_text)))
            metric_desc = html.escape(str(imp.get("metric_desc", takeaway_text)))

            slide_body = f"""
            <div style="background:{theme.primary_hex}; border:4px solid {theme.accent_hex}; border-radius:12px; padding:40px; text-align:center; color:{on_primary}; margin-top:20px;">
                <h1 style="font-size:4.5rem; color:{theme.accent_hex}; margin:0;">{metric_val}</h1>
                <h3 style="color:{theme.subtext_hex}; text-transform:uppercase; margin:10px 0;">{metric_lbl}</h3>
                <p style="font-size:1.2rem; color:{on_primary};">{metric_desc}</p>
            </div>
            """

        # ── 3. CHECKPOINT QUIZ LAYOUT — interactive, no spoiler ───────────────
        elif layout_type == "QUIZ":
            q_text = html.escape(str(imp.get("question", "Checkpoint Question")))
            options = imp.get("options", [])
            correct_opt = str(imp.get("correct", "A")).strip()[:1].upper()
            explanation = html.escape(str(imp.get("explanation", "")))
            difficulty = html.escape(str(imp.get("difficulty", "")).upper())
            letters = "ABCD"

            opt_buttons = ""
            for i, opt in enumerate(options[:4]):
                opt_str = html.escape(re.sub(r"^\s*[A-Da-d][).:]\s*", "", str(opt)))
                is_correct = "true" if letters[i] == correct_opt else "false"
                opt_buttons += (
                    f'<button onclick="lvQuizPick(this,{is_correct})" '
                    f'style="flex:1 1 45%;padding:14px 16px;background:{theme.card_bg_hex};'
                    f'border:2px solid {theme.primary_hex};border-radius:8px;font-size:0.95rem;'
                    f'cursor:pointer;text-align:left;color:{theme.text_hex};">'
                    f'<b>{letters[i]}.</b> {opt_str}</button>'
                )

            diff_badge = (
                f'<span style="font-size:0.7rem;color:{theme.subtext_hex};'
                f'border:1px solid {theme.subtext_hex};border-radius:10px;padding:1px 8px;'
                f'margin-left:10px;">{difficulty}</span>' if difficulty else ""
            )
            slide_body = f"""
            <div class="lv-quiz" style="text-align:left;background:{theme.card_bg_hex};
                 border-left:6px solid {theme.accent_hex};padding:20px;border-radius:8px;margin-top:20px;">
                <h3 style="color:{theme.primary_hex};margin-top:0;">{q_text}{diff_badge}</h3>
                <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:16px;">{opt_buttons}</div>
                <div class="lv-quiz-exp" style="display:none;margin-top:14px;font-size:0.9rem;
                     color:{theme.text_hex};line-height:1.5;background:{theme.bg_hex};
                     border-radius:6px;padding:12px;">{explanation}</div>
            </div>
            """

        # ── 4. FLOWCHART / PROCESS LAYOUT — staged, one step per click ────────
        elif layout_type in {"FLOWCHART", "PROCESS_DIAGRAM"}:
            bullets = imp.get("bullets", [])
            cyclic = "cycl" in str(imp.get("title", "")).lower() or bool(imp.get("cyclic"))
            slide_body = _staged_flow_html(bullets, frag_map, theme, cyclic=cyclic)
            if not slide_body:
                # No usable steps — fall back to whatever mermaid we have.
                escaped_mermaid = html.escape(
                    imp.get("mermaid_code", "graph TD\n  A[Start] --> B[End]")
                )
                slide_body = (
                    f'<div style="margin-top:20px;background:#fff;padding:15px;'
                    f'border:2px solid {theme.primary_hex};border-radius:8px;">'
                    f'<div class="mermaid" style="font-size:0.8rem;">{escaped_mermaid}</div></div>'
                )

        # ── 5. EXPANDED VISUAL FAMILIES (from the Deck Director) ─────────────
        elif sp and getattr(sp, "family", None) and getattr(sp, "data", None) and _family_block(
            sp.family, sp.data, theme
        ):
            slide_body = _family_block(sp.family, sp.data, theme)

        # ── 6. DEFAULT MINIMAL TEXT LAYOUT ───────────────────────────────────
        else:
            bullets = imp.get("bullets", [])
            n = len(bullets)
            total_chars = sum(len(str(b)) for b in bullets)
            # A teaching slide adapts by *display*, not by cutting text. Pick a
            # sensible base font from the load; the auto-fit script then nudges
            # it to fill the stage (grow when light, shrink when it overflows).
            if n <= 3 and total_chars < 360:
                fs, lh, gap = "1.5rem", "1.6", "16px"
            elif n <= 6 and total_chars < 1000:
                fs, lh, gap = "1.15rem", "1.5", "11px"
            elif total_chars < 2200:
                fs, lh, gap = "0.98rem", "1.44", "8px"
            else:
                fs, lh, gap = "0.86rem", "1.34", "6px"
            b_items = _bullets_html(bullets, f"margin-bottom:{gap};")
            slide_body = f"""
            <div class="lv-textbody" style="text-align:left; margin-top:12px;
                 font-size:{fs}; line-height:{lh};">
                <ul style="padding-left:20px; list-style:disc;">{b_items}</ul>
            </div>
            """

        # Takeaway section
        takeaway_html = f"""
        <div style="background:{theme.primary_hex}; color:{on_primary}; border-left:4px solid {theme.accent_hex}; padding:12px; font-size:0.9rem; margin-top:20px; text-align:left; border-radius:4px;">
            <strong>Key Takeaway:</strong> {takeaway_text}
        </div>
        """ if takeaway_text else ""

        # Body layout. A text slide that also has a figure puts the text in a
        # left column and the figure in a right rail, so neither is squashed and
        # the whole thing still fits (the auto-fit script does the final nudge).
        _text_layout = layout_type in {"MINIMAL_TEXT", "", "CARD_GRID"} and not _fam_block
        if _text_layout and image_block:
            body_inner = f"""
            <div style="display:flex; gap:26px; align-items:flex-start;">
              <div style="flex:1 1 60%; min-width:0;">{slide_body}</div>
              <div style="flex:0 0 34%; max-width:34%;">{image_block}</div>
            </div>
            {_inline_quiz_html(imp.get("inline_quiz"), theme)}
            {takeaway_html}
            """
        else:
            body_inner = f"""
            {slide_body}
            {image_block}
            {_inline_quiz_html(imp.get("inline_quiz"), theme)}
            {takeaway_html}
            """

        slides_html_list.append(f"""
        <section data-transition="{slide_transition}" style="text-align:left;">
            <div style="border-bottom:3px solid {theme.primary_hex}; padding-bottom:8px; margin-bottom:6px;">
                <h2 style="color:{theme.primary_hex}; font-family:'{theme.heading_font}', sans-serif; font-size:2rem; margin:0; text-transform:uppercase;">{title_text}</h2>
            </div>
            <div class="lv-body">
            {body_inner}
            </div>
            {notes_html}
        </section>
        """)

    slides_content = "\n".join(slides_html_list)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(topic_title)} – Learnova Interactive Presentation</title>
    {_head_assets(_font_query(theme))}
    <style>
        body, .reveal {{
            font-family: '{theme.body_font}', sans-serif !important;
            background-color: #f8f9fc;
        }}
        .reveal h1, .reveal h2, .reveal h3 {{
            font-family: '{theme.heading_font}', sans-serif !important;
        }}
        .reveal .slides {{
            text-align: left;
        }}
        /* Every slide fills the stage so a light slide isn't a small block
           floating in the middle of a big empty canvas. */
        .reveal .slides > section {{
            min-height: 690px;
            box-sizing: border-box;
        }}
        /* Teaching-slide bullet hierarchy + indentation */
        .reveal .lv-textbody ul {{ margin: 0; }}
        .reveal .lv-textbody li {{ padding-left: 2px; }}
        .reveal .lv-textbody li.lv-blabel {{
            list-style: none;
            margin-left: -20px;
            margin-top: 12px;
            font-weight: 700;
            color: {theme.primary_hex};
            text-transform: none;
        }}
        .reveal .lv-textbody li.lv-blabel::before {{
            content: "▸ ";
            color: {theme.accent_hex};
        }}
        .reveal .lv-textbody li.lv-bmain {{ margin-left: 4px; }}
        .reveal .lv-textbody li.lv-bsub {{
            margin-left: 22px;
            list-style: circle;
            opacity: .92;
        }}
        .reveal .lv-textbody li.lv-blabel + li,
        .reveal .lv-textbody li.lv-bmain,
        .reveal .lv-textbody li.lv-bsub {{ }}
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
            {slides_content}
        </div>
    </div>

    <!-- Reveal.js + notes plugin: bundled inline (offline-safe). Mermaid on CDN. -->
    {_body_scripts()}
    <script>
        // Progressive reveal (one idea per click) is OFF by default: a study
        // deck opened directly should show the WHOLE slide so it can be read.
        // It turns ON only when actually presenting — ?build / ?present in the
        // URL, window.__learnovaBuild set by an embedder, or the presenter
        // console calling __enableBuilds().
        var LV_BUILD = (function () {{
            try {{
                var s = (location.search + location.hash);
                if (/[?#&](build|present)\\b/.test(s)) return true;
                if (window.__learnovaBuild) return true;
                return false;
            }} catch (e) {{ return false; }}
        }})();

        function lvApplyBuilds() {{
            var els = document.querySelectorAll('[data-build]');
            els.forEach(function (el) {{
                if (LV_BUILD) {{
                    el.classList.add('fragment');
                    var i = parseInt(el.getAttribute('data-build'), 10);
                    if (!isNaN(i)) el.setAttribute('data-fragment-index', i);
                }} else {{
                    el.classList.remove('fragment');
                    el.removeAttribute('data-fragment-index');
                }}
            }});
        }}
        // Callable from a parent frame (the presenter console) to switch on builds.
        window.__enableBuilds = function () {{
            LV_BUILD = true;
            lvApplyBuilds();
            lvUpdateStepHud();
            if (window.Reveal && Reveal.sync) Reveal.sync();
        }};
        // ...and to switch them back off (study / scan mode).
        window.__disableBuilds = function () {{
            LV_BUILD = false;
            lvApplyBuilds();
            lvUpdateStepHud();
            if (window.Reveal && Reveal.sync) Reveal.sync();
        }};
        // Presenter's own screen: keep fragment tracking (so Next advances the
        // audience one point at a time) but SHOW every point + figure, dimming
        // the ones the audience has not seen yet.
        window.__presenterPeek = function () {{
            window.__enableBuilds();
            if (document.getElementById('lv-peek-style')) return;
            var st = document.createElement('style');
            st.id = 'lv-peek-style';
            st.textContent =
              '.reveal .slides section .fragment{{opacity:1!important;visibility:visible!important;}}'
              + '.reveal .slides section .fragment:not(.visible):not(.current-fragment){{opacity:.32!important;}}'
              + '.reveal figure,.reveal img{{opacity:1!important;visibility:visible!important;}}';
            document.head.appendChild(st);
        }};

        // Small "Step 2 / 5" heads-up + a toggle, bottom-right. Only meaningful
        // on slides that actually have build steps.
        function lvUpdateStepHud() {{
            var hud = document.getElementById('lv-step-hud');
            if (!hud || !window.Reveal || !Reveal.getState) return;
            var st = Reveal.getState();
            var cur = Reveal.getCurrentSlide();
            var total = cur ? cur.querySelectorAll('.fragment').length : 0;
            if (!LV_BUILD || total === 0) {{ hud.style.display = 'none'; return; }}
            var shown = cur.querySelectorAll('.fragment.visible').length;
            hud.style.display = 'flex';
            hud.querySelector('#lv-step-label').textContent =
                'Step ' + Math.min(shown, total) + ' / ' + total;
        }}

        lvApplyBuilds();

        Reveal.initialize({{
            controls: true,
            progress: true,
            // Content-heavy lecture slides: top-align (not vertically centred,
            // which pushes an 8-bullet slide off both edges) and allow the deck
            // to shrink further so nothing is clipped.
            center: false,
            width: 1180,
            height: 740,
            margin: 0.045,
            minScale: 0.2,
            maxScale: 1.6,
            disableLayout: false,
            // Hash routing calls history.replaceState with the page URL, which
            // throws a SecurityError inside a blob: iframe (the embedded
            // preview / presenter view) and kills Reveal init. The deck is
            // driven by Reveal.slide()/setState() there, so it is not needed.
            hash: false,
            respondToHashChanges: false,
            slideNumber: 'c/t',
            transition: 'slide',        // per-slide data-transition overrides this
            transitionSpeed: 'fast',
            fragments: LV_BUILD,
            plugins: [
                (typeof RevealNotes !== 'undefined' ? RevealNotes : null),
                (typeof RevealHighlight !== 'undefined' ? RevealHighlight : null),
            ].filter(Boolean),
        }});

        mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});

        // Auto-fit: keep every slide's content on screen and filling the stage.
        //  - taller than the stage  -> scale the body DOWN (nothing clipped)
        //  - much shorter            -> scale it UP (a light slide isn't a
        //                               postage stamp in the middle of the canvas)
        // Text is never cut; only the display adapts.
        function lvAutoFit(slide) {{
            if (!slide) return;
            var body = slide.querySelector('.lv-body');
            if (!body) return;
            body.style.transform = '';
            body.style.width = '';
            var h2 = slide.querySelector('h2');
            // Measure against the STAGE, not the section — a section that
            // overflows reports its own (too-large) height, so auto-fit would
            // never trigger. Reveal's configured stage is 740 tall.
            var stage = (Reveal.getConfig && Reveal.getConfig().height) || 740;
            var avail = stage - (h2 ? h2.offsetHeight : 40) - 34;
            if (avail < 120) return;
            var prevT = body.style.transform;
            body.style.transform = 'none';
            var need = body.scrollHeight;
            body.style.transform = prevT;
            var k = 1;
            if (need > avail) {{
                k = Math.max(0.5, avail / need);
            }} else if (need < avail * 0.72) {{
                k = Math.min(1.5, (avail * 0.9) / Math.max(need, 1));
            }}
            if (Math.abs(k - 1) > 0.015) {{
                body.style.transform = 'scale(' + k.toFixed(3) + ')';
                body.style.transformOrigin = 'top left';
                body.style.width = (100 / k).toFixed(1) + '%';
            }}
        }}
        Reveal.on('ready', function (e) {{ lvAutoFit(e.currentSlide); }});
        Reveal.on('slidechanged', function (e) {{ lvAutoFit(e.currentSlide); }});

        Reveal.on('ready', lvUpdateStepHud);
        Reveal.on('slidechanged', lvUpdateStepHud);
        Reveal.on('fragmentshown', lvUpdateStepHud);
        Reveal.on('fragmenthidden', lvUpdateStepHud);
        (function lvStepHudInit() {{
            var hud = document.createElement('div');
            hud.id = 'lv-step-hud';
            hud.style.cssText = 'position:fixed;right:14px;bottom:14px;z-index:60;'
                + 'display:none;gap:10px;align-items:center;background:{theme.primary_hex};'
                + 'color:{on_primary};padding:6px 12px;border-radius:20px;font-size:13px;'
                + 'font-family:sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.25);';
            hud.innerHTML = '<span id="lv-step-label">Step 1 / 1</span>'
                + '<button id="lv-step-toggle" style="all:unset;cursor:pointer;'
                + 'border:1px solid currentColor;border-radius:12px;padding:1px 8px;font-size:11px;">'
                + 'show all</button>';
            document.body.appendChild(hud);
            hud.querySelector('#lv-step-toggle').addEventListener('click', function () {{
                if (LV_BUILD) {{ window.__disableBuilds(); this.textContent = 'step through'; }}
                else {{ window.__enableBuilds(); this.textContent = 'show all'; }}
            }});
        }})();

        // Checkpoint quiz: mark the picked option, reveal the explanation.
        // Locks after the first pick so the answer is not a click-through.
        function lvQuizPick(btn, isCorrect) {{
            var box = btn.closest('.lv-quiz');
            if (!box || box.dataset.answered) return;
            box.dataset.answered = '1';
            var btns = box.querySelectorAll('button');
            btns.forEach(function (b) {{ b.disabled = true; b.style.cursor = 'default'; }});
            btn.style.borderColor = isCorrect ? '{theme.accent_hex}' : '#c0392b';
            btn.style.background = isCorrect ? '{theme.accent_hex}22' : '#c0392b18';
            if (!isCorrect) {{
                btns.forEach(function (b) {{
                    if (b.getAttribute('onclick').indexOf('true') > -1) {{
                        b.style.borderColor = '{theme.accent_hex}';
                        b.style.background = '{theme.accent_hex}22';
                    }}
                }});
            }}
            var exp = box.querySelector('.lv-quiz-exp');
            if (exp) exp.style.display = 'block';
        }}

        function checkAnswer(btn, isCorrect) {{
            const parent = btn.parentElement;
            const feedback = parent.parentElement.querySelector('.quiz-feedback');
            const exp = parent.parentElement.querySelector('.quiz-exp');
            
            if (isCorrect) {{
                btn.style.backgroundColor = '{theme.accent_hex}';
                btn.style.color = '#000000';
                feedback.style.display = 'block';
                feedback.style.backgroundColor = '#d4edda';
                feedback.style.color = '#155724';
                feedback.innerHTML = '✅ Correct Answer!';
            }} else {{
                btn.style.backgroundColor = '#ffcccc';
                feedback.style.display = 'block';
                feedback.style.backgroundColor = '#f8d7da';
                feedback.style.color = '#721c24';
                feedback.innerHTML = '❌ Incorrect. Try again!';
            }}
            if (exp) exp.style.display = 'block';
        }}
    </script>
</body>
</html>
"""
