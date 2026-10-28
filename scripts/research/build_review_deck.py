"""
IPD review deck in the dense, infographic style of an SIH idea deck: title, eight content slides (idea and solution,
literature review, architecture and tech stack, methodology and prototype, before vs after, results and impact,
feasibility and viability, research and references) and a thank-you slide. Built on the department template.

    python scripts/research/build_review_deck.py <template.pptx> <assets dir> <before_after.json> <out.pptx>
"""
import io
import json
import pathlib
import sys

import qrcode
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from learnova.visuals.icons import icon_png  # noqa: E402

TPL, IMG, BA_PATH, OUT = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3], sys.argv[4]
BA = json.load(open(BA_PATH))
REPO = "https://github.com/SDP42/LearnovaV2"

W = 13.333
INK, MUTED, WHITE = RGBColor(0x17, 0x21, 0x31), RGBColor(0x55, 0x5F, 0x6D), RGBColor(255, 255, 255)
ORANGE, BLUE, GREEN, PURPLE, TEAL, RED = (RGBColor(0xF2, 0x7A, 0x2E), RGBColor(0x1F, 0x5F, 0xBF), RGBColor(0x16, 0x84, 0x5B),
                                          RGBColor(0x6B, 0x3F, 0xA0), RGBColor(0x0E, 0x7C, 0x86), RGBColor(0xC0, 0x30, 0x30))
TINT = {ORANGE: RGBColor(0xFF, 0xF1, 0xE6), BLUE: RGBColor(0xE8, 0xF0, 0xFC), GREEN: RGBColor(0xE6, 0xF5, 0xEE),
        PURPLE: RGBColor(0xF1, 0xEB, 0xF9), TEAL: RGBColor(0xE3, 0xF4, 0xF5), RED: RGBColor(0xFC, 0xEB, 0xEA)}
HEX = {ORANGE: "#F27A2E", BLUE: "#1F5FBF", GREEN: "#168455", PURPLE: "#6B3FA0", TEAL: "#0E7C86", RED: "#C03030", INK: "#172131"}
FONT, HEAD = "Calibri", "Montserrat"

prs = Presentation(TPL)
TEMPLATE = list(prs.slides)


# ── drawing helpers ──────────────────────────────────────────────────────────
def rect(sl, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, radius=0.08, lw=1.0):
    s = sl.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(lw)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    return s


def text(sl, x, y, w, h, paras, size=11, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT, spacing=3):
    """paras: str | (str, opts) | [(run, opts), ...] per paragraph."""
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, p in enumerate(paras):
        if isinstance(p, str):
            runs, o = [(p, {})], {}
        elif isinstance(p, list):
            runs, o = p, {}
        else:
            runs, o = [(p[0], p[1])], p[1]
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = o.get("align", align)
        para.space_after = Pt(o.get("after", spacing))
        for rt, ro in runs:
            r = para.add_run()
            r.text = rt
            r.font.size = Pt(ro.get("size", o.get("size", size)))
            r.font.bold = ro.get("bold", o.get("bold", False))
            r.font.italic = ro.get("italic", o.get("italic", False))
            r.font.name = ro.get("font", o.get("font", font))
            r.font.color.rgb = ro.get("color", o.get("color", color))
    return tb


def icon(sl, name, x, y, d, color=WHITE):
    sl.shapes.add_picture(io.BytesIO(icon_png(name, color if isinstance(color, str) else "#FFFFFF", 160)), Inches(x), Inches(y), Inches(d), Inches(d))


def badge(sl, name, x, y, d, fill):
    rect(sl, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    icon(sl, name, x + d * 0.2, y + d * 0.2, d * 0.6)


def arrow(sl, x1, y1, x2, y2, color=MUTED, w=1.75):
    c = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(w)
    ln = c.line._get_or_add_ln()
    from lxml import etree

    etree.SubElement(ln, qn("a:tailEnd")).set("type", "triangle")
    return c


def picture(sl, path, x, y, w, h, border=True):
    """The whole picture inside the box (never cropped), centred."""
    from PIL import Image

    iw, ih = Image.open(path).size
    sc = min(w / iw, h / ih)
    pw, ph = iw * sc, ih * sc
    pic = sl.shapes.add_picture(path, Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))
    if border:
        pic.line.color.rgb = RGBColor(0xC9, 0xD0, 0xDA)
        pic.line.width = Pt(0.75)
    return pic


def qr(sl, url, x, y, d):
    img = qrcode.make(url, border=1)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    sl.shapes.add_picture(buf, Inches(x), Inches(y), Inches(d), Inches(d))


def panel(sl, x, y, w, h, title, color, icon_name=None, head_h=0.36):
    """A card with a coloured title bar (and icon) — the body area starts at y + head_h + 0.06."""
    rect(sl, x, y, w, h, TINT[color], line=color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04, lw=1.0)
    rect(sl, x, y, w, head_h, color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
    rect(sl, x, y + head_h * 0.5, w, head_h * 0.5, color)
    if icon_name:
        icon(sl, icon_name, x + 0.08, y + 0.05, head_h - 0.1)
    text(sl, x + (0.38 if icon_name else 0.1), y, w - 0.45, head_h, [(title, {"bold": True, "size": 12, "color": WHITE, "font": HEAD})], anchor=MSO_ANCHOR.MIDDLE)


def table(sl, x, y, w, rows, widths, head_fill=BLUE, size=9.5, head_size=10, row_h=0.3, zebra=True, first_bold=True):
    t = sl.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows))).table
    for c, cw in zip(t.columns, widths):
        c.width = Inches(cw)
    for i, row in enumerate(rows):
        t.rows[i].height = Inches(row_h)
        for j, v in enumerate(row):
            cell = t.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.05)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = ""
            r = p.add_run()
            r.text = str(v)
            r.font.name = FONT
            r.font.size = Pt(head_size if i == 0 else size)
            r.font.bold = i == 0 or (first_bold and j == 0)
            r.font.color.rgb = WHITE if i == 0 else INK
            cell.fill.solid()
            cell.fill.fore_color.rgb = head_fill if i == 0 else (RGBColor(0xF4, 0xF6, 0xFA) if (zebra and i % 2) else WHITE)
    return t


N_SLIDES = 10


def frame(title, tagline, n):
    """A content slide: white page, heading with orange rule, italic tagline, group tag, footer bar with page number."""
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    for ph in list(sl.placeholders):
        ph._element.getparent().remove(ph._element)
    sl.background.fill.solid()
    sl.background.fill.fore_color.rgb = WHITE
    text(sl, 0.3, 0.12, 9.6, 0.55, [(title, {"bold": True, "size": 26, "font": HEAD, "color": INK})])
    rect(sl, 0.34, 0.68, 1.3, 0.06, ORANGE)
    text(sl, 1.75, 0.6, 8.3, 0.3, [(tagline, {"italic": True, "size": 12, "color": BLUE})])
    rect(sl, 10.2, 0.14, 2.85, 0.62, None, line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3, lw=1.25)
    text(sl, 10.25, 0.14, 2.75, 0.62, [("LEARNOVA · Group 1", {"bold": True, "size": 12, "color": ORANGE, "align": PP_ALIGN.CENTER, "font": HEAD}),
                                       ("IPD Review · AI & DS, DJSCE", {"size": 9, "color": MUTED, "align": PP_ALIGN.CENTER})],
         anchor=MSO_ANCHOR.MIDDLE, spacing=0)
    rect(sl, 0, 7.18, W, 0.32, BLUE)
    text(sl, 0.3, 7.18, 9, 0.32, [("Learnova — redesigning outdated lecture slides into illustrated, interactive teaching decks", {"size": 10, "color": WHITE})],
         anchor=MSO_ANCHOR.MIDDLE)
    text(sl, 12.5, 7.18, 0.6, 0.32, [(f"{n}", {"size": 11, "bold": True, "color": WHITE, "align": PP_ALIGN.RIGHT})], anchor=MSO_ANCHOR.MIDDLE)
    return sl


def bullets(items, size=10.5, color=INK, mark="•", after=3):
    out = []
    for it in items:
        if isinstance(it, tuple):
            head, body = it
            out.append([(f"{mark} ", {"color": ORANGE, "bold": True, "size": size}), (head, {"bold": True, "size": size, "color": color}),
                        (f" {body}", {"size": size, "color": color})])
        else:
            out.append([(f"{mark} ", {"color": ORANGE, "bold": True, "size": size}), (it, {"size": size, "color": color})])
    return [(p, {"after": after}) if False else p for p in out]


# ── 1. Title (template's own title slide) ────────────────────────────────────
s1 = TEMPLATE[0]
for sh in list(s1.shapes):
    if sh.name == "TextBox 6":
        sh._element.getparent().remove(sh._element)
text(s1, 4.25, 3.95, 8.75, 2.6, [
    [("Title: ", {"bold": True, "color": ORANGE, "size": 20, "font": HEAD}),
     ("Learnova — AI-powered redesign of outdated lecture slides into illustrated, interactive teaching decks", {"size": 20, "color": WHITE})],
    ("Domain: Education Technology · Artificial Intelligence · Document Understanding", {"size": 13, "color": RGBColor(0xDD, 0xDD, 0xDD), "after": 2}),
    ("Group No. 1 · Department of Artificial Intelligence and Data Science, DJSCE · Interdisciplinary Project Review, Odd Sem 2026", {"size": 12, "color": RGBColor(0xBB, 0xBB, 0xBB)}),
], spacing=8)
grp = next(sh for sh in s1.shapes if sh.shape_type == 6)
members = next(g for g in grp.shapes if g.has_text_frame and "Group Members" in g.text_frame.text)
tf = members.text_frame
tf.clear()
for i, (rt, b) in enumerate([("Group Members:", True), ("", False), ("Kawaljeet Singh Bharaj", True), ("S004 · 60018240016", False), ("", False),
                             ("Jeevesh Bharat Bodhani", True), ("S005 · 60018240096", False), ("", False), ("Rishit Pankajkumar Lahoti", True),
                             ("S026 · 6001840101", False), ("", False), ("Swayam Devendra Panchal", True), ("S029 · 60018240013", False), ("", False),
                             ("Mentor:", True), ("________________", False)]):
    para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = para.add_run()
    r.text, r.font.bold, r.font.size, r.font.name = rt, b, Pt(12 if b else 11), FONT
    r.font.color.rgb = RGBColor(0, 0, 0)
for extra in TEMPLATE[1:]:                                   # the template's guidance slides are replaced by the slides below
    rid = next(e.rId for e in prs.slides._sldIdLst if prs.part.related_part(e.rId) is extra.part)
    prs.slides._sldIdLst.remove(next(e for e in prs.slides._sldIdLst if e.rId == rid))
    prs.part.drop_rel(rid)

UNTITLED = sum(v["before"]["untitled"] for v in BA.values())

# ── 2. Idea and proposed solution ────────────────────────────────────────────
s = frame("IDEA & PROPOSED SOLUTION", "From text walls to teaching decks — without losing a single point the teacher wrote", 2)
rect(s, 0.3, 0.98, 12.75, 0.36, BLUE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.4)
text(s, 0.3, 0.98, 12.75, 0.36, [(f"In five real course decks (306 slides) we found {UNTITLED} untitled slides, equations pasted as pictures, and not one diagram, quiz or interactive element",
                                  {"bold": True, "size": 12.5, "color": WHITE, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.3, 1.42, 12.75, 0.75, [
    [("Proposed solution:  ", {"bold": True, "color": ORANGE, "size": 11.5}),
     ("Faculty reuse the same slide decks for years, and students revise from them before every examination. Learnova is a web platform that takes the deck a "
      "teacher already has — a PowerPoint, a slide PDF, Word notes or a typed topic — and rebuilds it as an ", {"size": 11.5}),
     ("editable PowerPoint, an interactive web deck and a study pack", {"bold": True, "size": 11.5}),
     (". Every point of the original is kept; what changes is how it is shown: a visual for every idea, an illustration on every slide, and quizzes, "
      "solved problems and labs that let students work with the material instead of only reading it.", {"size": 11.5})]], spacing=0)
cols = [("Detailed explanation of the solution", BLUE, "workflow", [
            ("Slide reader:", "PDF/PPTX read page by page — titles, bullet levels, tables, figures; OCR for picture-only slides."),
            ("Decision engine:", "27 detectors choose process, timeline, comparison, definition, chart or cards — with a reason."),
            ("Assertion titles:", "every title states the slide's point (AI with key, rules without)."),
            ("Illustrations:", "AI-written diagram, teacher's figure or offline scene on every slide, each with an HTML link."),
            ("Interaction:", "checkpoint quizzes, exact step-by-step solvers, labs for NLP, ML and IPCV topics."),
            ("Outputs:", "editable PPTX, Reveal.js web deck, flashcards, Anki, quiz bank, share link, tutor.")]),
        ("How it addresses the problem", GREEN, "target", [
            ("Text walls →", "one idea per slide, drawn as a visual at a readable density."),
            ("Untitled slides →", f"{UNTITLED} → 0; split parts are named after what they cover."),
            ("Pictures of equations →", "kept as full-size figures; never replaced by OCR noise."),
            ("Passive reading →", "quizzes, steppers and labs on the slide itself."),
            ("Hours of redesign →", "a finished deck in about 10–60 s, fully editable."),
            ("Unreliable AI →", "source text kept verbatim; 98–100% of facts retained.")]),
        ("Innovation and uniqueness", PURPLE, "sparkles", [
            ("Redesign, not generate:", "starts from the teacher's deck; Gamma, Copilot and Canva start from a prompt."),
            ("Faithful by construction:", "every AI output is checked against the slide; numbers are computed."),
            ("Explainable design:", "each visual choice comes with its rule and confidence."),
            ("Glyph-measured layout:", "no overflow and no word ever broken across lines."),
            ("Two fallbacks:", "5-key Gemini pool → Groq/NVIDIA → full offline logic."),
            ("Built-in labs:", "Region Growing, Split & Merge, CYK, Viterbi, NB-WSD, HMM tagging.")])]
for i, (title, col, ic, items) in enumerate(cols):
    x = 0.3 + i * 4.27
    panel(s, x, 2.22, 4.13, 3.38, title, col, ic)
    text(s, x + 0.1, 2.64, 3.95, 2.95, bullets(items, 10.3), spacing=4)
phases = [("PHASE 1 · Sep–Dec 2025", "Research & design", "Literature survey, competitor study, problem statement, architecture, UI plan", ORANGE),
          ("PHASE 2 · Jan–Mar 2026", "Prototype V1", "Parsing, AI rewriting, engagement score, quiz generation, Streamlit demo", BLUE),
          ("PHASE 3 · Apr–Jul 2026", "Learnova V2 platform", "FastAPI + React, decision engine, PPTX & web builders, OTP accounts, library", GREEN),
          ("PHASE 4 · Aug–Oct 2026", "Real lecture decks", "Slide reader + OCR, illustrations, explainers, labs, AI keys, papers", PURPLE)]
for i, (h, sub, body, col) in enumerate(phases):
    x = 0.3 + i * 2.6
    rect(s, x, 5.7, 2.5, 0.3, col, shape=MSO_SHAPE.PENTAGON)
    text(s, x + 0.05, 5.7, 2.3, 0.3, [(h, {"bold": True, "size": 9.5, "color": WHITE})], anchor=MSO_ANCHOR.MIDDLE)
    text(s, x, 6.02, 2.5, 1.1, [(sub, {"bold": True, "size": 10.5, "color": col}), (body, {"size": 9.5, "color": INK})], spacing=1)
rect(s, 10.75, 5.7, 2.3, 1.42, TINT[BLUE], line=BLUE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
qr(s, REPO, 10.82, 5.78, 1.0)
text(s, 11.85, 5.74, 1.18, 1.35, [("LIVE CODE", {"bold": True, "size": 9.5, "color": BLUE}), ("Full source, 755 tests, papers and demo decks on GitHub", {"size": 8.5}),
                                   ("SDP42/LearnovaV2", {"bold": True, "size": 8.5, "color": BLUE})], spacing=1)

# ── 3. Literature review ─────────────────────────────────────────────────────
s = frame("LITERATURE REVIEW / EXISTING SYSTEMS", "What research and today's tools do — and the gap Learnova fills", 3)
rows = [["#", "Reference / existing system", "Method & key findings", "Gap / scope for improvement"],
        ["1", "Hu & Wan, “PPSGen”, IEEE TKDE 27(4), 2015", "Learns sentence importance with regression; ILP selects sentences into slides for academic papers.", "Papers only; summarises so content is lost; no visuals; cannot redesign existing slides."],
        ["2", "Fu et al., “DOC2PPT”, AAAI 36, 2022", "Hierarchical neural summariser + figure selection + layout prediction from paper–slide pairs.", "Needs training pairs; abstractive text can alter facts; input must be a scientific paper."],
        ["3", "Sun et al., “D2S”, NAACL 2021", "Slide titles used as queries; retrieval + QA-style summarisation fills each slide.", "Text only; no figures, quizzes or interaction; not for an existing lecture deck."],
        ["4", "Maynez et al., “Faithfulness in abstractive summarization”, ACL 2020", "Abstractive models hallucinate and omit content in a large share of outputs.", "Motivates keeping source text verbatim and checking every AI output."],
        ["5", "Garner & Alley, assertion–evidence, IJEE 29(6), 2013; Mayer, Multimedia Learning, 2009", "Sentence headlines + visual evidence beat bullet lists; one idea per slide, words near pictures.", "Design guidance only — no tool applies it automatically to old decks."],
        ["6", "Sweller & Cooper 1985; Hundhausen et al. 2002 (worked examples, algorithm visualisation)", "Studying solved steps and interacting with a visual simulation improves learning.", "Lecture slides show finished answers; no step-by-step or interactive layer."],
        ["7", "Gamma, MS Copilot in PowerPoint, Gemini in Slides, Canva Magic Design (2026)", "LLM writes an outline, then fills a template; attractive new decks from a prompt.", "Rewrite/merge the teacher's points, drop figures, no labs/solvers, need internet & paid plans."]]
table(s, 0.3, 1.0, 9.05, rows, [0.3, 2.55, 3.1, 3.1], size=9.2, row_h=0.62)
panel(s, 9.5, 1.0, 3.55, 4.98, "Gap → how Learnova closes it", ORANGE, "puzzle")
gaps = [("Generates new decks", "Redesigns the existing deck"), ("Paraphrases, drops items", "Verbatim content + fact check"),
        ("Loses figures/equations", "Keeps every figure; OCR only when reliable"), ("No visuals by meaning", "27-detector decision engine"),
        ("No illustration", "AI diagram / own figure / offline scene"), ("No interaction", "Quizzes, solvers, labs"),
        ("Cloud & paid only", "Offline mode, free keys optional")]
for i, (a, b) in enumerate(gaps):
    y = 1.46 + i * 0.64
    rect(s, 9.6, y, 1.45, 0.54, TINT[RED], line=RED, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.15, lw=0.75)
    text(s, 9.62, y, 1.41, 0.54, [(a, {"size": 8.8, "color": RED, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
    arrow(s, 11.07, y + 0.27, 11.33, y + 0.27, ORANGE)
    rect(s, 11.35, y, 1.6, 0.54, TINT[GREEN], line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.15, lw=0.75)
    text(s, 11.37, y, 1.56, 0.54, [(b, {"size": 8.8, "color": GREEN, "bold": True, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
rect(s, 0.3, 6.1, 12.75, 1.0, TINT[RED], line=RED, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
text(s, 0.45, 6.14, 12.5, 0.95, [
    [("Common limitations found:  ", {"bold": True, "color": RED, "size": 11}),
     ("research systems summarise scientific papers rather than lecture decks, and they trade faithfulness for brevity; commercial tools produce attractive "
      "slides but cannot be checked against the source, ignore picture-only and equation slides, add no interaction and require a connection and a subscription. "
      "None of them redesigns the deck a teacher already uses — which is exactly the gap Learnova targets.", {"size": 11})]])

# ── 4. Architecture & technology stack ───────────────────────────────────────
s = frame("TECHNICAL APPROACH — ARCHITECTURE", "Input → processing workflow → output; every AI step has an offline fallback", 4)
rect(s, 0.3, 0.98, 8.95, 0.32, GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.4)
text(s, 0.3, 0.98, 8.95, 0.32, [("System architecture and data flow", {"bold": True, "size": 12, "color": WHITE, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
flow = [("INPUT", BLUE, [("upload", "PowerPoint (.pptx)", "teacher's existing deck"), ("file-text", "Slide PDF", "exported lecture slides"),
                         ("notebook-pen", "Word / notes", ".docx, markdown, text"), ("pencil", "Typed topic", "a prompt or syllabus line"),
                         ("flask-conical", "Teacher labs", "own HTML labs via API")]),
        ("INGEST", TEAL, [("refresh-cw", "LibreOffice convert", "PPTX → PDF, cached by hash"), ("search", "Slide reader", "titles · bullet levels · tables"),
                          ("eye", "OCR decision", "Tesseract when text is reliable"), ("wrench", "Repair", "furniture, glued titles, split words"),
                          ("palette", "Colour DNA", "source palette → theme")]),
        ("ENGINES", ORANGE, [("list-checks", "Planner", "split · merge · agenda · glossary"), ("brain", "Decision engine", "27 detectors, reason + score"),
                             ("ruler", "Layout engine", "glyph-measured, no broken words"), ("sigma", "Explainer solvers", "exact step-by-step (SymPy)"),
                             ("puzzle", "Quiz + lab selector", "checkpoints, one lab per topic")]),
        ("AI SERVICE", PURPLE, [("bot", "LLM router", "Gemini ×5 → Groq → NVIDIA"), ("pencil", "AI polish", "assertion titles, explanations"),
                                ("palette", "Topic diagrams", "validated SVG + HTML page"), ("code", "AI labs", "JS checked with node --check"),
                                ("cpu", "Offline fallback", "rules, scenes, structure labs")]),
        ("OUTPUT", GREEN, [("presentation", "Editable PPTX", "native shapes, linked pictures"), ("globe", "Web deck", "Reveal.js, reveals, overlays"),
                           ("book-open", "Study pack", "flashcards · Anki · quiz bank"), ("users", "Share link", "view-only, no login"),
                           ("message-circle", "Deck tutor", "answers from the deck only")])]
labels = ["IR", "plan", "calls", "assets"]
for i, (name, col, comps) in enumerate(flow):
    x = 0.3 + i * 1.82
    rect(s, x, 1.38, 1.62, 4.27, TINT[col], line=col, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    rect(s, x + 0.12, 1.32, 1.38, 0.24, col, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    text(s, x + 0.12, 1.32, 1.38, 0.24, [(name, {"bold": True, "size": 9, "color": WHITE, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
    for j, (ic, h, sub) in enumerate(comps):
        y = 1.64 + j * 0.8
        rect(s, x + 0.07, y, 1.48, 0.72, WHITE, line=col, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12, lw=0.75)
        badge(s, ic, x + 0.11, y + 0.06, 0.32, col)
        text(s, x + 0.46, y + 0.02, 1.08, 0.36, [(h, {"bold": True, "size": 8.4})], anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 0.1, y + 0.38, 1.42, 0.33, [(sub, {"size": 7.6, "color": MUTED})], spacing=0)
    if i < len(flow) - 1:
        arrow(s, x + 1.63, 3.5, x + 1.81, 3.5, INK, 2.25)
        text(s, x + 1.5, 3.2, 0.44, 0.26, [(labels[i], {"size": 6.8, "color": INK, "align": PP_ALIGN.CENTER, "italic": True})])
rect(s, 0.3, 5.75, 8.95, 0.72, RGBColor(0xF4, 0xF6, 0xFA), line=RGBColor(0xC9, 0xD0, 0xDA), shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
text(s, 0.38, 5.76, 3, 0.22, [("DEPLOYMENT AND OPERATIONS · open-source / free tier", {"bold": True, "size": 8.5, "color": MUTED})])
dep = [("git-branch", "GitHub", "source · 755 tests"), ("globe", "Vercel / Netlify", "React static build"), ("ship", "Docker on Render", "FastAPI + LibreOffice + OCR"),
       ("database", "SQLite volume", "users · decks · caches"), ("gauge", "Monitoring", "health · audit · logs")]
for i, (ic, h, sub) in enumerate(dep):
    x = 0.42 + i * 1.77
    rect(s, x, 6.0, 1.58, 0.42, WHITE, line=RGBColor(0xC9, 0xD0, 0xDA), shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2, lw=0.75)
    badge(s, ic, x + 0.05, 6.04, 0.34, INK)
    text(s, x + 0.42, 6.0, 1.15, 0.42, [(h, {"bold": True, "size": 8.2}), (sub, {"size": 7, "color": MUTED})], anchor=MSO_ANCHOR.MIDDLE, spacing=0)
    if i < len(dep) - 1:
        arrow(s, x + 1.59, 6.21, x + 1.76, 6.21, MUTED, 1.5)
steps4 = [("1 · Read faithfully", "every page, every figure kept", TEAL), ("2 · Decide with rules", "explainable visual per slide", BLUE),
          ("3 · Enrich with AI", "checked titles, diagrams, labs", ORANGE), ("4 · Build and audit", "PPTX + web deck, no breaks", INK)]
for i, (h, b, col) in enumerate(steps4):
    x = 0.3 + i * 2.25
    rect(s, x, 6.55, 2.18, 0.58, col, shape=MSO_SHAPE.PENTAGON)
    text(s, x + 0.08, 6.55, 1.95, 0.58, [(h, {"bold": True, "size": 9.5, "color": WHITE}), (b, {"size": 8, "color": WHITE})], anchor=MSO_ANCHOR.MIDDLE, spacing=0)
rect(s, 9.4, 0.98, 3.65, 0.32, BLUE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.4)
text(s, 9.4, 0.98, 3.65, 0.32, [("Technologies to be used", {"bold": True, "size": 12, "color": WHITE, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
techs = [("atom", "React", RGBColor(0x14, 0x9E, 0xCA)), ("zap", "Vite", RGBColor(0x8B, 0x5C, 0xF6)), ("waves", "Tailwind", RGBColor(0x06, 0xB6, 0xD4)),
         ("presentation", "Reveal.js", RGBColor(0xE0, 0x9F, 0x1F)), ("code", "Python", RGBColor(0x30, 0x6F, 0xA8)), ("zap", "FastAPI", RGBColor(0x00, 0x96, 0x88)),
         ("database", "SQLite", RGBColor(0x0F, 0x5F, 0x8C)), ("file-text", "PyMuPDF", RGBColor(0xC0, 0x30, 0x30)), ("refresh-cw", "LibreOffice", RGBColor(0x18, 0xA3, 0x03)),
         ("eye", "Tesseract", RGBColor(0x55, 0x5F, 0x6D)), ("sparkles", "Gemini", RGBColor(0x42, 0x85, 0xF4)), ("cpu", "Groq", RGBColor(0xF5, 0x50, 0x36)),
         ("sigma", "SymPy", RGBColor(0x3B, 0x7A, 0x3B)), ("test-tube-diagonal", "pytest", RGBColor(0xC8, 0x9B, 0x10)), ("git-branch", "GitHub", INK),
         ("ship", "Docker", RGBColor(0x1D, 0x63, 0xED))]
for i, (ic, nm, col) in enumerate(techs):
    x = 9.45 + (i % 4) * 0.9
    y = 1.4 + (i // 4) * 0.78
    rect(s, x + 0.17, y, 0.5, 0.5, col, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
    icon(s, ic, x + 0.27, y + 0.1, 0.3)
    text(s, x - 0.05, y + 0.5, 0.95, 0.24, [(nm, {"size": 7.8, "bold": True, "align": PP_ALIGN.CENTER})])
stack = [("Frontend:", "React 18 · Vite · Tailwind CSS · Reveal.js web deck · PWA (manifest + service worker)"),
         ("Backend:", "Python 3.12 · FastAPI · Pydantic · background job queue · SQLite · OTP auth"),
         ("Documents:", "python-pptx · PyMuPDF · LibreOffice headless · python-docx · Tesseract OCR"),
         ("AI / NLP:", "Gemini (pool of 5 keys, per-key pacing) · Groq · NVIDIA NIM · failover router"),
         ("Maths & labs:", "SymPy exact solvers · JavaScript lab engine · SVG via MuPDF"),
         ("Quality & DevOps:", "pytest (755) · layout audit · gold sets · GitHub · Docker")]
text(s, 9.42, 4.55, 3.65, 2.6, bullets(stack, 8.9), spacing=3)

# ── 5. Methodology & prototype ───────────────────────────────────────────────
s = frame("TECHNICAL APPROACH — METHODOLOGY", "Nine stages from upload to audited deck, with the algorithm behind each", 5)
stages = [("upload", "Convert", "PPTX → PDF (LibreOffice), DOCX/text → Markdown IR; colour palette of the source kept."),
          ("search", "Read slides", "Furniture = text on ≥ max(3, 0.3n) pages; bullet level ℓ(x) = argmin |x − aₖ|; glued titles split by DP."),
          ("eye", "OCR decision", "γ = |ink ∖ text| / |ink|; OCR used only if conf ≥ 62, γ ≤ 0.42, < 15% symbol lines."),
          ("list-checks", "Plan", "Split overloaded slides at logical boundaries; merge thin parts; agenda, glossary, quizzes."),
          ("brain", "Decide visual", "27 detectors → (family, confidence, data, reason); d* = argmax c after exclusion rules."),
          ("pencil", "AI polish", "Assertion titles, explanations, key terms — accepted only if grounded in the slide's words."),
          ("palette", "Illustrate", "LLM SVG → whitelist + ≥ 6 shapes + render check → cache; else own figure / offline scene."),
          ("ruler", "Lay out & build", "s* = largest size that fits (≥ 11 pt); σ = min(1, W / w(longest word)); PPTX + web deck."),
          ("gauge", "Audit", "Overflow, broken words, sparse slides; fact retention R = |F_src ∩ F_deck| / |F_src|.")]
for i, (ic, h, b) in enumerate(stages):
    col, row = i % 3, i // 3
    x, y = 0.3 + col * 4.27, 1.0 + row * 1.2
    c = [ORANGE, BLUE, GREEN][row]
    rect(s, x, y, 4.13, 1.1, TINT[c], line=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    badge(s, ic, x + 0.1, y + 0.12, 0.5, c)
    text(s, x + 0.08, y + 0.66, 0.55, 0.3, [(f"{i + 1}", {"bold": True, "size": 12, "color": c, "align": PP_ALIGN.CENTER})])
    text(s, x + 0.7, y + 0.06, 3.38, 1.0, [(h, {"bold": True, "size": 11.5, "font": HEAD}), (b, {"size": 9.6, "color": INK})], spacing=1)
    if col < 2:
        arrow(s, x + 4.13, y + 0.55, x + 4.27, y + 0.55, c, 2)
text(s, 0.3, 4.62, 12.75, 0.3, [("WORKING PROTOTYPE · real screens from the running application", {"bold": True, "size": 11, "color": ORANGE})])
shots = [("app-preview.jpg", "Deck preview — visual chosen and why"), ("web_deck.png", "Web deck — AI diagram beside the content"),
         ("app-solve.jpg", "Solve step by step"), ("explainer-viterbi.png", "Viterbi explainer, exact"), ("lab_split.png", "Split & Merge lab (IPCV)")]
for i, (f, cap) in enumerate(shots):
    x = 0.3 + i * 2.57
    rect(s, x, 4.92, 2.47, 2.18, RGBColor(0xF4, 0xF6, 0xFA), line=RGBColor(0xD8, 0xDE, 0xE8), shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    picture(s, f"{IMG}/{f}", x + 0.06, 4.98, 2.35, 1.78)
    text(s, x, 6.78, 2.47, 0.3, [(cap, {"size": 9, "color": MUTED, "align": PP_ALIGN.CENTER})])

# ── 6. Before vs after ───────────────────────────────────────────────────────
s = frame("BEFORE vs AFTER", "The problems teachers and students faced — and what Learnova now achieves", 6)
pf = [("Text-heavy slides", "100+ words on a slide; students skim and miss points", "One idea per slide, drawn as a visual at a readable density"),
      ("Pictures of equations", "Content locked in images; tools drop these slides", "Kept full size as figures; OCR only when reliable"),
      ("Untitled / generic titles", "“Slide 9”, “Hypothesis (2/5)” says nothing", f"Assertion titles; {UNTITLED} untitled slides → 0"),
      ("No diagrams", "Plain text with nothing to explain the idea", "Illustration on every topic slide + HTML link"),
      ("No interaction", "Solved problems shown as finished tables", "Quizzes, step-by-step solvers, labs"),
      ("AI changes content", "Paraphrased, merged, invented facts", "Verbatim + checked: 98–100% facts kept"),
      ("Redesign takes hours", "An evening per lecture, needs design skill", "≈10–60 s per deck, fully editable"),
      ("Needs internet / paid AI", "Cloud-only, subscriptions, quotas", "Offline mode; 5 free keys rotate")]
rows = [["Area", "BEFORE — problem faced", "AFTER — with Learnova"]] + [[a, "✘ " + b, "✔ " + c] for a, b, c in pf]
t = table(s, 0.3, 1.0, 7.45, rows, [1.7, 2.8, 2.95], head_fill=INK, size=9.4, row_h=0.42, zebra=False)
for i in range(1, len(rows)):
    for j, col in ((1, TINT[RED]), (2, TINT[GREEN])):
        t.cell(i, j).fill.solid()
        t.cell(i, j).fill.fore_color.rgb = col
        t.cell(i, j).text_frame.paragraphs[0].runs[0].font.color.rgb = RED if j == 1 else GREEN
pairs = [("pair1", "ML · Bias & variance (PPTX)"), ("pair2", "ML · Linear regression (PPTX)"), ("pair3", "NLP · WSD (PDF)")]
text(s, 7.95, 0.98, 5.1, 0.28, [[("ORIGINAL", {"bold": True, "size": 10, "color": RED}), ("   →   ", {"size": 10}), ("LEARNOVA", {"bold": True, "size": 10, "color": GREEN})]],
     align=PP_ALIGN.CENTER)
for i, (k, cap) in enumerate(pairs):
    y = 1.28 + i * 1.32
    picture(s, f"{IMG}/{k}_before.png", 7.95, y, 2.35, 1.22)
    arrow(s, 10.33, y + 0.61, 10.6, y + 0.61, ORANGE, 2.25)
    picture(s, f"{IMG}/{k}_after.png", 10.65, y, 2.4, 1.22)
    text(s, 7.95, y + 1.0, 2.35, 0.24, [(cap, {"size": 8, "bold": True, "color": WHITE, "align": PP_ALIGN.CENTER})])
    rect(s, 7.95, y + 1.0, 2.35, 0.22, INK).fill.fore_color.rgb = INK
    s.shapes._spTree.remove(s.shapes[-1]._element)
for i, (big, lab, col) in enumerate([(f"{UNTITLED} → 0", "untitled slides", RED), (f"{sum(v['after']['visual_structures'] for v in BA.values())}", "slides drawn as visuals", BLUE),
                                     (f"{sum(v['after']['linked_illustrations'] for v in BA.values())}", "linked illustrations", PURPLE),
                                     (f"{sum(v['after']['quizzes'] + v['after']['labs'] for v in BA.values())}", "quizzes + labs added", GREEN)]):
    x = 7.95 + (i % 2) * 2.58
    y = 5.3 + (i // 2) * 0.92
    rect(s, x, y, 2.48, 0.84, TINT[col], line=col, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
    text(s, x, y + 0.02, 2.48, 0.82, [(big, {"bold": True, "size": 20, "color": col, "align": PP_ALIGN.CENTER, "font": HEAD}),
                                      (lab, {"size": 9.5, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE, spacing=0)
text(s, 0.3, 4.85, 7.45, 2.25, [
    ("Reading the comparison", {"bold": True, "size": 11, "color": ORANGE}),
    ("The left column lists the problems we saw in our own courses: decks that are hard to read, half their content locked in pictures and no way for a student to "
     "check understanding. The right column is what Learnova does to the same material, measured on five real decks (two machine-learning PowerPoints and "
     "three NLP PDFs). The slide pairs show the same source slide before and after; the counters on the right sum the changes across all five decks.", {"size": 10.3}),
    ("The content itself does not change: fact retention stayed between 98% and 100% for every deck, and the layout audit found no overflowing text and no "
     "broken words.", {"size": 10.3})], spacing=4)

# ── 7. Results & impact ──────────────────────────────────────────────────────
s = frame("RESULTS, IMPACT & BENEFITS", "Measured on real course material — not on promises", 7)
names = {"ml1": "ML Bias&Var", "ml2": "ML Lin.Reg", "wsd": "NLP WSD", "m4": "NLP Mod 4", "m5": "NLP Mod 5"}
keys = [k for k in names if k in BA]
cd = CategoryChartData()
cd.categories = [names[k] for k in keys]
cd.add_series("Slides with a picture — before", [BA[k]["before"]["with_picture"] for k in keys])
cd.add_series("after", [BA[k]["after"]["with_picture"] for k in keys])
cd.add_series("Untitled — before", [BA[k]["before"]["untitled"] for k in keys])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.3), Inches(1.0), Inches(4.6), Inches(2.95), cd)
ch = gf.chart
ch.has_legend, ch.legend.position, ch.legend.include_in_layout = True, XL_LEGEND_POSITION.BOTTOM, False
ch.legend.font.size = Pt(8)
ch.has_title = True
ch.chart_title.text_frame.text = "Pictures and titles per deck"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(11)
for ser, col in zip(ch.series, (RGBColor(0xB8, 0xC2, 0xD0), BLUE, RED)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
ch.category_axis.tick_labels.font.size = Pt(8)
ch.value_axis.tick_labels.font.size = Pt(8)
cd2 = CategoryChartData()
cd2.categories = [names[k] for k in keys]
cd2.add_series("Visual slides", [BA[k]["after"]["visual_structures"] for k in keys])
cd2.add_series("Linked illustrations", [BA[k]["after"]["linked_illustrations"] for k in keys])
cd2.add_series("Quizzes", [BA[k]["after"]["quizzes"] for k in keys])
cd2.add_series("Labs", [BA[k]["after"]["labs"] for k in keys])
gf2 = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(5.0), Inches(1.0), Inches(4.25), Inches(2.95), cd2)
c2 = gf2.chart
c2.has_legend, c2.legend.position, c2.legend.include_in_layout = True, XL_LEGEND_POSITION.BOTTOM, False
c2.legend.font.size = Pt(8)
c2.has_title = True
c2.chart_title.text_frame.text = "Added by Learnova (all were 0 before)"
c2.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(11)
for ser, col in zip(c2.series, (BLUE, PURPLE, ORANGE, GREEN)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
c2.category_axis.tick_labels.font.size = Pt(8)
c2.value_axis.tick_labels.font.size = Pt(8)
kpis = [("97%", "visual chosen correctly", "101 gold slides, 3 sets"), ("98–100%", "facts kept", "7 real decks"), ("0", "broken words / overflow", "layout audit"),
        ("26/26", "problems solved right", "held-out benchmark"), ("< 1 ms", "decision per slide", "rule engine"), ("~35 s", "216-page PDF → deck", "no API key")]
for i, (big, lab, sub) in enumerate(kpis):
    x = 9.4 + (i % 2) * 1.85
    y = 1.0 + (i // 2) * 1.0
    rect(s, x, y, 1.75, 0.92, TINT[ORANGE], line=ORANGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
    text(s, x, y, 1.75, 0.92, [(big, {"bold": True, "size": 17, "color": ORANGE, "align": PP_ALIGN.CENTER, "font": HEAD}),
                               (lab, {"bold": True, "size": 8.5, "align": PP_ALIGN.CENTER}), (sub, {"size": 7.5, "color": MUTED, "align": PP_ALIGN.CENTER})],
         anchor=MSO_ANCHOR.MIDDLE, spacing=0)
benefits = [("Students", BLUE, "graduation-cap", ["One clear idea per slide with a picture", "Steps with reasons for every solved problem", "Quizzes, labs and flashcards to practise",
                                                  "Revise on a phone, even offline"]),
            ("Faculty", GREEN, "lectern", ["Old decks modernised in about a minute", "Their own words and figures kept", "Editable PowerPoint, ready to teach",
                                           "Quizzes and labs with no extra work"]),
            ("Institution", PURPLE, "school", ["Consistent, accessible course material", "No paid AI licence needed", "Supports flipped and remote classes",
                                               "Reusable lab library across subjects"]),
            ("Society · SDG 4", TEAL, "globe", ["Quality education with low-cost tools", "Works where internet is unreliable", "Plain-language help for first-generation learners",
                                                "Open formats, easy to share"])]
for i, (h, col, ic, items) in enumerate(benefits):
    x = 0.3 + i * 3.2
    panel(s, x, 4.08, 3.08, 2.15, h, col, ic)
    text(s, x + 0.08, 4.47, 2.95, 1.75, bullets(items, 10.4, mark="✔"), spacing=4)
rect(s, 0.3, 6.32, 12.75, 0.78, TINT[BLUE], line=BLUE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
text(s, 0.45, 6.34, 12.5, 0.75, [
    [("Use cases:  ", {"bold": True, "color": BLUE, "size": 10.5}),
     ("a teacher uploads last year's PPT the night before a lecture and presents the redesigned deck; a student opens the shared web deck to revise with quizzes and labs; "
      "an IPCV class explores region growing and split-and-merge in the browser; a college without paid AI tools uses the offline mode. "
      "Next: a classroom study of learning outcomes with our own batch.", {"size": 10.5})]])

# ── 8. Feasibility & viability ───────────────────────────────────────────────
s = frame("FEASIBILITY & VIABILITY", "Running today on a laptop · pilot-ready for a department · every risk has a named safeguard", 8)
feas = [("TECHNICAL", BLUE, "cpu", "Already working end to end: FastAPI back end, React front end, 755 automated tests, layout audit. Each stage is a separate module, so "
                                  "features are added without rework."),
        ("DATA", TEAL, "database", "Input is the college's own lecture material (PPTX, PDF, DOCX). Tested on seven real decks of 15 to 216 slides from NLP, ML and IPCV."),
        ("ECONOMIC", GREEN, "piggy-bank", "Free to run offline; Gemini free-tier keys (pool of 5) are optional. Hosting a department server costs less than a single "
                                          "paid AI-presentation licence per year."),
        ("OPERATIONAL", ORANGE, "users", "Teachers keep control: every slide stays editable and every automatic choice shows its reason. Students need only a browser."),
        ("SECURITY", PURPLE, "lock", "OTP sign-in, hashed codes, rate limits; AI-written SVG and lab code are whitelisted and statically checked; share links are view-only.")]
for i, (h, col, ic, body) in enumerate(feas):
    y = 1.0 + i * 1.22
    rect(s, 0.3, y, 4.5, 1.14, TINT[col], line=col, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    badge(s, ic, 0.4, y + 0.12, 0.5, col)
    text(s, 0.98, y + 0.04, 3.78, 1.08, [(h, {"bold": True, "size": 10.5, "color": col}), (body, {"size": 9.3})], spacing=1)
panel(s, 4.95, 1.0, 4.1, 6.08, "Challenges / risks → our safeguard", RED, "shield")
risks = [("Messy lecture PDFs", "symbol bullets, glued titles, picture slides → page reader, DP title split, OCR decision"),
         ("AI hallucination", "paraphrase, invented facts → grounded checks, verbatim source, SymPy numbers"),
         ("API quota / cost", "free-tier limits → 5-key pool, per-key pacing, failover, offline mode, cache"),
         ("Broken layout", "overflow, split words → glyph-measured fitting, 11 pt floor, continuation slides"),
         ("Slow large decks", "216 pages, many diagrams → parallel generation, content-hash caching"),
         ("Unsafe generated code", "scripts in SVG/labs → element whitelist, node --check, no network APIs"),
         ("Wrong visual choice", "rule misfires → alternatives shown in the editor; slide stays editable")]
for i, (h, b) in enumerate(risks):
    y = 1.45 + i * 0.8
    rect(s, 5.05, y, 0.42, 0.42, RED, shape=MSO_SHAPE.OVAL)
    text(s, 5.05, y, 0.42, 0.42, [(str(i + 1), {"bold": True, "size": 11, "color": WHITE, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
    text(s, 5.55, y - 0.04, 3.45, 0.8, [(h, {"bold": True, "size": 10.2}), (b, {"size": 9.2, "color": MUTED})], spacing=0)
panel(s, 9.2, 1.0, 3.85, 3.1, "Adoption path", GREEN, "route")
steps = [("1 · Pilot", "AI & DS department: our own courses this semester, feedback from 3–4 faculty"),
         ("2 · Department", "shared server, deck library per teacher, labs library grows with faculty labs"),
         ("3 · College / LMS", "Moodle / Google Classroom export, regional languages, analytics")]
for i, (h, b) in enumerate(steps):
    y = 1.45 + i * 0.86
    rect(s, 9.3, y, 3.65, 0.78, WHITE, line=GREEN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1, lw=0.75)
    text(s, 9.38, y + 0.02, 3.5, 0.75, [(h, {"bold": True, "size": 10, "color": GREEN}), (b, {"size": 9})], spacing=0)
panel(s, 9.2, 4.2, 3.85, 2.88, "Deployment plan", BLUE, "cloud")
text(s, 9.3, 4.62, 3.65, 2.45, bullets([("Front end:", "static React build on Vercel / Netlify."),
                                        ("Back end:", "Docker container (FastAPI + LibreOffice + Tesseract) on Render, Railway or Google Cloud Run with a persistent volume."),
                                        ("Config:", "API URL for the front end; LEARNOVA_PUBLIC_URL so PowerPoint lab and illustration links resolve."),
                                        ("Why not all on Vercel:", "long jobs, system binaries and on-disk storage do not fit serverless functions.")], 9.2), spacing=3)

# ── 9. Research & references ─────────────────────────────────────────────────
s = frame("RESEARCH & REFERENCES", "Papers we built on · tools we compared · our own publications and code", 9)
cards = [("SLIDE GENERATION", BLUE, "presentation", ["Hu & Wan, PPSGen, IEEE TKDE 27(4):1085–1097, 2015", "Fu et al., DOC2PPT, AAAI 36:634–642, 2022", "Sun et al., D2S, NAACL 2021, pp. 1405–1418"]),
         ("FAITHFULNESS", RED, "shield-check", ["Maynez et al., ACL 2020, pp. 1906–1919", "Ji et al., Survey of hallucination, ACM CSUR 55(12), 2023"]),
         ("LEARNING SCIENCE", GREEN, "graduation-cap", ["Mayer, Multimedia Learning, CUP, 2009", "Sweller, Cognitive Science 12(2), 1988", "Garner & Alley, IJEE 29(6), 2013"]),
         ("WORKED EXAMPLES & LABS", ORANGE, "flask-conical", ["Sweller & Cooper, Cogn. & Instr. 2(1), 1985", "Hundhausen et al., JVLC 13(3), 2002", "Wieman et al., PhET, Science 322, 2008"]),
         ("LAYOUT & VISUALS", PURPLE, "ruler", ["Knuth & Plass, Breaking paragraphs into lines, SPE 11(11), 1981", "Mackinlay, APT, ACM TOG 5(2), 1986", "Moritz et al., Draco, IEEE TVCG 25(1), 2019"]),
         ("NLP & OCR", TEAL, "languages", ["Jurafsky & Martin, Speech and Language Processing, 3rd ed. draft", "Smith, Tesseract OCR, ICDAR 2007", "Meurer et al., SymPy, PeerJ CS 3:e103, 2017"]),
         ("TOOLS COMPARED", INK if False else BLUE, "search", ["Gamma (gamma.app)", "Microsoft Copilot in PowerPoint", "Gemini in Google Slides · Canva Magic Design"]),
         ("OUR PAPERS", RED, "newspaper", ["IEEE conf. paper: Rebuilding lecture slide decks into visually structured, interactive presentations",
                                          "Springer LNCS paper: Computed step-by-step explainers and generated labs"])]
for i, (h, col, ic, refs) in enumerate(cards):
    x = 0.3 + (i % 4) * 3.2
    y = 1.0 + (i // 4) * 2.55
    rect(s, x, y, 3.08, 2.45, TINT[col], line=col, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    badge(s, ic, x + 0.1, y + 0.1, 0.5, col)
    text(s, x + 0.68, y + 0.12, 2.35, 0.45, [(h, {"bold": True, "size": 11, "color": col, "font": HEAD})], anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.12, y + 0.66, 2.88, 1.76, [[("▸ ", {"color": col, "bold": True, "size": 10}), (r, {"size": 10})] for r in refs], spacing=7)
rect(s, 0.3, 6.14, 12.75, 0.95, TINT[BLUE], line=BLUE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
qr(s, REPO, 0.38, 6.19, 0.85)
qr(s, REPO + "/tree/main/docs/research/papers", 1.32, 6.19, 0.85)
text(s, 2.3, 6.17, 10.6, 0.9, [
    [("Scan to verify:  ", {"bold": True, "color": BLUE, "size": 10.5}), ("left — full source code, tests and demo decks (github.com/SDP42/LearnovaV2); right — both research papers (IEEE and "
     "Springer LNCS), gold sets and the measurement scripts used for every number on these slides. ", {"size": 10.5}),
     ("Web resources: ", {"bold": True, "size": 10.5}), ("revealjs.com · python-pptx · PyMuPDF · LibreOffice · Tesseract · ai.google.dev", {"size": 10.5})]])

# ── 10. Thank you ────────────────────────────────────────────────────────────
s = prs.slides.add_slide(prs.slide_layouts[6])
for ph in list(s.placeholders):
    ph._element.getparent().remove(ph._element)
s.background.fill.solid()
s.background.fill.fore_color.rgb = RGBColor(0x0F, 0x17, 0x2A)
for d, col, x, y in ((5.5, RGBColor(0x1F, 0x3A, 0x6B), -1.6, 3.6), (3.4, RGBColor(0x5A, 0x2E, 0x12), 10.8, -1.2), (1.6, ORANGE, 11.7, 5.9)):
    rect(s, x, y, d, d, col, shape=MSO_SHAPE.OVAL)
rect(s, 0.9, 1.25, 0.14, 2.3, ORANGE)
text(s, 1.2, 1.05, 7.5, 1.4, [("Thank You", {"bold": True, "size": 66, "color": WHITE, "font": HEAD})])
text(s, 1.22, 2.45, 7.5, 1.2, [("Questions, feedback — and a live demo of Learnova", {"size": 20, "color": RGBColor(0xFF, 0xB0, 0x7A)}),
                               ("Upload any lecture deck and watch it become an illustrated, interactive teaching deck.", {"size": 14, "color": RGBColor(0xC8, 0xD0, 0xDC)})], spacing=6)
team = ["Kawaljeet Singh Bharaj · 60018240016", "Jeevesh Bharat Bodhani · 60018240096", "Rishit Pankajkumar Lahoti · 6001840101", "Swayam Devendra Panchal · 60018240013"]
rect(s, 1.0, 4.05, 6.6, 2.35, RGBColor(0x18, 0x24, 0x3D), line=RGBColor(0x2E, 0x3E, 0x5C), shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
text(s, 1.2, 4.12, 6.3, 2.25, [("TEAM · GROUP 1", {"bold": True, "size": 12, "color": ORANGE})] + [(t_, {"size": 13, "color": WHITE}) for t_ in team]
     + [("Department of Artificial Intelligence and Data Science, DJSCE, Mumbai", {"size": 11, "color": RGBColor(0xA8, 0xB3, 0xC4)})], spacing=4)
picture(s, f"{IMG}/art_sheet.png", 8.1, 1.25, 4.6, 2.1, border=False)
text(s, 8.1, 3.38, 4.6, 0.3, [("Diagrams drawn by Learnova for real lecture slides", {"size": 10, "color": RGBColor(0xA8, 0xB3, 0xC4), "align": PP_ALIGN.CENTER})])
rect(s, 8.55, 3.95, 3.7, 2.45, WHITE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
qr(s, REPO, 8.7, 4.08, 1.55)
text(s, 10.35, 4.1, 1.85, 2.25, [("Scan for", {"size": 11, "color": MUTED}), ("code, papers & demo decks", {"bold": True, "size": 12, "color": INK}),
                                 ("github.com/SDP42/LearnovaV2", {"size": 9.5, "color": BLUE})], spacing=4, anchor=MSO_ANCHOR.MIDDLE)
text(s, 1.0, 6.65, 11.3, 0.4, [("LEARNOVA  ·  Read  ·  Redesign  ·  Illustrate  ·  Engage  ·  Deliver", {"bold": True, "size": 13, "color": RGBColor(0x7F, 0x8C, 0xA0), "font": HEAD})])

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
