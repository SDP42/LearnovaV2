"""
NVIDIA NIM provider (build.nvidia.com).

Implemented with plain ``requests`` against NVIDIA's OpenAI-compatible
chat-completions endpoint. The ``openai`` SDK is deliberately NOT used: the
wire format is a simple JSON POST, and avoiding the SDK keeps any OpenAI
package out of the dependency tree entirely.

Reasoning-tuned NIM models return their chain of thought in a separate
``reasoning_content`` field. We read ``content`` only, so JSON-mode callers
never see thinking text leak into the payload they try to parse.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

from learnova.config import NVIDIA_BASE_URL, get_nvidia_key
from learnova.logging_config import logger
from learnova.providers.base import LLMProvider

# NVIDIA rotates model ids; make it overridable. The default is a small, fast
# reasoning model — we turn thinking OFF for the pipeline's structured-JSON
# calls (set NVIDIA_THINKING=1 to allow it).
DEFAULT_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
_ALLOW_THINKING = os.getenv("NVIDIA_THINKING", "").lower() in {"1", "true", "yes", "on"}


class RateLimitedError(RuntimeError):
    """Raised on HTTP 429 so the router can fail over to another provider."""


class NvidiaProvider(LLMProvider):
    """LLMProvider backed by NVIDIA NIM's OpenAI-compatible REST endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        # Large NIM models (Nemotron Ultra) answer in ~15-60 s; the old 30 s
        # default cut them off mid-generation.
        timeout: float = 90.0,
        default_model: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key or get_nvidia_key()
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not found in environment variables.")
        self.base_url = (base_url or NVIDIA_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.default_model = default_model
        self._session = requests.Session()

    # ── LLMProvider interface ────────────────────────────────────────────────
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        model = kwargs.get("model", self.default_model)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.3),
            "stream": False,
        }
        max_tokens = kwargs.get("max_tokens")
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]

        # Nemotron 3.x reasoning models spend the budget on chain-of-thought and
        # can leave `content` empty. The pipeline wants fast structured output,
        # so disable thinking unless explicitly allowed.
        if "nemotron" in model and not _ALLOW_THINKING:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
            payload["reasoning_budget"] = 0

        response = self._session.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=kwargs.get("timeout", self.timeout),
        )

        if response.status_code == 429:
            raise RateLimitedError("NVIDIA NIM rate limit reached (HTTP 429)")
        response.raise_for_status()

        data = response.json()
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            logger.error("NVIDIA NIM returned an unexpected payload: %s", data)
            raise RuntimeError("Malformed response from NVIDIA NIM") from exc

        # Prefer `content`; only fall back to `reasoning_content` when a
        # reasoning model returned nothing else (so JSON callers still get
        # *something* to parse).
        text = (message.get("content") or "").strip()
        if not text:
            text = (message.get("reasoning_content") or "").strip()
        return text

    def rewrite(self, text: str, instructions: str, **kwargs: Any) -> str:
        return self.generate(f"Instructions: {instructions}\n\nText:\n{text}", **kwargs)
