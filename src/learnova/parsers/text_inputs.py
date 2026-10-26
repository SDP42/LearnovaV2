"""Plain-text style inputs (.md, .txt, .docx) turned into the markdown IR. No model, no network."""

from __future__ import annotations

import io
import re
from typing import List

TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
DOCX_SUFFIX = ".docx"


def decode_text(payload: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return payload.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def plain_text_to_markdown(text: str) -> str:
    """A .txt outline: ALL-CAPS or numbered short lines become headings, the rest stays as paragraphs."""
    out: List[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            out.append("")
        elif re.match(r"^#{1,6}\s", s):
            out.append(s)
        elif len(s.split()) <= 9 and (s.isupper() or re.match(r"^(?:unit|chapter|module|lesson|week|topic)\s+\w+", s, re.I)
                                      or re.match(r"^\d+(?:\.\d+)*[.)]\s+[A-Z][^.!?]{2,70}$", s)):
            out.append("## " + re.sub(r"^\d+(?:\.\d+)*[.)]\s+", "", s).title() if s.isupper() else "## " + s)
        else:
            out.append(line)
    return "\n".join(out).strip()


def docx_to_markdown(payload: bytes) -> str:
    """Headings, lists and tables from a Word file."""
    import docx  # python-docx

    doc = docx.Document(io.BytesIO(payload))
    out: List[str] = []
    body = doc.element.body
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            text = p.text.strip()
            if not text:
                out.append("")
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            m = re.match(r"heading\s*(\d)", style)
            if style == "title":
                out.append(f"# {text}")
            elif m:
                out.append("#" * min(4, int(m.group(1)) + (1 if int(m.group(1)) == 1 else 0)) + f" {text}")
            elif "list" in style:
                out.append(f"- {text}")
            else:
                out.append(text)
        elif tag == "tbl":
            t = Table(child, doc)
            rows = [[c.text.strip().replace("\n", " ").replace("|", "/") for c in r.cells] for r in t.rows]
            if rows and len(rows[0]) >= 2:
                out.append("[TABLE DATA]")
                out.append("| " + " | ".join(rows[0]) + " |")
                out.append("|" + "---|" * len(rows[0]))
                out.extend("| " + " | ".join(r) + " |" for r in rows[1:])
                out.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def looks_like(payload: bytes, suffix: str) -> bool:
    """Cheap magic-byte check so a renamed file is refused with a clear message instead of failing deep in a parser."""
    if suffix == ".pdf":
        return payload[:1024].lstrip().startswith(b"%PDF")
    if suffix in {".pptx", ".docx"}:
        return payload[:2] == b"PK"
    return True
