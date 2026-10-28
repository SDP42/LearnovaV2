"""
Numbers and figures for the research papers, all computed from the system itself (no API key).

    python scripts/research/paper_data.py <out_dir> name=source[:pages] ...

Writes paper_data.json and PNG figures:
  * PSF (deck score, mean load L, information efficiency E, coherence C) of each source deck read as-is versus the rebuilt deck;
  * CLASS versus even splitting on every overloaded section (total cost, slides, load of the worst slide);
  * visual-family distribution over all rebuilt decks; time against pages; gold-set accuracy.
"""
import collections
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
for k in ("GEMINI_API_KEY", "GEMINI_API_KEYS", "GROQ_API_KEY", "NVIDIA_API_KEY"):
    os.environ[k] = ""
import logging  # noqa: E402

logging.disable(logging.CRITICAL)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from learnova.scoring.psf import DEFAULT_PARAMS, _group_cost, psf_deck, segment_blocks  # noqa: E402

OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
C1, C2, C3, C4 = "#1F5FBF", "#F27A2E", "#168455", "#6B3FA0"


def source_deck(path: str):
    """The source as slides, exactly as written (title + bullets + picture flag)."""
    from learnova.parsers.markdown_converter import pptx_to_pdf
    from learnova.parsers.slide_pdf import read_slide_pdf

    pdf = pptx_to_pdf(path) if path.endswith(".pptx") else path
    pages = read_slide_pdf(pdf, ocr=False, previews=False)["pages"]
    deck = []
    for p in pages:
        bullets = [i["text"] for i in p["items"]] + [" | ".join(r) for t in p["tables"] for r in t]
        deck.append({"original": {"image": {"bytes": b"x"} if p["figure"] else None},
                     "improved": {"title": p["title"] or "", "bullets": bullets, "layout_type": "MINIMAL_TEXT"}})
    return deck, len(pages)


def rebuilt_deck(path: str):
    from learnova.pipeline.orchestrator import PipelineConfig, run_all

    t0 = time.time()
    res = run_all(path, config=PipelineConfig(enable_enhancement=False, enable_vision_ocr=False, enable_quizzes=True))
    return res.final_deck, time.time() - t0


def summary(deck):
    r = psf_deck(deck)
    s = r["slide_scores"] or [{"E": 0, "L": 0, "C": 0, "psf": 0}]
    mean = lambda k: round(sum(x[k] for x in s) / len(s), 3)  # noqa: E731
    return {"psf_deck": r["psf_deck"], "E": mean("E"), "L": mean("L"), "C": mean("C"), "psf_mean": mean("psf"),
            "overloaded": sum(1 for x in s if x["L"] > 0.5)}


data = {"decks": {}, "class": [], "families": collections.Counter()}
for arg in sys.argv[2:]:
    name, path = arg.split("=", 1)
    src, pages = source_deck(path)
    out, secs = rebuilt_deck(path)
    from learnova.rendering.deck_director import plan_deck

    fams = collections.Counter(sp.family for sp in plan_deck(out).slides)
    data["families"].update(fams)
    data["decks"][name] = {"pages": pages, "slides": len(out), "seconds": round(secs, 1),
                           "before": summary(src), "after": summary(out)}
    # CLASS against even splitting, on every source slide that has more than 6 points
    for e in src:
        b = [x for x in e["improved"]["bullets"] if x.strip()]
        if len(b) <= 6:
            continue
        cap = 5
        cls = segment_blocks(b, max_per_slide=cap)
        k = -(-len(b) // cap)
        base, extra = divmod(len(b), k)
        even, i = [], 0
        for j in range(k):
            n = base + (1 if j < extra else 0)
            even.append(b[i:i + n])
            i += n
        cost = lambda groups: sum(_group_cost(g, DEFAULT_PARAMS, soft_target=4) + DEFAULT_PARAMS.lambda_slide for g in groups)  # noqa: E731
        worst = lambda groups: max(_group_cost(g, DEFAULT_PARAMS, soft_target=4) for g in groups)  # noqa: E731
        data["class"].append({"deck": name, "points": len(b), "class_cost": round(cost(cls), 3), "even_cost": round(cost(even), 3),
                              "class_slides": len(cls), "even_slides": len(even), "class_worst": round(worst(cls), 3), "even_worst": round(worst(even), 3)})
    print(name, data["decks"][name], flush=True)

data["families"] = dict(data["families"].most_common())
json.dump(data, open(OUT / "paper_data.json", "w"), indent=1)

names = list(data["decks"])
x = range(len(names))
# Fig: PSF before/after
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6))
bw = 0.38
ax[0].bar([i - bw / 2 for i in x], [data["decks"][n]["before"]["psf_mean"] for n in names], bw, color="#B8C2D0", label="source deck")
ax[0].bar([i + bw / 2 for i in x], [data["decks"][n]["after"]["psf_mean"] for n in names], bw, color=C1, label="Learnova deck")
ax[0].set_xticks(list(x), names, rotation=20)
ax[0].set_ylabel("mean PSF")
ax[0].legend(frameon=False, fontsize=8)
ax[0].set_title("(a) Pedagogical Slide Fitness")
ax[1].bar([i - bw / 2 for i in x], [data["decks"][n]["before"]["L"] for n in names], bw, color="#B8C2D0", label="source deck")
ax[1].bar([i + bw / 2 for i in x], [data["decks"][n]["after"]["L"] for n in names], bw, color=C2, label="Learnova deck")
ax[1].set_xticks(list(x), names, rotation=20)
ax[1].set_ylabel("mean cognitive load L")
ax[1].legend(frameon=False, fontsize=8)
ax[1].set_title("(b) Estimated cognitive load (lower is better)")
fig.tight_layout()
fig.savefig(OUT / "fig_psf.png", dpi=220)
# Fig: CLASS vs even
cl = data["class"]
if cl:
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.scatter([c["even_cost"] for c in cl], [c["class_cost"] for c in cl], s=12, color=C1, alpha=0.75)
    lim = max(max(c["even_cost"] for c in cl), max(c["class_cost"] for c in cl)) * 1.05
    ax.plot([0, lim], [0, lim], "--", color="#888", lw=0.8)
    ax.set_xlabel("even split: total cost")
    ax.set_ylabel("CLASS: total cost")
    ax.set_title("CLASS vs even splitting")
    fig.tight_layout()
    fig.savefig(OUT / "fig_class.png", dpi=220)
# Fig: time vs pages
fig, ax = plt.subplots(figsize=(3.5, 2.6))
ax.scatter([data["decks"][n]["pages"] for n in names], [data["decks"][n]["seconds"] for n in names], color=C3)
for n in names:
    ax.annotate(n, (data["decks"][n]["pages"], data["decks"][n]["seconds"]), fontsize=7, xytext=(3, 3), textcoords="offset points")
ax.set_xlabel("source pages")
ax.set_ylabel("upload to finished deck (s)")
ax.set_title("Run time without an API key")
fig.tight_layout()
fig.savefig(OUT / "fig_time.png", dpi=220)
# Fig: family distribution
fams = list(data["families"].items())[:14]
fig, ax = plt.subplots(figsize=(3.5, 2.8))
ax.barh([f.replace("_", " ").lower() for f, _ in fams][::-1], [v for _, v in fams][::-1], color=C4)
ax.set_xlabel("slides")
ax.set_title("Visual families chosen (all decks)")
fig.tight_layout()
fig.savefig(OUT / "fig_families.png", dpi=220)
print("figures written to", OUT)
