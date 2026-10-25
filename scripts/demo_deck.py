"""
Build the demo deck offline (no keys, no server) so a presentation never depends on live generation.

    python scripts/demo_deck.py [path/to/syllabus.md] [theme_id]

Writes demo/output/demo.pptx, demo/output/demo.html and demo/output/analysis.json,
and prints the before/after summary.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from learnova.analysis import build_analysis  # noqa: E402
from learnova.config import apply_runtime_env  # noqa: E402
from learnova.parsers.markdown_converter import from_typed_text  # noqa: E402
from learnova.pipeline.orchestrator import PipelineConfig, generate  # noqa: E402

apply_runtime_env()
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "demo" / "sample_syllabus.md"
theme = sys.argv[2] if len(sys.argv) > 2 else "auto"
out = ROOT / "demo" / "output"
out.mkdir(parents=True, exist_ok=True)

res = generate(from_typed_text(src.read_text(), "Learnova Demo Deck"),
               PipelineConfig(theme_id=theme, enable_quizzes=True, quiz_frequency=3, enable_enhancement=False, enable_vision_ocr=False))
(out / "demo.pptx").write_bytes(res.pptx_bytes)
(out / "demo.html").write_bytes(res.html_bytes)
analysis = build_analysis(res)
(out / "analysis.json").write_text(json.dumps(analysis, indent=2, default=str))
print(json.dumps(analysis["summary"], indent=2))
print(f"\nwrote {out}/demo.pptx, demo.html, analysis.json")
