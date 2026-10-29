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
        flags = {}
        for sl in rep["per_slide"][1:]:
            for f in sl["flags"]:
                flags[f.split(":")[0]] = flags.get(f.split(":")[0], 0) + 1
        row.update(ok=True, seconds=round(time.time() - t0, 1), slides=rep["slides"], flagged=rep["flagged"],
                   flagged_pct=rep["flagged_pct"], coverage=rep["mean_coverage"], min_pt=rep["min_pt"], flags=flags,
                   examples=[(sl["index"], sl["flags"]) for sl in rep["per_slide"] if sl["flags"]][:8])
    except Exception as exc:
        row.update(ok=False, seconds=round(time.time() - t0, 1), error=f"{type(exc).__name__}: {exc}"[:300],
                   trace=traceback.format_exc()[-1200:])
    rows.append(row)
    print(json.dumps({k: row.get(k) for k in ("input", "ok", "seconds", "slides", "flagged", "flags", "min_pt", "error")}), flush=True)
pathlib.Path(out).write_text(json.dumps(rows, indent=1, default=str))
