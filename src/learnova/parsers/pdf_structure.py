"""
Structure-aware PDF → markdown for reports, theses and papers.

Converters treat a PDF as a stream of text, so page furniture (running headers, "Page 4" footers), tables and lists
leak into the content. This reader rebuilds the *logical* structure from layout instead:

* **running headers / footers** — text in the top or bottom band that repeats on ≥ 50 % of pages is dropped;
* **headings** — numbered ("1.", "1.2", "2.3.1") or typographically larger / bold short lines; depth from numbering;
* **tables** — ruled tables via PyMuPDF; borderless ones are accepted only when a "Table N" caption sits next to them;
  the caption becomes the table title;
* **lists** — bullet / numbered items kept as items, continuation lines joined;
* **paragraphs** — lines joined, hyphenation repaired;
* **front matter** — title page, certificate, declaration, acknowledgements, contents and lists of figures are left out
  (the document title is detected from the largest text on page 1 and used as the deck title).

Returns ``None`` when the document does not look structured (then the generic converter is used).
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from learnova.logging_config import logger
from learnova.parsers.pdf_tables import page_tables, table_markdown

_NUM_HEAD = re.compile(r"^(\d+(?:\.\d+){0,3})[.)]?\s+(\S.*)$")
_LIST = re.compile(r"^\s*(?:[•●▪◦·–—-]|\(?\d{1,2}[.)]|\(?[a-z][.)]|\[\d{1,3}\])\s*(\S.*)$")
_NAMED_HEAD = re.compile(r"^(references|bibliography|appendix(?:\s+[A-Z0-9])?|abstract|conclusions?|introduction|future work|acknowledg\w+)\s*$", re.I)
_CAPTION = re.compile(r"^(Table|Fig(?:ure)?\.?)\s*(\d+)\s*[.:–-]?\s*(.*)$", re.I)
_SKIP_TITLES = re.compile(r"^(certificate|declaration|acknowledg\w*|table of contents|contents|list of (figures|tables|abbreviations|symbols)|"
                          r"approval|preface|dedication)\b", re.I)
_KEEP_FRONT = re.compile(r"^(abstract|summary|executive summary)\b", re.I)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", t.lower())).strip()


class _Line:
    __slots__ = ("text", "size", "bold", "x0", "y0", "x1", "y1", "block", "page", "kind")

    def __init__(self, text, size, bold, bbox, block, page):
        self.text, self.size, self.bold = text, size, bold
        self.x0, self.y0, self.x1, self.y1 = bbox
        self.block, self.page, self.kind = block, page, ""


def _page_lines(page, pno: int) -> List[_Line]:
    out: List[_Line] = []
    d = page.get_text("dict")
    for b_i, b in enumerate(d.get("blocks", [])):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            spans = [s for s in ln.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans).strip()
            chars = sum(len(s["text"]) for s in spans)
            size = sum(s["size"] * len(s["text"]) for s in spans) / max(1, chars)
            bold = all((s["flags"] & 16) or "bold" in s["font"].lower() for s in spans)
            out.append(_Line(text, round(size, 1), bold, ln["bbox"], b_i, pno))
    return out


def _tables(page, lines: List[_Line]) -> Tuple[List[Dict], List[_Line]]:
    """Tables on the page (+ captions); returns (tables, lines with table text and captions removed)."""
    tabs = page_tables(page)
    caps = [l for l in lines if _CAPTION.match(l.text) and l.text.lower().startswith("table")]
    if not tabs and caps:  # borderless table next to a caption
        try:
            for t in page.find_tables(strategy="text").tables:
                g = [[re.sub(r"\s+", " ", str(c or "")).strip() for c in r] for r in t.extract()]
                g = [r for r in g if any(r)]
                if len(g) >= 3 and 2 <= len(g[0]) <= 8 and statistics.mean(len(c.split()) for r in g for c in r if c) <= 14:
                    tabs.append({"rows": g, "bbox": tuple(t.bbox)})
        except Exception:
            pass
    keep = list(lines)
    for t in tabs:
        x0, y0, x1, y1 = t["bbox"]
        keep = [l for l in keep if not (x0 - 3 <= (l.x0 + l.x1) / 2 <= x1 + 3 and y0 - 3 <= (l.y0 + l.y1) / 2 <= y1 + 3)]
        best, dist = None, 1e9
        for c in caps:
            d = min(abs(c.y1 - y0), abs(c.y0 - y1))
            if d < dist and d < 70:
                best, dist = c, d
        t["caption"] = re.sub(r"\s+", " ", best.text).strip() if best else ""
        if best is not None:
            keep = [l for l in keep if l is not best]
            # a caption can wrap onto the next line (same block, smaller y gap)
            keep = [l for l in keep if not (l.block == best.block and 0 <= l.y0 - best.y1 < 6 and l.size <= best.size + 0.1 and l.page == best.page)]
    return tabs, keep


def pdf_to_markdown(path: str) -> Optional[Dict]:
    try:
        import fitz

        doc = fitz.open(path)
    except Exception:
        return None
    n = len(doc)
    if n < 2:
        return None

    pages: List[List[_Line]] = [_page_lines(p, i + 1) for i, p in enumerate(doc)]
    sizes = Counter()
    for pl in pages:
        for l in pl:
            sizes[round(l.size * 2) / 2] += len(l.text)
    if not sizes:
        return None
    body = sizes.most_common(1)[0][0]

    # 1) running headers / footers: same normalised text in the same band on ≥ 50 % of pages
    band_seen: Dict[Tuple[str, str], set] = defaultdict(set)
    for pno, (page, pl) in enumerate(zip(doc, pages)):
        H = page.rect.height
        for l in pl:
            band = "top" if l.y1 < H * 0.13 else "bottom" if l.y0 > H * 0.88 else ""
            if band:
                band_seen[(band, _norm(l.text))].add(pno)
    furniture = {k for k, v in band_seen.items() if len(v) >= max(3, int(0.5 * n))}
    # page numbers on their own ("12", "- 12 -") are furniture too
    def _is_furniture(l: _Line, H: float) -> bool:
        band = "top" if l.y1 < H * 0.13 else "bottom" if l.y0 > H * 0.88 else ""
        return bool(band) and ((band, _norm(l.text)) in furniture or re.fullmatch(r"[-–\s]*\d{1,3}[-–\s]*", l.text) is not None)

    blocks: List[Tuple[str, object]] = []     # ("line", _Line) | ("table", dict)
    for pno, (page, pl) in enumerate(zip(doc, pages)):
        H = page.rect.height
        pl = [l for l in pl if not _is_furniture(l, H)]
        tabs, pl = _tables(page, pl)
        items: List[Tuple[float, str, object]] = [(l.y0, "line", l) for l in pl] + [(t["bbox"][1], "table", t) for t in tabs]
        items.sort(key=lambda it: (it[0], getattr(it[2], "x0", 0) if it[1] == "line" else 0))
        blocks += [(k, o) for _, k, o in items]

    # 2) document title from the largest text before the first numbered heading
    title = ""
    first_lines = [o for k, o in blocks[:60] if k == "line"]
    if first_lines:
        top = max(l.size for l in first_lines[:40])
        if top >= body * 1.25:
            title = " ".join(l.text for l in first_lines[:40] if abs(l.size - top) < 0.6)
            title = re.sub(r"\s+", " ", title).strip()

    # 3) assemble markdown
    out: List[str] = []
    n_head = 0
    started = False            # content begins at the first numbered heading (or abstract)
    skipping = False
    skip_level = 9
    para: List[str] = []
    lst: List[str] = []
    last: Optional[_Line] = None

    def flush():
        nonlocal para, lst
        if para:
            text = " ".join(para)
            text = re.sub(r"(\w)- (\w)", lambda m: m.group(1) + m.group(2) if m.group(2).islower() else m.group(0), text)
            out.append(re.sub(r"\s+", " ", text).strip())
            out.append("")
            para = []
        if lst:
            out.extend(f"- {re.sub(r'\\s+', ' ', i).strip()}" for i in lst)
            out.append("")
            lst = []

    for kind, obj in blocks:
        if kind == "table":
            if not started or skipping:
                continue
            flush()
            out.append(table_markdown(obj["rows"], caption=obj.get("caption", "")))
            out.append("")
            continue
        l: _Line = obj
        text = re.sub(r"\s+", " ", l.text).strip()
        m = _NUM_HEAD.match(text)
        is_head = False
        level = 0
        if m and len(text.split()) <= 16 and not text.rstrip().endswith((".", ",", ";")) or (m and l.bold and l.size >= body and len(text.split()) <= 12):
            if m and (l.size >= body + 0.4 or l.bold):
                is_head, level = True, min(3, m.group(1).count(".") + 1)
        elif not m and l.size >= body * 1.18 and len(text.split()) <= 10 and (l.bold or l.size >= body * 1.3) and not text.endswith((".", ",")):
            is_head, level = True, 1 if l.size >= body * 1.4 else 2
        elif l.bold and len(text.split()) <= 6 and text.isupper() and l.size >= body:
            is_head, level = True, 1
        elif l.bold and _NAMED_HEAD.match(text) and l.size >= body:
            is_head, level = True, 1
        if is_head:
            flush()
            title_text = text
            if _SKIP_TITLES.match(re.sub(r"^\d+(\.\d+)*[.)]?\s*", "", title_text)):
                skipping, skip_level = True, level
                continue
            if skipping and level <= skip_level:
                skipping = False
            if not started and not (m or _KEEP_FRONT.match(title_text)):
                continue
            started = started or bool(m) or bool(_KEEP_FRONT.match(title_text))
            if skipping:
                continue
            n_head += 1
            out.append("#" * level + " " + title_text)
            out.append("")
            last = l
            continue
        if not started or skipping:
            continue
        li = _LIST.match(text)
        if li and re.match(r"^\[\d{1,3}\]", text):
            li = re.match(r"^(\[\d{1,3}\]\s*\S.*)$", text)  # keep the [n] marker as part of the reference text
        if li and not re.match(r"^\d+\s+\d", text):
            if para:
                flush()
            lst.append(li.group(1))
        elif lst and last is not None and l.x0 > last.x0 - 1 and l.block == last.block and not _NUM_HEAD.match(text):
            lst[-1] += " " + text           # wrapped list item
        else:
            if lst:
                flush()
            if last is not None and (l.block != last.block or l.y0 - last.y1 > 0.8 * l.size) and para:
                flush()
            para.append(text)
        last = l
    flush()

    md = "\n".join(out).strip()
    words = len(md.split())
    if n_head < 2 or words < 150:
        return None
    logger.info("pdf-structure: %d pages, %d headings, %d words, title=%r, furniture lines dropped=%d", n, n_head, words, title[:50], len(furniture))
    return {"markdown": md, "title": title, "pages": n, "headings": n_head}
