"""Chunks for a slide deck read by ``parsers.slide_pdf``: one page, one slide, nesting and figures kept."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List


def md_fingerprint(markdown: str) -> str:
    return hashlib.sha1((markdown or "").encode("utf-8", "ignore")).hexdigest()[:16]


def _text_of(page: Dict[str, Any]) -> str:
    lines: List[str] = []
    for it in page.get("items") or []:
        lines.append("  " * int(it.get("level", 0)) + "- " + it["text"])
    for lab in page.get("labels") or []:
        lines.append(f"- {lab}")
    for rows in page.get("tables") or []:
        if not rows or not rows[0]:
            continue
        lines.append("[TABLE DATA]")
        lines.append("| " + " | ".join(rows[0]) + " |")
        lines.append("|" + "---|" * len(rows[0]))
        lines.extend("| " + " | ".join((r + [""] * len(rows[0]))[:len(rows[0])]) + " |" for r in rows[1:])
    return "\n".join(lines)


def _words(page: Dict[str, Any]) -> set:
    return set(re.findall(r"[a-z0-9]{2,}", _text_of(page).lower()))


def collapse_buildups(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Teachers often build a slide up over several pages (same title, one more row or point each time). Only the last,
    complete page is kept: a page is dropped when the next page has the same title and contains at least 90% of its words."""
    out: List[Dict[str, Any]] = []
    for k, p in enumerate(pages):
        nxt = pages[k + 1] if k + 1 < len(pages) else None
        if nxt is not None and re.sub(r"\W+", "", (p.get("title") or "").lower()) == re.sub(r"\W+", "", (nxt.get("title") or "").lower()) \
                and (p.get("title") or "").strip():
            mine, theirs = _words(p), _words(nxt)
            same_fig = not p.get("figure") or (nxt.get("figure") and (p["figure"].get("bytes") == nxt["figure"].get("bytes")))
            if mine and len(mine & theirs) >= 0.9 * len(mine) and len(theirs) > len(mine) and same_fig:
                continue
        out.append(p)
    return out


def chunks_from_pages(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[{id, title, text, source, image?, outline, slide_kind}] — titles of consecutive pages that share one are numbered (1/3)…"""
    kept = [p for p in pages if p.get("kind") != "title" and (p.get("items") or p.get("tables") or p.get("figure") or p.get("labels"))]
    kept = collapse_buildups(kept)
    titles: List[str] = []
    last = ""
    for p in kept:
        t = (p.get("title") or "").strip() or last or f"Slide {p['page'] + 1}"
        titles.append(t)
        last = t
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(kept):
        j = i
        while j + 1 < len(kept) and re.sub(r"\W+", "", titles[j + 1].lower()) == re.sub(r"\W+", "", titles[i].lower()):
            j += 1
        run = j - i + 1
        for k in range(i, j + 1):
            p = kept[k]
            title = titles[k] if run == 1 else f"{titles[k]} ({k - i + 1}/{run})"
            chunk: Dict[str, Any] = {"id": len(out), "title": title, "text": _text_of(p), "source": p["page"] + 1, "slide_kind": p.get("kind", "content"),
                                     "outline": list(p.get("items") or [])}
            if p.get("preview"):
                chunk["source_preview"] = p["preview"]                   # the page as it was, for the web deck's "Original slide" viewer
            if p.get("figure_text"):
                chunk["figure_text"] = p["figure_text"]                  # what the picture says (OCR): feeds notes, quizzes and the tutor
            fig = p.get("figure")
            if fig and fig.get("bytes"):
                chunk["image"] = {"bytes": fig["bytes"], "ext": fig.get("ext", "png"), "width": fig.get("w", 0), "height": fig.get("h", 0)}
            out.append(chunk)
        i = j + 1
    return out
