"""
IPD review presentation on the department template (IPD Review Templet_Odd_SEM_III.pptx), in the SIH style:
problem, objectives, literature, idea and prototype, architecture and tech stack, use cases, implementation, novelty,
results, future scope and references.

    python scripts/research/build_review_ppt.py <template.pptx> <images dir> <out.pptx>
"""
import copy
import json
import pathlib
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ORANGE = RGBColor(0xFF, 0x91, 0x4D)
INK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x55, 0x5F, 0x6D)
BLUE = RGBColor(0x44, 0x72, 0xC4)
SOFT = RGBColor(0xF4, 0xF6, 0xFA)
FONT = "Montserrat Light"
HEAD = "Montserrat"

TPL, IMG, OUT = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3]
BA = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
prs = Presentation(TPL)
S = list(prs.slides)


# ── helpers ──────────────────────────────────────────────────────────────────
def remove(shape):
    shape._element.getparent().remove(shape._element)


def shape_named(slide, name):
    return next(sh for sh in slide.shapes if sh.name == name)


def text(slide, x, y, w, h, paras, size=14, color=INK, font=FONT, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """paras: list of str or (str, dict(bold, color, size, bullet))."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    for i, p in enumerate(paras):
        t, o = (p, {}) if isinstance(p, (str, list)) else p
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = o.get("align", align)
        para.space_after = Pt(o.get("after", 5))
        runs = t if isinstance(t, list) else [(t, o)]
        for rt, ro in runs:
            r = para.add_run()
            r.text = rt
            r.font.size = Pt(ro.get("size", o.get("size", size)))
            r.font.bold = ro.get("bold", o.get("bold", False))
            r.font.name = ro.get("font", o.get("font", font))
            r.font.color.rgb = ro.get("color", o.get("color", color))
    return tb


def box(slide, x, y, w, h, fill=SOFT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, label=None, size=12, bold=False, color=INK):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1.25)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.12
    s.shadow.inherit = False
    if label is not None:
        tf = s.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.06)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        lines = label if isinstance(label, list) else [label]
        for i, ln in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = ln
            r.font.size = Pt(size if i == 0 else size - 2)
            r.font.bold = bold if i == 0 else False
            r.font.name = HEAD if (bold and i == 0) else FONT
            r.font.color.rgb = color
    return s


def arrow(slide, x1, y1, x2, y2, color=MUTED):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln()
    from pptx.oxml.ns import qn
    from lxml import etree

    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    return c


def picture(slide, path, x, y, w=None, h=None, border=True):
    pic = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if border:
        pic.line.color.rgb = RGBColor(0xD0, 0xD5, 0xDD)
        pic.line.width = Pt(0.75)
    return pic


def heading(slide, title, sub=None):
    """A title in the template's style: large heading, orange rule under it."""
    text(slide, 0.35, 0.18, 12.4, 0.8, [(title, {"size": 30, "bold": True, "font": HEAD})])
    r = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.4), Inches(0.98), Inches(1.4), Inches(0.07))
    r.fill.solid()
    r.fill.fore_color.rgb = ORANGE
    r.line.fill.background()
    if sub:
        text(slide, 0.38, 1.08, 12.4, 0.4, [(sub, {"size": 13, "color": MUTED})])


def new_slide():
    """A blank slide on the template's content layout (same master, page-number box added)."""
    s = prs.slides.add_slide(prs.slide_layouts[11])
    for ph in list(s.placeholders):
        remove(ph)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = RGBColor(255, 255, 255)
    n = len(prs.slides) - 1                       # the references slide is moved after the new slides
    text(s, 12.86, 6.97, 0.47, 0.47, [(str(n), {"size": 10, "color": RGBColor(255, 255, 255), "align": PP_ALIGN.CENTER})])
    num = s.shapes[-1]
    num.name = "Slide Number Placeholder 5"
    num.fill.solid()
    num.fill.fore_color.rgb = RGBColor(0, 0, 0)
    return s


def move_to(slide, index):
    lst = prs.slides._sldIdLst
    ids = list(lst)
    for e in ids:
        if prs.part.related_part(e.rId) is slide.part:
            lst.remove(e)
            lst.insert(index, e)
            return


# ── 1. Title ─────────────────────────────────────────────────────────────────
s1 = S[0]
t = shape_named(s1, "TextBox 6")
t.left, t.top, t.width, t.height = Inches(4.3), Inches(4.1), Inches(8.6), Inches(1.6)
t.text_frame.clear()
t.text_frame.word_wrap = True
p = t.text_frame.paragraphs[0]
for rt, b, c in (("Title: ", True, ORANGE), ("Learnova — AI-powered redesign of outdated lecture slides into interactive, illustrated teaching decks", False, RGBColor(255, 255, 255))):
    r = p.add_run()
    r.text, r.font.bold, r.font.size, r.font.name = rt, b, Pt(18), HEAD if b else FONT
    r.font.color.rgb = c
p2 = t.text_frame.add_paragraph()
r = p2.add_run()
r.text = "Group No. 1  ·  Department of Artificial Intelligence and Data Science, DJSCE"
r.font.size, r.font.name = Pt(13), FONT
r.font.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
grp = next(sh for sh in s1.shapes if sh.shape_type == 6)
members = next(g for g in grp.shapes if g.has_text_frame and "Group Members" in g.text_frame.text)
tf = members.text_frame
tf.clear()
rows = [("Group Members:", True), ("", False),
        ("Kawaljeet Singh Bharaj", True), ("S004 · 60018240016", False), ("", False),
        ("Jeevesh Bharat Bodhani", True), ("S005 · 60018240096", False), ("", False),
        ("Rishit Pankajkumar Lahoti", True), ("S026 · 6001840101", False), ("", False),
        ("Swayam Devendra Panchal", True), ("S029 · 60018240013", False), ("", False),
        ("Mentor:", True), ("________________", False)]
for i, (rt, b) in enumerate(rows):
    para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = para.add_run()
    r.text, r.font.bold, r.font.size, r.font.name = rt, b, Pt(12 if b else 11), FONT
    r.font.color.rgb = RGBColor(0, 0, 0)

def retitle(slide, name, title, sub=""):
    """Replace a template heading's guidance text with the real heading (keeps the template's font and size)."""
    tb = shape_named(slide, name)
    p = tb.text_frame.paragraphs[0]
    runs = list(p.runs)
    first = runs[0]
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    for extra in list(tb.text_frame.paragraphs)[1:]:
        extra._p.getparent().remove(extra._p)
    first.text = title
    if sub:
        r = p.add_run()
        r.text = sub
        r.font.size, r.font.name = Pt(16), FONT
        r.font.color.rgb = MUTED


# ── 2. Idea / approach: problem and objectives ───────────────────────────────
s2 = S[1]
remove(shape_named(s2, "TextBox 13"))
_h = shape_named(s2, "TextBox 14")
_h.left, _h.width = Inches(0.45), Inches(12.4)            # one line, clear of the content below
text(s2, 0.5, 1.55, 12.3, 0.4, [[("❖ Problem Statement", {"bold": True, "color": ORANGE, "size": 20, "font": HEAD})]])
text(s2, 0.75, 2.0, 12.0, 1.5, [
    "Lecture slides used in colleges are mostly old PowerPoint files or PDFs: dense bullet text, equations and diagrams pasted as "
    "pictures, missing titles and no interaction. Faculty do not have the time to redesign every deck, and AI deck generators create "
    "new slides from a prompt but rewrite or drop the teacher's content and cannot redesign an existing deck faithfully.",
    [("Learnova redesigns an existing lecture deck into a modern, illustrated, interactive deck while keeping every point the "
      "teacher wrote.", {"bold": True})]], size=15)
text(s2, 0.5, 3.7, 12.3, 0.4, [[("❖ Objectives", {"bold": True, "color": ORANGE, "size": 20, "font": HEAD})]])
objs = ["Read real lecture material (PPTX, slide PDFs, Word notes, typed topics) and recover titles, bullet levels, tables, figures and picture-only slides.",
        "Choose a suitable visual for each slide (process, timeline, comparison, definition, chart …) and draw an illustration on every slide.",
        "Keep 100% of the source content: no item dropped, no fact invented, no word broken across lines.",
        "Make slides interactive: checkpoint quizzes, step-by-step solved problems and hands-on labs for hard topics (NLP, ML, IPCV).",
        "Work with AI keys for better titles, explanations and diagrams, and fully offline when keys are unavailable."]
text(s2, 0.75, 4.15, 12.0, 2.8, [(f"{i}.  {o}", {"size": 14, "after": 5}) for i, o in enumerate(objs, 1)])

# ── 3. Literature review table ───────────────────────────────────────────────
s3 = S[2]
remove(shape_named(s3, "TextBox 2"))
tbl_shape = next(sh for sh in s3.shapes if sh.has_table)
tbl_shape.top, tbl_shape.left, tbl_shape.width = Inches(1.25), Inches(0.35), Inches(12.6)
tbl = tbl_shape.table
lit = [
    ("Hu & Wan, “PPSGen: Learning-based presentation slides generation for academic papers”, IEEE TKDE, 2015",
     "Regression model scores sentence importance; ILP selects sentences into slides.", "Works on papers only; summarises (loses content); no visuals, no redesign of existing slides."),
    ("Fu et al., “DOC2PPT: Automatic presentation slides generation from scientific documents”, AAAI, 2022",
     "Neural summariser + figure selection + layout prediction, trained on paper–slide pairs.", "Needs training data; abstractive text can drop or alter facts; input must be a paper."),
    ("Sun et al., “D2S: Document-to-slide generation via query-based text summarization”, NAACL, 2021",
     "Slide titles used as queries; QA-style retrieval + summarisation per slide.", "Text only; no figures or interactivity; cannot rebuild an existing deck."),
    ("Garner & Alley, “How the design of presentation slides affects audience comprehension: assertion–evidence approach”, IJEE, 2013",
     "Sentence headlines + visual evidence improve comprehension over bullet lists.", "Design guidance only — no tool applies it automatically to old decks."),
    ("Existing tools: Gamma, Microsoft Copilot in PowerPoint, Gemini in Slides, Canva Magic Design",
     "LLM outline → template fill; good-looking new decks from a prompt.", "Rewrite/merge the teacher's content, lose original figures, no quizzes/labs, need internet and paid AI."),
]
for _ in range(len(lit) + 1 - len(tbl.rows)):
    tbl._tbl.append(copy.deepcopy(tbl._tbl.tr_lst[-1]))
widths = [0.7, 4.3, 3.6, 4.0]
for c, w in zip(tbl.columns, widths):
    c.width = Inches(w)
heads = ["Sr. No.", "Reference Paper / Existing Application", "Key Findings", "Gap / Scope for Improvement"]


def set_cell(cell, value, size=10.5, bold=False, color=None):
    tf = cell.text_frame
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    p = tf.paragraphs[0]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    r = p.add_run()
    r.text = value
    r.font.size, r.font.bold, r.font.name = Pt(size), bold, FONT
    if color is not None:
        r.font.color.rgb = color


for j, h in enumerate(heads):
    set_cell(tbl.cell(0, j), h, 11.5, True, RGBColor(255, 255, 255))
for i, (ref, find, gap) in enumerate(lit, 1):
    for j, v in enumerate((str(i), ref, find, gap)):
        set_cell(tbl.cell(i, j), v)
lim = shape_named(s3, "TextBox 13")
lim.top, lim.height = Inches(6.35), Inches(0.6)
lim.text_frame.clear()
p = lim.text_frame.paragraphs[0]
for rt, b, c in (("Common limitations: ", True, INK), ("existing systems generate new decks instead of redesigning old ones, are not faithful to the source, "
                                                       "ignore picture-only and equation slides, and offer no interactivity or offline mode.", False, RGBColor(0xC0, 0x30, 0x30))):
    r = p.add_run()
    r.text, r.font.bold, r.font.size, r.font.name = rt, b, Pt(13), FONT
    r.font.color.rgb = c

# ── 4. Idea / prototype ──────────────────────────────────────────────────────
s4 = S[3]
retitle(s4, "TextBox 3", "IDEA", "   Prototype — upload an old deck, get a redesigned interactive deck")
text(s4, 0.35, 1.5, 4.7, 5.2, [
    [("How it works", {"bold": True, "color": ORANGE, "size": 17, "font": HEAD})],
    "1.  Upload a lecture deck — PPTX, PDF, Word notes — or type a topic.",
    "2.  Learnova reads every slide: titles, bullet levels, tables, figures; OCR for picture slides.",
    "3.  Each slide gets the right visual, an assertion title, and an illustration (AI-drawn diagram, the teacher's figure, or an offline illustration).",
    "4.  Quizzes, step-by-step solved problems and labs are added.",
    "5.  Download an editable PowerPoint, an interactive web deck and a study pack; share a link.",
], size=13)
text(s4, 5.35, 1.45, 3.6, 0.35, [[("Before — original slide", {"bold": True, "size": 12, "color": MUTED})]])
picture(s4, f"{IMG}/before_lowbias.png", 5.35, 1.8, w=3.6)
text(s4, 9.15, 1.45, 3.9, 0.35, [[("After — Learnova slide", {"bold": True, "size": 12, "color": ORANGE})]])
picture(s4, f"{IMG}/after_19.png", 9.15, 1.8, w=3.9)
arrow(s4, 8.98, 2.85, 9.12, 2.85, ORANGE)
picture(s4, f"{IMG}/app-preview.jpg", 5.35, 4.15, h=2.6)
picture(s4, f"{IMG}/app-solve.jpg", 9.6, 4.15, h=2.6)

# ── 5. Architecture + technology stack ───────────────────────────────────────
s5 = S[4]
remove(shape_named(s5, "TextBox 1"))
_old = shape_named(s5, "TextBox 22")
ts = s5.shapes.add_textbox(_old.left, _old.top, _old.width, _old.height)
ts.text_frame.word_wrap = True
remove(_old)
stack = [("Front-end: ", "React 18, Vite, Tailwind CSS, Reveal.js (web deck), installable PWA"),
         ("Back-end: ", "Python 3.12, FastAPI, background job queue, SQLite"),
         ("Document processing: ", "python-pptx, PyMuPDF, LibreOffice (PPTX→PDF), Tesseract OCR, python-docx"),
         ("AI / NLP: ", "Google Gemini (5-key pool), Groq, NVIDIA NIM — router with failover; rule-based offline engine"),
         ("Maths & labs: ", "SymPy (exact solvers), vanilla JS lab engine, SVG illustrations"),
         ("Quality: ", "pytest (750+ tests), layout audit, gold-set evaluation")]
for i, (k, v) in enumerate(stack):
    para = ts.text_frame.paragraphs[0] if i == 0 else ts.text_frame.add_paragraph()
    para.space_after = Pt(6)
    for rt, b, c in (("●  ", False, ORANGE), (k, True, ORANGE), (v, False, INK)):
        r = para.add_run()
        r.text, r.font.bold, r.font.size, r.font.name = rt, b, Pt(12.5), FONT
        r.font.color.rgb = c
ts.height = Inches(5.6)
# Input → Processing → Output, drawn with editable shapes
text(s5, 0.25, 0.8, 8.2, 0.4, [[("Input", {"bold": True, "color": RGBColor(0x16, 0x84, 0x5B)}), (" → Processing (workflow) → ", {"color": RGBColor(0x6B, 0x3F, 0xA0)}),
                                 ("Output", {"bold": True, "color": RGBColor(0x16, 0x84, 0x5B)})]], size=14, align=PP_ALIGN.CENTER)
GREEN, PURPLE, OUTC = RGBColor(0xDC, 0xF3, 0xE8), RGBColor(0xEC, 0xE6, 0xF7), RGBColor(0xFF, 0xEB, 0xDD)
ins = [("PPTX deck", ""), ("Slide PDF", ""), ("Word / notes", ""), ("Typed topic", "")]
for i, (a, _) in enumerate(ins):
    box(s5, 0.25, 1.45 + i * 0.75, 1.45, 0.58, GREEN, label=a, size=11, bold=True)
steps = [("Reader", "PDF/PPTX parse · OCR · figures"), ("Planner", "split · merge · agenda"), ("Decision engine", "visual family per slide"),
         ("AI assist", "titles · explanations (key)"), ("Illustrations", "LLM SVG / own figure / offline"), ("Labs & explainers", "solvers · quizzes")]
for i, (a, b) in enumerate(steps):
    col, row = i % 2, i // 2
    box(s5, 2.15 + col * 2.2, 1.45 + row * 1.05, 2.05, 0.85, PURPLE, label=[a, b], size=11.5, bold=True)
outs = [("Editable PPTX", ""), ("Interactive web deck", ""), ("Study pack & quizzes", ""), ("Share link · tutor", "")]
for i, (a, _) in enumerate(outs):
    box(s5, 6.75, 1.45 + i * 0.75, 1.65, 0.58, OUTC, label=a, size=11, bold=True)
arrow(s5, 1.72, 2.6, 2.12, 2.6)
arrow(s5, 6.43, 2.6, 6.72, 2.6)
box(s5, 2.15, 4.75, 4.25, 0.55, SOFT, line=BLUE, label=["Layout engine + audit: text measured glyph by glyph — no overflow, no broken words"], size=10.5)
box(s5, 0.25, 5.5, 8.15, 0.85, SOFT, line=ORANGE,
    label=["FastAPI service · job queue · deck library · OTP sign-in · AI router (Gemini ×5 → Groq → NVIDIA → offline rules)",
           "React front-end: Create · Generate (live progress) · Preview · Present · Solve · Export · Settings"], size=11)

# ── 6. Use cases ─────────────────────────────────────────────────────────────
s6 = S[5]
retitle(s6, "TextBox 17", "USE CASES", "   Where Learnova is used")
cases = [("Faculty before a lecture", "Uploads last year's PPT; gets a redesigned, illustrated deck with quizzes in under a minute, fully editable in PowerPoint."),
         ("Students revising for exams", "Open the web deck, flip key-term cards, solve checkpoint questions and step through solved problems at their own pace."),
         ("Lab-heavy subjects", "IPCV / NLP / ML topics get hands-on labs: region growing, split & merge, CYK, Viterbi, Naive Bayes WSD, HMM tagging."),
         ("Colleges without paid AI", "Everything works offline with rule-based logic; AI keys only improve titles, explanations and diagrams."),
         ("Remote and flipped classes", "Share a view-only link; the deck tutor answers questions from the deck's own content."),
         ("Accessibility", "Large readable text, no broken words, plain-language explanations and alt text for every illustration.")]
for i, (h, b) in enumerate(cases):
    col, row = i % 3, i // 3
    x, y = 0.55 + col * 4.15, 1.5 + row * 2.75
    box(s6, x, y, 3.95, 2.5, SOFT, line=RGBColor(0xE2, 0xE6, 0xEE))
    text(s6, x + 0.2, y + 0.18, 3.55, 2.2, [(h, {"bold": True, "color": ORANGE, "size": 16, "font": HEAD, "after": 8}), (b, {"size": 13})])

# ── 7. Implementation ────────────────────────────────────────────────────────
s7 = S[6]
retitle(s7, "TextBox 17", "Implementation", "   Modules developed and integrated")
mods = [("Input readers", "PPTX via LibreOffice → slide reader; PDF page reader with OCR; DOCX; typed topics", "Done"),
        ("Content Decision Engine", "27 detectors, 20+ visual families, reason for every choice", "Done"),
        ("PowerPoint + web builders", "Native editable shapes; Reveal.js deck with click-by-click reveals", "Done"),
        ("Illustrations", "AI SVG diagram per slide (5 Gemini keys) · source figure · offline scenes; HTML link", "Done"),
        ("Quizzes & explainers", "Checkpoint MCQs; exact solvers incl. Bayes, bigram, Naive Bayes, Viterbi, CYK", "Done"),
        ("Interactive labs", "7 built-in (incl. Region Growing, Split & Merge) + generated labs per topic", "Done"),
        ("Platform", "FastAPI jobs, OTP login, library, share links, study pack, PWA front-end", "Done"),
        ("Evaluation & papers", "Gold-set accuracy, layout audit, fact retention; IEEE + Springer papers", "Done"),
        ("Classroom study", "Controlled study with students on learning outcomes", "Planned")]
tb = s7.shapes.add_table(len(mods) + 1, 3, Inches(0.55), Inches(1.4), Inches(12.2), Inches(5.3)).table
for c, w in zip(tb.columns, (3.0, 7.6, 1.6)):
    c.width = Inches(w)
for j, h in enumerate(("Module", "What is implemented", "Status")):
    set_cell(tb.cell(0, j), h, 12.5, True, RGBColor(255, 255, 255))
    tb.cell(0, j).fill.solid()
    tb.cell(0, j).fill.fore_color.rgb = BLUE
for i, row in enumerate(mods, 1):
    for j, v in enumerate(row):
        set_cell(tb.cell(i, j), v, 12, j == 0, RGBColor(0x16, 0x84, 0x5B) if (j == 2 and v == "Done") else (ORANGE if j == 2 else INK))

# ── 8. Novelty (new) ─────────────────────────────────────────────────────────
s8 = new_slide()
heading(s8, "Novelty — what Learnova does that others do not")
feat = ["Redesigns an existing deck (not only new ones)", "Keeps every source point (fact check)", "Keeps teacher's figures, OCR of picture slides",
        "Illustration on every slide + HTML link", "Exact step-by-step solved problems", "Interactive labs for hard topics", "Works offline without AI keys",
        "Explains every design choice"]
tools = ["Learnova", "Gamma", "Copilot PPT", "Gemini Slides", "Canva"]
marks = [["✔", "✘", "~", "~", "~"], ["✔", "✘", "✘", "✘", "✘"], ["✔", "✘", "~", "✘", "✘"], ["✔", "~", "~", "~", "~"],
         ["✔", "✘", "✘", "✘", "✘"], ["✔", "✘", "✘", "✘", "✘"], ["✔", "✘", "✘", "✘", "✘"], ["✔", "✘", "✘", "✘", "✘"]]
tb = s8.shapes.add_table(len(feat) + 1, len(tools) + 1, Inches(0.55), Inches(1.45), Inches(12.2), Inches(4.7)).table
tb.columns[0].width = Inches(5.2)
for j in range(1, len(tools) + 1):
    tb.columns[j].width = Inches(1.4)
set_cell(tb.cell(0, 0), "Capability", 12.5, True, RGBColor(255, 255, 255))
for j, t_ in enumerate(tools, 1):
    set_cell(tb.cell(0, j), t_, 12, True, RGBColor(255, 255, 255))
for i, f in enumerate(feat, 1):
    set_cell(tb.cell(i, 0), f, 12.5)
    for j, m in enumerate(marks[i - 1], 1):
        set_cell(tb.cell(i, j), m, 15, True, RGBColor(0x16, 0x84, 0x5B) if m == "✔" else (RGBColor(0xC0, 0x30, 0x30) if m == "✘" else MUTED))
        tb.cell(i, j).text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
text(s8, 0.55, 6.3, 12.2, 0.5, ["✔ supported   ~ partly (e.g. generic stock images, or only with a paid plan / internet)   ✘ not supported — based on the team's comparison of each tool's documented features (Oct 2026)."],
     size=11, color=MUTED)

# ── 9. Results (new) ─────────────────────────────────────────────────────────
s9 = new_slide()
heading(s9, "Results on real course material")
stats = [("97%", "visual chosen correctly", "101 gold slides, 3 held-out sets"), ("98–100%", "facts kept", "6 real decks, 36–216 pages"),
         ("0", "broken words / overflow", "layout audit, all decks"), ("26 / 26", "problems solved correctly", "held-out explainer benchmark"),
         ("< 1 ms", "decision per slide", "rule-based engine"), ("~35 s", "216-page PDF → full deck", "without any API key")]
for i, (big, lab_, sub) in enumerate(stats):
    col, row = i % 3, i // 3
    x, y = 0.5 + col * 2.75, 1.45 + row * 2.0
    box(s9, x, y, 2.55, 1.8, SOFT, line=RGBColor(0xE2, 0xE6, 0xEE))
    text(s9, x + 0.1, y + 0.12, 2.35, 1.6, [(big, {"bold": True, "size": 26, "color": ORANGE, "font": HEAD, "align": PP_ALIGN.CENTER, "after": 2}),
                                             (lab_, {"bold": True, "size": 12.5, "align": PP_ALIGN.CENTER, "after": 2}),
                                             (sub, {"size": 10.5, "color": MUTED, "align": PP_ALIGN.CENTER})])
text(s9, 8.85, 1.35, 4.2, 0.35, [[("AI-drawn diagrams (one per slide)", {"bold": True, "size": 12, "color": MUTED})]])
picture(s9, f"{IMG}/art_sheet.png", 8.85, 1.7, w=4.25)
text(s9, 8.85, 3.15, 4.2, 0.35, [[("Region Splitting & Merging lab (IPCV)", {"bold": True, "size": 12, "color": MUTED})]])
picture(s9, f"{IMG}/lab_split.png", 8.85, 3.5, w=4.25)
text(s9, 0.5, 5.6, 8.1, 1.2, [
    "Tested on: NLP Module 4 (36 pp), Module 5 (95 pp), Syntax analysis (216 pp), WSD slides and notes, Lesk algorithm notes, "
    "ML Bias & Variance (PPTX, 28 slides) and Linear Regression (PPTX, 63 slides).",
    "Linear Regression PPTX: earlier parser kept 23 of 63 slides; the new reader keeps all of them with the original derivations as figures."], size=12)

# ── 10. Future scope (new) ───────────────────────────────────────────────────
s10 = new_slide()
heading(s10, "Future scope and conclusion")
text(s10, 0.55, 1.45, 6.0, 5.2, [
    [("Future scope", {"bold": True, "color": ORANGE, "size": 18, "font": HEAD})],
    "•  Classroom study with students to measure learning gains.",
    "•  Narrated video export of each deck (text-to-speech).",
    "•  More labs: CNN filters, decision trees, gradient descent.",
    "•  Teacher review mode: approve or edit AI suggestions slide by slide.",
    "•  Hindi and regional-language decks.",
    "•  College LMS integration (Moodle / Google Classroom).",
], size=14)
text(s10, 6.85, 1.45, 6.0, 5.2, [
    [("Conclusion", {"bold": True, "color": ORANGE, "size": 18, "font": HEAD})],
    "Learnova turns the decks teachers already have into clear, illustrated and interactive lessons without losing their content.",
    "It is faithful by design (every point kept and checked), visual on every slide, interactive through quizzes, solved problems and labs, "
    "and dependable — it works with AI keys and without them.",
    "Two research papers (IEEE conference format and Springer LNCS) describe the methods and the evaluation.",
], size=14)


# ── Proposed solution (new) ──────────────────────────────────────────────────
s_sol = new_slide()
heading(s_sol, "Proposed Solution — Learnova", "One upload in, a complete redesigned teaching kit out — faithful to the teacher's content")
pillars = [
    ("1  Read", ["PPTX, slide PDF, Word notes or a typed topic", "Titles, bullet levels, tables, figures recovered", "OCR for picture-only slides; logos, footers, page numbers removed", "Original colour palette carried into the new design"]),
    ("2  Redesign", ["Visual chosen per slide: process, timeline, comparison, definition, chart, cards …", "Assertion titles that state the point", "Overloaded slides split, thin slides merged", "Text fitted glyph by glyph — never overflows or breaks words"]),
    ("3  Illustrate", ["An illustration on every topic slide", "AI-written diagram of the slide's idea (Gemini, 5-key pool)", "Teacher's own figure kept beside the text", "Offline illustrator when no key — each linked as an HTML page"]),
    ("4  Engage", ["Checkpoint quizzes from the content", "Exact step-by-step solved problems (Bayes, Viterbi, CYK …)", "Interactive labs: Region Growing, Split & Merge, NLP labs", "Flip cards, matching activity, deck tutor"]),
    ("5  Deliver", ["Editable PowerPoint with native shapes", "Interactive web deck (Reveal.js)", "Study pack: flashcards, Anki, quiz bank, cheat sheet", "Share link, presenter console, mobile app (PWA)"]),
]
for i, (h, items) in enumerate(pillars):
    x = 0.4 + i * 2.52
    box(s_sol, x, 1.6, 2.38, 0.55, ORANGE, label=h, size=14, bold=True, color=RGBColor(255, 255, 255))
    box(s_sol, x, 2.2, 2.38, 3.55, SOFT, line=RGBColor(0xE2, 0xE6, 0xEE))
    text(s_sol, x + 0.08, 2.3, 2.22, 3.4, [(f"• {t}", {"size": 11.5, "after": 7}) for t in items])
box(s_sol, 0.4, 5.92, 12.52, 1.0, RGBColor(0xFF, 0xF3, 0xEA), line=ORANGE)
text(s_sol, 0.6, 5.98, 12.1, 0.9, [
    [("Innovation & uniqueness:  ", {"bold": True, "color": ORANGE}),
     ("redesigns the deck a teacher already has instead of generating a new one; every structural decision is an explainable rule; "
      "AI is used only where its output can be checked (titles, explanations, diagrams, labs) and the system keeps working fully offline.", {})]], size=13)

# ── Technical approach / methodology (new) ───────────────────────────────────
s_tech = new_slide()
heading(s_tech, "Technical Approach & Methodology", "Processing workflow with the algorithm used at each stage")
stages = [("Upload & convert", "PPTX → PDF (LibreOffice), DOCX, typed text → Markdown IR"),
          ("Slide reader", "Line geometry; furniture = text repeated on ≥ max(3, 0.3n) pages; bullet level = nearest x-anchor"),
          ("OCR decision", "Graphic ratio γ = |ink ∖ text| / |ink|; use OCR only if conf ≥ 62, γ ≤ 0.42, little symbol debris"),
          ("Planner", "Split slides over the density budget; merge thin parts; agenda, glossary, quizzes"),
          ("Decision engine", "27 detectors → (family, confidence, data, reason); d* = argmax confidence after exclusion rules"),
          ("AI assist (optional)", "Assertion titles, explanations, key terms — accepted only if grounded in the slide's words"),
          ("Illustrations", "LLM writes SVG → validated (safe elements, ≥ 6 shapes, renders) → cached; else offline scene"),
          ("Layout & build", "Font s* = largest size that fits; word scale σ = min(1, W / w(longest word)); PPTX + web deck"),
          ("Audit", "Overflow, broken words, sparse slides; fact retention R = |F_src ∩ F_deck| / |F_src|")]
for i, (h, b) in enumerate(stages):
    col, row = i % 3, i // 3
    x, y = 0.4 + col * 4.2, 1.6 + row * 1.75
    box(s_tech, x, y, 4.0, 1.55, SOFT, line=RGBColor(0xE2, 0xE6, 0xEE))
    box(s_tech, x + 0.12, y + 0.14, 0.42, 0.42, ORANGE, shape=MSO_SHAPE.OVAL, label=str(i + 1), size=12, bold=True, color=RGBColor(255, 255, 255))
    text(s_tech, x + 0.62, y + 0.1, 3.3, 1.4, [(h, {"bold": True, "size": 13.5, "font": HEAD, "after": 3}), (b, {"size": 11.5, "color": MUTED})])

# ── Prototype screens (new) ──────────────────────────────────────────────────
s_proto = new_slide()
heading(s_proto, "Prototype — working application screens")
shots = [("app-preview.jpg", "Deck preview: every slide with the visual chosen and why"), ("web_deck.png", "Interactive web deck with AI diagram"),
         ("app-solve.jpg", "Solve step by step: beginner-level walkthrough"), ("explainer-viterbi.png", "Viterbi explainer, computed exactly"),
         ("lab_split.png", "Region Splitting & Merging lab (IPCV)"), ("mobile-home.jpg", "Phone layout / installable app")]
for i, (f, cap) in enumerate(shots):
    col, row = i % 3, i // 3
    x, y = 0.4 + col * 4.2, 1.45 + row * 2.85
    try:
        from PIL import Image as _Im

        iw, ih = _Im.open(f"{IMG}/{f}").size
    except Exception:
        continue
    bw, bh = 4.0, 2.35
    sc = min(bw / iw, bh / ih)
    w_, h_ = iw * sc, ih * sc
    picture(s_proto, f"{IMG}/{f}", x + (bw - w_) / 2, y + (bh - h_) / 2, w=w_)
    text(s_proto, x, y + 2.38, 4.0, 0.4, [(cap, {"size": 11, "color": MUTED, "align": PP_ALIGN.CENTER})])


# ── Before vs after: problems faced → what is achieved (new) ─────────────────
s_ba0 = new_slide()
heading(s_ba0, "Before vs After — problems faced → what is achieved")
pf = [("Text-heavy slides", "Walls of bullets, 100+ words on one slide; students skim and miss points",
       "One idea per slide drawn as a visual (process, timeline, table, definition, cards); split at a readable density"),
      ("Pictures of equations & diagrams", "Content locked in images; nothing searchable; tools drop these slides",
       "Every picture slide kept as a figure; OCR only when the text is reliable; derivations shown full size"),
      ("Untitled / generic titles", "“Slide 9”, “Hypothesis (2/5)” — the title says nothing",
       "Assertion titles that state the point; split parts named after what they cover"),
      ("No visuals for many topics", "Plain text with no diagram to explain the idea",
       "An illustration on every topic slide: AI-drawn diagram, teacher's figure or offline scene — with an HTML link"),
      ("No interaction", "Students only read; solved problems shown as finished tables",
       "Checkpoint quizzes, exact step-by-step explainers, labs (Region Growing, Split & Merge, CYK, Viterbi, NB-WSD)"),
      ("AI tools change the content", "Generators paraphrase, merge items, invent facts; nothing can be checked",
       "Content kept verbatim and checked: 98–100% of facts retained, explanation for every design choice"),
      ("Redesign takes hours", "Faculty spend an evening per lecture; needs design skill",
       "Upload → finished PPTX + web deck in ~10–60 s; fully editable"),
      ("Needs internet / paid AI", "Cloud-only tools, subscriptions, quotas",
       "Works offline; free API keys used only to improve; automatic fallback when a key runs out")]
tb = s_ba0.shapes.add_table(len(pf) + 1, 3, Inches(0.4), Inches(1.3), Inches(12.5), Inches(5.65)).table
for c, w in zip(tb.columns, (2.7, 4.4, 5.4)):
    c.width = Inches(w)
for j, (h, col) in enumerate((("Area", BLUE), ("BEFORE — problem faced", RGBColor(0xC0, 0x30, 0x30)), ("AFTER — with Learnova", RGBColor(0x16, 0x84, 0x5B)))):
    set_cell(tb.cell(0, j), h, 12.5, True, RGBColor(255, 255, 255))
    tb.cell(0, j).fill.solid()
    tb.cell(0, j).fill.fore_color.rgb = col
for i, (a, b, c_) in enumerate(pf, 1):
    set_cell(tb.cell(i, 0), a, 12, True, INK)
    set_cell(tb.cell(i, 1), "✘  " + b, 11.5, False, RGBColor(0x8A, 0x1F, 0x1F))
    set_cell(tb.cell(i, 2), "✔  " + c_, 11.5, False, RGBColor(0x10, 0x5E, 0x40))
    for j, col in ((1, RGBColor(0xFD, 0xEE, 0xEC)), (2, RGBColor(0xE8, 0xF6, 0xEF))):
        tb.cell(i, j).fill.solid()
        tb.cell(i, j).fill.fore_color.rgb = col

# ── Before vs after: slides (new) ────────────────────────────────────────────
s_ba1 = new_slide()
heading(s_ba1, "Before vs After — the same slides, redesigned", "Left: original lecture slide · Right: slide generated by Learnova from it")
pairs = [("pair1", "ML · Bias and variance (PPTX)", "Untitled bullet slide → assertion title, full definitions, the teacher's diagram beside the text, key takeaway and key terms."),
         ("pair2", "ML · Linear regression (PPTX)", "Picture-only slide of plots → kept as a figure with its explanation as text; title states the learning-rate trade-off."),
         ("pair3", "NLP · Word sense disambiguation (PDF)", "Dense bullet list → structured cards with an AI-drawn diagram, quiz and a Naive Bayes WSD lab link.")]
for i, (k, cap, what) in enumerate(pairs):
    y = 1.5 + i * 1.83
    text(s_ba1, 0.35, y + 0.35, 1.75, 1.2, [(cap, {"bold": True, "size": 12, "color": ORANGE})])
    for j, side in enumerate(("before", "after")):
        f = f"{IMG}/{k}_{side}.png"
        if pathlib.Path(f).is_file():
            picture(s_ba1, f, 2.15 + j * 3.6, y, h=1.75)
    arrow(s_ba1, 5.33, y + 0.87, 5.72, y + 0.87, ORANGE)
    box(s_ba1, 9.35, y, 3.6, 1.75, RGBColor(0xE8, 0xF6, 0xEF), line=RGBColor(0x16, 0x84, 0x5B))
    text(s_ba1, 9.45, y + 0.06, 3.4, 1.65, [("What changed", {"bold": True, "size": 12, "color": RGBColor(0x16, 0x84, 0x5B), "after": 3}), (what, {"size": 11.5})])

# ── Before vs after: measured (new) ──────────────────────────────────────────
s_ba2 = new_slide()
heading(s_ba2, "Before vs After — measured on our test decks", "Original deck → Learnova deck (offline rules + Gemini keys)")
names = {"ml1": "ML Bias & Variance (PPTX)", "ml2": "ML Linear Regression (PPTX)", "wsd": "WSD lecture slides (PDF)", "wsddoc": "WSD notes (DOCX)",
         "lesk": "Lesk algorithm (DOCX)", "m4": "NLP Module 4 (PDF)", "m5": "NLP Module 5 (PDF)"}
cols = ["Deck", "Slides", "Untitled", "Slides with picture", "Visual structures", "Quizzes", "Labs", "Linked illustrations", "Fact retention"]
rows = [k for k in names if k in BA]
tb = s_ba2.shapes.add_table(len(rows) + 1, len(cols), Inches(0.4), Inches(1.5), Inches(12.5), Inches(0.4 * (len(rows) + 1))).table
for c, w in zip(tb.columns, (3.0, 1.1, 1.05, 1.35, 1.35, 1.0, 0.9, 1.4, 1.35)):
    c.width = Inches(w)
for j, h in enumerate(cols):
    set_cell(tb.cell(0, j), h, 11, True, RGBColor(255, 255, 255))
    tb.cell(0, j).fill.solid()
    tb.cell(0, j).fill.fore_color.rgb = BLUE
for i, k in enumerate(rows, 1):
    b, a = BA[k]["before"], BA[k]["after"]
    vals = [names[k], f"{b['slides']} → {a['slides']}", f"{b['untitled']} → 0", f"{b['with_picture']} → {a['with_picture']}",
            f"0 → {a['visual_structures']}", f"0 → {a['quizzes']}", f"0 → {a['labs']}", f"0 → {a['linked_illustrations']}", f"{BA[k].get('retention', '—')}"]
    for j, v in enumerate(vals):
        set_cell(tb.cell(i, j), v, 11, j == 0)
tot = {f: sum(BA[k]["after"][f] for k in rows) for f in ("visual_structures", "quizzes", "labs", "linked_illustrations", "with_picture", "slides")}
untitled = sum(BA[k]["before"]["untitled"] for k in rows)
y0 = 1.6 + 0.4 * (len(rows) + 1) + 0.15
cards = [(f"{untitled} → 0", "untitled slides"), (f"{tot['visual_structures']}", "slides drawn as a visual"), (f"{tot['quizzes']}", "checkpoint quizzes added"),
         (f"{tot['labs']}", "interactive lab links"), (f"{tot['linked_illustrations']}", "illustrations with HTML link"), ("98–100%", "facts kept")]
cw = (12.5 - 5 * 0.15) / 6
for i, (big, lab_) in enumerate(cards):
    x = 0.4 + i * (cw + 0.15)
    box(s_ba2, x, y0, cw, 6.95 - y0, RGBColor(0xFF, 0xF3, 0xEA), line=ORANGE)
    text(s_ba2, x + 0.05, y0 + 0.08, cw - 0.1, 6.95 - y0 - 0.1, [(big, {"bold": True, "size": 22, "color": ORANGE, "font": HEAD, "align": PP_ALIGN.CENTER, "after": 2}),
                                                               (lab_, {"size": 11.5, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)

# ── Feasibility & viability (new) ────────────────────────────────────────────
s_feas = new_slide()
heading(s_feas, "Feasibility & Viability", "Challenges we met, how they are handled, and what it costs to run")
risks = [("Real lecture PDFs are messy", "Symbol-font bullets, glued titles, picture-only slides, repeated logos", "Page reader with OCR decision, title segmentation by dynamic programming, furniture removal"),
         ("AI errors / hallucination", "LLMs paraphrase, drop items, miscalculate", "AI output accepted only if grounded in the slide; numbers computed by SymPy; source text kept verbatim"),
         ("API quota and cost", "Free tiers limit requests; keys get exhausted", "5-key Gemini pool with per-key pacing, Groq/NVIDIA failover, full offline mode, response cache"),
         ("Layout breaking in PowerPoint", "Overflow, words split across lines, tiny fonts", "Glyph-measured fitting, minimum 11 pt then continuation slide, automatic layout audit"),
         ("Speed for large decks", "216-page decks, many diagrams and labs", "Parallel generation (labs, diagrams), caching by content hash: 216 pp in ~35 s offline"),
         ("Unsafe generated code", "AI-written labs and SVG could contain scripts", "Whitelisted SVG elements; lab JS checked with node --check, no network or storage APIs")]
tb = s_feas.shapes.add_table(len(risks) + 1, 3, Inches(0.4), Inches(1.5), Inches(12.5), Inches(4.6)).table
for c, w in zip(tb.columns, (3.0, 4.2, 5.3)):
    c.width = Inches(w)
for j, h in enumerate(("Challenge", "Why it is hard", "How Learnova handles it")):
    set_cell(tb.cell(0, j), h, 12, True, RGBColor(255, 255, 255))
    tb.cell(0, j).fill.solid()
    tb.cell(0, j).fill.fore_color.rgb = BLUE
for i, row in enumerate(risks, 1):
    for j, v in enumerate(row):
        set_cell(tb.cell(i, j), v, 11.5, j == 0)
text(s_feas, 0.4, 6.2, 12.5, 0.8, [
    [("Viability:  ", {"bold": True, "color": ORANGE}), ("runs on a college laptop or one small server (Python + LibreOffice + Tesseract); free-tier AI keys are optional; "
     "open formats (PPTX, HTML) need no special viewer; freemium model possible — free offline tier, paid AI diagrams and LMS integration.", {})]], size=12.5)

# ── Impact & benefits (new) ──────────────────────────────────────────────────
s_imp = new_slide()
heading(s_imp, "Impact & Benefits")
groups = [("Students", ["Clear slides: one idea per slide with a picture", "Solve problems step by step with reasons", "Practice with quizzes, labs and flashcards", "Revise on phone, offline"]),
          ("Faculty", ["Old decks modernised in about a minute", "Content kept exactly — nothing to re-check", "Editable PowerPoint, ready to present", "Quizzes and labs without extra preparation"]),
          ("Institution", ["Consistent, accessible course material", "No paid AI licence required", "Supports flipped and remote classes", "Reusable labs library across subjects"]),
          ("Society (SDG 4)", ["Quality education with low-cost tools", "Works where internet is unreliable", "Plain-language explanations help first-generation learners", "Open web formats, easy to share"])]
for i, (h, items) in enumerate(groups):
    x = 0.4 + i * 3.17
    box(s_imp, x, 1.45, 3.0, 0.6, BLUE, label=h, size=15, bold=True, color=RGBColor(255, 255, 255))
    box(s_imp, x, 2.1, 3.0, 3.3, SOFT, line=RGBColor(0xE2, 0xE6, 0xEE))
    text(s_imp, x + 0.12, 2.22, 2.78, 3.1, [(f"✔  {t}", {"size": 12.5, "after": 9}) for t in items])
box(s_imp, 0.4, 5.6, 12.68, 1.3, RGBColor(0xFF, 0xF3, 0xEA), line=ORANGE)
text(s_imp, 0.6, 5.68, 12.3, 1.15, [
    [("Measured so far:  ", {"bold": True, "color": ORANGE}),
     ("on seven real course decks every slide was kept, untitled slides went to zero, every topic slide received an illustration, and quizzes and labs were added "
      "automatically. A classroom study on learning outcomes is planned for the next semester.", {})]], size=13)

# ── references last ──────────────────────────────────────────────────────────
s_ref = S[7]
r2 = shape_named(s_ref, "TextBox 2")
r2.top, r2.height = Inches(0.85), Inches(4.6)
r2.text_frame.clear()
refs = ["[1] Y. Hu and X. Wan, “PPSGen: Learning-based presentation slides generation for academic papers,” IEEE Trans. Knowl. Data Eng., vol. 27, no. 4, pp. 1085–1097, 2015.",
        "[2] T.-J. Fu, W. Y. Wang, D. McDuff and Y. Song, “DOC2PPT: Automatic presentation slides generation from scientific documents,” in Proc. AAAI, vol. 36, pp. 634–642, 2022.",
        "[3] E. Sun, Y. Hou, D. Wang, Y. Zhang and N. X. R. Wang, “D2S: Document-to-slide generation via query-based text summarization,” in Proc. NAACL, pp. 1405–1418, 2021.",
        "[4] J. K. Garner and M. P. Alley, “How the design of presentation slides affects audience comprehension,” Int. J. Eng. Educ., vol. 29, no. 6, pp. 1564–1579, 2013.",
        "[5] R. E. Mayer, Multimedia Learning, 2nd ed. Cambridge University Press, 2009.",
        "[6] J. Sweller, “Cognitive load during problem solving: Effects on learning,” Cognitive Science, vol. 12, no. 2, pp. 257–285, 1988.",
        "[7] J. Maynez, S. Narayan, B. Bohnet and R. McDonald, “On faithfulness and factuality in abstractive summarization,” in Proc. ACL, pp. 1906–1919, 2020.",
        "[8] R. Smith, “An overview of the Tesseract OCR engine,” in Proc. ICDAR, pp. 629–633, 2007.",
        "[9] D. Jurafsky and J. H. Martin, Speech and Language Processing, 3rd ed. draft, 2025."]
p = r2.text_frame.paragraphs[0]
r = p.add_run()
r.text, r.font.bold, r.font.size, r.font.name = "Ref. Papers:", True, Pt(14), FONT
for ref in refs:
    para = r2.text_frame.add_paragraph()
    para.space_after = Pt(3)
    rr = para.add_run()
    rr.text, rr.font.size, rr.font.name = ref, Pt(11.5), FONT
    rr.font.color.rgb = INK
w3 = shape_named(s_ref, "TextBox 3")
w3.top = Inches(5.55)
text(s_ref, 0.45, 5.95, 12.0, 1.2, ["Gamma — https://gamma.app · Microsoft Copilot in PowerPoint · Google Gemini in Slides · Canva Magic Design — accessed Oct 2026",
                                    "Reveal.js — https://revealjs.com · python-pptx — https://python-pptx.readthedocs.io · PyMuPDF — https://pymupdf.readthedocs.io",
                                    "Project repository — https://github.com/SDP42/LearnovaV2"], size=11.5)
# final order (SIH flow) and page numbers
order = [S[0], S[1], s_sol, S[2], s_tech, S[3], s_proto, S[4], s_ba0, s_ba1, s_ba2, S[5], S[6], s_feas, s_imp, s8, s9, s10, s_ref]
lst = prs.slides._sldIdLst
by_part = {prs.part.related_part(e.rId): e for e in list(lst)}
for e in list(lst):
    lst.remove(e)
for sl in order:
    lst.append(by_part[sl.part])
for n, sl in enumerate(order, 1):
    for sh in sl.shapes:
        if sh.name == "Slide Number Placeholder 5" and sh.has_text_frame:
            r0 = sh.text_frame.paragraphs[0].runs
            if r0:
                r0[0].text = str(n)

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
