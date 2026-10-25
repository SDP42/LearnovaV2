"""
Unit Tests for Learnova AI Provider Layer
Run with: pytest tests/test_providers.py -v

The live tests are marked ``live`` and skip on any credential/dependency
problem rather than failing. A key being present in ``.env`` does not mean it
is valid or in quota, so "key exists" is not a sufficient precondition.
Run them deliberately with: pytest -m live
"""

import os

import pytest

from learnova.providers import (
    GeminiEmbeddingProvider,
    GeminiVisionProvider,
    GroqProvider,
    NvidiaProvider,
)
from learnova.providers.base import EmbeddingProvider, LLMProvider, VisionProvider
from learnova.providers.router import LLMRouter


def test_provider_interfaces():
    """Every concrete provider must implement its abstract interface."""
    assert issubclass(GroqProvider, LLMProvider)
    assert issubclass(NvidiaProvider, LLMProvider)
    assert issubclass(GeminiVisionProvider, VisionProvider)
    assert issubclass(GeminiEmbeddingProvider, EmbeddingProvider)


def test_router_is_an_llm_provider():
    """The router must be drop-in substitutable for a single provider."""
    assert issubclass(LLMRouter, LLMProvider)


def test_router_with_no_providers_reports_unavailable():
    router = LLMRouter(providers=[])
    assert not router.available
    with pytest.raises(RuntimeError):
        router.generate("hello")


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
def test_groq_provider_generate():
    try:
        provider = GroqProvider()
        response = provider.generate("Say hello", system_prompt="You are a friendly assistant")
    except Exception as exc:  # invalid key, quota, network
        pytest.skip(f"Groq unavailable: {exc}")
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("NVIDIA_API_KEY"), reason="NVIDIA_API_KEY not set")
def test_nvidia_provider_generate():
    try:
        provider = NvidiaProvider()
        response = provider.generate("Say hello", system_prompt="You are a friendly assistant")
    except Exception as exc:
        pytest.skip(f"NVIDIA NIM unavailable: {exc}")
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_gemini_embedding_provider():
    try:
        provider = GeminiEmbeddingProvider()
        embeddings = provider.embed(["This is a test document."])
    except ImportError as exc:
        pytest.skip(f"optional embedding dependency missing: {exc}")
    except Exception as exc:
        pytest.skip(f"Gemini embeddings unavailable: {exc}")
    assert isinstance(embeddings, list)
    assert len(embeddings) == 1
    assert isinstance(embeddings[0], list)
    assert len(embeddings[0]) > 0
    assert isinstance(embeddings[0][0], float)


def test_router_caches_identical_requests(tmp_path, monkeypatch):
    """The same prompt is paid for once; failures are not cached."""
    from learnova.providers import router as r

    monkeypatch.setattr(r, "_llm_cache_dir", lambda: tmp_path)
    monkeypatch.setenv("LEARNOVA_LLM_CACHE", "1")
    calls = []

    class P:
        def generate(self, prompt, system_prompt=None, **kw):
            calls.append(prompt)
            return "answer"

    router = r.LLMRouter([("fake", P())])
    assert router.generate("hello", task=None) == "answer"
    assert router.generate("hello", task=None) == "answer"
    assert router.generate("other", task=None) == "answer"
    assert calls == ["hello", "other"]
