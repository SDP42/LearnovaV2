"""
Learnova review deck written onto the team's SIH (SAIL) deck: every shape, colour and position of that deck is kept; only
its text and its project-specific pictures are replaced with Learnova content.

    python scripts/research/build_sail_style_review.py <sail.pptx> <assets dir> <before_after.json> <out.pptx>
"""
import copy
import io
import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import qrcode  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from learnova.visuals.icons import icon_png  # noqa: E402

SRC, IMG, BA_PATH, OUT = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3], sys.argv[4]
BA = json.load(open(BA_PATH))
REPO = "https://github.com/SDP42/LearnovaV2"
prs = Presentation(SRC)
SL = list(prs.slides)
WHITE, INK, MUTED = RGBColor(255, 255, 255), RGBColor(0x17, 0x21, 0x31), RGBColor(0x55, 0x5F, 0x6D)


# ── helpers ──────────────────────────────────────────────────────────────────
def walk(shapes):
    for sh in shapes:
        if sh.shape_type == 6:
            yield from walk(sh.shapes)
        else:
            yield sh


def by_id(slide):
    return {sh.shape_id: sh for sh in walk(slide.shapes)}


def set_text(sh, lines):
    """Replace a text box's paragraphs, keeping each paragraph's formatting. A line may be (label, body): the label takes the
    first run's style and the body the second run's (or the first, if the paragraph had one run)."""
    tf = sh.text_frame
    paras = list(tf.paragraphs)
    protos = [copy.deepcopy(p._p) for p in paras if p.runs] or [copy.deepcopy(paras[0]._p)]
    body = tf._txBody
    for p in paras:
        body.remove(p._p)
    for i, line in enumerate(lines):
        proto = protos[min(i, len(protos) - 1)] if i < len(protos) else protos[-1]
        p_el = copy.deepcopy(proto)
        runs = p_el.findall(qn("a:r"))
        for r in runs[2:]:
            p_el.remove(r)
        for br in p_el.findall(qn("a:br")):
            p_el.remove(br)
        label, rest = (line if isinstance(line, tuple) else (None, line))
        if not runs:
            r = p_el.makeelement(qn("a:r"), {})
            r.append(r.makeelement(qn("a:t"), {}))
            p_el.append(r)
            runs = [r]
        if label is None:
            runs[0].find(qn("a:t")).text = rest
            if len(runs) > 1:
                p_el.remove(runs[1])
        else:
            runs[0].find(qn("a:t")).text = label
            if len(runs) > 1:
                runs[1].find(qn("a:t")).text = rest
            else:
                r2 = copy.deepcopy(runs[0])
                rpr = r2.find(qn("a:rPr"))
                if rpr is not None:
                    rpr.set("b", "0")
                r2.find(qn("a:t")).text = rest
                p_el.append(r2)
        end = p_el.find(qn("a:endParaRPr"))
        if end is not None:
            p_el.remove(end)
            p_el.append(end)
        body.append(p_el)


def put(slide, mapping):
    ids = by_id(slide)
    for sid, lines in mapping.items():
        sh = ids.get(sid)
        if sh is None or not sh.has_text_frame:
            print("missing", sid)
            continue
        set_text(sh, lines if isinstance(lines, list) else [lines])


def replace_pic(slide, sid, png_or_path, fit=True):
    ids = by_id(slide)
    pic = ids[sid]
    x, y, w, h = pic.left, pic.top, pic.width, pic.height
    src = png_or_path if isinstance(png_or_path, (bytes, bytearray)) else open(png_or_path, "rb").read()
    from PIL import Image

    iw, ih = Image.open(io.BytesIO(src)).size
    if fit:
        sc = min(w / iw, h / ih)
        nw, nh = int(iw * sc), int(ih * sc)
        x, y, w, h = x + (w - nw) // 2, y + (h - nh) // 2, nw, nh
    new = slide.shapes.add_picture(io.BytesIO(src), x, y, w, h)
    pic._element.addprevious(new._element)              # same z-order as the picture it replaces
    pic._element.getparent().remove(pic._element)
    return new


def remove(slide, sid):
    sh = by_id(slide).get(sid)
    if sh is not None:
        sh._element.getparent().remove(sh._element)


def qr_png(url):
    buf = io.BytesIO()
    qrcode.make(url, border=1).save(buf, "PNG")
    return buf.getvalue()


def rect(sl, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12, lw=0.75):
    s = sl.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
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


def tb(sl, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP):
    t = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = t.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.03)
    tf.margin_top = tf.margin_bottom = Inches(0.01)
    for i, (txt, size, bold, col) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text, r.font.size, r.font.bold, r.font.name = txt, Pt(size), bold, "Calibri"
        r.font.color.rgb = col
    return t


def arrow(sl, x1, y1, x2, y2, col, w=1.5):
    c = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = col
    c.line.width = Pt(w)
    from lxml import etree

    etree.SubElement(c.line._get_or_add_ln(), qn("a:tailEnd")).set("type", "triangle")


def badge(sl, name, x, y, d, col):
    rect(sl, x, y, d, d, col, shape=MSO_SHAPE.OVAL)
    sl.shapes.add_picture(io.BytesIO(icon_png(name, "#FFFFFF", 128)), Inches(x + d * 0.2), Inches(y + d * 0.2), Inches(d * 0.6), Inches(d * 0.6))


def fig_png(fn, w, h):
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(w, h))
    fn(ax)
    fig.tight_layout(pad=0.4)
    buf = io.BytesIO()
    fig.savefig(buf, dpi=220)
    plt.close(fig)
    return buf.getvalue()


NAMES = {"ml1": "ML-1", "ml2": "ML-2", "wsd": "WSD", "m4": "NLP-4", "m5": "NLP-5"}
KEYS = [k for k in NAMES if k in BA]
FOOT = "IPD Review · Learnova · AI&DS DJSCE"
TEAM = "Learnova"

# ── 1. Title page ────────────────────────────────────────────────────────────
s = SL[0]
put(s, {8: "IPD PROJECT REVIEW 2026",
        4: ["", "TITLE PAGE"],
        10: ["", "Project – Learnova", "Theme – EdTech · Generative AI", "Category – Software", "Group No. – 1 (AI & DS, DJSCE)",
             "Team – Swayam · Kawaljeet · Jeevesh · Rishit", "HoD – Dr. Pratik Kanani"]})
replace_pic(s, 5, f"{IMG}/art_sheet.png")
remove(s, 2)

# ── 2. Idea ──────────────────────────────────────────────────────────────────
s = SL[1]
untitled = sum(BA[k]["before"]["untitled"] for k in KEYS)
put(s, {15361: "LEARNOVA — IDEA",
        4: f"5 real lecture decks: {untitled} untitled slides · 0 diagrams · 0 quizzes",
        36: [("Proposed Solution:  ", "Teachers reuse old decks for years and students revise from them before every exam, yet most are walls of bullets with "
              "pictures of equations. Learnova takes the deck a teacher already has (PPTX, PDF, Word notes or a topic) and rebuilds it as an editable "
              "PowerPoint, an interactive web deck and a study pack — every point kept, plus a visual, an illustration, quizzes, solved steps and labs.")],
        40: [("Slide Reader: ", "every page read with titles, bullet levels, tables, figures; OCR only for picture slides."),
             ("Decision Engine: ", "27 detectors pick process, timeline, comparison, definition, chart or cards — with a reason."),
             ("Assertion Titles: ", "each title states the point of its slide; split parts are named, never “(2/5)”."),
             ("Illustrations: ", "AI-drawn diagram, teacher's figure or offline scene on every slide, linked as an HTML page."),
             ("Explainers & Labs: ", "beginner step-by-step solutions and hands-on labs for hard topics."),
             ("Outputs: ", "editable PPTX, web deck, study pack, share link, tutor.")],
        45: [("Redesign, not generate: ", "starts from the teacher's own deck; other tools start from a prompt."),
             ("Faithful by design: ", "source text kept verbatim; 98–100% of facts retained on real decks."),
             ("Explainable choices: ", "every visual decision shows its rule and confidence."),
             ("PSF metric + CLASS: ", "our own slide-fitness score and load-optimal slide splitting."),
             ("Two safety nets: ", "5 Gemini keys rotate; if all fail, offline rules finish the deck."),
             ("Verified AI output: ", "diagrams sanitised, labs code-checked, titles grounded in the slide."),
             ("Works offline: ", "no paid licence, runs on a college laptop.")],
        47: "PHASE 1 · Sep–Dec 2025", 48: "Research and design", 49: ["Literature + competitor study", "Problem, architecture, UI plan"],
        50: "PHASE 2 · Jan–Jul 2026", 51: "Build the platform", 52: ["Prototype V1 → Learnova V2", "Engine, builders, accounts"],
        53: "PHASE 3 · Aug–Oct 2026", 54: "Real decks, AI, research", 55: ["Reader + OCR, illustrations, labs", "AI key pool, papers, review"],
        58: "LIVE CODE", 59: ["github.com/SDP42/LearnovaV2", "Open source · 755 tests · demo decks"],
        2: TEAM, 7: FOOT})
pair = __import__("PIL.Image", fromlist=["Image"])
from PIL import Image, ImageDraw  # noqa: E402

b, a = Image.open(f"{IMG}/pair1_before.png").convert("RGB"), Image.open(f"{IMG}/pair1_after.png").convert("RGB")
W0 = 900
b = b.resize((W0, int(b.height * W0 / b.width)))
a = a.resize((W0, int(a.height * W0 / a.width)))
comb = Image.new("RGB", (W0, b.height + a.height + 120), "white")
d = ImageDraw.Draw(comb)
comb.paste(b, (0, 50))
comb.paste(a, (0, b.height + 120))
d.rectangle([0, 0, 220, 44], fill=(192, 48, 48))
d.text((14, 10), "BEFORE", fill="white")
d.rectangle([0, b.height + 66, 220, b.height + 110], fill=(22, 132, 91))
d.text((14, b.height + 76), "WITH LEARNOVA", fill="white")
d.polygon([(W0 / 2 - 30, b.height + 60), (W0 / 2 + 30, b.height + 60), (W0 / 2, b.height + 105)], fill=(242, 122, 46))
buf = io.BytesIO()
comb.save(buf, "PNG")
replace_pic(s, 43, buf.getvalue())
replace_pic(s, 60, qr_png(REPO))
remove(s, 11)

# ── 3. Technical approach: native architecture diagram in the picture's place ─
s = SL[2]
ids = by_id(s)
arch = ids[17410]
ax0, ay0 = Emu(arch.left).inches, Emu(arch.top).inches
remove(s, 17410)
remove(s, 12)
cols = [("INPUTS", RGBColor(0x1F, 0x5F, 0xBF), [("upload", "PowerPoint .pptx", "teacher's old deck, any template"), ("file-text", "Slide PDF", "exported or scanned lecture slides"),
                                               ("notebook-pen", "Word / notes", ".docx, markdown or plain text"), ("pencil", "Typed topic", "a syllabus line or a prompt"),
                                               ("flask-conical", "Teacher labs", "own HTML labs added via API")]),
        ("INGEST", RGBColor(0x0E, 0x7C, 0x86), [("refresh-cw", "LibreOffice convert", "PPTX → PDF, cached by file hash"), ("search", "Slide reader", "titles, bullet levels, tables, figures"),
                                                ("eye", "OCR decision", "Tesseract only when γ ≤ 0.42, conf ≥ 62"), ("wrench", "Repair rules", "logos, page numbers, glued titles"),
                                                ("palette", "Colour DNA", "source palette becomes the theme")]),
        ("ENGINES", RGBColor(0xF2, 0x7A, 0x2E), [("list-checks", "Planner + CLASS", "load-optimal split, agenda, glossary"), ("brain", "Decision engine", "27 detectors → visual + reason"),
                                                 ("ruler", "Layout engine", "glyph-measured, 11 pt floor, no breaks"), ("sigma", "Explainer solvers", "exact steps with reasons (SymPy)"),
                                                 ("gauge", "PSF scorer + audit", "fitness, overflow, fact retention")]),
        ("AI SERVICE", RGBColor(0x6B, 0x3F, 0xA0), [("bot", "LLM router", "Gemini ×5 → Groq → NVIDIA"), ("pencil", "AI polish", "assertion titles, plain explanations"),
                                                    ("palette", "Topic diagrams", "SVG sanitised → PNG + HTML page"), ("code", "AI labs", "JS checked, no network access"),
                                                    ("cpu", "Offline fallback", "rules, scenes, structure labs")]),
        ("OUTPUTS", RGBColor(0x16, 0x84, 0x5B), [("presentation", "Editable PPTX", "native shapes, linked pictures, notes"), ("globe", "Web deck", "click reveals, labs, flip cards"),
                                                 ("book-open", "Study pack", "flashcards, Anki, quiz bank, cheat sheet"), ("users", "Share + present", "view-only link, presenter console"),
                                                 ("message-circle", "Deck tutor", "answers only from the deck")])]
cw, gap = 1.7, 0.12
for i, (name, col, comps) in enumerate(cols):
    x = ax0 + 0.05 + i * (cw + gap)
    rect(s, x, ay0 + 0.02, cw, 4.5, RGBColor(0xF7, 0xF8, 0xFB), line=col, radius=0.04)
    rect(s, x + 0.2, ay0 - 0.04, cw - 0.4, 0.24, col, radius=0.5)
    tb(s, x + 0.2, ay0 - 0.04, cw - 0.4, 0.24, [(name, 8.5, True, WHITE)], MSO_ANCHOR.MIDDLE).text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    for j, (ic, h, sub) in enumerate(comps):
        y = ay0 + 0.26 + j * 0.85
        rect(s, x + 0.06, y, cw - 0.12, 0.78, WHITE, line=col)
        badge(s, ic, x + 0.1, y + 0.07, 0.3, col)
        tb(s, x + 0.43, y + 0.04, cw - 0.52, 0.32, [(h, 8.6, True, INK)], MSO_ANCHOR.MIDDLE)
        tb(s, x + 0.1, y + 0.38, cw - 0.2, 0.4, [(sub, 7.6, False, MUTED)])
    if i < len(cols) - 1:
        arrow(s, x + cw + 0.01, ay0 + 2.3, x + cw + gap - 0.01, ay0 + 2.3, INK, 2)
put(s, {17409: "TECHNICAL APPROACH", 11: TEAM, 7: FOOT,
        9: [("Frontend: ", "React 18 · Vite · Tailwind CSS · Reveal.js web deck · PWA"),
            ("Backend: ", "Python 3.12 · FastAPI · Pydantic · job queue · SQLite · OTP auth"),
            ("Documents: ", "python-pptx · PyMuPDF · LibreOffice · python-docx · Tesseract OCR"),
            ("AI / NLP: ", "Gemini (5-key pool) · Groq · NVIDIA NIM via failover router"),
            ("Maths & labs: ", "SymPy exact solvers · JavaScript lab engine · SVG"),
            ("Quality & DevOps: ", "pytest (755 tests) · layout audit · GitHub · Docker")],
        13: "1 · Read faithfully", 15: "Every page, title, level, table and figure recovered; nothing summarised away",
        16: "2 · Decide with rules", 17: "27 detectors + PSF score: 97% right visual on 101 gold slides, < 1 ms",
        18: "3 · Enrich with AI", 19: "Titles, diagrams, labs from 5 Gemini keys — each checked before use",
        20: "4 · Build and audit", 21: "PPTX + web deck; 0 broken words, 98–100% facts kept, 755 tests",
        22: "WORKING PROTOTYPE · real screens from Learnova"})
logo = by_id(s)[8]
lx, ly = Emu(logo.left).inches, Emu(logo.top).inches
remove(s, 8)
techs = [("atom", RGBColor(0x14, 0x9E, 0xCA)), ("zap", RGBColor(0x8B, 0x5C, 0xF6)), ("waves", RGBColor(0x06, 0xB6, 0xD4)), ("presentation", RGBColor(0xE0, 0x9F, 0x1F)),
         ("code", RGBColor(0x30, 0x6F, 0xA8)), ("zap", RGBColor(0x00, 0x96, 0x88)), ("database", RGBColor(0x0F, 0x5F, 0x8C)), ("file-text", RGBColor(0xC0, 0x30, 0x30)),
         ("refresh-cw", RGBColor(0x18, 0xA3, 0x03)), ("eye", MUTED), ("sparkles", RGBColor(0x42, 0x85, 0xF4)), ("cpu", RGBColor(0xF5, 0x50, 0x36)),
         ("sigma", RGBColor(0x3B, 0x7A, 0x3B)), ("test-tube-diagonal", RGBColor(0xC8, 0x9B, 0x10)), ("git-branch", INK), ("ship", RGBColor(0x1D, 0x63, 0xED))]
for i, (ic, col) in enumerate(techs):
    badge(s, ic, lx + 0.05 + (i % 8) * 0.455, ly + 0.05 + (i // 8) * 0.48, 0.4, col)
for sid, f in ((23, "app-preview.jpg"), (24, "web_deck.png"), (25, "app-solve.jpg")):
    replace_pic(s, sid, f"{IMG}/{f}")

# ── 4. Feasibility ───────────────────────────────────────────────────────────
s = SL[3]
put(s, {17409: "FEASIBILITY AND VIABILITY", 2: TEAM, 7: FOOT,
        17488: "Running today  ·  pilot-ready  ·  every risk has a safeguard",
        17509: ["TECHNICAL", "Working end to end: FastAPI back end, React front end, 755 automated tests and a layout audit; each stage is a separate module."],
        17510: ["DATA", "Input is the college's own material (PPTX, PDF, DOCX). Tested on 7 real decks of 15–216 slides from NLP and ML courses."],
        17511: ["ECONOMIC", "Free offline; Gemini free-tier keys optional (pool of 5). A department server costs less than one paid AI-slides licence."],
        17512: ["OPERATIONAL", "Teachers stay in control: every slide editable, every automatic choice shows its reason; students need only a browser."],
        17513: ["SECURITY", "OTP sign-in, hashed codes, rate limits; AI SVG and lab code sanitised and checked; share links are view-only."],
        17514: ["SCALE", "216-page PDF → full deck in ~35 s offline; work runs in parallel and is cached by content hash."],
        17515: "755 tests", 17516: "7 real decks", 17517: "₹0 offline", 17518: "editable", 17519: "sanitised", 17520: "~35 s / 216 pp",
        17521: "Potential challenges and risks",
        17529: "Code", 17530: "Tests", 17531: "Gold sets", 17583: "Papers",
        17533: "ADOPTION PATH  ·  low-risk, one step at a time",
        17534: "1 · PILOT", 17535: "2 · DEPT", 17536: "3 · COLLEGE",
        17537: "Our AI & DS courses; 3–4 faculty", 17538: "Shared server, deck + lab library", 17539: "LMS export, regional languages",
        17540: "Strategies for overcoming these challenges",
        17562: "Faithful Reader", 17563: "Page reader, title DP split and OCR decision keep messy PDFs, logos and picture slides correct.",
        17571: "Grounded AI", 17577: "AI titles and explanations accepted only if they reuse the slide's words; numbers come from SymPy.",
        17572: "Key Pool + Offline", 17578: "5 Gemini keys, per-key pacing and rotation; Groq/NVIDIA failover; offline rules always finish.",
        17573: "Glass-box Decisions", 17579: "Every visual shows its rule, confidence and alternatives; slide stays editable in the editor.",
        17574: "Measured Layout", 17580: "Glyph-measured fitting, 11 pt floor, CLASS continuation slides: no overflow, no broken words.",
        17575: "Fast by Design", 17581: "Parallel diagrams and labs (2 per key), content-hash caches: re-runs are instant.",
        17576: "Safe Generated Code", 17582: "SVG whitelist and sanitiser; lab JS passes node --check and may not use network or storage.",
        17564: "vs Messy PDFs", 17565: "vs Hallucination", 17566: "vs Quota / cost", 17567: "vs Black-box", 17568: "vs Broken layout",
        17569: "vs Slow decks", 17570: "vs Unsafe code"})
for sid, path in ((17525, REPO), (17526, REPO + "/tree/main/tests"), (17527, REPO + "/tree/main/tests/fixtures"), (17528, REPO + "/tree/main/docs/research/papers")):
    replace_pic(s, sid, qr_png(path))
risks = ["PDFs", "AI errors", "Quota", "Black-box", "Layout", "Speed", "Code"]
cols7 = ["#C03030", "#E07A1F", "#C89B10", "#168455", "#0E7C86", "#1F5FBF", "#6B3FA0"]


def wheel(ax):
    ax.pie([1] * 7, labels=risks, colors=cols7, startangle=90, wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2),
           labeldistance=0.81, textprops=dict(color="white", fontsize=7.5, fontweight="bold"))
    ax.text(0, 0.08, "FEASIBLE", ha="center", fontsize=13, fontweight="bold", color="#172131")
    ax.text(0, -0.18, "7 risks · 7 safeguards", ha="center", fontsize=8, color="#555F6D")
    ax.set_aspect("equal")


replace_pic(s, 17522, fig_png(wheel, 4.4, 4.1))
remove(s, 11)

# ── 5. Impact ────────────────────────────────────────────────────────────────
s = SL[4]
put(s, {4: ["IMPACT AND BENEFITS", "Measured on our own test decks — not on promises"], 2: TEAM, 7: FOOT,
        13: f"Untitled slides across 5 real decks fell from {untitled} to 0: every slide now states its point in a full-sentence title.",
        17: "Slides showing a picture rose on every deck — the teacher's figures kept, plus AI diagrams on topic slides.",
        21: "Visual slides, quizzes and labs went from zero to hundreds, all generated from the deck's own content.",
        25: "Run time grows linearly with length: a 216-page PDF becomes a full deck in about 35 s without any API key.",
        29: "EDUCATIONAL", 30: "One idea per slide with a picture; solved steps with reasons; quizzes and labs to practise.",
        34: "SOCIAL", 35: "Works offline and free, so students without paid tools or stable internet get the same material.",
        39: "INSTITUTIONAL", 41: "Consistent, accessible course decks; reusable lab library; supports flipped and remote classes.",
        44: "TECHNOLOGICAL", 47: "Explainable rules, our PSF metric and CLASS splitting; AI used only where it can be checked.",
        55: ["Students", "revise with visuals, quizzes, labs"], 57: ["Faculty", "old deck redesigned in a minute"], 59: ["HoD / Department", "consistent course material"],
        61: ["Exam preparation", "flashcards, quiz bank, cheat sheet"], 63: ["Remote learners", "share link, phone app, offline"], 17411: ["Accessibility", "readable text, alt text, plain words"]})


def c_untitled(ax):
    ax.bar([NAMES[k] for k in KEYS], [BA[k]["before"]["untitled"] for k in KEYS], color="#C03030", label="before")
    ax.bar([NAMES[k] for k in KEYS], [0] * len(KEYS), color="#168455", label="after (0)")
    ax.set_title("Untitled slides: before → 0", fontsize=9, fontweight="bold")
    ax.legend(frameon=False, fontsize=7)


def c_pics(ax):
    import numpy as np

    x = np.arange(len(KEYS))
    ax.bar(x - 0.2, [BA[k]["before"]["with_picture"] for k in KEYS], 0.4, color="#B8C2D0", label="before")
    ax.bar(x + 0.2, [BA[k]["after"]["with_picture"] for k in KEYS], 0.4, color="#1F5FBF", label="after")
    ax.set_xticks(x, [NAMES[k] for k in KEYS])
    ax.set_title("Slides with a picture", fontsize=9, fontweight="bold")
    ax.legend(frameon=False, fontsize=7)


def c_added(ax):
    bottom = [0] * len(KEYS)
    for f, col, lab in (("visual_structures", "#1F5FBF", "visual"), ("quizzes", "#F27A2E", "quiz"), ("labs", "#168455", "lab"), ("linked_illustrations", "#6B3FA0", "linked art")):
        vals = [BA[k]["after"][f] for k in KEYS]
        ax.bar([NAMES[k] for k in KEYS], vals, bottom=bottom, color=col, label=lab)
        bottom = [a_ + b_ for a_, b_ in zip(bottom, vals)]
    ax.set_title("Added by Learnova (all 0 before)", fontsize=9, fontweight="bold")
    ax.legend(frameon=False, fontsize=6.5, ncol=2)


pd = json.load(open(pathlib.Path(IMG) / "paper_data.json")) if (pathlib.Path(IMG) / "paper_data.json").exists() else None


def c_time(ax):
    pts = [(v["pages"], v["seconds"], k) for k, v in (pd or {}).get("decks", {}).items()]
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], color="#168455")
    for p in pts:
        ax.annotate(p[2], (p[0], p[1]), fontsize=6.5, xytext=(2, 2), textcoords="offset points")
    ax.set_xlabel("source pages")
    ax.set_ylabel("seconds")
    ax.set_title("Time to build (no API key)", fontsize=9, fontweight="bold")


for sid, fn in ((17419, c_untitled), (17420, c_pics), (20, c_added), (24, c_time)):
    replace_pic(s, sid, fig_png(fn, 3.0, 2.0), fit=False)
for sid, f in ((17418, "pair2_after.png"), (17416, "art_sheet.png"), (17417, "lab_split.png")):
    replace_pic(s, sid, f"{IMG}/{f}")
remove(s, 11)

# ── 6. Research and references ───────────────────────────────────────────────
s = SL[5]
R = [(17491, ["THE PROBLEM", "why old decks fail learners"]),
     (17414, ["Tufte 2003: Cognitive Style of PowerPoint", "bullets fragment the argument", "edwardtufte.com"]),
     (17415, ["Sweller 1988: Cognitive load", "working memory limits learning", "doi.org/10.1207/s15516709cog1202_4"]),
     (3, ["Cowan 2001: the magical number 4", "about four chunks at a time", "doi.org/10.1017/S0140525X01003922"]),
     (17492, ["SLIDE DESIGN", "what a good slide looks like"]),
     (17416, ["Garner & Alley 2013, IJEE", "assertion-evidence beats bullets", "ijee.ie"]),
     (17417, ["Alley et al. 2006", "sentence headlines aid retention", "Technical Communication 53(2)"]),
     (24, ["Mayer 2009: Multimedia Learning", "coherence, signalling, contiguity", "cambridge.org"]),
     (17493, ["SLIDE GENERATION", "prior systems we improve on"]),
     (17418, ["Fu et al. 2022: DOC2PPT", "paper → slides, neural", "doi.org/10.1609/aaai.v36i1.19943"]),
     (17419, ["Sun et al. 2021: D2S", "query-based summarisation", "aclanthology.org/2021.naacl-main.111"]),
     (27, ["Hu & Wan 2015: PPSGen", "learned sentence selection", "doi.org/10.1109/TKDE.2014.2359652"]),
     (17494, ["FAITHFULNESS", "why we keep text verbatim"]),
     (17466, ["Maynez et al. 2020, ACL", "summaries hallucinate and omit", "aclanthology.org/2020.acl-main.173"]),
     (17450, ["Ji et al. 2023, ACM CSUR", "survey of hallucination", "doi.org/10.1145/3571730"]),
     (30, ["Kasneci et al. 2023", "LLMs in education: risks", "doi.org/10.1016/j.lindif.2023.102274"]),
     (17495, ["WORKED EXAMPLES", "steps with reasons"]),
     (17420, ["Sweller & Cooper 1985", "worked examples teach novices", "doi.org/10.1207/s1532690xci0201_3"]),
     (17421, ["Atkinson et al. 2000", "principles of example study", "doi.org/10.3102/00346543070002181"]),
     (33, ["Renkl 2014, Cognitive Science", "example-based learning theory", "doi.org/10.1111/cogs.12086"]),
     (17496, ["INTERACTIVE LABS", "learning by doing"]),
     (17422, ["Hundhausen et al. 2002", "engagement drives visualisation gains", "doi.org/10.1006/jvlc.2002.0237"]),
     (17423, ["Wieman et al. 2008: PhET", "simulations that teach", "doi.org/10.1126/science.1161948"]),
     (59, ["Chi & Wylie 2014: ICAP", "interactive > active > passive", "doi.org/10.1080/00461520.2014.965823"]),
     (17497, ["LAYOUT & DESIGN RULES", "algorithms we adapted"]),
     (17424, ["Knuth & Plass 1981", "optimal line breaking → CLASS", "doi.org/10.1002/spe.4380111102"]),
     (17425, ["Mackinlay 1986: APT", "automatic visual design rules", "doi.org/10.1145/22949.22950"]),
     (62, ["Moritz et al. 2019: Draco", "design knowledge as constraints", "doi.org/10.1109/TVCG.2018.2865240"]),
     (17498, ["DOCUMENTS & OCR", "reading real decks"]),
     (17426, ["Smith 2007: Tesseract OCR", "open-source OCR engine", "github.com/tesseract-ocr"]),
     (17515, ["PyMuPDF + LibreOffice", "PDF geometry, PPTX → PDF", "pymupdf.readthedocs.io"]),
     (17517, ["python-pptx", "native, editable PowerPoint", "python-pptx.readthedocs.io"]),
     (17499, ["CODE AND TESTS", "open, testable, honest"]),
     (17518, ["Source code", "755 tests, all modules", "github.com/SDP42/LearnovaV2"]),
     (17427, ["Gold sets", "101 labelled slides", "tests/fixtures on GitHub"]),
     (17521, ["Measurement scripts", "every number on these slides", "scripts/research on GitHub"]),
     (17500, ["TRY IT", "run it today"]),
     (17428, ["Run locally", "uvicorn API + Vite web app", "README on GitHub"]),
     (17429, ["Demo decks", "7 real decks rebuilt", "docs/review on GitHub"]),
     (17524, ["API docs", "every endpoint, try it live", "localhost:8000/docs"]),
     (17501, ["TOOLS COMPARED", "what exists today"]),
     (17430, ["Gamma", "prompt → new deck", "gamma.app"]),
     (17431, ["Microsoft Copilot / Gemini Slides", "AI inside office suites", "microsoft.com · workspace.google.com"]),
     (17451, ["Canva Magic Design", "template-first AI slides", "canva.com"]),
     (17502, ["AI MODELS", "what powers the AI layer"]),
     (17452, ["Google Gemini API", "5-key pool, diagrams, titles", "ai.google.dev"]),
     (5, ["RESEARCH  AND REFERENCES", "12 road signs  ·  36 sources  ·  scan any code to check"]),
     (17527, TEAM), (7, FOOT)]
put(s, {k: v for k, v in R})
urls = {sid: v[2] for sid, v in R if isinstance(v, list) and len(v) == 3}
texts = [(Emu(sh.left).inches, Emu(sh.top).inches, sid) for sid, sh in by_id(s).items() if sid in urls]
for sid, sh in list(by_id(s).items()):
    if sh.shape_type == 13 and 0.35 <= Emu(sh.width).inches <= 0.45:
        px, py = Emu(sh.left).inches, Emu(sh.top).inches
        near = min(texts, key=lambda t: abs(t[1] - py) + abs(t[0] - px - 0.4) * 2)
        u = urls[near[2]]
        replace_pic(s, sid, qr_png(u if u.startswith("http") else "https://" + u.split(" ")[0] if "." in u.split(" ")[0] else REPO))
for sid in (53, 54, 55, 49, 56):
    sh = by_id(s).get(sid)
    if sh is not None and sh.has_text_frame and sh.text_frame.text.strip() == "QR":
        remove(s, sid)
remove(s, 12)

for i, sl in enumerate(prs.slides, 1):
    sh = by_id(sl).get(6)
    if sh is not None and sh.has_text_frame and sh.text_frame.text.strip().isdigit():
        set_text(sh, [str(i)])
prs.save(OUT)
print("saved", OUT, len(prs.slides))
