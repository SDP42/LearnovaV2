"""
Vendor a curated subset of Lucide icons (ISC licence, https://lucide.dev) into
src/learnova/visuals/icons.json so the backend can draw illustrations and card
icons with no frontend/node dependency.

Run:  python scripts/vendor_icons.py
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "node_modules" / "lucide-react" / "dist" / "esm" / "icons"
OUT = ROOT / "src" / "learnova" / "visuals" / "icons.json"

NAMES = """book-open lightbulb brain atom leaf globe settings chart-column rocket clock heart shield-check laptop
flask-conical users cloud search target calendar dollar-sign trophy trees droplets sun zap puzzle key map-pin smartphone
mail graduation-cap microscope dna calculator code database network lock award flag compass layers git-branch factory
truck building-2 landmark scale gavel stethoscope pill activity apple dumbbell bed music palette camera film plane car
wifi cpu bot sparkles message-circle megaphone handshake trending-up chart-pie coins wallet shopping-cart store house
book pencil ruler telescope magnet thermometer mountain waves flame snowflake wind recycle battery-charging circuit-board
file-text clipboard-list list-checks bookmark eye ear hand-heart baby brush scissors wrench hammer hourglass infinity
sigma function-square triangle square circle star moon bell gift globe-2 languages map route anchor ship bike footprints
newspaper presentation lectern school library notebook-pen test-tube-diagonal bug shield alert-triangle check-circle
arrow-right-left refresh-cw repeat workflow split merge funnel gauge percent receipt banknote piggy-bank building
briefcase user-round crown medal""".split()


def parse(js: str):
    els = []
    for m in re.finditer(r'\[\s*"(\w+)"\s*,\s*\{(.*?)\}\s*\]', js, re.S):
        tag, body = m.group(1), m.group(2)
        attrs = {k: v for k, v in re.findall(r'(\w+)\s*:\s*"([^"]*)"', body) if k != "key"}
        els.append([tag, attrs])
    return els


def main():
    data = {}
    for n in NAMES:
        f = SRC / f"{n}.js"
        if not f.exists():
            continue
        els = parse(f.read_text())
        if els:
            data[n] = els
    OUT.write_text(json.dumps({"license": "ISC — Lucide (https://lucide.dev)", "icons": data}, separators=(",", ":")))
    print(f"{len(data)} icons -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
