"""
Markdown intermediate representation.

Every input route — PPTX, PDF, or a typed syllabus — converges on one markdown
document, so downstream stages reason over a single shape.

Conversion strategy
-------------------
**Text** comes from AnyDoc (``firecrawl-anydoc``) when it is installed: it is
pure Rust, needs no model or API key, and produces cleaner heading/list
structure than flattening our own parser output. The native parsers are the
fallback, and remain the only path that handles scanned pages.

**Images** never come from AnyDoc's markdown, because markdown cannot carry
bytes and AnyDoc exposes no document model for PDF at all. They are always
extracted by the native parsers, which know the slide/page each image came
from, and are then *anchored* back onto the markdown section they belong to
(see ``anchor_assets``). That is what keeps an image next to the text that
discusses it rather than dumped at the end of the deck.

Results are cached on disk by file content hash.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from learnova.config import CACHE_DIR
from learnova.logging_config import logger

# Below this many characters we assume the document is scanned/image-only and
# defer to the native parser, which can OCR and extract images.
_MIN_ANYDOC_CHARS = 200

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is",
    "are", "was", "were", "be", "by", "as", "at", "from", "that", "this", "it",
    "its", "into", "than", "then", "but", "not", "can", "will", "step",
}


@dataclass
class MarkdownDocument:
    """The markdown IR plus the binary assets markdown cannot carry."""

    markdown: str
    source_name: str
    source_type: str            # "pptx" | "pdf" | "typed"
    converter: str              # "anydoc" | "native" | "anydoc+native-assets" | "typed"
    assets: List[dict] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "markdown": self.markdown,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "converter": self.converter,
            "asset_count": len(self.assets),
            "meta": self.meta,
        }


# ── Section splitting ─────────────────────────────────────────────────────────
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def is_junk_heading(text: str) -> bool:
    """
    True when a detected heading is really content, not a section title.

    PDF extractors promote anything visually prominent to a heading, so a
    formula fragment on a worksheet ("No. of groups = k =", "|XA - XB| =")
    or a stray repeated label ("Conclusion: Conclusion:") becomes a slide
    title. These make terrible titles and fragment the deck.
    """
    stripped = (text or "").strip()
    if not stripped:
        return True

    # Ends on an operator, or is mostly symbols/digits rather than words.
    if stripped.endswith(("=", "+", "-", "/", "*", ":")) and "=" in stripped:
        return True

    letters = sum(ch.isalpha() for ch in stripped)
    if letters < max(3, len(stripped) * 0.4):
        return True

    # Same word repeated back to back ("Conclusion: Conclusion:").
    words = [w.strip(":;,.").lower() for w in stripped.split() if w.strip(":;,.")]
    if len(words) >= 2 and len(set(words)) == 1:
        return True

    # A heading is a label, not a paragraph.
    if len(words) > 12:
        return True

    return False


def split_sections(markdown: str, max_level: int = 2) -> List[Dict[str, Any]]:
    """
    Split markdown on headings of ``max_level`` or shallower.

    This is what makes chunking semantic instead of arbitrary: a textbook
    structured as ``## CHAPTER 1`` / ``## CHAPTER 2`` yields one section per
    chapter rather than fixed-size word windows that cut mid-sentence.
    """
    sections: List[Dict[str, Any]] = []
    current = {"title": "", "level": 0, "body": []}

    for line in markdown.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match and len(match.group(1)) <= max_level:
            # A junk heading stays as body text rather than starting a section,
            # so formula fragments never become slide titles.
            if is_junk_heading(match.group(2)):
                current["body"].append(match.group(2).strip())
                continue
            if current["title"] or any(l.strip() for l in current["body"]):
                sections.append(current)
            current = {
                "title": match.group(2).strip(),
                "level": len(match.group(1)),
                "body": [],
            }
        else:
            current["body"].append(line)

    if current["title"] or any(l.strip() for l in current["body"]):
        sections.append(current)

    built = [
        {
            "title": s["title"],
            "level": s["level"],
            # Strip residual '#' markers so sub-headings render as plain
            # bullets instead of literal "### Topic" text on the slide.
            "text": "\n".join(
                _HEADING_RE.sub(r"\2", line.strip()) if _HEADING_RE.match(line.strip())
                else line
                for line in s["body"]
            ).strip(),
        }
        for s in sections
    ]
    return _merge_repeated_titles(_inherit_missing_titles(built))


# A merged section beyond this size stops being one topic and becomes an
# unreadable dump. The density stage then paginates it into "Topic (2/4)".
# Generous, because a lecture topic ("Applications of NLP") legitimately spans
# 6-10 slide pages and should read as ONE numbered run, not six "(1/2)" pairs.
_MAX_MERGED_SECTION_CHARS = 6000


def _merge_repeated_titles(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fold consecutive sections sharing a title into one topic.

    A multi-page PDF repeats its chapter heading on every page, so each page
    became its own slide with an identical title. Merging gives one topic that
    the density stage paginates into ``Topic (2/4)`` — a numbered run rather
    than pages that look duplicated.

    Merging is capped: past ``_MAX_MERGED_SECTION_CHARS`` a new section starts,
    so an entire chapter does not collapse into a single overloaded slide.
    """
    merged: List[Dict[str, Any]] = []
    for section in sections:
        title = (section.get("title") or "").strip()
        body = section.get("text", "").strip()

        if merged and title:
            previous = merged[-1]
            same_title = title.lower() == (previous.get("title") or "").strip().lower()
            room = len(previous.get("text", "")) + len(body) <= _MAX_MERGED_SECTION_CHARS
            if same_title and room:
                if body:
                    previous["text"] = f"{previous['text'].rstrip()}\n{body}".strip()
                continue

        merged.append(dict(section))
    return merged


def _inherit_missing_titles(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Give untitled sections the previous real heading instead of "Page 10".

    A PDF page whose heading did not survive extraction produced a slide
    titled by its page number, which tells a reader nothing. Continuing the
    previous topic is both truer and more useful.
    """
    out: List[Dict[str, Any]] = []
    last_title = ""
    for section in sections:
        item = dict(section)
        title = (item.get("title") or "").strip()
        if (not title or re.fullmatch(r"(page|section|slide)\s*\d+", title, re.I)) and last_title:
            item["title"] = last_title
        elif title:
            last_title = title
        out.append(item)
    return out


def sections_to_parsed_dicts(sections: List[Dict[str, Any]]) -> List[dict]:
    """Adapt markdown sections to the dict shape the chunker already consumes."""
    out: List[dict] = []
    for i, section in enumerate(sections):
        body = section["text"]
        out.append(
            {
                "id": i,
                "slide": i + 1,
                "page": i + 1,
                "title": section["title"] or f"Section {i + 1}",
                "content": [ln for ln in body.splitlines() if ln.strip()],
                "text": body,
            }
        )
    return out


# ── Image anchoring ───────────────────────────────────────────────────────────
def _significant_words(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}


def _similarity(a: str, b: str) -> float:
    """Jaccard-ish overlap between two texts, biased toward the shorter one."""
    wa, wb = _significant_words(a), _significant_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def anchor_assets(
    sections: List[Dict[str, Any]],
    assets: List[dict],
) -> List[Tuple[int, dict]]:
    """
    Decide which markdown section each extracted image belongs to.

    An image carries the title and text of the slide/page it was pulled from.
    We match that against the sections in three escalating steps:

    1. **Exact title match** — the strongest signal, and the common case for
       PPTX where one slide becomes one ``##`` section.
    2. **Text similarity** — word overlap between the image's source text and
       the section body. Survives heading rewrites and reordering.
    3. **Positional fallback** — the section at the same ordinal index.

    Returns ``(section_index, asset)`` pairs. Without this, images end up
    attached to whichever section happens to share their list position, which
    is wrong the moment the two documents differ in length.
    """
    if not sections or not assets:
        return []

    normalized_titles = [(s.get("title") or "").strip().lower() for s in sections]
    anchored: List[Tuple[int, dict]] = []

    for asset in assets:
        source_title = (asset.get("unit_title") or "").strip().lower()
        source_text = asset.get("unit_text") or ""
        chosen: Optional[int] = None

        # 1. exact title match
        if source_title and source_title in normalized_titles:
            chosen = normalized_titles.index(source_title)

        # 2. best text similarity
        if chosen is None and source_text:
            scored = [
                (_similarity(source_text, f"{s.get('title','')} {s.get('text','')}"), i)
                for i, s in enumerate(sections)
            ]
            best_score, best_index = max(scored, key=lambda pair: pair[0])
            if best_score >= 0.25:
                chosen = best_index

        # 3. positional fallback
        if chosen is None:
            unit_index = asset.get("unit_index")
            if isinstance(unit_index, int) and 0 <= unit_index < len(sections):
                chosen = unit_index
            else:
                chosen = 0

        anchored.append((chosen, asset))
        logger.debug(
            "anchored asset from %r -> section %d (%r)",
            source_title or "?", chosen, sections[chosen].get("title"),
        )

    return anchored


def attach_assets_to_units(
    parsed_units: List[dict],
    sections: List[Dict[str, Any]],
    assets: List[dict],
) -> int:
    """
    Attach anchored images onto the parsed unit dicts the chunker consumes.

    The first image for a section becomes ``unit["image"]`` (what the renderers
    read); any extras are kept in ``unit["images"]`` so nothing is silently
    dropped.
    """
    attached = 0
    for section_index, asset in anchor_assets(sections, assets):
        if not (0 <= section_index < len(parsed_units)):
            continue
        unit = parsed_units[section_index]
        unit.setdefault("images", []).append(asset)
        if "image" not in unit:
            unit["image"] = asset
        attached += 1
    return attached


# ── Caching ───────────────────────────────────────────────────────────────────
def _cache_path(file_bytes: bytes, suffix: str) -> pathlib.Path:
    digest = hashlib.sha256(file_bytes).hexdigest()[:32]
    return CACHE_DIR / f"md_{digest}{suffix}.md"


# ── Converters ────────────────────────────────────────────────────────────────
def anydoc_available() -> bool:
    try:
        import anydoc  # noqa: F401
    except ImportError:
        return False
    return True


# AnyDoc represents an embedded picture as a bare filename line ("image.png")
# or markdown image syntax. We extract real image bytes natively, so these
# placeholders are noise — left in, each one becomes its own junk slide.
_IMAGE_EXTS = r"png|jpe?g|gif|bmp|tiff?|webp|emf|wmf|svg"
_BARE_IMAGE_LINE_RE = re.compile(rf"^\s*[\w\-. ]+\.(?:{_IMAGE_EXTS})\s*$", re.I)
_MD_IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")


def strip_asset_placeholders(markdown: str) -> str:
    """Drop image-placeholder lines, then collapse the blank runs they leave."""
    kept = [
        line
        for line in markdown.splitlines()
        if not (_BARE_IMAGE_LINE_RE.match(line) or _MD_IMAGE_LINE_RE.match(line))
    ]
    cleaned = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def is_multi_column_pdf(path: str, sample_pages: int = 4) -> bool:
    """
    True when a PDF is laid out in columns on most of its sampled pages.

    AnyDoc reads a page in raw order with no column awareness, so a two-column
    worksheet comes back with the columns interleaved into nonsense. Our native
    parser sorts blocks per column, so it must win for these documents.
    """
    try:
        import fitz

        from learnova.parsers.pdf_parser import detect_columns
    except ImportError:
        return False

    try:
        with fitz.open(path) as doc:
            pages = min(sample_pages, len(doc))
            if not pages:
                return False
            multi = 0
            for index in range(pages):
                page = doc[index]
                blocks = [b for b in page.get_text("dict").get("blocks", [])
                          if b.get("type") == 0]
                if detect_columns(blocks, float(page.rect.width)) >= 2:
                    multi += 1
        return multi >= max(1, pages // 2)
    except Exception as exc:
        logger.debug("column detection failed for %s: %s", path, exc)
        return False


def is_slide_style_pdf(path: str) -> bool:
    """
    True when a PDF is a slide deck exported to PDF — many pages, each with only
    a headline and a few bullets. AnyDoc merges these pages and drops structure;
    the native page-per-slide parser keeps one slide per page, which is what a
    lecture deck needs.
    """
    try:
        import fitz
    except ImportError:
        return False
    try:
        with fitz.open(path) as doc:
            n = len(doc)
            if n < 12:
                return False
            sample = list(range(0, n, max(1, n // 15)))[:15]
            light = 0
            for i in sample:
                words = len(re.findall(r"\S+", doc[i].get_text("text")))
                if words <= 140:
                    light += 1
            return light >= 0.7 * len(sample)
    except Exception:
        return False


_OCR_MARKER = re.compile(
    r"^\s*\[*\s*(?:Extracted\s+OCR|OCR\s+Transcription|OCR\s*&\s*Image|"
    r"Image\s+Diagram\s+Content|Local)\b.*$",
    re.I,
)
_PAGE_NO = re.compile(r"^\s*(?:page\s*)?\d{1,3}\s*$", re.I)


def strip_boilerplate(markdown: str) -> str:
    """
    Drop the running headers / footers / page numbers a PDF repeats on every
    page, plus stray OCR wrapper markers. A non-heading line that shows up 3+
    times (or on a third of the pages) is chrome, not content — a lecturer's
    name-and-course footer, a copyright line, a slide number.
    """
    lines = (markdown or "").splitlines()
    if len(lines) < 8:
        return markdown

    n_pages = max(1, sum(1 for l in lines if _HEADING_RE.match(l.strip())))
    counts: Dict[str, int] = {}
    for l in lines:
        s = l.strip()
        if not s or _HEADING_RE.match(s):
            continue
        key = re.sub(r"\s+", " ", re.sub(r"^[-*+•\d.)\s]+", "", s)).lower()
        if len(key) >= 8:
            counts[key] = counts.get(key, 0) + 1

    # Three-plus identical content lines in a slide/lecture PDF is chrome.
    repeat_floor = max(3, n_pages // 8)
    boiler = {k for k, c in counts.items() if c >= repeat_floor}
    # A line with a person's initials + an institution + a year range reads as a
    # running author footer even if it only survived a couple of pages.
    footerish = re.compile(
        r"^(?:dr\.?|prof\.?|mr\.?|ms\.?|shri)\b.*\b\d{4}[-/]\d{2,4}\b"
        r"|\bsem\.?\s*[-.]?\s*[iv\d]+\s*$",
        re.I,
    )
    # The same footer AnyDoc sometimes glues onto the end of a content line.
    trailing_footer = re.compile(
        r"\s*(?:Dr\.?|Prof\.?|Mr\.?|Ms\.?)\s+[A-Z].{0,60}?\b\d{4}[-/]\d{2,4}\b.*$",
    )

    out: List[str] = []
    for l in lines:
        s = l.strip()
        if _OCR_MARKER.match(s) or s in {"]", "]]"}:
            continue
        if not _HEADING_RE.match(s):
            body = re.sub(r"^[-*+•>\d.)\s]+", "", s)
            key = re.sub(r"\s+", " ", body).lower()
            if key in boiler or _PAGE_NO.match(s) or footerish.search(body):
                continue
            l = trailing_footer.sub("", l).rstrip()
            if not l.strip():
                continue
        out.append(l)
    return _flatten_fake_tables("\n".join(out))


_PIPE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_PIPE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


def _flatten_fake_tables(markdown: str) -> str:
    """
    AnyDoc sometimes reads a bulleted slide as a pipe table where most cells are
    empty or a lone bullet char. Turn such blocks back into bullet lists so the
    content is readable instead of ``|•||NLP-Natural Language Processing.|``.
    """
    lines = markdown.splitlines()
    out: List[str] = []
    i = 0
    while i < len(lines):
        if _PIPE_ROW.match(lines[i]):
            j = i
            block = []
            while j < len(lines) and _PIPE_ROW.match(lines[j]):  # one contiguous run
                block.append(lines[j])
                j += 1
            cells_all, junk = [], 0
            empty_lead = False
            for row in block:
                if _PIPE_SEP.match(row):
                    continue
                stripped = row.strip()
                if stripped.startswith("||") or stripped.startswith("|•") or stripped.startswith("| |"):
                    empty_lead = True
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                for c in cells:
                    if c in {"", "•", "-", "*", "Ø", "�"} or len(c) <= 1:
                        junk += 1
                    elif c:
                        cells_all.append(c)
            total = junk + len(cells_all)
            if cells_all and total and (empty_lead or junk / total >= 0.3):
                for c in cells_all:
                    out.append(f"- {c}")
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def merge_wrapped_headings(markdown: str) -> str:
    """
    A PDF heading that wrapped onto two visual lines becomes two ``##`` lines
    ("## Introduction to Natural Language" then "## Processing"). If a heading is
    short and directly follows another heading with no body between, fold it in.
    """
    lines = (markdown or "").splitlines()
    out: List[str] = []
    for l in lines:
        m = _HEADING_RE.match(l.strip())
        frag = m.group(2).strip() if m else ""
        # A wrap fragment is 1-2 lowercase-continuation words, e.g. "Processing"
        # or "Recognition" — not a new sub-heading like "Rule-based Systems".
        is_wrap = bool(m) and len(frag.split()) <= 2 and not frag.endswith((":", ".", "?"))
        if is_wrap:
            k = len(out) - 1
            while k >= 0 and not out[k].strip():
                k -= 1
            prev = _HEADING_RE.match(out[k].strip()) if k >= 0 else None
            prev_txt = prev.group(2).rstrip() if prev else ""
            # only when the previous heading itself looks truncated
            if prev and prev.group(1) == m.group(1) and not prev_txt.endswith((":", ".", "?", ")")):
                out[k] = f"{prev.group(1)} {prev_txt} {frag}"
                del out[k + 1:]
                continue
        out.append(l)
    return "\n".join(out)


def _clean_markdown(markdown: str) -> str:
    return merge_wrapped_headings(strip_boilerplate(strip_asset_placeholders(markdown or "")))


def _convert_with_anydoc(path: str) -> Optional[str]:
    """Try AnyDoc for text. Returns None when unavailable or unhelpful."""
    try:
        import anydoc
    except ImportError:
        logger.info("AnyDoc not installed — using native parser for text.")
        return None

    try:
        markdown = anydoc.to_markdown(path)
    except Exception as exc:
        logger.warning("AnyDoc conversion failed (%s) — using native parser.", exc)
        return None

    markdown = _clean_markdown(markdown or "")

    if len(markdown) < _MIN_ANYDOC_CHARS:
        logger.info(
            "AnyDoc produced %d chars — likely scanned; using native parser for OCR.",
            len(markdown),
        )
        return None

    return markdown


def _extract_native_assets(path: str, ext: str, textbook_mode: bool) -> List[dict]:
    """
    Pull images out with the native parsers, tagging each with the slide/page
    it came from so it can be anchored back to the right markdown section.
    """
    from learnova.parsers.pdf_parser import parse_pdf, parse_textbook_pdf
    from learnova.parsers.ppt_parser import parse_ppt

    try:
        if ext == ".pptx":
            document = parse_ppt(path)
        elif textbook_mode:
            document = parse_textbook_pdf(path)
        else:
            document = parse_pdf(path)
    except Exception as exc:
        logger.warning("native asset extraction failed (%s) — continuing without images.", exc)
        return []

    assets: List[dict] = []
    seen: set = set()

    for unit in document.slide_units:
        candidates = list(getattr(unit, "images", []) or [])
        if unit.image:
            candidates.insert(0, unit.image)

        for image in candidates:
            data = image.get("bytes") if isinstance(image, dict) else None
            if not data:
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            assets.append(
                {
                    "index": len(assets),
                    "bytes": data,
                    "ext": image.get("ext", "png"),
                    "unit_index": unit.id,
                    "unit_title": unit.title or "",
                    "unit_text": unit.text or "",
                }
            )

    logger.info("extracted %d unique image asset(s) natively", len(assets))
    return assets


# Any stack of list markers a parser may leave: "- ", "- • ", "- - • ", "Ø ",
# "1. ", "a) " …
_BULLET_LEAD = re.compile(
    r"^\s*(?:[-*+]\s*)*(?:[•●▪◦‣▶►➢➤»]\s*)*"
    r"(?:\d+[.)]\s+|[a-hA-H][.)]\s+)?",
)
_MARKER_ONLY = re.compile(r"^[\s\-*+•●▪◦‣·]+$")
_SENT_END = re.compile(r"[.!?:;]$|[.!?][\"'”’)\]]$")


def _reflow_slide_body(body: str, title: str) -> List[str]:
    """
    Turn one PDF/PPTX slide's raw text (which the parser gives line-by-line,
    broken at the visual line width) into clean bullet lines:

    * strip stacked list markers ("- - • foo" -> "foo");
    * rejoin a line that was wrapped mid-sentence with its continuation;
    * fix "word ," / "word ." spacing that PyMuPDF leaves between spans;
    * drop a sub-heading that just repeats the slide title.
    """
    title_norm = re.sub(r"[^a-z0-9]", "", (title or "").lower())
    raw_lines = [l.rstrip() for l in (body or "").splitlines()]

    items: List[str] = []
    buf = ""

    def _flush():
        nonlocal buf
        s = re.sub(r"\s+([,.;:!?)”’])", r"\1", buf).strip()
        s = re.sub(r"([(“‘])\s+", r"\1", s)
        s = re.sub(r"\s{2,}", " ", s).strip(" -•·–—")
        if s and re.sub(r"[^a-z0-9]", "", s.lower()) != title_norm and len(s) > 1:
            items.append(s)
        buf = ""

    for raw in raw_lines:
        line = raw.strip()
        if not line or line in {"[TABLE DATA]", "(No readable text on this slide)"}:
            continue
        if line.startswith("## ") or line.startswith("### "):
            frag = line.lstrip("#").strip()
            if re.sub(r"[^a-z0-9]", "", frag.lower()) == title_norm:
                continue  # duplicate of the slide title
            _flush()
            buf = frag
            _flush()
            continue
        if _MARKER_ONLY.match(line):
            continue

        lead = _BULLET_LEAD.match(line).group(0)
        has_marker = bool(re.search(r"[-*+•●▪◦‣▶►➢➤»]|\d+[.)]|[a-h][.)]", lead))
        content = line[len(lead):].strip()
        if not content:
            continue

        # A bullet char mid-line ("... foo. • bar ...") joins two items on one
        # physical line — split them.
        pieces = re.split(r"\s+[•●▪◦‣▶►➢➤]\s+", content)
        for pi, piece in enumerate(pieces):
            piece = piece.strip()
            if not piece:
                continue
            if pi > 0 or has_marker:        # a new list item begins
                _flush()
                buf = piece
            elif not buf:                   # first line of the slide, no marker
                buf = piece
            elif _SENT_END.search(buf):     # previous item finished
                _flush()
                buf = piece
            else:                           # wrapped continuation
                buf = f"{buf} {piece}"

    _flush()
    return items


def _native_to_markdown(path: str, ext: str, textbook_mode: bool = False):
    """Convert via the existing parsers, flattening their output to markdown."""
    from learnova.parsers.pdf_parser import parse_pdf, parse_textbook_pdf
    from learnova.parsers.ppt_parser import parse_ppt

    if ext == ".pptx":
        document = parse_ppt(path)
    elif textbook_mode:
        document = parse_textbook_pdf(path)
    else:
        document = parse_pdf(path)

    lines: List[str] = []
    for unit in document.slide_units:
        title = (unit.title or "").strip() or f"Section {unit.id + 1}"
        body = (unit.text or "").strip()
        items = _reflow_slide_body(body, title)
        # A table the parser flagged is kept as a pipe block for split_sections.
        table_rows = [l for l in (body or "").splitlines() if " | " in l]

        # Only keep a real table: 2+ data rows that each have 2+ non-empty
        # cells. PyMuPDF's table finder fires on any aligned bullet layout.
        real_table = [
            r for r in table_rows
            if sum(1 for c in r.split(" | ") if c.strip() and c.strip() not in "•-*") >= 2
        ]
        lines.append(f"## {title}")
        lines.append("")
        for it in items:
            lines.append(f"- {it}")
        if len(real_table) >= 2:
            for row in real_table:
                lines.append(f"| {row.strip()} |")
        lines.append("")

    return _clean_markdown("\n".join(lines).strip()), document


# ── Public API ────────────────────────────────────────────────────────────────
def convert_to_markdown(
    path: str,
    source_name: Optional[str] = None,
    textbook_mode: bool = False,
    use_cache: bool = True,
    prefer_anydoc: bool = True,
    extract_images: bool = True,
) -> MarkdownDocument:
    """
    Convert a PPTX or PDF into the markdown IR.

    Text prefers AnyDoc; images always come from the native parsers, because
    AnyDoc exposes no document model for PDF and markdown cannot carry bytes.
    """
    file_path = pathlib.Path(path)
    ext = file_path.suffix.lower()
    name = source_name or file_path.name

    file_bytes = file_path.read_bytes()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(file_bytes, "_tb" if textbook_mode else "")

    # Images are expensive to re-extract but cannot be cached as text, so the
    # cache only short-circuits the text half.
    cached_markdown = None
    if use_cache and cache_file.exists():
        cached_markdown = cache_file.read_text(encoding="utf-8")
        logger.info("markdown cache hit for %s", name)

    assets: List[dict] = []
    if extract_images:
        assets = _extract_native_assets(str(file_path), ext, textbook_mode)

    if cached_markdown:
        return MarkdownDocument(
            markdown=cached_markdown,
            source_name=name,
            source_type=ext.lstrip("."),
            converter="cache",
            assets=assets,
        )

    # AnyDoc has no column awareness and merges slide pages, so a multi-column
    # PDF or a slide deck exported to PDF must go through the native parser.
    use_anydoc = prefer_anydoc
    if use_anydoc and ext == ".pdf":
        if is_multi_column_pdf(str(file_path)):
            logger.info("%s is multi-column — using the native parser", name)
            use_anydoc = False
        elif is_slide_style_pdf(str(file_path)):
            logger.info("%s is a slide deck PDF — using the page-per-slide native parser", name)
            use_anydoc = False

    if use_anydoc:
        markdown = _convert_with_anydoc(str(file_path))
        if markdown:
            if use_cache:
                cache_file.write_text(markdown, encoding="utf-8")
            return MarkdownDocument(
                markdown=markdown,
                source_name=name,
                source_type=ext.lstrip("."),
                converter="anydoc+native-assets" if assets else "anydoc",
                assets=assets,
                meta={"asset_count": len(assets)},
            )

    markdown, document = _native_to_markdown(str(file_path), ext, textbook_mode)
    if use_cache and markdown:
        cache_file.write_text(markdown, encoding="utf-8")
    return MarkdownDocument(
        markdown=markdown,
        source_name=name,
        source_type=ext.lstrip("."),
        converter="native",
        assets=assets,
        meta={"unit_count": len(document.slide_units), "asset_count": len(assets)},
    )


def from_typed_text(text: str, source_name: str = "Typed Input") -> MarkdownDocument:
    """Wrap user-typed content (a syllabus, an outline) as the markdown IR."""
    stripped = text.strip()
    if not any(_HEADING_RE.match(l.strip()) for l in stripped.splitlines()):
        stripped = f"## {source_name}\n\n{stripped}"
    return MarkdownDocument(
        markdown=stripped,
        source_name=source_name,
        source_type="typed",
        converter="typed",
    )


__all__ = [
    "MarkdownDocument",
    "convert_to_markdown",
    "from_typed_text",
    "split_sections",
    "sections_to_parsed_dicts",
    "anchor_assets",
    "attach_assets_to_units",
    "anydoc_available",
]
