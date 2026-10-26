"""
Learnova Modern Themed PPTX Builder
Generates PPTX decks with dynamic visual layouts (Flowcharts, Tables, Metric Cards, Quizzes)
and embeds PowerPoint OpenXML slide transition animations.
"""

import io
import os
import re
from pptx import Presentation
from pptx.util import Emu, Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement

from learnova.rendering import layout as L
from learnova.rendering.pptx_visuals import group as vis_group, groups_for, reset_groups
from learnova.textutils import strip_inline_markdown
from learnova.rendering.theme_engine import (
    get_theme, auto_detect_theme, select_slide_layout, resolve_theme,
    ColorPalette, THEMES, LAYOUT_STYLES,
)

from learnova.rendering.pptx_chrome import _lum, _contrast, _readable, _tint, add_header, add_footer, add_title_slide


def SubElement(parent, tagname, **kwargs):
    element = OxmlElement(tagname)
    element.attrib.update(kwargs)
    parent.append(element)
    return element


_IMAGE_KEEP_ALL = os.getenv("LEARNOVA_IMAGE_KEEP_ALL", "").lower() in {"1", "true", "yes", "on"}


def _image_decision(orig: dict):
    """
    Decide whether a figure attached to a slide should appear in the PPTX, using
    the SAME policy as the web deck (``ai.image_policy``) so the two outputs never
    disagree. Returns ``(show: bool, caption: str)``. Only a confident DROP
    (logo / divider / bullet icon) is hidden.
    """
    img = (orig or {}).get("image") if isinstance(orig, dict) else None
    if not img or not img.get("bytes"):
        return False, ""
    try:
        from learnova.ai.image_policy import (
            ImageMeta, decide_image_action, meta_from_bytes,
        )

        ext = str(img.get("ext", "png")).lower().lstrip(".")
        slide_text = " ".join(str(x) for x in (orig.get("text"),))
        try:
            meta = meta_from_bytes(
                img["bytes"], ext=ext,
                ocr_text=str(img.get("description", "")), slide_text=slide_text,
            )
        except Exception:
            meta = ImageMeta(ext=ext, ocr_text=str(img.get("description", "")),
                             slide_text=slide_text)
        action = decide_image_action(meta)
        if action.action == "DROP" and not _IMAGE_KEEP_ALL:
            return False, ""
        return True, (action.caption or str(img.get("description", ""))[:200])
    except Exception:
        # Policy must never cost us a figure — when in doubt, show it.
        return True, str(img.get("description", ""))[:200]

def _add_slide_transition(slide, name: str = "none"):
    """Schema-correct slide transition (after clrMapOvr, before timing). 'none' writes nothing."""
    try:
        from learnova.rendering.pptx_animation import set_transition

        set_transition(slide, name)
    except Exception:
        pass


def _add_header_bar(slide, title_text: str, theme: ColorPalette):
    add_header(slide, title_text, theme)


def _add_footer(slide, n: int, total: int, theme: ColorPalette):
    """Footer band: identical position on every slide, text edges on the 0.5in margins."""
    add_footer(slide, n, total, theme)


def _add_takeaway_bar(slide, rows, theme: ColorPalette):
    """Footer callout. ``rows`` is a string (plain takeaway) or [[label, text], …] (takeaway, key terms, example)."""
    if isinstance(rows, str):
        rows = [["Key takeaway", rows]] if rows else []
    rows = [r for r in rows if r and str(r[1]).strip()]
    if not rows:
        return
    band = L.takeaway_band()
    fill = _tint(theme.accent_rgb, 0.78)
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(band.left), Inches(band.top),
                                 Inches(band.width), Inches(band.height))
    try:
        box.adjustments[0] = 0.2
    except Exception:
        pass
    box.fill.solid(); box.fill.fore_color.rgb = fill
    box.line.fill.background()
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(band.left), Inches(band.top + 0.14),
                                 Inches(0.09), Inches(max(0.1, band.height - 0.28)))
    bar.fill.solid(); bar.fill.fore_color.rgb = theme.accent_rgb
    bar.line.fill.background()

    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(L.PAD + 0.09)
    tf.margin_right = Inches(L.PAD)
    tf.margin_top = tf.margin_bottom = Inches(0.06)
    texts = [f"{lbl}:  {txt}" for lbl, txt in rows]
    size = L.fit_font_size(texts, (band.width - 2 * L.PAD - 0.09) * 0.94, (band.height - 0.12) * 0.9, max_pt=16 if len(rows) == 1 else 13, min_pt=9, spacing_pt=2)
    ink = _readable(fill, prefer=theme.text_rgb)
    for i, (lbl, txt) in enumerate(rows):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = PP_ALIGN.LEFT
        r1 = para.add_run(); r1.text = f"{lbl}:  "
        r1.font.bold = True; r1.font.size = Pt(size); r1.font.color.rgb = _readable(fill, prefer=theme.primary_rgb)
        r2 = para.add_run(); r2.text = str(txt)
        r2.font.size = Pt(size); r2.font.color.rgb = ink; r2.font.bold = len(rows) == 1

def _draw_figure_in_band(slide, theme: ColorPalette, band, image_bytes: bytes, caption: str = "") -> bool:
    """A source figure fitted into the content band inside a soft frame, centred, with an optional one-line caption."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as im:
            iw, ih = im.size
        cap_h = 0.45 if caption else 0.0
        pad = 0.18
        box_w, box_h = band.width, band.height - cap_h
        scale = min((box_w - 2 * pad) / iw, (box_h - 2 * pad) / ih)
        dw, dh = iw * scale, ih * scale
        fx, fy, fw, fh = band.left + (box_w - dw) / 2 - pad, band.top + (box_h - dh) / 2 - pad, dw + 2 * pad, dh + 2 * pad
        with vis_group(slide):
            frame = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(fx), Inches(fy), Inches(fw), Inches(fh))
            try:
                frame.adjustments[0] = 0.03
            except Exception:
                pass
            frame.fill.solid()
            frame.fill.fore_color.rgb = RGBColor(255, 255, 255)
            frame.line.color.rgb = _tint(theme.primary_rgb, 0.6)
            frame.line.width = Pt(1)
            frame.shadow.inherit = False
            slide.shapes.add_picture(io.BytesIO(image_bytes), Inches(fx + pad), Inches(fy + pad), Inches(dw), Inches(dh))
        if caption:
            with vis_group(slide):
                tb = slide.shapes.add_textbox(Inches(band.left), Inches(band.top + box_h + 0.05), Inches(band.width), Inches(cap_h - 0.05))
                tf = tb.text_frame
                tf.word_wrap = True
                tf.margin_left = tf.margin_right = 0
                p = tf.paragraphs[0]
                p.text = caption
                p.alignment = PP_ALIGN.CENTER
                p.font.size = Pt(13)
                p.font.italic = True
                p.font.color.rgb = theme.subtext_rgb
        return True
    except Exception:
        return False


def _add_figure_slide(prs, theme: ColorPalette, title_text: str, image_bytes: bytes,
                      caption: str = "") -> bool:
    """
    Emit a dedicated slide for an extracted figure.

    Layouts other than MINIMAL_TEXT fill their content area with cards, tables
    or metric blocks, leaving nowhere to put an image without overlapping. So
    rather than dropping the figure, we give it its own slide directly after
    the slide it was anchored to — keeping it beside the content that
    discusses it, at a readable size.
    """
    try:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = theme.bg_rgb
        _add_header_bar(slide, f"{title_text} — Figure", theme)

        # Fit the image inside the content band, preserving aspect ratio, then
        # centre it. Setting height alone let python-pptx derive the width from
        # the aspect ratio unchecked: a wide figure came out 12.15" starting at
        # x=2.4", i.e. 1.2" past the right edge of the slide.
        box_w = L.SLIDE_W - 2 * L.MARGIN_X
        box_h = (6.0 if caption else L.SLIDE_H - L.BOTTOM_MARGIN) - L.CONTENT_TOP - L.GAP
        pic = slide.shapes.add_picture(io.BytesIO(image_bytes), Inches(0), Inches(0))
        native_w, native_h = Emu(pic.width).inches, Emu(pic.height).inches
        scale = min(box_w / native_w, box_h / native_h) if native_w and native_h else 1.0
        draw_w, draw_h = native_w * scale, native_h * scale
        pic.width, pic.height = Inches(draw_w), Inches(draw_h)
        pic.left = Inches(L.MARGIN_X + (box_w - draw_w) / 2)
        pic.top = Inches(L.CONTENT_TOP + (box_h - draw_h) / 2)

        if caption:
            cap_box = slide.shapes.add_textbox(Inches(0.5), Inches(6.0), Inches(12.3), Inches(0.9))
            ctf = cap_box.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = caption[:300]
            cp.font.size = Pt(13)
            cp.font.italic = True
            cp.font.color.rgb = theme.text_rgb
        return True
    except Exception:
        return False


# A leading "Label: body" pair, which source decks use constantly
# ("Definition: ...", "Purpose: ...", "Cash Flows: ..."). The label is the most
# useful thing on the card and was being discarded.
_LABELLED = re.compile(r"^\s*([A-Z][\w&/()\- ]{2,34}?)\s*[:–—-]\s+(\S.*)$", re.S)

# Schema words that describe the field rather than name the content.
_META_LABELS = {
    "label", "item", "point", "bullet", "text", "title", "heading",
    "description", "desc", "value", "field", "key", "name", "content",
}


def _split_card_label(text: str, fallback: str) -> tuple[str, str]:
    """
    Split a bullet into (card heading, card body).

    Cards used to be headed "PILLAR 1", "STEP 2" — numbering that tells a
    reader nothing. Where the text carries its own label we promote it; the
    generic heading is only a fallback.
    """
    # Normalise here as well as upstream: a leftover emphasis marker sits
    # between the label and its colon ("Strategic Growth:* Helps ...") and
    # stops the pattern matching, silently costing the card its real heading.
    clean = strip_inline_markdown(text)

    # Models sometimes echo the schema word instead of the content's own label,
    # giving "Label: Cash Flows - Estimated inflows". Peel that off and let the
    # real label behind it be found.
    for _ in range(2):
        match = _LABELLED.match(clean)
        if not match:
            break
        label, body = match.group(1).strip(), match.group(2).strip()
        if not body or len(label.split()) > 5:
            break
        if label.lower() in _META_LABELS:
            clean = body           # retry against what followed
            continue
        return label.upper(), body
    return fallback, clean


def _apply_theme_fonts(prs, theme: ColorPalette) -> None:
    """
    Stamp the theme's typefaces onto every run in the deck.

    python-pptx sets no font name by default, so slides render in Calibri
    regardless of the chosen pairing. Rather than thread the family through
    ~40 individual paragraph writes, apply it once at the end: bold or large
    runs get the display face, everything else gets the body face.
    """
    for slide in prs.slides:
        for shape in slide.shapes:
            frames = []
            if shape.has_text_frame:
                frames.append(shape.text_frame)
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    for cell in row.cells:
                        frames.append(cell.text_frame)

            for frame in frames:
                for paragraph in frame.paragraphs:
                    targets = list(paragraph.runs) or []
                    for run in targets:
                        size = run.font.size or paragraph.font.size
                        is_display = bool(run.font.bold) or (
                            size is not None and size >= Pt(24)
                        )
                        run.font.name = (
                            theme.heading_font if is_display else theme.body_font
                        )


def _add_inline_quiz(slide, quiz: dict, theme: ColorPalette, has_takeaway: bool) -> None:
    """
    Draw a checkpoint question as a band at the foot of the slide.

    Keeping the question beside the material it tests reads better than a
    standalone quiz slide, and it stops the deck inflating with interruptions.
    The four options sit in one row so the whole band stays shallow.
    """
    band = L.quiz_band(has_takeaway)

    backdrop = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(band.left), Inches(band.top), Inches(band.width), Inches(band.height))
    backdrop.fill.solid()
    backdrop.fill.fore_color.rgb = theme.card_bg_rgb
    backdrop.line.color.rgb = theme.accent_rgb
    backdrop.line.width = Pt(2)
    backdrop.text_frame.text = ""

    question = (quiz.get("question") or "").strip()
    label = f"Q{quiz.get('index', 1)}. {question}"

    q_box = slide.shapes.add_textbox(
        Inches(band.left + 0.18), Inches(band.top + 0.1),
        Inches(band.width - 0.36), Inches(0.72))
    q_tf = q_box.text_frame
    q_tf.word_wrap = True
    q_para = q_tf.paragraphs[0]
    q_para.text = label
    q_para.font.bold = True
    q_para.font.color.rgb = theme.text_rgb
    q_para.font.size = Pt(L.fit_font_size([label], band.width - 0.4, 0.7,
                                          max_pt=14, min_pt=9))

    options = [str(o).strip() for o in (quiz.get("options") or []) if str(o).strip()][:4]
    if not options:
        return

    letters = "ABCD"
    row_top = band.top + 0.9
    row_h = band.height - 1.02
    cells = L.grid_cells(len(options),
                         L.Box(band.left + 0.18, row_top, band.width - 0.36, row_h),
                         gap=0.14, max_per_row=4)

    # One size across every option keeps the row visually even.
    opt_pt = min(
        L.fit_font_size([o], c.width - 0.2, c.height - 0.08, max_pt=12, min_pt=7)
        for o, c in zip(options, cells)
    )

    for i, (option, cell) in enumerate(zip(options, cells)):
        chip = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(cell.left), Inches(cell.top), Inches(cell.width), Inches(cell.height))
        chip.fill.solid()
        chip.fill.fore_color.rgb = theme.bg_rgb
        chip.line.color.rgb = theme.primary_rgb
        chip.line.width = Pt(1)

        tf = chip.text_frame
        tf.word_wrap = True
        para = tf.paragraphs[0]
        # Strip any leading "A)" the model already produced, so it is not doubled.
        clean = re.sub(r"^\s*[A-Da-d][).:]\s*", "", option)
        para.text = f"{letters[i]}. {clean}"
        para.font.size = Pt(opt_pt)
        para.font.color.rgb = theme.text_rgb


def build_pptx(slides_data: list[dict], topic_title: str = "Learnova Presentation",
               theme_id: str = "auto", theme_spec: dict | None = None,
               deck_plan=None) -> bytes:
    reset_groups()
    theme = resolve_theme(topic_title, theme_id, theme_spec)

    # Deck Director → per-slide speaker notes (the PPTX notes pane). Best-effort.
    if deck_plan is None:
        try:
            from learnova.rendering.deck_director import plan_deck

            deck_plan = plan_deck(slides_data)
        except Exception:
            deck_plan = None

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.33), Inches(7.5)

    # ── Title slide (template-driven) ─────────────────────────────────────────
    def _hero(kind: str) -> bytes:
        from learnova.ai.image_gen import vector_illustration
        from learnova.visuals.icons import pick_icons

        _seed_text = topic_title + " " + " ".join(str((d.get("improved") or {}).get("title", "")) for d in slides_data[:6])
        return vector_illustration(pick_icons(_seed_text, 5), theme.primary_hex, theme.accent_hex, topic_title, kind=kind, width=800)

    title_slide = add_title_slide(prs, theme, topic_title, len(slides_data), _hero)

    # ── Content slides ────────────────────────────────────────────────────────
    prev_style = None
    slide_meta = [{"slide": title_slide, "idx": None, "layout": "TITLE"}]
    for idx, data in enumerate(slides_data):
        orig = data.get("original", {})
        imp = data.get("improved", {})
        if not isinstance(imp, dict):
            imp = {}

        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = theme.bg_rgb

        layout_type = imp.get("layout_type", "MINIMAL_TEXT").upper()
        slide_meta.append({"slide": slide, "idx": idx, "layout": layout_type})
        style_pattern = select_slide_layout(idx, layout_type, prev_style)
        prev_style = style_pattern

        title_text = imp.get("title", orig.get("title", "Presentation Slide"))
        takeaway_text = imp.get("takeaway", "").strip()
        inline_quiz = imp.get("inline_quiz") or None

        # Speaker notes pane (key point, per-click cues, "read exactly", timing)
        _sp = deck_plan.by_index(idx) if deck_plan is not None else None
        if _sp is not None and "takeaway" in (getattr(_sp, "params", None) or {}):
            takeaway_text = str(_sp.params["takeaway"] or "").strip()  # the visual's own synthesis wins
        elif len(takeaway_text) > 190:
            takeaway_text = ""
        footer_rows = []
        if _sp is not None and (getattr(_sp, "params", None) or {}).get("footer"):
            footer_rows = [r for r in _sp.params["footer"] if r and str(r[1]).strip()]
            takeaway_text = footer_rows[0][1] if footer_rows else ""
        elif takeaway_text:
            footer_rows = [["Key takeaway", takeaway_text]]
        if layout_type == "QUIZ":
            takeaway_text, footer_rows = "", []  # the answer/explanation box owns the bottom of a checkpoint slide
        if _sp and getattr(_sp, "speaker_notes", ""):
            try:
                slide.notes_slide.notes_text_frame.text = _sp.speaker_notes
            except Exception:
                pass

        # Geometry is derived per slide: the body shrinks when a takeaway bar
        # or a checkpoint band is also being drawn, so nothing overlaps.
        band = L.content_band(has_takeaway=bool(footer_rows),
                              has_quiz=bool(inline_quiz))

        _add_header_bar(slide, title_text, theme)
        _add_footer(slide, idx + 1, len(slides_data), theme)

        # ── 0a. FIGURE — the slide is a picture (diagram / table image from the source): large, framed, with its caption
        _family_drawn = False
        if _sp is not None and getattr(_sp, "family", "") == "FIGURE" and (orig.get("image") or {}).get("bytes"):
            _family_drawn = _draw_figure_in_band(slide, theme, band, orig["image"]["bytes"], str((_sp.data or {}).get("caption", "")))

        # ── 0. CONTENT-ENGINE VISUAL — wins over the older layout guesses, as in the web deck
        if (not _family_drawn and _sp and getattr(_sp, "family", None) and getattr(_sp, "data", None)
                and getattr(_sp, "confidence", 0) >= 0.62 and layout_type != "QUIZ"
                and not (layout_type == "TABLE" and imp.get("table_rows"))):
            from learnova.rendering.pptx_visuals import draw_family

            _illo = imp.get("illustration") or None
            _draw_band = band
            if _illo and _illo.get("bytes"):
                _pw = band.width * 0.26
                _draw_band = L.Box(band.left, band.top, band.width - _pw - L.GUTTER, band.height)
            _family_drawn = draw_family(slide, _sp, theme, _draw_band)
            if _family_drawn and _illo and _illo.get("bytes"):
                from learnova.rendering.pptx_visuals import _Canvas

                with vis_group(slide):
                    _Canvas(slide, theme, band).picture(_illo["bytes"], band.left + band.width - _pw, band.top, _pw, band.height)

        # ── 1. TABLE LAYOUT ──────────────────────────────────────────────────
        if _family_drawn:
            pass
        elif layout_type == "TABLE" and imp.get("table_headers") and imp.get("table_rows"):
            from learnova.rendering.pptx_visuals import _Canvas, draw_table

            headers = imp.get("table_headers", [])
            rows = imp.get("table_rows", [])

            # Lead-in bullets sit above the grid; the table takes what is left,
            # so the two never overlap.
            lead = [str(b).strip() for b in (imp.get("bullets") or []) if str(b).strip()]
            table_band = band
            if lead:
                lead_pt = L.fit_font_size(lead, band.width - 0.3, band.height * 0.3, max_pt=17, min_pt=11)
                lead_h = min(band.height * 0.34, L.block_height(lead, band.width, lead_pt) + 0.1)
                with vis_group(slide):
                    lead_box = slide.shapes.add_textbox(Inches(band.left), Inches(band.top), Inches(band.width), Inches(lead_h))
                    ltf = lead_box.text_frame
                    ltf.word_wrap = True
                    ltf.margin_left = ltf.margin_right = ltf.margin_top = ltf.margin_bottom = 0
                    for i, line in enumerate(lead):
                        lp = ltf.add_paragraph() if i else ltf.paragraphs[0]
                        lp.text = line
                        lp.font.size = Pt(lead_pt)
                        lp.font.color.rgb = theme.text_rgb
                top_off = lead_h + L.GUTTER
                table_band = L.Box(band.left, band.top + top_off, band.width, band.height - top_off)
            if headers and rows:
                draw_table(_Canvas(slide, theme, table_band), headers, rows)

        # ── 2. METRIC STAT CALLOUT LAYOUT ─────────────────────────────────────
        elif layout_type == "METRIC":
            from learnova.rendering.pptx_visuals import draw_metric

            draw_metric(slide, theme, band, str(imp.get("metric_value", "100%")),
                        str(imp.get("metric_label", title_text)), str(imp.get("metric_desc", takeaway_text)))

        # ── 3. INTERLEAVED QUIZ CHECKPOINT ────────────────────────────────────
        elif layout_type == "QUIZ":
            q_text = imp.get("question", "Checkpoint Question")
            options = [str(o) for o in imp.get("options", [])][:4]
            correct_opt = str(imp.get("correct", "A")).strip()[:1].upper()
            explanation = str(imp.get("explanation", "")).strip()
            difficulty = str(imp.get("difficulty", "")).strip()
            from learnova.rendering.pptx_visuals import P, _Canvas

            qc = _Canvas(slide, theme, band)
            PAD, GUT = L.PAD, L.GUTTER
            # question card (stays visible)
            qh = min(1.7, qc.h * 0.26)
            qtint = _tint(theme.primary_rgb, 0.9)
            with vis_group(slide):
                qc.card(qc.x, qc.y, qc.w, qh, fill=qtint, line=theme.primary_rgb)
                tag = qc.shape(MSO_SHAPE.ROUNDED_RECTANGLE, qc.x + PAD, qc.y + PAD * 0.75, 2.7, 0.36, theme.primary_rgb, radius=0.5)
                qc.tb(0, 0, 0, 0, [P(f"QUESTION  ·  {difficulty.upper() or 'CHECK'}", 10.5, True, _readable(theme.primary_rgb))],
                      MSO_ANCHOR.MIDDLE, PP_ALIGN.CENTER, shape=tag, inset=(0.05, 0, 0.05, 0))
                tx, ty = qc.x + PAD, qc.y + PAD * 0.75 + 0.36 + 0.08
                qsz = qc.fit([q_text], qc.w - 2 * PAD, qc.y + qh - PAD * 0.6 - ty, 28, 15, bold=True)
                qc.tb(tx, ty, qc.w - 2 * PAD, qc.y + qh - PAD * 0.6 - ty,
                      [P(q_text, qsz, True, _readable(qtint, prefer=theme.primary_rgb))], anchor=MSO_ANCHOR.MIDDLE)

            ah = min(1.15, qc.h * 0.2)
            top = qc.y + qh + GUT
            avail = qc.h - qh - GUT - ah - GUT
            cw, ch = (qc.w - GUT) / 2, (avail - GUT) / 2
            letters = "ABCD"
            dd = min(L.BADGE_D + 0.1, ch * 0.5)
            osz = min([qc.fit([o], cw - dd - 3 * PAD, ch - 0.2, 22, 12) for o in options] or [18])
            with vis_group(slide):
                for i, opt in enumerate(options):
                    r, k = divmod(i, 2)
                    x, y = qc.x + k * (cw + GUT), top + r * (ch + GUT)
                    qc.card(x, y, cw, ch)
                    qc.badge(x + PAD, y + (ch - dd) / 2, letters[i], d=dd)
                    qc.tb(x + 2 * PAD + dd, y + 0.08, cw - dd - 3 * PAD, ch - 0.16, [P(opt, osz, False, theme.text_rgb)], anchor=MSO_ANCHOR.MIDDLE)

            # answer box — revealed on the last click (visible in static exports)
            with vis_group(slide):
                ans = qc.shape(MSO_SHAPE.ROUNDED_RECTANGLE, qc.x, qc.y + qc.h - ah, qc.w, ah, theme.primary_rgb, radius=0.12)
                ink = _readable(theme.primary_rgb)
                paras = [P(f"Answer: {correct_opt}", 20, True, _readable(theme.primary_rgb, prefer=theme.accent_rgb))]
                if explanation:
                    esz = qc.fit([explanation], qc.w - 2 * PAD, ah - 0.2 - 0.4, 16, 10.5)
                    paras.append(P(explanation, esz, False, ink, 2))
                qc.tb(0, 0, 0, 0, paras, MSO_ANCHOR.MIDDLE, PP_ALIGN.LEFT, shape=ans, inset=(PAD, 0.06, PAD, 0.06))

        # ── 4. FLOWCHART / PROCESS STEP CARDS ──────────────────────────────────
        elif layout_type == "FLOWCHART":
            from learnova.rendering.pptx_visuals import draw_cards

            bullets = imp.get("bullets", [])
            steps = bullets if bullets else ["Step 1: Initiation", "Step 2: Execution", "Step 3: Completion"]
            steps = [s for s in steps if str(s).strip()][:8]
            items = []
            for n_, st in enumerate(steps):
                head, body = _split_card_label(st, "")
                items.append((head.title() if head else "", body))
            if len(items) < 2 or not draw_cards(slide, theme, band, items, kind="process"):
                draw_cards(slide, theme, band, items, kind="grid")

        # ── 5. CARD GRID LAYOUT ──────────────────────────────────────────────
        elif layout_type == "CARD_GRID":
            from learnova.rendering.pptx_visuals import draw_cards

            # No placeholder cards: an empty grid used to render three boxes
            # literally reading "Pillar 1", "Pillar 2", "Pillar 3".
            items = [b for b in (imp.get("bullets") or []) if str(b).strip()][:6]
            pairs = []
            for it in items:
                head, body = _split_card_label(it, "")
                pairs.append((head.title() if head else "", body))
            draw_cards(slide, theme, band, pairs, kind="grid")

        # ── 6. DEFAULT / MINIMAL TEXT + IMAGE COLUMN LAYOUT ───────────────────
        else:
            from learnova.rendering.pptx_visuals import _Canvas, draw_bullets

            _show_img, _img_caption = _image_decision(orig)
            has_img = _show_img
            text_area, image_area = L.split_text_image(band, has_img)

            bullets = [str(b).replace("▪", "").strip()
                       for b in (imp.get("bullets") or []) if str(b).strip()]
            draw_bullets(slide, theme, text_area, bullets)

            if has_img:
                try:
                    with vis_group(slide):
                        _Canvas(slide, theme, band).picture(orig["image"]["bytes"], image_area.left, image_area.top,
                                                            image_area.width, image_area.height)
                except Exception:
                    pass

        if inline_quiz:
            with vis_group(slide):
                _add_inline_quiz(slide, inline_quiz, theme, bool(footer_rows))

        with vis_group(slide):
            _add_takeaway_bar(slide, footer_rows, theme)

        # A figure anchored to a non-MINIMAL layout gets its own slide, placed
        # immediately after so it stays with the content it belongs to.
        image = orig.get("image") if isinstance(orig, dict) else None
        if layout_type != "MINIMAL_TEXT" and image and image.get("bytes"):
            _fig_show, _fig_caption = _image_decision(orig)
            if _fig_show:
                if _add_figure_slide(
                    prs, theme, title_text, image["bytes"],
                    caption=(_fig_caption or image.get("description") or "")[:300],
                ):
                    slide_meta.append({"slide": prs.slides[len(prs.slides) - 1], "idx": None, "layout": "FIGURE",
                                       "transition": "fade"})

    # ── Closing slide ─────────────────────────────────────────────────────────
    end_slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_meta.append({"slide": end_slide, "idx": None, "layout": "END", "transition": "fade"})
    end_slide.background.fill.solid()
    end_slide.background.fill.fore_color.rgb = theme.primary_rgb
    for d, col, x, y in ((5.4, _tint(theme.accent_rgb, 0.1), -1.4, 4.6), (2.8, _tint(theme.primary_rgb, 0.25), 10.6, -0.9)):
        o = end_slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
        o.fill.solid(); o.fill.fore_color.rgb = col
        o.line.fill.background()
    tfe = end_slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.33), Inches(1.6)).text_frame
    tfe.text = "Thank you"
    tfe.paragraphs[0].font.size = Pt(64)
    tfe.paragraphs[0].font.bold = True
    tfe.paragraphs[0].font.color.rgb = _readable(theme.primary_rgb)
    tfe.paragraphs[0].alignment = PP_ALIGN.CENTER
    tq = end_slide.shapes.add_textbox(Inches(1), Inches(4.0), Inches(11.33), Inches(0.8)).text_frame
    tq.text = "Questions?"
    tq.paragraphs[0].font.size = Pt(26)
    tq.paragraphs[0].font.color.rgb = _readable(theme.primary_rgb, prefer=theme.accent_rgb)
    tq.paragraphs[0].alignment = PP_ALIGN.CENTER

    _apply_theme_fonts(prs, theme)

    # ── Slide transitions (Deck Director) and click-build animations ─────────
    try:
        from learnova.rendering.pptx_animation import (
            animations_enabled, apply_click_builds, merge_groups, set_transition, strip_all_timing,
        )

        for meta in slide_meta:
            sp = deck_plan.by_index(meta["idx"]) if (deck_plan is not None and meta["idx"] is not None) else None
            name = meta.get("transition") or (getattr(sp, "transition", "none") if sp else "none")
            if meta["layout"] != "TITLE":
                set_transition(meta["slide"], name)

        if animations_enabled():
            for meta in slide_meta:
                if meta["idx"] is None:
                    continue
                sp = deck_plan.by_index(meta["idx"]) if deck_plan is not None else None
                groups = groups_for(meta["slide"])
                if meta["layout"] == "QUIZ":
                    # question visible; the four options together on click 1; the answer on the last click
                    apply_click_builds(meta["slide"], groups, static_first=True)
                    continue
                anim = (getattr(sp, "animation", None) or {}) if sp else {}
                if anim.get("mode") == "static":
                    continue
                n_steps = len(anim.get("steps") or [])
                if n_steps >= 2 and len(groups) > n_steps:
                    groups = merge_groups(groups, n_steps)
                apply_click_builds(meta["slide"], groups, static_first=True)

        # Validate: the file must still round-trip through python-pptx.
        check = io.BytesIO()
        prs.save(check)
        check.seek(0)
        try:
            Presentation(check)
        except Exception:
            strip_all_timing(prs)
    except Exception:
        pass

    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output.getvalue()
