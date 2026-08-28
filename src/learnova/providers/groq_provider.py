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


class GroqProvider(LLMProvider):
    """Concrete implementation of LLMProvider for Groq API."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        """
        Initialize the Groq client.

        Args:
            api_key: Groq API key. If not provided, reads from GROQ_API_KEY environment variable.
            timeout: Default request timeout in seconds.
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables.")
        self.client = Groq(api_key=self.api_key, timeout=timeout)

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
            extra["reasoning_effort"] = "low"
            extra["reasoning_format"] = "hidden"
            if max_tokens:
                max_tokens = max(max_tokens, 512)

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
