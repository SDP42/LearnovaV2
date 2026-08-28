"""
Learnova Web Deck Builder Module
Generates a standalone, responsive 60fps HTML5 presentation powered by Reveal.js and Mermaid.js.
Supports live interactive quizzes, flowcharts, tables, metric cards, and smooth slide transitions.
"""

import html
import os
import re
import json
from learnova.rendering.theme_engine import (
    get_theme, auto_detect_theme, select_slide_layout, resolve_theme,
    readable_text_hex, THEMES,
)

def _inline_quiz_html(quiz: dict, theme) -> str:
    """Render a checkpoint question as a band at the foot of a web-deck slide."""
    if not quiz:
        return ""
    options = [str(o).strip() for o in (quiz.get("options") or []) if str(o).strip()][:4]
    letters = "ABCD"
    chips = "".join(
        f'<div style="flex:1 1 0;min-width:0;border:1px solid {theme.primary_hex};'
        f'background:{theme.bg_hex};color:{theme.text_hex};padding:6px 10px;'
        f'font-size:0.62em;border-radius:6px;">'
        f'<b>{letters[i]}.</b> {html.escape(re.sub(r"^\s*[A-Da-d][).:]\s*", "", opt))}</div>'
        for i, opt in enumerate(options)
    )
    return f"""
    <div style="margin-top:18px;border:2px solid {theme.accent_hex};
                background:{theme.card_bg_hex};border-radius:10px;padding:12px 14px;">
      <div style="color:{theme.text_hex};font-weight:700;font-size:0.72em;margin-bottom:8px;">
        Q{quiz.get('index', 1)}. {html.escape(str(quiz.get('question', '')))}
      </div>
      <div style="display:flex;gap:8px;">{chips}</div>
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
            f'<figure style="margin:18px auto 0;max-width:70%;text-align:center;">'
            f'<img src="data:image/{mime};base64,{b64}" '
            f'style="max-width:100%;max-height:340px;border-radius:8px;'
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
            out = []
            for bi, b in enumerate(items):
                db = f' data-build="{frag_map[bi]}"' if bi in frag_map else ""
                out.append(f"<li{db} style='{li_style}'>{html.escape(str(b))}</li>")
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

        # ── 3. INTERLEAVED QUIZ LAYOUT ────────────────────────────────────────
        elif layout_type == "QUIZ":
            q_text = html.escape(imp.get("question", "Checkpoint Question"))
            options = imp.get("options", [])
            correct_opt = html.escape(imp.get("correct", "A"))
            explanation = html.escape(imp.get("explanation", ""))

            opt_buttons = ""
            for opt in options:
                opt_str = html.escape(str(opt))
                is_correct = "true" if opt_str.startswith(correct_opt) else "false"
                opt_buttons += f"""
                <button onclick="checkAnswer(this, {is_correct})" style="width:48%; padding:15px; margin:1%; background:#ffffff; border:3px solid {theme.primary_hex}; font-weight:bold; font-size:1rem; cursor:pointer; transition:all 0.2s;">
                    {opt_str}
                </button>
                """

            slide_body = f"""
            <div style="text-align:left; background:#f4f6fb; border-left:6px solid {theme.primary_hex}; padding:20px; border-radius:8px; margin-top:20px;">
                <h3 style="color:{theme.primary_hex}; margin-top:0;">❓ {q_text}</h3>
                <div style="display:flex; flex-wrap:wrap; margin-top:15px;">
                    {opt_buttons}
                </div>
                <div class="quiz-feedback" style="display:none; margin-top:15px; padding:12px; border-radius:6px; font-weight:bold;"></div>
                <p class="quiz-exp" style="display:none; font-size:0.9rem; color:#444; margin-top:5px;">💡 {explanation}</p>
            </div>
            """

        # ── 4. FLOWCHART LAYOUT ───────────────────────────────────────────────
        elif layout_type == "FLOWCHART":
            mermaid_code = imp.get("mermaid_code", "graph TD\n  A[Start] --> B[End]")
            escaped_mermaid = html.escape(mermaid_code)
            bullets = imp.get("bullets", [])
            b_items = _bullets_html(bullets, "margin-bottom:8px;")

            slide_body = f"""
            <div style="display:flex; gap:20px; text-align:left; margin-top:20px;">
                <div style="flex:1; background:#ffffff; padding:15px; border:2px solid {theme.primary_hex}; border-radius:8px;">
                    <div class="mermaid" style="font-size:0.8rem;">
                        {escaped_mermaid}
                    </div>
                </div>
                <div style="flex:1; font-size:0.9rem;">
                    <h4 style="color:{theme.primary_hex}; margin-top:0;">Process Steps:</h4>
                    <ul>{b_items}</ul>
                </div>
            </div>
            """

        # ── 5. EXPANDED VISUAL FAMILIES (from the Deck Director) ─────────────
        elif sp and getattr(sp, "family", None) and getattr(sp, "data", None) and _family_block(
            sp.family, sp.data, theme
        ):
            slide_body = _family_block(sp.family, sp.data, theme)

        # ── 6. DEFAULT MINIMAL TEXT LAYOUT ───────────────────────────────────
        else:
            bullets = imp.get("bullets", [])
            b_items = _bullets_html(bullets, "margin-bottom:12px;")
            slide_body = f"""
            <div style="text-align:left; margin-top:20px; font-size:1.1rem; line-height:1.6;">
                <ul>{b_items}</ul>
            </div>
            """

        # Takeaway section
        takeaway_html = f"""
        <div style="background:{theme.primary_hex}; color:{on_primary}; border-left:4px solid {theme.accent_hex}; padding:12px; font-size:0.9rem; margin-top:20px; text-align:left; border-radius:4px;">
            <strong>Key Takeaway:</strong> {takeaway_text}
        </div>
        """ if takeaway_text else ""

        # Slide wrapper
        slides_html_list.append(f"""
        <section data-transition="{slide_transition}" style="text-align:left;">
            <div style="border-bottom:3px solid {theme.primary_hex}; padding-bottom:10px;">
                <h2 style="color:{theme.primary_hex}; font-family:'{theme.heading_font}', sans-serif; font-size:2.2rem; margin:0; text-transform:uppercase;">{title_text}</h2>
            </div>
            {slide_body}
            {image_block}
            {_inline_quiz_html(imp.get("inline_quiz"), theme)}
            {takeaway_html}
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
    <!-- Reveal.js CSS (pinned stable 4.6.1) -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/reveal.min.css" crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/theme/white.min.css" crossorigin="anonymous">
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family={_font_query(theme)}&display=swap" rel="stylesheet">
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
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
            {slides_content}
        </div>
    </div>

    <!-- Reveal.js (pinned stable 4.6.1, classic UMD build) -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/reveal.js" crossorigin="anonymous"></script>
    <!-- Presenter view (speaker notes + next-slide preview + timer): press 's' -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/plugin/notes/notes.js" crossorigin="anonymous"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.6.1/plugin/highlight/highlight.js" crossorigin="anonymous"></script>
    <!-- Mermaid.js (cdnjs UMD standalone build – works in local file:// and data URIs) -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.6.1/mermaid.min.js" crossorigin="anonymous"></script>
    <script>
        // Present mode = ?build / #build in the URL, or a parent frame that set
        // window.__learnovaBuild before load. Normal / preview view keeps every
        // bullet visible; only present mode turns [data-build] into fragments.
        var LV_BUILD = (function () {{
            try {{
                if (window.__learnovaBuild) return true;
                var s = (location.search + location.hash);
                return /[?#&]build\\b/.test(s);
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
            if (window.Reveal && Reveal.sync) Reveal.sync();
        }};

        lvApplyBuilds();

        Reveal.initialize({{
            controls: true,
            progress: true,
            center: true,
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
