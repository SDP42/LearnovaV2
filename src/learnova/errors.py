"""
User-facing error text.

Exceptions from parsers and providers carry file paths, stack details and vendor messages. None of that belongs in
an API response. ``friendly_error`` maps the failures people actually hit to a sentence they can act on; anything
else becomes a generic message with a short reference that can be found in the server log.
"""

from __future__ import annotations

import re
import uuid
from typing import Tuple

from learnova.logging_config import logger

_RULES: Tuple[Tuple[str, str], ...] = (
    (r"cannot open broken document|failed to open file|file is not a pdf|no /root object|xref|not a pdf|pdf.*(corrupt|damaged|broken)",
     "This PDF could not be read. It may be damaged, password-protected or not a real PDF — try re-exporting it."),
    (r"package not found|not a zip file|badzipfile|bad magic number|pptx.*(corrupt|damaged)",
     "This PowerPoint file could not be read. Re-save it as .pptx (not the old .ppt format) and try again."),
    (r"password|encrypted",
     "This file is password-protected. Remove the password and upload it again."),
    (r"too many pages|page limit",
     "This document has more pages than the limit. Split it into parts and upload them separately."),
    (r"timed out|timeout",
     "This took too long and was stopped. Try a shorter document or generate again."),
    (r"no text|empty document|nothing to convert",
     "No readable text was found in this file. If it is a scan, enable text recognition (OCR) and try again."),
    (r"rate.?limit|429|quota",
     "The AI service is busy right now. The deck can still be built without it — generate again, or try in a minute."),
)


def friendly_error(exc: BaseException | str, *, context: str = "") -> str:
    """A safe, actionable message for ``exc``; the full detail goes to the log under a short reference."""
    raw = str(exc)
    low = raw.lower()
    for pattern, message in _RULES:
        if re.search(pattern, low):
            logger.info("friendly_error (%s): %s", context or "job", raw[:200])
            return message
    ref = uuid.uuid4().hex[:6]
    logger.error("unclassified error %s (%s): %s", ref, context or "job", raw[:400])
    return f"Something went wrong while building this deck (ref {ref}). Please try again; if it keeps happening, send us that reference."
