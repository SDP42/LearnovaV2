"""
Image generation providers, enabled by an API key alone.

* ``gemini`` — Google's image models over plain REST (no SDK needed). Default model ``gemini-2.5-flash-image``;
  ``imagen-*`` ids use the Imagen ``predict`` endpoint. The key is ``GEMINI_IMAGE_API_KEY`` if set (so image
  generation can use its own key, billed separately) and ``GEMINI_API_KEY`` otherwise.
* ``pollinations`` — keyless, opt-in with ``LEARNOVA_IMAGE_PROVIDER=pollinations`` (prompts are sent to a third party).
* nothing configured → callers fall back to the offline vector illustrator.

``LEARNOVA_IMAGE_AI=0`` switches AI images off even when a key exists.
A provider that fails twice in a row is paused for the rest of the process, so a bad key or an outage costs one
slow slide, not one per slide.
"""

from __future__ import annotations

import base64
import io
import os
import threading
import time
import urllib.parse
from typing import Any, Dict, Optional

from learnova.logging_config import logger

DEFAULT_MODEL = "gemini-2.5-flash-image"
_API = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT = 40.0
_lock = threading.Lock()
_fails: Dict[str, int] = {}
_paused_until: Dict[str, float] = {}


def _key() -> str:
    return (os.getenv("GEMINI_IMAGE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()


def provider_name() -> str:
    if os.getenv("LEARNOVA_IMAGE_AI", "1").lower() in {"0", "false", "off", "no"}:
        return ""
    wanted = os.getenv("LEARNOVA_IMAGE_PROVIDER", "").strip().lower()
    if wanted == "pollinations":
        return "pollinations"
    if _key() and wanted in {"", "gemini"}:
        return "gemini"
    return ""


def status() -> Dict[str, Any]:
    name = provider_name()
    return {"configured": bool(name), "provider": name or "vector", "model": os.getenv("LEARNOVA_IMAGE_MODEL", DEFAULT_MODEL) if name == "gemini" else "",
            "separate_key": bool(os.getenv("GEMINI_IMAGE_API_KEY")), "paused": bool(name and _paused_until.get(name, 0) > time.time())}


def _png(data: bytes, max_side: int = 1400) -> Optional[bytes]:
    """Validate and normalise whatever came back to a PNG of sane size."""
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data))
        im.load()
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side))
        out = io.BytesIO()
        im.convert("RGB").save(out, "PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return None


def _record(name: str, ok: bool) -> None:
    with _lock:
        if ok:
            _fails[name] = 0
            return
        _fails[name] = _fails.get(name, 0) + 1
        if _fails[name] >= 2:
            _paused_until[name] = time.time() + 600
            logger.warning("image provider %s failed twice — paused for 10 minutes", name)


def reset() -> None:
    with _lock:
        _fails.clear()
        _paused_until.clear()


def _http(client=None):
    import httpx

    return client or httpx.Client(timeout=_TIMEOUT)


def _gemini(prompt: str, aspect: str, client=None) -> Optional[bytes]:
    model = os.getenv("LEARNOVA_IMAGE_MODEL", DEFAULT_MODEL)
    headers = {"x-goog-api-key": _key(), "Content-Type": "application/json"}
    if model.startswith("imagen"):
        body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": aspect}}
        r = _http(client).post(f"{_API}/models/{model}:predict", headers=headers, json=body)
        r.raise_for_status()
        pred = (r.json().get("predictions") or [{}])[0]
        return base64.b64decode(pred["bytesBase64Encoded"]) if pred.get("bytesBase64Encoded") else None
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["IMAGE"]}}
    r = _http(client).post(f"{_API}/models/{model}:generateContent", headers=headers, json=body)
    r.raise_for_status()
    for cand in r.json().get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                return base64.b64decode(blob["data"])
    return None


def _pollinations(prompt: str, aspect: str, client=None) -> Optional[bytes]:
    w, h = (1024, 768) if aspect in {"4:3", "landscape"} else (768, 1024) if aspect == "3:4" else (1024, 1024)
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt[:600])}?width={w}&height={h}&nologo=true&model=flux"
    r = _http(client).get(url, follow_redirects=True)
    r.raise_for_status()
    return r.content


def generate(prompt: str, aspect: str = "4:3", client=None) -> Optional[bytes]:
    """PNG bytes for ``prompt`` from the configured provider, or None (not configured, paused, or failed)."""
    name = provider_name()
    if not name or _paused_until.get(name, 0) > time.time():
        return None
    fn = _gemini if name == "gemini" else _pollinations
    for attempt in range(2):
        try:
            raw = fn(prompt, aspect, client)
            png = _png(raw) if raw else None
            _record(name, bool(png))
            return png
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", 0)
            logger.info("image provider %s attempt %d failed (%s %s)", name, attempt + 1, status_code or "", type(exc).__name__)
            if status_code in {400, 401, 403, 404}:          # bad key / bad model: retrying will not help
                _record(name, False)
                _record(name, False)
                return None
            if attempt == 0:
                time.sleep(1.5)
    _record(name, False)
    return None


def style_prompt(subject: str, primary_hex: str, accent_hex: str, style: str = "flat") -> str:
    """The brief sent to the model: one clear subject, a consistent look, and no text in the picture."""
    looks = {
        "flat": "clean flat vector illustration, simple geometric shapes, soft gradients, friendly and modern",
        "isometric": "isometric 3D-style illustration, clean lines, soft shadows",
        "watercolor": "soft watercolor illustration, gentle textures, light paper background",
        "photo": "realistic editorial photograph, natural light, shallow depth of field",
    }
    return (f"An educational illustration for a presentation slide about: {subject.strip()[:300]}. "
            f"Style: {looks.get(style, looks['flat'])}. Colour accents {primary_hex} and {accent_hex} on a white or very light background. "
            "One clear central subject with generous empty space around it. No text, no letters, no numbers, no logos, no watermark, no people's faces.")


# ── keys saved from the Settings screen ──────────────────────────────────────
_KEY_VARS = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "nvidia": "NVIDIA_API_KEY", "gemini_image": "GEMINI_IMAGE_API_KEY"}


def key_vars() -> Dict[str, str]:
    return dict(_KEY_VARS)


def _env_path():
    import pathlib

    return pathlib.Path(__file__).resolve().parents[3] / ".env"


def _write_env(name: str, value: Optional[str]) -> None:
    """Set or remove ``NAME="value"`` in the project's .env (created if missing, other lines untouched)."""
    path = _env_path()
    lines = path.read_text().splitlines() if path.exists() else []
    out, done = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == name:
            if value is not None and not done:
                out.append(f'{name}="{value}"')
            done = True
            continue
        out.append(line)
    if value is not None and not done:
        out.append(f'{name}="{value}"')
    path.write_text("\n".join(out).rstrip("\n") + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def save_key(provider: str, key: str) -> None:
    name = _KEY_VARS[provider]
    os.environ[name] = key
    _write_env(name, key)
    _after_change()


def remove_key(provider: str) -> None:
    name = _KEY_VARS[provider]
    os.environ.pop(name, None)
    _write_env(name, None)
    _after_change()


def _after_change() -> None:
    reset()
    try:
        from learnova.providers.router import reset_router

        reset_router()
    except Exception:
        pass


_VERIFY = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models", "x-goog-api-key"),
    "gemini_image": ("https://generativelanguage.googleapis.com/v1beta/models", "x-goog-api-key"),
    "groq": ("https://api.groq.com/openai/v1/models", "Authorization"),
    "nvidia": ("https://integrate.api.nvidia.com/v1/models", "Authorization"),
}


def verify_key(provider: str, key: str, client=None) -> Optional[bool]:
    """True/False when the provider answered (key accepted/rejected); None when it could not be reached."""
    url, header = _VERIFY[provider]
    try:
        r = _http(client).get(url, headers={header: key if header != "Authorization" else f"Bearer {key}"}, timeout=8.0)
    except Exception:
        return None
    if r.status_code in {401, 403}:
        return False
    if r.status_code == 400 and "api key" in r.text.lower():
        return False
    return True if r.status_code < 400 else None
