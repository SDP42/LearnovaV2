"""Gemini Vision image description utilities for Learnova.

Strategy:
  1. Try Gemini Vision API (synchronous, 4s SDK-level timeout).
  2. On first 429 / RESOURCE_EXHAUSTED, set module-level _quota_exceeded flag.
  3. All subsequent images skip Gemini and go straight to local Tesseract OCR.

NO ThreadPoolExecutor — zombie background threads from shutdown(wait=False)
keep live google.genai gRPC connections open which crash macOS during GC (exit 139).
"""

import base64
import os
import subprocess
import tempfile
import time
from typing import Optional

os.environ["PYDANTIC_DISABLE_PLUGINS"] = "1"

from dotenv import load_dotenv
from learnova.providers import GeminiVisionProvider
from learnova.logging_config import logger

load_dotenv()

IMAGE_PROMPT = (
    "You are an expert OCR and Educational Visual Content Transcriber.\n"
    "1. EXTRACT AND TRANSCRIBE ALL TEXT, LABELS, CAPTIONS, HEADINGS, NUMBERS, AND TABLES VISIBLE IN THIS IMAGE WORD-FOR-WORD.\n"
    "2. IF THIS IMAGE IS A DIAGRAM, FLOWCHART, ARCHITECTURE, OR INFOGRAPHIC, DESCRIBE EVERY NODE, STEP, ARROW, RELATIONSHIP, AND CONNECTED CONCEPT IN DETAIL.\n"
    "3. IF THERE IS HANDWRITTEN TEXT, TRANSCRIBE IT VERBATIM.\n"
    "4. RETURN A STRUCTURED TEXT TRANSCRIPTION THAT CONTAINS ALL KNOWLEDGE AND TEXT FROM THE IMAGE SO IT CAN BE USED FOR EDUCATIONAL SLIDES."
)
DELAY_BETWEEN_CALLS = 0.3

# ── Module-level quota flag ───────────────────────────────────────────────────
# Set to True on the first 429 / quota error so all remaining images skip
# Gemini immediately and fall back to local Tesseract OCR.
_gemini_quota_exceeded: bool = False
_gemini_off_at: float = 0.0


def _mime_from_ext(ext: str) -> str:
    ext_l = (ext or "").lower().strip(".")
    if ext_l in {"jpg", "jpeg"}:
        return "image/jpeg"
    if ext_l == "webp":
        return "image/webp"
    if ext_l == "gif":
        return "image/gif"
    if ext_l == "bmp":
        return "image/bmp"
    return "image/png"


def local_tesseract_ocr(image_bytes: bytes) -> Optional[str]:
    """
    Perform local OCR using tesseract CLI.
    Handles printed text, handwritten notes, diagrams, and tables.
    """
    try:
        tess_bin = "tesseract"
        if os.path.exists("/opt/homebrew/bin/tesseract"):
            tess_bin = "/opt/homebrew/bin/tesseract"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [tess_bin, tmp_path, "stdout", "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if text:
                    return f"[OCR Transcription (Local):\n{text}]"
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    except Exception as e:
        logger.warning("Local tesseract OCR fallback failed: %s", e)
    return None


def describe_images(images: list[dict]) -> list[dict]:
    """Describe page images with Gemini Vision, falling back to local Tesseract OCR.

    Uses a module-level quota flag: the moment Gemini returns a 429, ALL
    remaining images instantly use Tesseract — no retries, no background threads.

    Args:
        images: List like [{"index": 0, "bytes": b"...", "ext": "png"}, ...]

    Returns:
        List like [{"index": 0, "description": "...", "bytes": b"..."}, ...]
    """
    global _gemini_quota_exceeded, _gemini_off_at
    import time as _time

    if _gemini_quota_exceeded and _time.time() - _gemini_off_at > 900:     # quotas reset; try Gemini again after a while
        _gemini_quota_exceeded = False
    failures = 0

    # Try to create the provider once; if it fails (bad key, no env var), use local OCR only.
    provider: Optional[GeminiVisionProvider] = None
    if not _gemini_quota_exceeded:
        try:
            provider = GeminiVisionProvider()
        except Exception as e:
            logger.warning("Could not initialize Gemini Vision client: %s — using Tesseract OCR only.", e)

    described_images = []
    total = len(images or [])

    for idx, image in enumerate(images or []):
        image_bytes = image.get("bytes")
        if not image_bytes and image.get("base64"):
            image_bytes = base64.b64decode(image.get("base64"))
        if not image_bytes:
            continue

        description: Optional[str] = None

        # ── 1. Gemini Vision (synchronous, SDK has 4s HTTP timeout) ──────────
        if provider and not _gemini_quota_exceeded:
            try:
                description = provider.describe_image(
                    image_bytes=image_bytes,
                    prompt=IMAGE_PROMPT,
                    models_to_try=["gemini-2.0-flash"],
                    max_retries=1,
                )
            except Exception as e:
                err_str = str(e)
                if (
                    "Quota exceeded" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "429" in err_str
                    or "timed out" in err_str.lower()
                    or "timeout" in err_str.lower()
                ):
                    _gemini_quota_exceeded, _gemini_off_at = True, _time.time()
                    logger.warning(
                        "Gemini Vision quota/timeout hit for image %s; "
                        "switching ALL remaining images to local Tesseract OCR.",
                        image.get("index", idx),
                    )
                else:
                    failures += 1
                    logger.warning("Gemini Vision OCR failed for image %s: %s", image.get("index", idx), e)
                    if failures >= 2:                       # a rejected key fails every time: stop asking
                        _gemini_quota_exceeded, _gemini_off_at = True, _time.time()

        # ── 2. Local Tesseract OCR fallback ─────────────────────────────────
        if not description:
            logger.info("Running local Tesseract OCR for image %s...", image.get("index", idx))
            description = local_tesseract_ocr(image_bytes)

        if description:
            described_images.append({
                "index": image.get("index", idx),
                "description": description,
                "bytes": image_bytes,
            })

        # Only sleep between calls when Gemini is actually being used
        if idx < total - 1 and provider and not _gemini_quota_exceeded:
            time.sleep(DELAY_BETWEEN_CALLS)

    return described_images
