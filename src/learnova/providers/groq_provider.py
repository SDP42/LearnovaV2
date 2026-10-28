"""
LLM Providers Implementation for Learnova.
Contains GroqProvider implementing the LLMProvider interface.
"""

import os
# Must be set before groq/pydantic import to prevent TimeoutError
# from Anaconda metadata entry_points scanning
os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")
from typing import Any, Dict, List, Optional
from groq import Groq
from learnova.providers.base import LLMProvider


import time

# Keys found spent (daily token limit, rejected) → when; each gets another chance after _KEY_RETRY_S.
_dead_keys: Dict[str, float] = {}
_KEY_RETRY_S = 900.0


def groq_keys() -> List[str]:
    """Every configured Groq key, in order: ``GROQ_API_KEY`` then the ``GROQ_API_KEYS`` pool (comma-separated)."""
    keys: List[str] = []
    for k in [os.getenv("GROQ_API_KEY", "")] + os.getenv("GROQ_API_KEYS", "").split(","):
        k = k.strip()
        if k and k not in keys:
            keys.append(k)
    return keys


def _spent(exc: Exception) -> bool:
    t = f"{type(exc).__name__} {exc}".lower()
    return any(n in t for n in ("429", "401", "403", "rate limit", "rate_limit", "tokens per day", "invalid api key", "unauthorized"))


class GroqProvider(LLMProvider):
    """Concrete implementation of LLMProvider for Groq API, rotating through a pool of free-tier keys."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        """
        Args:
            api_key: one Groq key. If not provided, every key in GROQ_API_KEY / GROQ_API_KEYS is used in turn.
            timeout: Default request timeout in seconds.
        """
        self._keys = [api_key] if api_key else groq_keys()
        if not self._keys:
            raise ValueError("GROQ_API_KEY not found in environment variables.")
        self._timeout = timeout
        self._clients: Dict[str, Any] = {}
        self._use(self._live()[0] if self._live() else self._keys[0])

    def _live(self) -> List[str]:
        now = time.time()
        return [k for k in self._keys if now - _dead_keys.get(k, -1e18) > _KEY_RETRY_S]

    def _use(self, key: str) -> None:
        if key not in self._clients:
            self._clients[key] = Groq(api_key=key, timeout=self._timeout)
        self.api_key, self.client = key, self._clients[key]

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Generate response using a simple system/user message pair.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """A chat completion; a key that is spent or rejected is set aside and the next key in the pool is tried."""
        last: Optional[Exception] = None
        for key in (self._live() or [self.api_key]):
            self._use(key)
            try:
                return self._chat_once(messages, **kwargs)
            except Exception as exc:
                if not _spent(exc) or len(self._keys) == 1:
                    raise
                _dead_keys[key] = time.time()
                last = exc
        raise last or RuntimeError("no Groq key left")

    def _chat_once(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """
        Create a chat completion.
        """
        import os as _os

        model = kwargs.get("model") or _os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        temperature = kwargs.get("temperature", 0.3)
        max_tokens = kwargs.get("max_tokens", None)
        timeout = kwargs.get("timeout", None)

        extra: Dict[str, Any] = {}
        # gpt-oss / other reasoning models on Groq spend the token budget on
        # chain-of-thought unless told otherwise, leaving `content` empty.
        if "gpt-oss" in model or "reason" in model.lower():
            # Callers that need better structured output (the layout stage writing
            # full teaching sentences) can ask for more reasoning; default stays
            # low so bulk classification stays fast.
            extra["reasoning_effort"] = kwargs.get("reasoning_effort", "low")
            extra["reasoning_format"] = "hidden"
            if max_tokens:
                # The visible answer needs headroom once thinking is hidden;
                # 512 clipped multi-bullet JSON mid-array.
                max_tokens = max(max_tokens, 900)

        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **extra,
        )
        msg = completion.choices[0].message
        text = (getattr(msg, "content", None) or "").strip()
        if not text:
            # last resort — some models leave the answer in `reasoning`
            text = (getattr(msg, "reasoning", None) or "").strip()
        return text

    def rewrite(self, text: str, instructions: str, **kwargs: Any) -> str:
        """
        Rewrite text according to instructions.
        """
        prompt = f"Instructions: {instructions}\n\nText:\n{text}"
        return self.generate(prompt, **kwargs)
