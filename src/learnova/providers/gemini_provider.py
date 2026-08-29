"""
GeminiProvider — Google Gemini as a text LLMProvider.

Why it exists: Groq's free tier has a hard 200k-tokens/day ceiling that a
single lecture deck can exhaust, and the NVIDIA NIM endpoint is slow and
frequently times out. Gemini's free tier (``gemini-3.5-flash-lite`` and the
``gemini-flash-latest`` alias) has a far larger daily budget and structures
teaching JSON better than ``gpt-oss-20b``.

The ``google-genai`` SDK is imported lazily inside ``__init__`` — importing it
at module load spins up gRPC C-threads that segfault under ``fork()`` in the
render subprocesses (same reasoning as ``providers/gemini_vision.py``).
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional

from learnova.logging_config import logger
from learnova.providers.base import LLMProvider

# Free tier is 15 requests/minute/model. Space calls ~4.2 s apart so a long
# pipeline run stays under the cap instead of tripping the router's circuit
# breaker mid-deck. Override with GEMINI_MIN_INTERVAL (seconds); 0 disables.
_MIN_INTERVAL = float(os.getenv("GEMINI_MIN_INTERVAL", "4.2"))
_pace_lock = threading.Lock()
_last_call = [0.0]


def _pace() -> None:
    if _MIN_INTERVAL <= 0:
        return
    with _pace_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


class GeminiProvider(LLMProvider):
    """Concrete ``LLMProvider`` backed by the Gemini API."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 45.0):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")

        from google import genai as _genai

        self._genai = _genai
        try:
            from google.genai import types as _types

            self._types = _types
            http_opts = _types.HttpOptions(timeout=int(timeout * 1000))  # ms
            self.client = _genai.Client(api_key=self.api_key, http_options=http_opts)
        except Exception:
            self._types = None
            self.client = _genai.Client(api_key=self.api_key)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _model(self, kwargs: Dict[str, Any]) -> str:
        return kwargs.get("model") or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    def _config(self, system_prompt: Optional[str], kwargs: Dict[str, Any],
                *, minimal: bool = False):
        """Build a GenerateContentConfig. ``minimal`` drops every optional field
        so a 400 from a fussy model can be retried with just the essentials."""
        if self._types is None:
            return None
        t = self._types
        opts: Dict[str, Any] = {
            "temperature": kwargs.get("temperature", 0.3),
            "max_output_tokens": kwargs.get("max_tokens") or 2048,
        }
        if not minimal:
            if system_prompt:
                opts["system_instruction"] = system_prompt
            # Flash models "think" by default, which doubles latency. Only ask
            # to disable it when the caller explicitly wants the fast path AND
            # opts in — some models 400 on an unexpected thinking_config, and
            # the generate() wrapper falls back to `minimal` if that happens.
            effort = str(kwargs.get("reasoning_effort", "")).lower()
            if effort in {"low", "none", "0"} and kwargs.get("disable_thinking"):
                try:
                    opts["thinking_config"] = t.ThinkingConfig(thinking_budget=0)
                except Exception:
                    pass
        try:
            return t.GenerateContentConfig(**opts)
        except Exception:
            return t.GenerateContentConfig(
                temperature=opts["temperature"],
                max_output_tokens=opts["max_output_tokens"],
            )

    def _generate_once(self, prompt: str, system_prompt: Optional[str],
                       kwargs: Dict[str, Any], *, minimal: bool) -> str:
        _pace()
        cfg = self._config(system_prompt, kwargs, minimal=minimal)
        contents = prompt
        if minimal and system_prompt:
            contents = f"{system_prompt}\n\n{prompt}"
        resp = self.client.models.generate_content(
            model=self._model(kwargs),
            contents=contents,
            **({"config": cfg} if cfg is not None else {}),
        )
        return (getattr(resp, "text", None) or "").strip()

    # ── LLMProvider interface ────────────────────────────────────────────────
    def generate(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any
    ) -> str:
        try:
            return self._generate_once(prompt, system_prompt, kwargs, minimal=False)
        except Exception as exc:
            if "INVALID_ARGUMENT" in str(exc) or "400" in str(exc):
                logger.warning("Gemini rejected full config (%s) — retrying minimal", exc)
                return self._generate_once(prompt, system_prompt, kwargs, minimal=True)
            raise

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        system = "\n\n".join(
            m["content"] for m in messages if m.get("role") == "system"
        )
        turns = [m["content"] for m in messages if m.get("role") != "system"]
        return self.generate("\n\n".join(turns), system_prompt=system or None, **kwargs)

    def rewrite(self, text: str, instructions: str, **kwargs: Any) -> str:
        return self.generate(f"Instructions: {instructions}\n\nText:\n{text}", **kwargs)
