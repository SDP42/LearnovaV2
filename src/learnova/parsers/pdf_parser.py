"""
Advanced PDF Parser for Learnova (Migrated to Unified Extraction Architecture)
Uses PyMuPDF's full block/dict parsing to extract:
- Paragraphs with heading detection, font size, bold/italic flags, and spatial bboxes
- Tables via PyMuPDF table finder (find_tables) into TableElement
- Embedded images into VisualAssetElement with SHA-256 hashes
- Full-page pixmap rendering for scanned/image-heavy pages
- Single-page per slide mode and Textbook PDF chapter grouping mode
"""

import io
import re
import os
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from PIL import Image

from learnova.parsers.base import BaseDocumentParser
from learnova.parsers.legacy import SlideData, ParsedDocument
from learnova.parsers.schema import (
    DocumentEntity,
    SlidePageEntity,
    TextBlockElement,
    TableElement,
    VisualAssetElement,
    StructuredChartElement,
    DiagramElement,
    EquationElement,
    DocumentType,
    VisualAssetType,
    ChartType,
    DiagramType,
)


# SlideData / ParsedDocument are re-exported so that existing callers doing
# `from learnova.parsers.pdf_parser import ParsedDocument` keep working.


def _is_heading(span: dict, avg_body_size: float) -> bool:
    """True if this span looks like a heading: significantly larger font or bold."""
    size = span.get("size", 0)
    flags = span.get("flags", 0)
    font_name = span.get("font", "").lower()
    is_bold = bool(flags & 2**4) or "bold" in font_name
    return size >= avg_body_size * 1.25 or (is_bold and size >= avg_body_size * 1.05)


def _avg_body_font_size(page_dict: dict) -> float:
    """Calculate the median body font size on a page."""
    sizes = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    sizes.append(span["size"])
    if not sizes:
        return 12.0
    sizes.sort()
    return sizes[len(sizes) // 2]  # median


def _extract_tables_from_page(page) -> List[str]:
    """
    Use PyMuPDF's built-in table finder to extract table cells as text.
    Returns formatted rows joined by ' | '.
    """
    table_texts = []
    try:
        import fitz
        tabs = page.find_tables()
        for tab in tabs.tables:
            for row in tab.extract():
                clean_row = [str(cell or "").strip() for cell in row]
                non_empty = [c for c in clean_row if c]
                if non_empty:
                    table_texts.append(" | ".join(non_empty))
    except Exception:
        pass
    return table_texts


def detect_columns(blocks: List[dict], page_width: float) -> int:
    """
    Count text columns on a page from the horizontal spread of its blocks.

    A worksheet or academic handout is often laid out in two columns. Read in
    naive top-to-bottom order, the two columns interleave and the text becomes
    nonsense ("Sample A: 10, 12 Step 2: To calculate ... Sample B: 14, 15").
    Detecting the split lets us read each column fully before moving on.
    """
    if page_width <= 0:
        return 1

    mid = page_width / 2
    left = right = spanning = 0

    for block in blocks:
        bbox = block.get("bbox")
        if not bbox:
            continue
        x0, x1 = bbox[0], bbox[2]
        width = x1 - x0
        if width > page_width * 0.62:      # crosses the gutter
            spanning += 1
        elif x1 < mid * 1.06:
            left += 1
        elif x0 > mid * 0.94:
            right += 1

    sided = left + right
    # Two columns only when both sides are populated and few blocks span the
    # gutter — otherwise a single wide column with a stray narrow block wins.
    if sided >= 4 and left >= 2 and right >= 2 and spanning <= sided * 0.5:
        return 2
    return 1


def _reading_order(blocks: List[dict], page_width: float) -> List[dict]:
    """
    Sort blocks into human reading order, column-aware.

    Full-width blocks (titles, banners) act as horizontal rules: they keep
    their vertical position, while column blocks are grouped left-then-right
    within the band they belong to.
    """
    if detect_columns(blocks, page_width) < 2:
        return sorted(blocks, key=lambda b: (round(b.get("bbox", [0, 0])[1], 1),
                                             b.get("bbox", [0, 0])[0]))

    mid = page_width / 2

    def key(block):
        bbox = block.get("bbox", [0, 0, 0, 0])
        x0, y0, x1 = bbox[0], bbox[1], bbox[2]
        if (x1 - x0) > page_width * 0.62:
            column = 0                      # spanning: sorts with the left band
        else:
            column = 1 if x1 < mid * 1.06 else 2
        return (column, round(y0, 1), x0)

    return sorted(blocks, key=key)


def _page_to_structured_text(page) -> Tuple[str, str]:
    """
    Extract text from a PDF page using dict mode for full layout awareness.
    Returns (detected_title, full_body_text).
    Headings are prefixed with ## for hierarchy preservation.
    Tables are extracted separately and inserted inline.
    """
    page_dict = page.get_text("dict", sort=True)
    avg_size = _avg_body_font_size(page_dict)
    page_width = float(getattr(page.rect, "width", 0) or 0)

    detected_title = ""
    paragraphs = []

    text_blocks = [b for b in page_dict.get("blocks", []) if b.get("type") == 0]

    for block in _reading_order(text_blocks, page_width):
        block_lines_text = []
        block_is_heading = False

        for line in block.get("lines", []):
            line_text_parts = []
            line_is_heading = False

            for span in line.get("spans", []):
                raw = span.get("text", "").strip()
                if not raw:
                    continue
                if _is_heading(span, avg_size):
                    line_is_heading = True
                line_text_parts.append(raw)

            line_text = " ".join(line_text_parts).strip()
            if line_text:
                if line_is_heading:
                    block_is_heading = True
                block_lines_text.append(line_text)

        block_text = " ".join(block_lines_text).strip()
        if not block_text:
            continue

        if block_is_heading:
            if not detected_title and len(block_text) < 120:
                detected_title = block_text
            paragraphs.append(f"## {block_text}")
        else:
            paragraphs.append(block_text)

    # Inject table data
    table_lines = _extract_tables_from_page(page)
    if table_lines:
        paragraphs.append("[TABLE DATA]")
        paragraphs.extend(table_lines)

    return detected_title, "\n".join(paragraphs)


def _extract_page_images(page, doc, min_size: int = 120) -> List[dict]:
    """Extract embedded images from a PDF page above minimum dimensions."""
    images = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            w = base_image.get("width", 0)
            h = base_image.get("height", 0)
            if w >= min_size and h >= min_size:
                raw_bytes = bytes(base_image.get("image") or b"")
                with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                    pil_img.load()
                    out = io.BytesIO()
                    pil_img.convert("RGB").save(out, format="PNG")
                    images.append({"bytes": bytes(out.getvalue()), "ext": "png"})
        except Exception:
            pass
    return images


def _render_page_as_image(page, dpi: int = 150) -> Optional[dict]:
    """Render a whole PDF page as PNG for Gemini Vision OCR fallback."""
    try:
        import fitz
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = bytes(pix.tobytes("png"))
        pix = None
        return {"bytes": png_bytes, "ext": "png"}
    except Exception:
        return None


def _detect_chapter_heading(text: str) -> Optional[str]:
    """Detect chapter/unit/section headings for grouping in textbook mode."""
    patterns = [
        r"^(Chapter|Unit|Section|Module|Lesson|Part)\s+[\dIVXivx]+",
        r"^[\dIVXivx]+\.\s+[A-Z][a-zA-Z\s]{3,}",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(0).strip().title()
    return None


class PDFParser(BaseDocumentParser):
    """
    Production-ready PDF parser implementing the BaseDocumentParser interface.
    Extracts structured DocumentEntity graphs with typed elements.
    """

    def supports(self, file_path_or_extension: str) -> bool:
        ext = file_path_or_extension.lower().strip()
        return ext.endswith(".pdf") or ext == "pdf"

    def parse(self, file_path: str) -> DocumentEntity:
        if not self.validate(file_path):
            raise ValueError(f"Invalid or unsupported PDF file path: {file_path}")

        import fitz
        doc = fitz.open(file_path)
        slides: List[SlidePageEntity] = []

        for i, page in enumerate(doc):
            slide_entity = self._parse_page(page, doc, page_index=i)
            slides.append(slide_entity)

        doc.close()

        doc_id = hashlib.sha256(os.path.basename(file_path).encode("utf-8")).hexdigest()[:16]
        return DocumentEntity(
            id=doc_id,
            filename=os.path.basename(file_path),
            doc_type=DocumentType.PDF,
            total_units=len(slides),
            slides=slides,
            metadata={"source_path": file_path, "page_count": len(slides)},
        )

    def _parse_page(self, page, doc, page_index: int) -> SlidePageEntity:
        page_dict = page.get_text("dict", sort=True)
        avg_size = _avg_body_font_size(page_dict)

        detected_title = ""
        text_blocks: List[TextBlockElement] = []
        tables: List[TableElement] = []
        visual_assets: List[VisualAssetElement] = []
        reading_order_counter = 0

        # 1. Text Blocks & Headings
        for b_idx, block in enumerate(page_dict.get("blocks", [])):
            if block.get("type") != 0:
                continue

            block_bbox = tuple(round(float(c), 2) for c in block.get("bbox", (0, 0, 0, 0)))
            block_text_parts = []
            block_is_heading = False
            font_size = None
            is_bold = False
            is_italic = False

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    raw = span.get("text", "").strip()
                    if not raw:
                        continue

                    flags = span.get("flags", 0)
                    font_name = span.get("font", "").lower()
                    if bool(flags & 2**4) or "bold" in font_name:
                        is_bold = True
                    if bool(flags & 2**1) or "italic" in font_name or "oblique" in font_name:
                        is_italic = True
                    if span.get("size"):
                        font_size = float(span.get("size"))

                    if _is_heading(span, avg_size):
                        block_is_heading = True

                    block_text_parts.append(raw)

            full_block_text = " ".join(block_text_parts).strip()
            if not full_block_text:
                continue

            if block_is_heading and not detected_title and len(full_block_text) < 120:
                detected_title = full_block_text

            # Detect bullet point formatting
            bullet_level = 0
            if re.match(r"^[\-\*•▪➤►→▶▷◆◇■□●○]\s+", full_block_text):
                bullet_level = 1

            text_blocks.append(TextBlockElement(
                id=f"p{page_index}_b{b_idx}",
                text=full_block_text,
                is_heading=block_is_heading,
                heading_level=1 if block_is_heading and full_block_text == detected_title else (2 if block_is_heading else 0),
                bullet_level=bullet_level,
                font_size=font_size,
                is_bold=is_bold,
                is_italic=is_italic,
                bbox=block_bbox,
                reading_order=reading_order_counter,
            ))
            reading_order_counter += 1

        # 2. Native Table Extraction via PyMuPDF find_tables()
        try:
            tabs = page.find_tables()
            for t_idx, tab in enumerate(tabs.tables):
                headers = []
                rows = []
                tab_rows = tab.extract()
                for r_idx, r in enumerate(tab_rows):
                    clean_row = [str(cell or "").strip() for cell in r]
                    if r_idx == 0:
                        headers = clean_row
                    else:
                        rows.append(clean_row)

                tab_bbox = tuple(round(float(c), 2) for c in tab.bbox) if hasattr(tab, "bbox") and tab.bbox else None
                tables.append(TableElement(
                    id=f"p{page_index}_tbl_{t_idx}",
                    headers=headers,
                    rows=rows,
                    num_rows=len(tab_rows),
                    num_cols=len(tab_rows[0]) if tab_rows else 0,
                    bbox=tab_bbox,
                    reading_order=reading_order_counter,
                ))
                reading_order_counter += 1
        except Exception:
            pass

        # 3. Embedded Images with SHA-256 Hashing
        try:
            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image.get("image")
                if not image_bytes:
                    continue

                raw_bytes = bytes(image_bytes)
                sha256 = hashlib.sha256(raw_bytes).hexdigest()
                w = base_image.get("width", 0)
                h = base_image.get("height", 0)

                png_bytes = raw_bytes
                try:
                    with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                        pil_img.load()
                        out = io.BytesIO()
                        pil_img.convert("RGB").save(out, format="PNG")
                        png_bytes = bytes(out.getvalue())
                        w, h = pil_img.size
                except Exception:
                    pass

                if w >= 100 and h >= 100:
                    asset_type = VisualAssetType.ICON if (w < 120 and h < 120) else VisualAssetType.PICTURE
                    visual_assets.append(VisualAssetElement(
                        id=f"p{page_index}_img_{img_idx}",
                        image_bytes=png_bytes,
                        format="png",
                        width_px=w,
                        height_px=h,
                        asset_type=asset_type,
                        sha256_hash=sha256,
                        reading_order=reading_order_counter,
                    ))
                    reading_order_counter += 1
        except Exception:
            pass

        # 4. Scanned Page Fallback Rendering
        has_image_blocks = any(b.get("type") == 1 for b in page_dict.get("blocks", []))
        word_count = sum(len(tb.text.split()) for tb in text_blocks)

        rendered_page_img = None
        # Render a full-page image only for a genuinely scanned / image-only page
        # — it has raster blocks and little or no extractable text. A sparse
        # *text* slide (a title page, a section divider) has no image blocks and
        # must not become a page screenshot.
        if has_image_blocks and word_count < 30:
            rendered = _render_page_as_image(page)
            if rendered:
                rendered_page_img = VisualAssetElement(
                    id=f"p{page_index}_rendered",
                    image_bytes=rendered["bytes"],
                    format="png",
                    asset_type=VisualAssetType.SCANNED_PAGE,
                )

        reading_order_ids = [tb.id for tb in text_blocks] + [t.id for t in tables] + [v.id for v in visual_assets]

        return SlidePageEntity(
            id=page_index,
            unit_number=page_index + 1,
            title=detected_title or f"Page {page_index + 1}",
            text_blocks=text_blocks,
            tables=tables,
            visual_assets=visual_assets,
            rendered_page_image=rendered_page_img,
            reading_order_elements=reading_order_ids,
        )


def parse_pdf(file_path: str) -> ParsedDocument:
    """
    Backward-compatible single-page-per-slide PDF parser.
    Invokes PDFParser to construct a DocumentEntity graph, then bridges to legacy ParsedDocument.
    """
    parser = PDFParser()
    doc_entity = parser.parse(file_path)
    legacy_dicts = doc_entity.to_legacy_parsed_dicts()

    slides = [
        SlideData(
            id=d["id"],
            title=d["title"],
            text=d["text"],
            image=d["image"],
            images=d["images"],
        )
        for d in legacy_dicts
    ]
    return ParsedDocument(slide_units=slides)


def parse_textbook_pdf(file_path: str) -> ParsedDocument:
    """
    Backward-compatible textbook-mode PDF parser:
    Groups pages by chapter/unit headings and hard-chunks text every 150 words.
    """
    import fitz
    doc = fitz.open(file_path)
    current_chapter = "Introduction"
    chapter_texts: Dict[str, List[str]] = {}
    chapter_images: Dict[str, List[dict]] = {}

    for page in doc:
        detected_title, body_text = _page_to_structured_text(page)

        chapter_match = _detect_chapter_heading(detected_title or body_text)
        if chapter_match:
            current_chapter = chapter_match

        if current_chapter not in chapter_texts:
            chapter_texts[current_chapter] = []
            chapter_images[current_chapter] = []

        if body_text.strip():
            chapter_texts[current_chapter].append(body_text)

        images = _extract_page_images(page, doc)
        chapter_images[current_chapter].extend(images)

        word_count = len(body_text.split())
        if word_count < 25:
            rendered = _render_page_as_image(page)
            if rendered:
                chapter_images[current_chapter].append(rendered)

    doc.close()

    slides = []
    global_id = 0
    CHUNK_SIZE = 150

    for chapter, texts in chapter_texts.items():
        combined = " ".join(texts)
        words = combined.split()
        img_idx = 0
        chapter_imgs = chapter_images[chapter]

        for part_idx, word_start in enumerate(range(0, max(1, len(words)), CHUNK_SIZE)):
            chunk_words = words[word_start: word_start + CHUNK_SIZE]
            chunk_text = " ".join(chunk_words) if chunk_words else "(Visual Content)"

            img_dict = None
            if img_idx < len(chapter_imgs):
                img_dict = chapter_imgs[img_idx]
                img_idx += 1

            slides.append(SlideData(
                id=global_id,
                title=f"{chapter} — Part {part_idx + 1}",
                text=chunk_text,
                image=img_dict,
            ))
            global_id += 1

    return ParsedDocument(slide_units=slides)
