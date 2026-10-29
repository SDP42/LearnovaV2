"""
Robustness run on inputs the system was never tuned on: every file must build, and the finished PPTX must pass the layout audit.

    python scripts/research/robustness.py <out.json> <file or "topic:..."> ...
"""
import json
import pathlib
import sys
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from learnova.config import apply_runtime_env  # noqa: E402

apply_runtime_env()
from learnova.evaluation.layout_audit import audit_pptx  # noqa: E402
from learnova.parsers.markdown_converter import from_typed_text  # noqa: E402
from learnova.pipeline.orchestrator import PipelineConfig, generate, run_all  # noqa: E402

out, inputs = sys.argv[1], sys.argv[2:]
rows = []
for item in inputs:
    t0 = time.time()
    row = {"input": item[:80]}
    try:
        if item.startswith("topic:"):
            res = generate(from_typed_text(item[6:], "typed topic"), PipelineConfig())
        else:
            res = run_all(item, source_name=pathlib.Path(item).name, config=PipelineConfig())
        rep = audit_pptx(res.pptx_bytes)
        row.update(ok=True, seconds=round(time.time() - t0, 1), slides=len(res.final_deck),
                   audit={k: v for k, v in rep.items() if k != "slides"},
                   issues=[(s["index"], s.get("issues")) for s in rep.get("slides", []) if s.get("issues")][:12])
    except Exception as exc:
        row.update(ok=False, seconds=round(time.time() - t0, 1), error=f"{type(exc).__name__}: {exc}"[:300],
                   trace=traceback.format_exc()[-1200:])
    rows.append(row)
    print(json.dumps({k: row.get(k) for k in ("input", "ok", "seconds", "slides", "error")}), flush=True)
pathlib.Path(out).write_text(json.dumps(rows, indent=1, default=str))
