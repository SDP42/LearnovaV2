"""Interactive labs: self-contained HTML simulations that let a student *play* with a hard idea (seed a region, step an algorithm).

A lab is one HTML file. Its topics come from ``<meta name="learnova-topics" content="a, b, c">`` and its name from ``<title>``.
Built-in labs live in ``labs/builtin``; teachers can add their own (``.data/labs`` or ``POST /api/labs``). A slide whose title
names a lab's topic gets that lab: an overlay in the web deck and a clickable button in the PowerPoint.
"""

from __future__ import annotations

import html as _html
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from learnova.config import DATA_DIR

BUILTIN = Path(__file__).parent / "builtin"
USER_DIR = DATA_DIR / "labs"
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,60}$")


def _meta(text: str) -> Dict[str, object]:
    t = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
    m = re.search(r'<meta\s+name="learnova-topics"\s+content="([^"]+)"', text, re.I)
    topics = [x.strip().lower() for x in (m.group(1).split(",") if m else []) if x.strip()]
    return {"name": _html.unescape(t.group(1).strip()) if t else "Interactive lab", "topics": topics}


def _files() -> List[Path]:
    out = sorted(BUILTIN.glob("*.html"))
    if USER_DIR.is_dir():
        out += sorted(USER_DIR.glob("*.html"))
    return out


@lru_cache(maxsize=1)
def _catalog_cached(stamp: tuple) -> List[Dict[str, object]]:
    labs = []
    for f in _files():
        try:
            info = _meta(f.read_text(encoding="utf-8", errors="ignore")[:6000])
        except OSError:
            continue
        if info["topics"]:
            labs.append({"id": f.stem, "builtin": f.parent == BUILTIN, **info})
    return labs


def catalog() -> List[Dict[str, object]]:
    stamp = tuple((f.name, f.stat().st_mtime) for f in _files())
    return _catalog_cached(stamp)


def lab_html(lab_id: str) -> Optional[str]:
    if not _SAFE_ID.match(lab_id or ""):
        return None
    for d in (USER_DIR, BUILTIN):
        p = d / f"{lab_id}.html"
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="ignore")
    return None


def lab_url(lab_id: str) -> str:
    """Where a PowerPoint button sends the student: this server's public lab page (set LEARNOVA_PUBLIC_URL when deployed)."""
    import os

    return f"{os.getenv('LEARNOVA_PUBLIC_URL', 'http://localhost:8000').rstrip('/')}/api/labs/{lab_id}"


def find_lab(title: str, text: str = "") -> Optional[Dict[str, object]]:
    """The lab for a slide: a topic phrase in the title, or one named twice in the body."""
    t, b = (title or "").lower(), (text or "").lower()
    best = None
    for lab in catalog():
        for topic in lab["topics"]:
            pat = rf"\b{re.escape(topic)}\b"
            score = 2 if re.search(pat, t) else (1 if len(re.findall(pat, b)) >= 2 else 0)
            if score and (best is None or score > best[0]):
                best = (score, lab)
    return best[1] if best else None


def save_lab(lab_id: str, html_text: str, topics: List[str]) -> Dict[str, object]:
    """Store a teacher's own lab. The topics are written into the file so it is self-describing."""
    if not _SAFE_ID.match(lab_id):
        raise ValueError("lab id: lower-case letters, digits, - and _ only")
    if "<html" not in html_text.lower() or len(html_text) > 2_000_000:
        raise ValueError("a lab must be one HTML page under 2 MB")
    clean = [re.sub(r"[^\w \-]", "", x).strip().lower() for x in topics if x.strip()][:12]
    if not clean:
        raise ValueError("give at least one topic")
    html_text = re.sub(r'<meta\s+name="learnova-topics"[^>]*>\s*', "", html_text, flags=re.I)
    tag = f'<meta name="learnova-topics" content="{_html.escape(", ".join(clean))}">'
    html_text = re.sub(r"<head[^>]*>", lambda m: m.group(0) + "\n" + tag, html_text, count=1, flags=re.I) if re.search(r"<head", html_text, re.I) else tag + html_text
    USER_DIR.mkdir(parents=True, exist_ok=True)
    (USER_DIR / f"{lab_id}.html").write_text(html_text, encoding="utf-8")
    return {"id": lab_id, **_meta(html_text)}
