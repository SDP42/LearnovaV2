"""
Experiments for the Springer LNCS paper (our own components only, no lecture content).

E1  diagram sanitiser on crafted SVG answers (benign and hostile)
E2  lab-code gate on crafted model answers
E3  key-pool scheduler: wall time for 40 diagram requests vs number of keys (simulated, time scaled 1/10)
E4  dead-key failover: same run with some keys rejected
E5  grounding filter on crafted model answers for three of our own slides
E6  detector precision on 40 ordinary sentences written for this study

    /opt/anaconda3/bin/python scripts/research/lncs_data.py     # writes docs/research/papers/figs/lncs_*.{json,png}
"""
import json
import os
import pathlib
import re
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
SCALE = 10.0                                    # simulated seconds = real seconds / SCALE
os.environ["GEMINI_MIN_INTERVAL"] = str(4.2 / SCALE)
os.environ.setdefault("LEARNOVA_DATA_DIR", "/tmp/learnova_lncs_data")
OUT = ROOT / "docs" / "research" / "papers" / "figs"

from learnova.ai import topic_art, assist  # noqa: E402
from learnova.labs import auto  # noqa: E402
from learnova.explain import solve_text  # noqa: E402
from learnova.providers import gemini_provider as gp  # noqa: E402

BOX = '<rect x="{x}" y="40" width="120" height="60" rx="8" fill="PRIMARY"/>'
BASE = "".join(BOX.format(x=40 + 150 * i) for i in range(4)) + '<line x1="160" y1="70" x2="190" y2="70" stroke="ACCENT"/>'


def svg(extra: str = "", head: str = "", body: str = BASE) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 405"{head}>{body}{extra}<text x="60" y="80">Input</text></svg>'


UNSAFE = re.compile(r"<script|foreignObject|javascript:|\bon[a-z]+=|<iframe|<image|xlink:href=\"http|href=\"http|url\(http", re.I)

SVG_CASES = [
    ("Plain diagram, five shapes", svg()),
    ("Diagram wrapped in prose and a code fence", "Here is the diagram:\n```svg\n" + svg() + "\n```"),
    ("Gradient fill and arrow marker", svg('<defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient>'
                                           '<marker id="m"><path d="M0 0L6 3L0 6z"/></marker></defs><path d="M10 10L50 10" marker-end="url(#m)"/>')),
    ("Inline style attribute", svg('<circle cx="600" cy="300" r="20" style="fill:#f00;stroke:#000;font-size:14px"/>')),
    ("Script element", svg('<script>alert(1)</script>')),
    ("Event handler attribute", svg('<rect x="1" y="1" width="5" height="5" onclick="alert(1)"/>')),
    ("foreignObject with HTML", svg('<foreignObject width="100" height="50"><div xmlns="http://www.w3.org/1999/xhtml">hi</div></foreignObject>')),
    ("Embedded remote image", svg('<image href="http://example.com/x.png" width="10" height="10"/>')),
    ("Link element around shapes", svg('<a href="http://example.com"><rect x="1" y="1" width="5" height="5"/></a>')),
    ("External href on use", svg('<use href="http://example.com/s.svg#a"/>')),
    ("CSS url() to remote file", svg('<rect x="1" y="1" width="5" height="5" fill="url(http://example.com/a)"/>')),
    ("Animation elements", svg('<circle cx="5" cy="5" r="3"><animate attributeName="r" values="1;3"/></circle>')),
    ("Style sheet element", svg('<style>rect{fill:red}</style>')),
    ("Too few shapes (two)", svg(body='<rect x="1" y="1" width="5" height="5"/>')),
    ("Too many labels (35)", svg("".join(f'<text x="10" y="{10 + i * 10}">t{i}</text>' for i in range(35)))),
    ("Truncated answer (no closing tag)", svg()[:-10]),
    ("Malformed XML", svg('<rect x="1" y="1" width="5"')),
    ("Over-long label at right edge", svg('<text x="640" y="200" font-size="22">a label far too long for its place</text>')),
]


def e1_sanitiser():
    rows = []
    for name, raw in SVG_CASES:
        out = topic_art.clean_svg(raw, "#1E40AF", "#F97316")
        rows.append({"case": name, "accepted": out is not None, "unsafe_left": bool(out and UNSAFE.search(out)),
                     "removed": (len(raw) - len(out)) if out else None})
        if name.startswith("Over-long") and out:
            rows[-1]["font"] = re.findall(r'font-size="([\d.]+)"', out)
    return rows


GOOD_JS = ("const PRESETS=[{tag:'a',name:'n',desc:'d',input:{n:3}}];function fill(i){}function readInputs(){return {n:3}}"
           "function build(i){const F=[];for(let k=0;k<i.n;k++)F.push({k:'Step',title:'t',explain:'e',view:'v'});F.push({k:'Answer',title:'a',explain:'',view:''});return F}")
LAB_CASES = [
    ("Well-formed lab", GOOD_JS),
    ("Calls fetch()", GOOD_JS + "fetch('/x');"),
    ("Uses XMLHttpRequest", GOOD_JS + "new XMLHttpRequest();"),
    ("Dynamic import()", GOOD_JS + "import('x');"),
    ("Uses eval", GOOD_JS + "eval('1');"),
    ("Reads document.cookie", GOOD_JS + "let c=document.cookie;"),
    ("Writes localStorage", GOOD_JS + "localStorage.setItem('a','b');"),
    ("Closes the script tag", GOOD_JS + "'</script><script>alert(1)';"),
    ("Missing build()", GOOD_JS.replace("function build", "function make")),
    ("Missing PRESETS", GOOD_JS.replace("PRESETS", "EXAMPLES")),
    ("Syntax error", GOOD_JS + "function broken( {"),
    ("Answer is not JSON", None),
]


def e2_labs():
    from learnova.providers import router as r

    class Fake:
        def __init__(self, reply):
            self.reply = reply

        def generate(self, *a, **k):
            return self.reply

    rows = []
    orig_avail, orig_router = assist.llm_available, r.get_router
    assist.llm_available = lambda: True
    try:
        for name, js in LAB_CASES:
            reply = "Sorry, I cannot help." if js is None else json.dumps(
                {"title": "Test Lab", "lead": "x", "cond": "x", "inputs": "<input id=a>", "ideas": ["a"], "js": js})
            r.get_router = lambda reply=reply: Fake(reply)
            t0 = time.perf_counter()
            ok = auto._llm_lab("Topic", "text") is not None                    # noqa: SLF001
            rows.append({"case": name, "accepted": ok, "ms": round(1000 * (time.perf_counter() - t0), 1)})
    finally:
        assist.llm_available, r.get_router = orig_avail, orig_router
    return rows


LAT = 0.9                                         # simulated model latency (9 s real)
_dead: set = set()


def _fake_once(self, prompt, system_prompt, kwargs, *, minimal):
    gp._pace(self.api_key)                                          # noqa: SLF001
    if self.api_key in _dead:
        raise RuntimeError("429 RESOURCE_EXHAUSTED: quota per day")
    time.sleep(LAT)
    return "ok"


def run_pool(k: int, n: int = 40, dead=()):
    from concurrent.futures import ThreadPoolExecutor

    keys = [f"sim-key-{i}" for i in range(k)]
    os.environ["GEMINI_API_KEYS"] = ",".join(keys)
    _dead.clear()
    _dead.update(keys[i] for i in dead)
    gp._last_call.clear()                                           # noqa: SLF001
    gp._dead_keys.clear()                                           # noqa: SLF001
    workers = max(4, min(12, 2 * k))
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        got = list(pool.map(lambda _: topic_art._ask("x"), range(n)))  # noqa: SLF001
    return {"keys": k, "dead": len(dead), "workers": workers, "served": sum(g == "ok" for g in got),
            "real_s": round((time.monotonic() - t0) * SCALE, 1)}


def e3_e4_pool():
    from learnova.providers.gemini_provider import GeminiProvider

    GeminiProvider._generate_once = _fake_once                      # noqa: SLF001
    orig_avail = assist.llm_available
    assist.llm_available = lambda: False                            # no router fallback: a request either gets a key or nothing
    try:
        through = [run_pool(k) for k in range(1, 6)]
        fail = [run_pool(5, dead=(1, 3)), run_pool(5, dead=(0, 1, 2, 3)), run_pool(3, dead=(0, 1, 2))]
    finally:
        assist.llm_available = orig_avail
    return through, fail


# Three of our own slides about the system (no lecture content) and crafted model answers.
SLIDES = [
    {"id": 0, "title": "Key pool", "text": "The scheduler spaces requests per key and skips a rejected key for fifteen minutes before trying again."},
    {"id": 1, "title": "Sanitiser", "text": "The sanitiser removes scripts, links and remote images from model diagrams and keeps shapes, gradients and markers."},
    {"id": 2, "title": "Lab gate", "text": "Generated lab code must define presets and a build function and must pass a syntax check with Node before use."},
]
ANSWERS = [
    (0, "title", "The scheduler spaces requests so each key stays within its quota", "explain",
     "Each key has its own budget. The scheduler waits between requests on one key and skips a rejected key for fifteen minutes."),
    (0, "title", "Bananas are a rich source of potassium for athletes", "explain",
     "Bananas grow in tropical regions and are popular with runners because they contain potassium."),
    (1, "title", "Compare the sanitiser with a firewall", "explain", ""),
    (1, "title", "Sanitiser", "explain", ""),
    (1, "title", "The sanitiser removes scripts and remote images but keeps shapes, gradients and markers in every model diagram it receives "
                 "from any provider today", "explain", ""),
    (2, "title", "Generated lab code runs only after a Node syntax check", "explain",
     "The model writes presets and a build function. The code is syntax checked with Node and is rejected otherwise. " * 5),
    (2, "title", "Generated lab code runs only after a Node syntax check", "explain",
     "A build function returns frames; the presets give worked inputs, and Node checks the syntax before the page is used."),
]


def e5_grounding():
    from learnova.ai import assist as a

    rows = []
    orig_avail, orig_router = a.llm_available, a.get_router
    a.llm_available = lambda: True
    try:
        for sid, _, title, _, explain in ANSWERS:
            reply = json.dumps([{"id": sid, "title": title, "explain": explain, "example": "", "terms": []}])
            a.get_router = lambda reply=reply: type("F", (), {"generate": lambda self, *x, **k: reply})()
            res = a.ai_polish([SLIDES[sid]]).get(sid, {})
            rows.append({"slide": SLIDES[sid]["title"], "title": title, "title_kept": "title" in res,
                         "explain_words": len(explain.split()), "explain_kept": "explain" in res if explain else None})
    finally:
        a.llm_available, a.get_router = orig_avail, orig_router
    return rows


NEGATIVES = [
    "A slide deck is a sequence of pages shown during a lecture.", "The decision engine assigns one visual family to each slide.",
    "Students often revise from slides the night before an examination.", "The reader removes headers and footers that repeat on many pages.",
    "Each lab shows one small decision per frame.", "Teachers reuse decks from earlier years.", "The cache key is a hash of the content.",
    "Version 2 of the system was released in 2026.", "There are 3 ways to export a deck: PDF, PPTX and HTML.",
    "The score combines efficiency, load and coherence.", "Slide 12 shows the overall architecture.",
    "Our team has 4 students and one faculty guide.", "We tested the system on 7 decks from 3 courses.",
    "Up to 10 generated labs are attached to a deck.", "A key that fails is skipped for 15 minutes.",
    "Section 4 explains the solvers in detail.", "The free tier allows 15 requests per minute.",
    "Figure 3 compares the build times.", "The equation editor supports LaTeX input.", "A stepper has Step, Back and Play buttons.",
    "Visual families include process, timeline and comparison.", "The web deck uses Reveal.js for navigation.",
    "Each explainer ends with a short recap.", "In 2025 we started with a simple prototype.", "Learnova runs on a laptop without a GPU.",
    "The minimum font size on a slide is 11 points.", "Wide families keep the full width of the slide.",
    "A quiz is generated for every section.", "Probability questions appear in many courses.", "The derivative is a rate of change.",
    "Equations are rendered with MathJax.", "Every step has a title and a reason.", "Bayes' rule links a prior to a posterior.",
    "The mean is sensitive to outliers.", "Speed is distance divided by time.", "Interest can be simple or compound.",
    "The model was asked for 3 to 8 steps.", "A grammar has rules and symbols.", "The answer is checked by substitution.",
    "Ratio and percentage are taught in school.",
]


def e6_negatives():
    hits = []
    for s in NEGATIVES:
        ex = solve_text(s)
        if ex:
            hits.append({"sentence": s, "kind": ex.kind})
    return {"sentences": len(NEGATIVES), "false_detections": hits}


def figures(through, bench):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    ks = [r["keys"] for r in through]
    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    ax.plot(ks, [r["real_s"] for r in through], "o-", color="#1E40AF", label="measured (simulated run)")
    ax.plot(ks, [40 * max(4.2 / k, 9 / r["workers"]) for k, r in zip(ks, through)], "s--", color="#F97316",
            label=r"bound $N\max(\tau/k,\,L/w)$")
    ax.set_xlabel("number of keys $k$")
    ax.set_ylabel("seconds for 40 diagrams")
    ax.set_xticks(ks)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "lncs_pool.png", dpi=200)
    plt.close(fig)

    kinds = {}
    for r in bench:
        kinds.setdefault(r["got_kind"].replace(" decoding", "").replace(" equation", ""), []).append(r["steps"])
    order = sorted(kinds, key=lambda k: sum(kinds[k]) / len(kinds[k]))
    fig, ax = plt.subplots(figsize=(4.4, 3.2))
    ax.barh(order, [sum(kinds[k]) / len(kinds[k]) for k in order], color="#F97316")
    ax.set_xlabel("steps per explainer (mean)")
    fig.tight_layout()
    fig.savefig(OUT / "lncs_steps.png", dpi=200)
    plt.close(fig)


def main():
    e1 = e1_sanitiser()
    e2 = e2_labs()
    through, fail = e3_e4_pool()
    e5 = e5_grounding()
    e6 = e6_negatives()
    bench = json.loads((OUT / "explainer_bench.json").read_text())["rows"]
    figures(through, bench)
    # measured with the code before dead keys were remembered (commit 37b5b7f), same settings
    data_before = [{"keys": 5, "dead": 2, "real_s": 73.1, "served": 40}, {"keys": 5, "dead": 4, "real_s": 175.4, "served": 40},
                   {"keys": 3, "dead": 3, "real_s": 166.3, "served": 0}]
    data = {"sanitiser": e1, "labs": e2, "pool": through, "failover": fail, "failover_before": data_before, "grounding": e5, "negatives": e6}
    (OUT / "lncs_data.json").write_text(json.dumps(data, indent=1))
    for k, v in data.items():
        print(f"== {k}")
        for row in (v if isinstance(v, list) else [v]):
            print("  ", row)


if __name__ == "__main__":
    main()
