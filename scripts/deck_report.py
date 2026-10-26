"""
Text report of what the engine decided for every slide — cheap to read, no rendering.

    python scripts/deck_report.py demo/corpus/history_revolution.md [more files …]
"""
import logging
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
logging.disable(logging.CRITICAL)
from learnova.config import apply_runtime_env  # noqa: E402

apply_runtime_env()
from learnova.parsers.markdown_converter import from_typed_text  # noqa: E402
from learnova.pipeline.orchestrator import PipelineConfig, generate, run_all  # noqa: E402
from learnova.rendering.deck_director import plan_deck  # noqa: E402


def report(path: pathlib.Path, show_text: bool = False) -> None:
    cfg = PipelineConfig(enable_quizzes=True, quiz_frequency=3, enable_enhancement=False, enable_vision_ocr=False)
    res = run_all(str(path), config=cfg) if path.suffix.lower() in {".pdf", ".pptx"} else generate(from_typed_text(path.read_text(), path.stem), cfg)
    deck = res.final_deck
    plan = plan_deck(deck)
    print(f"\n=== {path.name}: {len(deck)} slides")
    for i, e in enumerate(deck):
        imp = e.get("improved") or {}
        sp = plan.by_index(i)
        if str(imp.get("layout_type", "")).upper() == "QUIZ":
            print(f"{i + 1:>2} QUIZ        {imp.get('title', '')[:60]}")
            continue
        words = len(" ".join(map(str, imp.get("bullets") or [])).split())
        print(f"{i + 1:>2} {sp.family:<17}{(sp.variant or '')[:8]:<9}{sp.confidence:.2f} w={words:<3} {imp.get('title', '')[:70]}")
        if show_text:
            for b in (imp.get("bullets") or [])[:6]:
                print(f"      · {str(b)[:110]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    for a in args:
        report(pathlib.Path(a), show_text="--text" in sys.argv)
