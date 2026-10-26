"""Give every table its own slide(s); long tables continue over several slides with the header repeated."""

from __future__ import annotations

import copy
from typing import List

from learnova.parsers.pdf_tables import TABLE_SENTINEL, split_tables

PER_PAGE = 7


def _table_text(headers, rows) -> str:
    lines = [TABLE_SENTINEL, "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows])


def _sentences(text: str) -> List[str]:
    from learnova.visuals.engine import split_sentences

    return [x.strip() for x in split_sentences(text) if len(x.split()) >= 3]


def _prose_entries(template: dict, base: str, text: str, suffix: str = "") -> List[dict]:
    sents = _sentences(text)
    if not sents:
        return []
    groups = [sents[i:i + 6] for i in range(0, len(sents), 6)]
    out = []
    for k, g in enumerate(groups, 1):
        e = copy.deepcopy(template)
        e["original"]["text"] = " ".join(g)
        title = f"{base}{suffix}"
        e["improved"] = {"title": title if len(groups) == 1 else f"{title} ({k}/{len(groups)})", "bullets": g,
                         "takeaway": "", "layout_type": "MINIMAL_TEXT"}
        out.append(e)
    return out


def paginate_tables(slides: List[dict], per_page: int = PER_PAGE) -> int:
    """
    In-place. A source chunk that holds tables is rebuilt from its structure: one slide per table (captioned,
    paginated at ``per_page`` rows with the header repeated) plus prose slides for the text around them.

    Several slides can share one source chunk (the improver splits a chunk into many) — each chunk is expanded
    once and its siblings are dropped, since the segments already cover the whole source text. Returns the
    change in slide count.
    """
    out: List[dict] = []
    done = set()
    for entry in slides:
        orig = entry.get("original") if isinstance(entry.get("original"), dict) else {}
        text = str(orig.get("text") or "")
        if "|" not in text:
            out.append(entry)
            continue
        segs = split_tables(text)
        n_tables = sum(1 for x in segs if x["kind"] == "table")
        if not n_tables:
            out.append(entry)
            continue
        key = hash(text)
        if key in done:
            continue
        done.add(key)
        base = str(orig.get("title") or (entry.get("improved") or {}).get("title") or "Table")
        n_tab = 0
        # short prose next to a table (an intro line, a remark under it) rides with the table instead of taking its own slide
        for k, seg in enumerate(segs):
            if seg["kind"] == "prose" and len(seg["text"].split()) <= 50:
                nxt = segs[k + 1] if k + 1 < len(segs) else None
                prv = segs[k - 1] if k > 0 else None
                if nxt is not None and nxt["kind"] == "table":
                    nxt["lead_text"] = (nxt.get("lead_text", "") + " " + seg["text"]).strip()
                    seg["text"] = ""
                elif prv is not None and prv["kind"] == "table":
                    prv["tail_text"] = (prv.get("tail_text", "") + " " + seg["text"]).strip()
                    seg["text"] = ""
        segs = [x for x in segs if x["kind"] == "table" or x["text"].strip()]
        for seg in segs:
            if seg["kind"] == "prose":
                out.extend(_prose_entries(entry, base, seg["text"], "" if n_tab == 0 else " (notes)"))
                continue
            n_tab += 1
            chunks = [seg["rows"][i:i + per_page] for i in range(0, len(seg["rows"]), per_page)] or [[]]
            title = seg["caption"] or (base if n_tables == 1 else f"{base} — table {n_tab}")
            for k, rows in enumerate(chunks, 1):
                e = copy.deepcopy(entry)
                e["original"]["text"] = (seg.get("lead_text", "") + "\n\n" if (k == 1 and seg.get("lead_text")) else "") + _table_text(seg["headers"], rows) \
                    + ("\n\n" + seg["tail_text"] if (k == len(chunks) and seg.get("tail_text")) else "")
                e["improved"] = {"section": base, "title": title if len(chunks) == 1 else f"{title} ({k}/{len(chunks)})", "bullets": [],
                                 "takeaway": "", "layout_type": "MINIMAL_TEXT"}
                out.append(e)
    delta = len(out) - len(slides)
    slides[:] = out
    return delta
