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


def box(slide, sid, x=None, y=None, w=None, h=None):
    """Move or resize a shape (inches); None keeps that side."""
    sh = by_id(slide)[sid]
    for attr, v in (("left", x), ("top", y), ("width", w), ("height", h)):
        if v is not None:
            setattr(sh, attr, Inches(v))
    return sh


def fsize(slide, sid, first, rest=None):
    """Font size of a text shape: the first run of each paragraph gets ``first``, later runs ``rest``."""
    for p in by_id(slide)[sid].text_frame.paragraphs:
        for i, r in enumerate(p.runs):
            r.font.size = Pt(first if i == 0 or rest is None else rest)


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
        58: "LIVE CODE", 59: ["github.com/SDP42/LearnovaV2", "Open source · 774 tests · demo decks"],
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
cols = [("INPUTS", RGBColor(0x1F, 0x5F, 0xBF), [("upload", "PowerPoint .pptx", "python-pptx · LibreOffice", "teacher's old deck, any template"),
                                               ("file-text", "Slide PDF", "PyMuPDF", "exported or scanned slides"),
                                               ("notebook-pen", "Word / notes", "python-docx · Markdown", ".docx, markdown, plain text"),
                                               ("pencil", "Typed topic", "React form → REST", "a syllabus line or prompt"),
                                               ("flask-conical", "Teacher labs", "HTML · JavaScript", "own labs added via the API")]),
        ("INGEST", RGBColor(0x0E, 0x7C, 0x86), [("refresh-cw", "Convert", "LibreOffice headless", "PPTX → PDF, cached by hash"),
                                                ("search", "Slide reader", "PyMuPDF geometry rules", "titles, levels, tables, figures"),
                                                ("eye", "OCR decision", "Tesseract OCR", "only when γ ≤ 0.42, conf ≥ 62"),
                                                ("wrench", "Repair rules", "Python · regex · DP", "logos, page numbers, glued titles"),
                                                ("palette", "Colour DNA", "Pillow colour clustering", "source palette → deck theme")]),
        ("ENGINES", RGBColor(0xF2, 0x7A, 0x2E), [("list-checks", "Planner + CLASS", "Python dynamic programming", "load-optimal split, agenda"),
                                                 ("brain", "Decision engine", "27 rule detectors", "visual family + reason"),
                                                 ("ruler", "Layout engine", "glyph metrics · python-pptx", "11 pt floor, no broken words"),
                                                 ("sigma", "Explainer solvers", "SymPy · exact fractions", "steps with reasons"),
                                                 ("gauge", "PSF scorer + audit", "NumPy · pytest", "fitness, overflow, facts kept")]),
        ("AI SERVICE", RGBColor(0x6B, 0x3F, 0xA0), [("bot", "LLM router", "Gemini ×5 · Groq · NVIDIA", "failover, per-key pacing"),
                                                    ("pencil", "AI polish", "Gemini 3.5 Flash-Lite", "assertion titles, explanations"),
                                                    ("palette", "Topic diagrams", "SVG → CairoSVG → PNG", "sanitised, linked HTML page"),
                                                    ("code", "AI labs", "JavaScript · Node check", "no network, no storage"),
                                                    ("cpu", "Offline fallback", "rules · scenes · labs", "works with no key at all")]),
        ("OUTPUTS", RGBColor(0x16, 0x84, 0x5B), [("presentation", "Editable PPTX", "python-pptx native shapes", "linked pictures, notes"),
                                                 ("globe", "Web deck", "Reveal.js · HTML5", "reveals, labs, flip cards"),
                                                 ("book-open", "Study pack", "HTML · CSV (Anki)", "flashcards, quiz bank"),
                                                 ("users", "Share + present", "React 18 · FastAPI", "view-only link, presenter"),
                                                 ("message-circle", "Deck tutor", "router + deck context", "answers only from the deck")])]
cw, gap = 1.7, 0.12
for i, (name, col, comps) in enumerate(cols):
    x = ax0 + 0.05 + i * (cw + gap)
    rect(s, x, ay0 + 0.02, cw, 4.5, RGBColor(0xF7, 0xF8, 0xFB), line=col, radius=0.04)
    rect(s, x + 0.2, ay0 - 0.04, cw - 0.4, 0.24, col, radius=0.5)
    tb(s, x + 0.2, ay0 - 0.04, cw - 0.4, 0.24, [(name, 8.5, True, WHITE)], MSO_ANCHOR.MIDDLE).text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    for j, (ic, h, tech, sub) in enumerate(comps):
        y = ay0 + 0.26 + j * 0.85
        rect(s, x + 0.06, y, cw - 0.12, 0.78, WHITE, line=col)
        badge(s, ic, x + 0.1, y + 0.07, 0.3, col)
        tb(s, x + 0.43, y + 0.04, cw - 0.52, 0.32, [(h, 9, True, INK)], MSO_ANCHOR.MIDDLE)
        tb(s, x + 0.1, y + 0.37, cw - 0.2, 0.4, [(tech, 7.8, True, col), (sub, 7.4, False, MUTED)])
    if i < len(cols) - 1:
        arrow(s, x + cw + 0.01, ay0 + 2.3, x + cw + gap - 0.01, ay0 + 2.3, INK, 2)
put(s, {17409: "TECHNICAL APPROACH", 11: TEAM, 7: FOOT, 2: "System architecture and technology stack",
        9: [("Frontend: ", "React 18 · Vite · Tailwind CSS · Reveal.js web deck · PWA"),
            ("Backend: ", "Python 3.12 · FastAPI · Pydantic · job queue · SQLite · OTP auth"),
            ("Documents: ", "python-pptx · PyMuPDF · LibreOffice · python-docx · Tesseract OCR"),
            ("AI / NLP: ", "Gemini (5-key pool) · Groq · NVIDIA NIM via failover router"),
            ("Maths & labs: ", "SymPy exact solvers · JavaScript lab engine · SVG"),
            ("Quality & DevOps: ", "pytest (774 tests) · layout audit · GitHub · Docker")],
        13: "Data and storage", 15: "SQLite for users, decks and jobs; content-hash caches for PDFs, diagrams and labs",
        16: "API and jobs", 17: "FastAPI with about 70 REST routes, background job queue, live progress, OpenAPI docs",
        18: "Security", 19: "OTP e-mail sign-in, hashed codes, rate limits, SVG sanitiser, lab-code gate",
        20: "Deploy and test", 21: "One laptop or server; Vercel-ready front end; 774 pytest tests on GitHub",
        22: "WORKING PROTOTYPE · real screens from Learnova"})
logo = by_id(s)[8]
lx, ly = Emu(logo.left).inches, Emu(logo.top).inches
remove(s, 8)
techs = [("atom", RGBColor(0x14, 0x9E, 0xCA)), ("zap", RGBColor(0x8B, 0x5C, 0xF6)), ("waves", RGBColor(0x06, 0xB6, 0xD4)), ("presentation", RGBColor(0xE0, 0x9F, 0x1F)),
         ("code", RGBColor(0x30, 0x6F, 0xA8)), ("zap", RGBColor(0x00, 0x96, 0x88)), ("database", RGBColor(0x0F, 0x5F, 0x8C)), ("file-text", RGBColor(0xC0, 0x30, 0x30)),
         ("refresh-cw", RGBColor(0x18, 0xA3, 0x03)), ("eye", MUTED), ("sparkles", RGBColor(0x42, 0x85, 0xF4)), ("cpu", RGBColor(0xF5, 0x50, 0x36)),
         ("sigma", RGBColor(0x3B, 0x7A, 0x3B)), ("test-tube-diagonal", RGBColor(0xC8, 0x9B, 0x10)), ("git-branch", INK), ("ship", RGBColor(0x1D, 0x63, 0xED))]
tech_names = ["React", "Vite", "Tailwind", "Reveal.js", "Python", "FastAPI", "SQLite", "PyMuPDF", "LibreOffice", "Tesseract", "Gemini",
              "Groq", "SymPy", "pytest", "GitHub", "Docker"]
for i, (ic, col) in enumerate(techs):
    bx, by_ = lx + 0.05 + (i % 8) * 0.455, ly - 0.02 + (i // 8) * 0.62
    badge(s, ic, bx, by_, 0.4, col)
    t = tb(s, bx - 0.06, by_ + 0.4, 0.52, 0.17, [(tech_names[i], 6.3, True, INK)])
    t.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
box(s, 9, y=2.86, h=2.66)
for sid in (15, 17, 19, 21):
    fsize(s, sid, 10.5)
for sid in (13, 16, 18, 20):
    fsize(s, sid, 11.5)
for sid, f in ((23, "app-preview.jpg"), (24, "web_deck.png"), (25, "app-solve.jpg")):
    replace_pic(s, sid, f"{IMG}/{f}")

# ── 4. Feasibility ───────────────────────────────────────────────────────────
s = SL[3]
put(s, {17409: "FEASIBILITY AND VIABILITY", 2: TEAM, 7: FOOT,
        17488: "Running today  ·  pilot-ready  ·  every risk has a safeguard",
        17509: ["TECHNICAL", "Built and running end to end: FastAPI back end, React front end, 16 pipeline stages as separate modules, 774 automated tests and a layout audit."],
        17510: ["DATA", "No dataset to collect: input is the college's own PPTX, PDF and DOCX material. Verified on 7 real decks (15–216 pages) and 101 gold-labelled slides."],
        17511: ["ECONOMIC", "₹0 to run offline; free-tier Gemini keys (pool of 5) are optional. One department PC replaces paid AI-slide plans ($10–20 per teacher per month)."],
        17512: ["OPERATIONAL", "No retraining for staff: upload, review, download. Every slide stays editable, every choice shows its reason; students need only a browser or phone."],
        17513: ["SECURITY", "OTP sign-in with hashed codes and rate limits; AI diagrams sanitised, AI lab code checked before use; share links view-only; data stays on campus."],
        17514: ["SCALE", "Time grows linearly: a 216-page PDF becomes a full deck in ~35 s offline. Parallel workers, job queue and content-hash caches make re-runs instant."],
        17515: "774 tests", 17516: "7 real decks", 17517: "₹0 offline", 17518: "editable", 17519: "sanitised", 17520: "~35 s / 216 pp",
        17521: "Potential challenges and risks",
        17529: "Code", 17530: "Tests", 17531: "Gold sets", 17583: "Papers",
        17533: "ADOPTION PATH  ·  low-risk, one step at a time",
        17534: "1 · PILOT", 17535: "2 · DEPT", 17536: "3 · COLLEGE",
        17537: "Our AI & DS courses; 3–4 faculty", 17538: "Shared server, deck + lab library", 17539: "LMS export, regional languages",
        17540: "Strategies for overcoming these challenges",
        17562: "Faithful Reader", 17563: "Geometry rules, a DP title splitter and the γ ≤ 0.42 OCR test keep messy PDFs, logos and picture slides correct; 98–100% of facts kept.",
        17571: "Grounded AI", 17577: "An AI title or explanation is used only if it reuses the slide's own words and fits length rules; every number in a solution comes from SymPy.",
        17572: "Key Pool + Offline", 17578: "Offline first: free Gemini and Groq key pools are used only when the rule result is weak; spent keys are skipped; offline rules always finish.",
        17573: "Glass-box Decisions", 17579: "Each visual records the detector that fired, its confidence and the runner-up; the teacher can switch it in the editor in one click.",
        17574: "Measured Layout", 17580: "Text is measured glyph by glyph with an 11 pt floor; long sections split by CLASS. Result on 7 decks: 0 overflow, 0 broken words.",
        17575: "Fast by Design", 17581: "Diagrams and labs run in parallel (2 requests per key) before the build; with 5 keys 40 diagrams take ≈ 42 s instead of 3 min.",
        17576: "Safe Generated Code", 17582: "SVG whitelist removes scripts and links; lab JavaScript must pass node --check and may not use network, eval, cookies or storage.",
        17564: "vs Messy PDFs", 17565: "vs Hallucination", 17566: "vs Quota / cost", 17567: "vs Black-box", 17568: "vs Broken layout",
        17569: "vs Slow decks", 17570: "vs Unsafe code"})
for sid, path in ((17525, REPO), (17526, REPO + "/tree/main/tests"), (17527, REPO + "/tree/main/tests/fixtures"), (17528, REPO + "/tree/main/docs/research/papers")):
    replace_pic(s, sid, qr_png(path))
risks = ["PDFs", "AI errors", "Quota", "Black-box", "Layout", "Speed", "Code"]
cols7 = ["#C03030", "#E07A1F", "#C89B10", "#168455", "#0E7C86", "#1F5FBF", "#6B3FA0"]


def wheel(ax):
    ax.pie([1] * 7, colors=cols7, startangle=90, wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
    ax.text(0, -0.08, "LOW", ha="center", fontsize=10, fontweight="bold", color="#168455")
    ax.set_aspect("equal")


pic = by_id(s)[17522]
box(s, 17522, x=4.55, y=1.6, w=1.55, h=1.55)
replace_pic(s, 17522, fig_png(wheel, 1.7, 1.7))
for sid in (17509, 17510, 17511, 17512, 17513, 17514):
    for pi, para in enumerate(by_id(s)[sid].text_frame.paragraphs):
        for r in para.runs:
            r.font.size = Pt(10 if pi == 0 else 8.3)
for sid in (17563, 17577, 17578, 17579, 17580, 17581, 17582):
    fsize(s, sid, 8.5)
tb(s, 6.15, 1.62, 2.85, 1.5, [("7 risks found · 7 safeguards built", 11, True, INK),
                              ("We listed what could stop Learnova in a real classroom and built one safeguard for each. "
                               "Each risk is rated by how likely it is and how much harm it would do if it happened; the right-hand "
                               "column shows the safeguard already in the code. Residual risk after safeguards: LOW.", 8.6, False, MUTED)])
reg = [("Messy or scanned PDFs", "High", "High", "Geometry rules + OCR test"), ("AI makes up facts", "Med", "High", "Grounding check, SymPy maths"),
       ("Keys or quota run out", "High", "Med", "5-key pool + offline rules"), ("Teachers distrust AI", "Med", "High", "Reason + confidence shown"),
       ("Text overflows slides", "Med", "Med", "Glyph fit, CLASS split"), ("Slow on long decks", "Low", "Med", "Parallel + caches"),
       ("Unsafe generated code", "Low", "High", "Sanitiser + node --check")]
lvl = {"High": RGBColor(0xC0, 0x30, 0x30), "Med": RGBColor(0xE0, 0x9F, 0x1F), "Low": RGBColor(0x16, 0x84, 0x5B)}
y0, rh = 3.2, 0.32
rect(s, 4.55, y0, 4.4, rh, RGBColor(0x17, 0x21, 0x31), shape=MSO_SHAPE.RECTANGLE)
for x, w, t in ((4.6, 1.75, "Risk"), (6.33, 0.55, "Likely"), (6.88, 0.55, "Impact"), (7.45, 1.5, "Safeguard in code")):
    tb(s, x, y0, w, rh, [(t, 8.5, True, WHITE)], MSO_ANCHOR.MIDDLE)
for i, (r, lk, im, sg) in enumerate(reg):
    y = y0 + rh * (i + 1)
    rect(s, 4.55, y, 4.4, rh, RGBColor(0xF7, 0xF8, 0xFB) if i % 2 else WHITE, line=RGBColor(0xE2, 0xE6, 0xEC), shape=MSO_SHAPE.RECTANGLE)
    rect(s, 4.58, y + 0.06, 0.06, rh - 0.12, RGBColor.from_string(cols7[i][1:]), shape=MSO_SHAPE.RECTANGLE)
    tb(s, 4.68, y, 1.65, rh, [(r, 8.4, True, INK)], MSO_ANCHOR.MIDDLE)
    for x, v in ((6.36, lk), (6.92, im)):
        rect(s, x, y + 0.07, 0.48, rh - 0.14, lvl[v], radius=0.5)
        t = tb(s, x, y + 0.07, 0.48, rh - 0.14, [(v, 7.5, True, WHITE)], MSO_ANCHOR.MIDDLE)
        t.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    tb(s, 7.47, y, 1.47, rh, [(sg, 8, False, INK)], MSO_ANCHOR.MIDDLE)
remove(s, 11)

# ── 5. Impact ────────────────────────────────────────────────────────────────
s = SL[4]
put(s, {4: ["IMPACT AND BENEFITS", "Measured on our own test decks — not on promises"], 2: TEAM, 7: FOOT,
        13: f"Untitled slides across 5 real decks fell from {untitled} to 0. Every slide now states its point in a full-sentence title.",
        17: "Slides with a picture rose on every deck: the teacher's own figures are kept and AI diagrams are added on topic slides.",
        21: "Visual slides, quizzes, labs and linked illustrations went from zero to hundreds, all built from the deck's own content.",
        25: "Build time grows in a straight line with length: a 216-page PDF becomes a full deck in about 35 s with no API key.",
        29: "EDUCATIONAL", 30: "One idea per slide with a picture, so the eye has one thing to read. Solved problems become step-by-step "
                            "explainers with a reason for each step, and hard topics get labs and quizzes to practise on.",
        34: "SOCIAL", 35: "Runs offline and free on a college laptop, so students without paid tools, fast internet or a laptop of their own "
                       "get the same material through a share link on any phone. Plain words and alt text help first-generation learners.",
        39: "INSTITUTIONAL", 41: "Course decks become consistent and accessible across the department. A shared library of decks and labs "
                               "builds up every semester and supports flipped, remote and revision classes.",
        44: "TECHNOLOGICAL", 47: "Explainable rules instead of a black box, our own PSF score and CLASS splitting, and AI used only where its "
                               "output can be checked: sanitised diagrams, checked code, grounded titles.",
        55: ["Students", "revise with visuals, quizzes and labs"], 57: ["Faculty", "old deck redesigned in about a minute"],
        59: ["HoD / Department", "consistent, reusable course material"], 61: ["Exam preparation", "flashcards, quiz bank, cheat sheet"],
        63: ["Remote learners", "share link on any phone, works offline"], 17411: ["Accessibility", "readable text, alt text, plain words"]})
# bigger text: the screenshot strip goes, its height goes to the text
for sid in (17412, 17414, 17415, 17416, 17417, 17418):
    remove(s, sid)
for sid in (5, 15, 19, 23):
    box(s, sid, y=1.15, h=2.42)
for sid in (17419, 17420, 20, 24):
    box(s, sid, y=1.18, h=1.6)
for sid in (13, 17, 21, 25):
    box(s, sid, y=2.82, h=0.72)
    fsize(s, sid, 10.5)
for sid in (14, 18, 22, 26):
    box(s, sid, y=2.84, h=0.66)
for sid in (27, 32, 38, 43):
    box(s, sid, y=3.65, h=1.42)
for sid in (28, 36, 42, 45):
    box(s, sid, y=3.71, h=1.3)
for sid in (37, 33, 40, 46):
    box(s, sid, y=3.71)
replace_pic(s, 37, icon_png("book-open", "#1F5FBF", 128))
for sid in (29, 34, 39, 44):
    box(s, sid, y=3.68, h=0.28)
    fsize(s, sid, 12.5)
for sid in (30, 35, 41, 47):
    box(s, sid, y=3.98, h=1.05)
    fsize(s, sid, 10.5)
for sid in (48, 49, 50, 51, 52, 53):
    box(s, sid, y=5.14, h=0.74)
for sid in (54, 56, 58, 60, 62, 17408):
    box(s, sid, y=5.37)
for sid in (55, 57, 59, 61, 63, 17411):
    box(s, sid, y=5.14, h=0.74)
    fsize(s, sid, 11, 10)
stats = [(f"{untitled} → 0", "untitled slides"), ("251", "visual slides added"), ("190", "linked illustrations"),
         ("98–100%", "facts kept"), ("0", "overflow or broken words"), ("26 / 26", "explainers correct")]
cw6 = 12.73 / 6
for i, (big, small) in enumerate(stats):
    x = 0.3 + i * cw6
    rect(s, x + 0.03, 5.96, cw6 - 0.06, 0.9, RGBColor(0x1F, 0x5F, 0xBF) if i % 2 == 0 else RGBColor(0x16, 0x84, 0x5B), radius=0.1)
    t = tb(s, x + 0.05, 5.98, cw6 - 0.1, 0.86, [(big, 20, True, WHITE), (small, 10.5, False, WHITE)], MSO_ANCHOR.MIDDLE)
    for para in t.text_frame.paragraphs:
        para.alignment = PP_ALIGN.CENTER


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
    replace_pic(s, sid, fig_png(fn, 3.0, 1.6), fit=False)
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
     (17518, ["Source code", "774 tests, all modules", "github.com/SDP42/LearnovaV2"]),
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

# ── New slides on the deck's own chrome (footer band, title, team oval, number) ──
BLUE, GREEN, ORANGE, PURPLE, TEAL, RED = (RGBColor(0x1F, 0x5F, 0xBF), RGBColor(0x16, 0x84, 0x5B), RGBColor(0xF2, 0x7A, 0x2E),
                                         RGBColor(0x6B, 0x3F, 0xA0), RGBColor(0x0E, 0x7C, 0x86), RGBColor(0xC0, 0x30, 0x30))
SOFT = RGBColor(0xF7, 0xF8, 0xFB)
LINE = RGBColor(0xE2, 0xE6, 0xEC)


def new_slide(title, sub=None):
    src = SL[2]
    ns = prs.slides.add_slide(src.slide_layout)
    for sh in list(ns.shapes):
        sh._element.getparent().remove(sh._element)
    ids = by_id(src)
    for sid in (10, 17409, 6, 7, 11):
        ns.shapes._spTree.append(copy.deepcopy(ids[sid]._element))
    put(ns, {17409: title})
    if sub:
        t = tb(ns, 3.0, 0.68, 7.33, 0.34, [(sub, 15, False, BLUE)], MSO_ANCHOR.MIDDLE)
        t.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        t.text_frame.paragraphs[0].runs[0].font.italic = True
    return ns


def bar(sl, x, y, w, h, text, col, size=13):
    rect(sl, x, y, w, h, col, radius=0.25)
    t = tb(sl, x, y, w, h, [(text, size, True, WHITE)], MSO_ANCHOR.MIDDLE)
    t.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER


def bullets(sl, x, y, w, h, items, size=10, col=INK, mark="▸ ", mcol=None):
    t = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = t.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, it in enumerate(items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_after = Pt(2)
        lab, body = it if isinstance(it, tuple) else (None, it)
        for txt, b, c in ((mark, True, mcol or col), (lab, True, col), (body, False, col)):
            if not txt:
                continue
            r = para.add_run()
            r.text, r.font.size, r.font.bold, r.font.name = (txt + " " if txt is lab else txt), Pt(size), b, "Calibri"
            r.font.color.rgb = c
    return t


# ── Methodology ──
m = new_slide("METHODOLOGY", "Six stages from the teacher's old deck to a checked, interactive one")
bar(m, 0.3, 1.1, 12.73, 0.36, "Methodology and process for implementation", GREEN, 14)
steps = [("1 · READ", BLUE, "file-text", ["PPTX → PDF with LibreOffice, cached by file hash", "Words read with position, size, weight (PyMuPDF)",
                                          "Title rule: size ≥ 1.18 × body size", "OCR only if γ ≤ 0.42, confidence ≥ 62", "Tables and figures kept in place"]),
         ("2 · CLEAN", TEAL, "wrench", ["Text on ≥ max(3, 0.3n) pages removed: logos, footers", "Glued titles split by dynamic programming",
                                        "Split words and wrapped lines joined", "Chart debris and page counters dropped", "Repeated pictures marked as decoration"]),
         ("3 · PLAN", ORANGE, "list-checks", ["Pages grouped into topics and sections", "CLASS splits long sections at least load cost",
                                               "Agenda, glossary and summary slides added", "Parts get names, never “(2/5)”", "Each part stays under the load limit"]),
         ("4 · DECIDE", RED, "brain", ["27 detectors score every slide", "Visual family d* = highest confidence",
                                        "Exclusion rules stop clashing choices", "Reason and confidence stored per slide", "Flowchart, algorithm, code, equations, charts…"]),
         ("5 · ENRICH", PURPLE, "sparkles", ["AI titles kept only if grounded in the slide", "Topic diagrams from the 5-key Gemini pool",
                                              "Exact step-by-step explainers (SymPy)", "Labs: built-in, AI-written + checked, or offline", "Quizzes and flashcards from slide facts"]),
         ("6 · BUILD + AUDIT", GREEN, "gauge", ["Glyph-measured fitting, 11 pt floor", "Editable PPTX, web deck and study pack",
                                                 "PSF score, overflow and fact audit", "Caches make every re-run instant", "Notes and alt text on every slide"])]
cw6 = 12.73 / 6
for i, (name, col, ic, pts) in enumerate(steps):
    x = 0.3 + i * cw6
    sh = m.shapes.add_shape(MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, Inches(x), Inches(1.56), Inches(cw6 + 0.05), Inches(0.42))
    sh.fill.solid(); sh.fill.fore_color.rgb = col; sh.line.fill.background(); sh.shadow.inherit = False
    t = tb(m, x + 0.2, 1.56, cw6 - 0.3, 0.42, [(name, 12, True, WHITE)], MSO_ANCHOR.MIDDLE)
    t.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    rect(m, x + 0.04, 2.06, cw6 - 0.08, 2.62, SOFT, line=col, radius=0.05)
    badge(m, ic, x + cw6 / 2 - 0.22, 2.12, 0.44, col)
    bullets(m, x + 0.08, 2.6, cw6 - 0.16, 2.05, pts, 10.6, INK, "▸ ", col)
# formulas
rect(m, 0.3, 4.78, 7.6, 2.08, WHITE, line=BLUE, radius=0.04)
bar(m, 0.3, 4.78, 7.6, 0.32, "Our own formulas behind each decision", BLUE, 12)
forms = [("OCR decision", "γ = |I ∖ M| / |I|   use OCR only if γ ≤ 0.42", "share of the page that is picture, not text"),
         ("Slide fitness (PSF)", "PSF = E^0.40 · (1 − L)^0.42 · C^0.18", "efficiency, cognitive load L, coherence"),
         ("CLASS splitting", "F(i) = min_p [ F(p) + cost(p, i) ]", "cost = L + 0.9(1 − E) + 0.25·overflow² + 0.35"),
         ("Word-safe layout", "σ = max(0.62, min(1, W / w)),  s* ≥ 11 pt", "largest font on a 0.5 pt grid that fits")]
for i, (h, f, d) in enumerate(forms):
    x, y = 0.4 + (i % 2) * 3.75, 5.18 + (i // 2) * 0.84
    rect(m, x, y, 3.6, 0.78, SOFT, line=LINE, radius=0.08)
    tb(m, x + 0.08, y + 0.03, 3.45, 0.74, [(h, 10, True, BLUE), (f, 11, True, INK), (d, 8.8, False, MUTED)])
# process
rect(m, 8.0, 4.78, 5.03, 2.08, WHITE, line=ORANGE, radius=0.04)
bar(m, 8.0, 4.78, 5.03, 0.32, "How we built it", ORANGE, 12)
for i, (ph, when) in enumerate((("Research + design", "Sep–Dec 2025"), ("Build platform", "Jan–Jul 2026"), ("Test + publish", "Aug–Oct 2026"))):
    x = 8.1 + i * 1.62
    sh = m.shapes.add_shape(MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, Inches(x), Inches(5.18), Inches(1.65), Inches(0.5))
    sh.fill.solid(); sh.fill.fore_color.rgb = (BLUE, ORANGE, GREEN)[i]; sh.line.fill.background(); sh.shadow.inherit = False
    t = tb(m, x + 0.15, 5.18, 1.4, 0.5, [(ph, 8.8, True, WHITE), (when, 7.8, False, WHITE)], MSO_ANCHOR.MIDDLE)
    for para in t.text_frame.paragraphs:
        para.alignment = PP_ALIGN.CENTER
bullets(m, 8.08, 5.76, 4.9, 1.08, [("Agile:", "weekly sprints, reviewed with our guide every week"),
                                   ("Test-first:", "774 automated tests, gold sets of 101 slides"),
                                   ("Measured:", "every claim on these slides comes from a script"), ("Documented:", "IPD diary, report and two research papers")], 10.5, INK, "✓ ", GREEN)

# ── Literature review ──
lr = new_slide("LITERATURE REVIEW", "What earlier work found, what it left open, and how Learnova closes the gap")
papers = [("Fu et al., 2022", "DOC2PPT — AAAI", "Neural model turns a research paper into new slides section by section",
           "Readable slides from long documents", "Writes new text; drops points; needs training data; not for existing decks",
           "Starts from the teacher's own deck and keeps every point verbatim"),
          ("Sun et al., 2021", "D2S — NAACL", "Query-based summarisation: a slide title is used to retrieve and write its bullets",
           "Titles can steer content selection", "Abstractive text can drift from the source; no visual or layout choice",
           "Titles are grounded in the slide's words; 27 detectors choose a visual"),
          ("Hu & Wan, 2015", "PPSGen — IEEE TKDE", "Learns sentence importance and fills slides by integer programming",
           "Extractive selection keeps facts", "Bullet text only: no diagrams, no layout fitting, no interactivity",
           "Adds diagrams, labs and quizzes; fits every slide by glyph measurement"),
          ("Maynez et al., 2020", "Faithfulness — ACL", "Human study of hallucination in neural abstractive summaries",
           "Many model summaries contain unsupported content", "Generation without checks is unsafe for study material",
           "AI output is accepted only after grounding, sanitising or code checks"),
          ("Garner & Alley, 2013", "Assertion–evidence — IJEE", "Classroom study comparing sentence-headline slides with topic-bullet slides",
           "Assertion titles + visual evidence improve understanding", "Redesigning decks by hand takes teachers many hours",
           "Writes assertion titles and visuals automatically, in about a minute"),
          ("Mackinlay, 1986", "APT — ACM TOG", "Rules of expressiveness and effectiveness choose a chart for data",
           "Visual choice can be automated with explicit rules", "Covers data charts only, not lecture text",
           "Extends rule-based choice to 27 slide families with confidence and reason")]
hdr = ["Paper", "Method", "Finding", "Gap left open", "How Learnova addresses it"]
xs = [0.3, 2.35, 4.95, 7.25, 9.95, 13.03]
y = 1.12
rect(lr, 0.3, y, 12.73, 0.38, RGBColor(0x17, 0x21, 0x31), shape=MSO_SHAPE.RECTANGLE)
for j, hname in enumerate(hdr):
    tb(lr, xs[j] + 0.06, y, xs[j + 1] - xs[j] - 0.1, 0.38, [(hname, 11.5, True, WHITE)], MSO_ANCHOR.MIDDLE)
rh = 0.66
for i, (who, venue, meth, find, gap, ours) in enumerate(papers):
    yy = y + 0.38 + i * rh
    rect(lr, 0.3, yy, 12.73, rh, SOFT if i % 2 else WHITE, line=LINE, shape=MSO_SHAPE.RECTANGLE)
    rect(lr, 0.3, yy, 0.07, rh, (BLUE, TEAL, ORANGE, RED, PURPLE, GREEN)[i], shape=MSO_SHAPE.RECTANGLE)
    rect(lr, 9.95, yy, 3.08, rh, RGBColor(0xEA, 0xF6, 0xEF), line=LINE, shape=MSO_SHAPE.RECTANGLE)
    tb(lr, xs[0] + 0.12, yy + 0.04, xs[1] - xs[0] - 0.16, rh - 0.06, [(who, 10.5, True, INK), (venue, 9.2, False, BLUE)])
    for j, txt in ((1, meth), (2, find), (3, gap), (4, ours)):
        tb(lr, xs[j] + 0.06, yy + 0.04, xs[j + 1] - xs[j] - 0.12, rh - 0.06, [(txt, 9.6, j == 4, GREEN if j == 4 else INK)], MSO_ANCHOR.MIDDLE)
yb = y + 0.38 + 6 * rh + 0.1
rect(lr, 0.3, yb, 8.4, 6.87 - yb, WHITE, line=ORANGE, radius=0.06)
tb(lr, 0.42, yb + 0.06, 8.2, 6.8 - yb, [("Research gap", 12.5, True, ORANGE),
   ("Earlier systems either generate new slides from a document, which changes the teacher's wording and can invent content, or "
    "select sentences without any visual design. Design research tells us what a good slide looks like but leaves the redesign to the "
    "teacher. No published system takes an existing lecture deck, keeps every point, explains each design decision and checks the AI "
    "output it adds. Learnova is built for exactly this gap.", 11.2, False, INK)])
rect(lr, 8.8, yb, 4.23, 6.87 - yb, RGBColor(0x17, 0x21, 0x31), radius=0.06)
tb(lr, 8.95, yb + 0.06, 4.0, 6.8 - yb, [("Also reviewed", 12.5, True, WHITE),
   ("Tufte 2003 · Sweller 1988 · Cowan 2001 · Mayer 2009 · Knuth & Plass 1981 · Moritz 2019 · Ji 2023 · Kasneci 2023 · "
    "Renkl 2014 · Hundhausen 2002 · Wieman 2008 · Chi & Wylie 2014; tools: Gamma, Copilot, Gemini Slides, Canva. "
    "Full list with links on the next slide.", 9.8, False, RGBColor(0xD6, 0xDE, 0xEA))])

# ── Conclusion ──
c = new_slide("CONCLUSIONS OBTAINED", "What the project set out to do, what we achieved, and what comes next")
bar(c, 0.3, 1.1, 7.9, 0.36, "Objectives versus outcomes", BLUE, 13)
objs = [("Keep every point of the teacher's deck", "98–100% of facts kept on 7 real decks", GREEN),
        ("Give every slide a clear title", f"untitled slides {untitled} → 0 on 5 decks", GREEN),
        ("Pick the right visual, with a reason", "97% correct on 101 gold slides, < 1 ms each", GREEN),
        ("Illustrate every topic slide", "251 visual slides, 190 linked illustrations", GREEN),
        ("Explain solved problems step by step", "26 / 26 correct, 0 false alarms on 52 sentences", GREEN),
        ("No overflow, no broken words", "0 on every rebuilt deck", GREEN),
        ("Work on any uploaded file", "9 / 9 unseen files built; 2.3% slides flagged", GREEN),
        ("Lower cognitive load on every deck", "better on long PDFs, mixed on short decks", ORANGE)]
for i, (o, r, col) in enumerate(objs):
    yy = 1.54 + i * 0.5
    rect(c, 0.3, yy, 7.9, 0.45, SOFT if i % 2 else WHITE, line=LINE, radius=0.1)
    badge(c, "shield-check" if col == GREEN else "gauge", 0.38, yy + 0.06, 0.33, col)
    tb(c, 0.8, yy, 3.6, 0.45, [(o, 10.8, True, INK)], MSO_ANCHOR.MIDDLE)
    tb(c, 4.45, yy, 3.7, 0.45, [(r, 10.5, False, col if col == ORANGE else RGBColor(0x0F, 0x5F, 0x3C))], MSO_ANCHOR.MIDDLE)
bar(c, 8.35, 1.1, 4.68, 0.36, "Key conclusions", GREEN, 13)
bullets(c, 8.38, 1.52, 4.62, 3.0, [
    ("Redesign beats regeneration:", "starting from the teacher's deck keeps it trusted and correct."),
    ("Rules + checked AI work together:", "rules give speed and reasons; AI adds titles, diagrams and labs only after a check."),
    ("Exact maths matters:", "SymPy solvers were right even where our own hand answers were wrong."),
    ("Measure honestly:", "PSF showed where rebuilt slides were longer, and we report it."),
    ("Built for real classrooms:", "free, offline, editable, and fast enough to use before a lecture."),
    ("Checks catch real bugs:", "our own tests found and fixed a lab-gate and a key-pool fault."),
    ("Explainability builds trust:", "teachers accept a visual faster when they can see why it was chosen.")], 11.3, INK, "● ", GREEN)
rect(c, 8.35, 4.6, 4.68, 2.26, RGBColor(0x17, 0x21, 0x31), radius=0.05)
tb(c, 8.5, 4.66, 4.4, 2.15, [("Future scope", 12.5, True, ORANGE),
   ("•  Classroom study with our own students next semester", 12, False, WHITE),
   ("•  Hindi and Marathi decks; voice narration", 12, False, WHITE),
   ("•  LMS export (Moodle, Google Classroom)", 12, False, WHITE),
   ("•  Calibrate PSF weights with student ratings", 12, False, WHITE),
   ("•  Department server and shared lab library", 12, False, WHITE),
   ("•  Handwritten-slide OCR and more solver types", 12, False, WHITE),
   ("Outputs: 2 research papers · IPD report · open-source code", 10.5, True, RGBColor(0x9F, 0xD8, 0xB8))])
rect(c, 0.3, 5.6, 7.9, 1.26, RGBColor(0xEA, 0xF1, 0xFB), line=BLUE, radius=0.06)
tb(c, 0.45, 5.64, 7.6, 1.2, [("In one line", 12, True, BLUE),
   ("Learnova turns the decks teachers already have into faithful, visual and interactive lessons in about a minute, explains every "
    "design choice it makes, and uses AI only where its output can be checked.", 13, False, INK),
   ("Status: working prototype, tested on 7 real decks, ready for a department pilot.", 12, True, GREEN)])

# ── Thank you ──
ty = new_slide("THANK YOU")
rect(ty, 0.3, 1.0, 6.1, 5.85, RGBColor(0x17, 0x21, 0x31), radius=0.04)
rect(ty, 0.3, 1.0, 0.12, 5.85, ORANGE, shape=MSO_SHAPE.RECTANGLE)
tb(ty, 0.65, 1.12, 5.6, 5.7, [("LEARNOVA", 44, True, WHITE),
   ("Old decks.  New learning.", 20, False, RGBColor(0xF2, 0xA2, 0x6E)),
   ("", 8, False, WHITE),
   ("A faithful, explainable and interactive redesign of the lecture decks teachers already have — every point kept, every "
    "slide illustrated, every AI output checked.", 14, False, RGBColor(0xD6, 0xDE, 0xEA)),
   ("", 8, False, WHITE),
   ("Team", 14, True, ORANGE),
   ("Swayam Devendra Panchal  ·  Kawaljeet Singh Bharaj", 13.5, False, WHITE),
   ("Jeevesh Bharat Bodhani  ·  Rishit Pankajkumar Lahoti", 13.5, False, WHITE),
   ("", 6, False, WHITE),
   ("Guided by", 14, True, ORANGE),
   ("Dr. Pratik Kanani, Head of Department", 13.5, False, WHITE),
   ("Artificial Intelligence and Data Science, DJSCE, Mumbai", 12, False, RGBColor(0xD6, 0xDE, 0xEA)),
   ("", 8, False, WHITE),
   ("What it gives back", 14, True, ORANGE),
   ("Editable PowerPoint · interactive web deck · study pack · labs · quizzes · step-by-step explainers · deck tutor", 13, False, WHITE),
   ("", 8, False, WHITE),
   ("Questions and live demo welcome", 16, True, RGBColor(0x9F, 0xD8, 0xB8))])
ty.shapes.add_picture(f"{IMG}/web_deck.png", Inches(6.6), Inches(1.0), Inches(4.0), Inches(2.25))
from PIL import Image as _Im
_w, _h = _Im.open(f"{IMG}/mobile-home.jpg").size
_sc = min(2.28 / _w, 2.25 / _h)
ty.shapes.add_picture(f"{IMG}/mobile-home.jpg", Inches(10.75 + (2.28 - _w * _sc) / 2), Inches(1.0 + (2.25 - _h * _sc) / 2), Inches(_w * _sc), Inches(_h * _sc))
for i, (big, small, col) in enumerate(((f"{untitled}→0", "untitled slides", BLUE), ("98–100%", "facts kept", GREEN),
                                        ("774", "automated tests", ORANGE), ("~35 s", "216-page deck", PURPLE))):
    x = 6.6 + i * 1.62
    rect(ty, x, 3.4, 1.52, 1.0, col, radius=0.12)
    t = tb(ty, x, 3.42, 1.52, 0.96, [(big, 19, True, WHITE), (small, 9.5, False, WHITE)], MSO_ANCHOR.MIDDLE)
    for para in t.text_frame.paragraphs:
        para.alignment = PP_ALIGN.CENTER
rect(ty, 6.6, 4.55, 6.43, 2.3, SOFT, line=LINE, radius=0.05)
ty.shapes.add_picture(io.BytesIO(qr_png(REPO)), Inches(6.75), Inches(4.7), Inches(2.0), Inches(2.0))
tb(ty, 8.9, 4.68, 4.05, 2.12, [("Try it yourself", 14, True, BLUE),
   ("Scan for the source code, demo decks, test suite and both research papers.", 11, False, INK),
   ("github.com/SDP42/LearnovaV2", 11, True, GREEN),
   ("Upload any lecture deck: PPTX, PDF or Word. Get back an editable PowerPoint, an interactive web deck and a study pack.", 11, False, MUTED),
   ("Runs on one laptop: FastAPI + React, works offline, free.", 11, True, ORANGE)])

# order: title, idea, technical, methodology, feasibility, impact, literature, references, conclusion, thank you
lst = prs.slides._sldIdLst
ids_ = list(lst)
order = [0, 1, 2, 6, 3, 4, 7, 5, 8, 9]
for el in ids_:
    lst.remove(el)
for k in order:
    lst.append(ids_[k])

for i, sl in enumerate(prs.slides, 1):
    sh = by_id(sl).get(6)
    if sh is None or not sh.has_text_frame:
        continue
    for para in sh.text_frame.paragraphs:                 # keep the slide-number field, drop any typed copy of the number
        for r in para._p.findall(qn("a:r")):
            para._p.remove(r)
        for f in para._p.findall(qn("a:fld")):
            f.find(qn("a:t")).text = str(i)
prs.save(OUT)
print("saved", OUT, len(prs.slides))
