"""
Native table recovery for PDFs.

Markdown converters flatten tables badly: a cell per bullet, or one row broken
across several lines. PyMuPDF's table finder reads the ruling lines and returns
real rows and columns, so for every page that has a table we

1. extract the table as a clean grid (multi-line cells joined, empty rows/columns
   dropped, a header row detected),
2. remove the converter's fragments of that table from the page's markdown
   (lines whose words are all table words), and
3. append the table as a ``[TABLE DATA]`` block of ``| a | b |`` rows.

The decision engine then draws it as a real table instead of guessing at cards.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from learnova.logging_config import logger

TABLE_SENTINEL = "[TABLE DATA]"
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]*")
_PAGE = re.compile(r"^##\s+Page\s+(\d+)\s*$", re.M)


def _clean_cell(c) -> str:
    return re.sub(r"\s+", " ", str(c or "").replace("\n", " ")).strip()


def _grid(rows: List[List]) -> List[List[str]]:
    g = [[_clean_cell(c) for c in r] for r in rows]
    g = [r for r in g if any(r)]
    if not g:
        return []
    width = max(len(r) for r in g)
    g = [r + [""] * (width - len(r)) for r in g]
    keep = [j for j in range(width) if any(r[j] for r in g)]
    g = [[r[j] for j in keep] for r in g]
    # a row whose only filled cell is the first is a spanning caption → keep, but it can't be a header
    return g


def _looks_like_header(row: List[str]) -> bool:
    cells = [c for c in row if c]
    if len(cells) < 2:
        return False
    numeric = sum(1 for c in cells if re.fullmatch(r"[\d.,%$\s-]+", c))
    return numeric <= len(cells) // 3 and all(len(c.split()) <= 8 for c in cells)


def page_tables(page) -> List[Dict]:
    """Clean tables on a page: [{rows: [[str]], bbox: (x0,y0,x1,y1)}]."""
    out: List[Dict] = []
    try:
        found = page.find_tables()
    except Exception:  # find_tables needs a recent PyMuPDF; never block conversion
        return out
    for t in getattr(found, "tables", []):
        try:
            g = _grid(t.extract())
        except Exception:
            continue
        if len(g) >= 2 and len(g[0]) >= 2:
            out.append({"rows": g, "bbox": tuple(t.bbox)})
    return out


def table_markdown(rows: List[List[str]]) -> str:
    caps: List[str] = []
    while len(rows) > 2 and sum(1 for c in rows[0] if c) == 1:  # a spanning caption row, not a header
        caps.append(next(c for c in rows[0] if c))
        rows = rows[1:]
    head = rows[0] if _looks_like_header(rows[0]) else [f"Col {i + 1}" for i in range(len(rows[0]))]
    body = rows[1:] if _looks_like_header(rows[0]) else rows
    esc = lambda c: c.replace("|", "/")  # noqa: E731
    lines = [TABLE_SENTINEL, "| " + " | ".join(esc(h) for h in head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    lines += ["| " + " | ".join(esc(c) for c in r) + " |" for r in body]
    return ("\n".join(f"**{c}**" for c in caps) + "\n\n" if caps else "") + "\n".join(lines)


def _words(rows: List[List[str]]) -> Set[str]:
    return {w.lower() for r in rows for c in r for w in _WORD.findall(c)}


def _strip_fragments(section: str, tables: List[Dict]) -> str:
    """Drop lines made (almost) only of table words — the converter's broken copy of the table."""
    tw = set()
    for t in tables:
        tw |= _words(t["rows"])
    kept = []
    for line in section.split("\n"):
        if line.startswith("##") or not line.strip():
            kept.append(line)
            continue
        ws = [w.lower() for w in _WORD.findall(line)]
        if ws and sum(1 for w in ws if w in tw) / len(ws) >= 0.85 and len(ws) >= 1 and not line.startswith(TABLE_SENTINEL):
            continue
        kept.append(line)
    return "\n".join(kept)


def inject_native_tables(pdf_path: str, markdown: str) -> str:
    """Replace the converter's broken tables with clean ones. Returns the markdown unchanged on any problem."""
    try:
        import fitz

        doc = fitz.open(pdf_path)
    except Exception:
        return markdown
    per_page: Dict[int, List[Dict]] = {}
    for i, page in enumerate(doc):
        tabs = page_tables(page)
        if tabs:
            per_page[i + 1] = tabs
    if not per_page:
        return markdown
    parts = _PAGE.split(markdown)
    if len(parts) < 3:  # no "## Page N" structure: append tables per page at the end
        extra = "\n\n".join(f"## Page {p}\n" + "\n\n".join(table_markdown(t["rows"]) for t in tabs) for p, tabs in per_page.items())
        return markdown.rstrip() + "\n\n" + extra + "\n"
    pieces = [parts[0]]
    n_tables = 0
    for k in range(1, len(parts), 2):
        pno, body = int(parts[k]), parts[k + 1]
        tabs = per_page.get(pno)
        if tabs:
            body = _strip_fragments(body, tabs).rstrip() + "\n\n" + "\n\n".join(table_markdown(t["rows"]) for t in tabs) + "\n"
            n_tables += len(tabs)
        pieces.append(f"## Page {pno}{body}")
    logger.info("pdf tables: recovered %d native table(s) on %d page(s)", n_tables, len(per_page))
    return "".join(pieces)


def parse_table_block(text: str) -> Optional[Dict]:
    """Parse the first ``| a | b |`` table found in ``text`` → {headers, rows, before, after}."""
    lines = text.split("\n")
    idx = [i for i, l in enumerate(lines) if l.strip().startswith("|") and l.strip().endswith("|")]
    if len(idx) < 3:
        return None
    start = idx[0]
    run = [start]
    for i in idx[1:]:
        if i == run[-1] + 1:
            run.append(i)
        else:
            break
    rows = []
    has_sep = False
    for i in run:
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            has_sep = True
            continue
        rows.append(cells)
    if not has_sep:  # loose pipe fragments from a converter are not a table
        return None
    if len(rows) < 2:
        return None
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    rest = [l for j, l in enumerate(lines) if j not in set(run) and l.strip() != TABLE_SENTINEL]
    return {"headers": rows[0], "rows": rows[1:], "rest": "\n".join(rest).strip()}


def split_tables(text: str) -> List[Dict]:
    """Walk ``text`` and return ordered segments: {"kind": "prose", "text"} / {"kind": "table", headers, rows, caption}."""
    lines = text.split("\n")
    segs: List[Dict] = []
    prose: List[str] = []
    i, n = 0, len(lines)

    def flush():
        t = "\n".join(prose).strip()
        if t:
            segs.append({"kind": "prose", "text": t})
        prose.clear()

    while i < n:
        ln = lines[i].strip()
        if ln.startswith("|") and ln.endswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|") and lines[j].strip().endswith("|"):
                j += 1
            block = parse_table_block("\n".join(lines[i:j]))
            if block:
                caption = ""
                while prose and not prose[-1].strip():
                    prose.pop()
                if prose and re.fullmatch(r"\*\*(.+)\*\*", prose[-1].strip()):
                    caption = re.fullmatch(r"\*\*(.+)\*\*", prose.pop().strip()).group(1)
                flush()
                segs.append({"kind": "table", "headers": block["headers"], "rows": block["rows"], "caption": caption})
                i = j
                continue
        if ln != TABLE_SENTINEL:
            prose.append(lines[i])
        i += 1
    flush()
    return segs
