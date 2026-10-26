"""
Render a deck to images so layout can be inspected without opening PowerPoint.

    python scripts/render_preview.py demo/sample_syllabus.md [theme_id] [max_slides]
    python scripts/render_preview.py ~/Desktop/some.pdf
    python scripts/render_preview.py demo/sample_ml.md auto 6 template=editorial   # structural template

Writes demo/output/preview.pptx, preview.pdf, preview_sheet.png (contact sheet) and preview_NN.png (one per slide,
first ``max_slides``). Needs LibreOffice (``soffice``) for the PDF step.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from learnova.config import apply_runtime_env  # noqa: E402

apply_runtime_env()
from learnova.parsers.markdown_converter import from_typed_text  # noqa: E402
from learnova.pipeline.orchestrator import PipelineConfig, generate, run_all  # noqa: E402

src = pathlib.Path([a for a in sys.argv[1:] if "=" not in a][0]).expanduser()
_opts = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in sys.argv[1:] if "=" in a}
_pos = [a for a in sys.argv[1:] if "=" not in a]
theme = _pos[1] if len(_pos) > 1 and not _pos[1].isdigit() else "auto"
limit = int(_pos[-1]) if _pos[-1].isdigit() else 12
cfg = PipelineConfig(theme_id=theme, theme_spec=({"template_id": _opts["template"]} if "template" in _opts else None), enable_quizzes=True, quiz_frequency=3, enable_enhancement=False, enable_vision_ocr=False)
res = run_all(str(src), config=cfg) if src.suffix.lower() in {".pdf", ".pptx"} else generate(from_typed_text(src.read_text(), src.stem), cfg)

out = ROOT / "demo" / "output"
out.mkdir(parents=True, exist_ok=True)
pptx = out / "preview.pptx"
pptx.write_bytes(res.pptx_bytes)
soffice = shutil.which("soffice") or "/opt/homebrew/bin/soffice"
subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out), str(pptx)], capture_output=True)

import fitz  # noqa: E402
from PIL import Image  # noqa: E402

doc = fitz.open(str(out / "preview.pdf"))
tiles = []
for i, page in enumerate(list(doc)[:limit]):
    pix = page.get_pixmap(dpi=80)
    im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    im.save(out / f"preview_{i + 1:02d}.png")
    tiles.append(im.resize((pix.width // 2, pix.height // 2)))
cols = 3
w, h = tiles[0].size
sheet = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)), "white")
for i, im in enumerate(tiles):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out / "preview_sheet.png")
print(f"{len(doc)} slides rendered; sheet: {out / 'preview_sheet.png'}")
