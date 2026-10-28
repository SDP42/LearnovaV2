"""Build a deck from a real file exactly as the app does (keys from .env), then render pages to PNG for inspection.

    python scripts/research/render_real.py <file> <out_dir> [pages to render, e.g. 1-12]
"""
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from learnova.config import apply_runtime_env  # noqa: E402

apply_runtime_env()
import fitz  # noqa: E402

from learnova.pipeline.orchestrator import PipelineConfig, run_all  # noqa: E402

src, out = pathlib.Path(sys.argv[1]).expanduser(), pathlib.Path(sys.argv[2])
a, b = (sys.argv[3] if len(sys.argv) > 3 else "1-12").split("-")
out.mkdir(parents=True, exist_ok=True)
t0 = time.time()
res = run_all(str(src), source_name=src.stem, config=PipelineConfig())
print(f"built in {time.time() - t0:.0f}s, slides={len(res.final_deck) if hasattr(res, 'final_deck') else '?'}")
pp = out / "deck.pptx"
pp.write_bytes(res.pptx_bytes)
(out / "deck.html").write_bytes(res.html_bytes or b"")
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out), str(pp)], capture_output=True, timeout=300)
doc = fitz.open(out / "deck.pdf")
print("pages", len(doc))
for i in range(int(a) - 1, min(int(b), len(doc))):
    doc[i].get_pixmap(dpi=60).save(out / f"p{i + 1:02d}.png")
