"""
LLMRouter — ordered failover across multiple LLM providers.

The router *is* an ``LLMProvider``, so any module that already accepts one
takes a router with no code change. On a rate-limit or transient error it
moves to the next provider in the chain instead of raising.

Providers are constructed lazily and defensively: a missing API key means
that provider is simply absent from the chain, never an import-time crash.

Task-based preferences let each call site express intent ("this is a bulk
JSON classification, favour the fast model") without hardcoding a vendor.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from learnova.logging_config import logger
from learnova.providers.base import LLMProvider

# Task identifiers used across the codebase.
TASK_LAYOUT = "layout"          # short JSON, high call volume, latency-sensitive
TASK_IMPROVE = "improve"        # pedagogical rewriting, quality-sensitive
TASK_QUIZ = "quiz"              # distractor quality matters
TASK_ENHANCE = "enhance"        # examples/analogies/mnemonics
TASK_DIAGRAM = "diagram"        # mermaid generation
TASK_VISUAL_DATA = "visual_data"  # extract structured data for a chosen visual family

# Preferred provider order per task. First available wins; the rest are fallback.
#
# Gemini (2.5-flash-lite, free tier) sits in front of Groq for quality-sensitive
# work — its daily budget is far larger than Groq's 200k-token/day ceiling and
# it structures teaching JSON better than gpt-oss-20b. Groq still leads the
# bulk latency-bound tasks while it has quota; Gemini catches the failover, and
# NVIDIA is the last resort. A provider that fails repeatedly is circuit-broken
# for the rest of the run (see LLMRouter._attempt).
TASK_PREFERENCE: Dict[str, Sequence[str]] = {
    TASK_LAYOUT: ("groq", "gemini", "nvidia"),
    # Groq first while it has quota (fast, free); Gemini is the quality-grade
    # failover and self-paces to stay under its 15 req/min free-tier cap.
    TASK_IMPROVE: ("groq", "gemini", "nvidia"),
    TASK_QUIZ: ("groq", "gemini", "nvidia"),
    # Enhancement is the highest-volume LLM stage in the pipeline: six
    # sequential calls per slide across up to MAX_ENHANCED_SLIDES slides, so 72
    # calls in a full run. At ~13 s per Nemotron Ultra call that is 15 minutes
    # of wall clock, and the payload is short-form ("give me one analogy") where
    # a small model is already good enough. Latency wins here; NVIDIA stays as
    # the failover for when Groq hits its TPM ceiling.
    TASK_ENHANCE: ("groq", "gemini", "nvidia"),
    TASK_DIAGRAM: ("groq", "gemini", "nvidia"),
    # Structured extraction — a compact JSON classification job, latency-sensitive
    # (one call per visual slide). Fast model first.
    TASK_VISUAL_DATA: ("groq", "gemini", "nvidia"),
}

import os as _os

# Groq periodically retires model ids (``llama-3.1-8b-instant`` started
# returning 404 for newer accounts). Make it overridable and default to a
# currently-GA fast model.
_GROQ_MODEL = _os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
# NVIDIA rotates ids too; one env var drives every task.
_NVIDIA_MODEL = _os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
# gemini-3.5-flash-lite is the current GA free-tier model (2.5-flash and
# 2.5-flash-lite are now closed to new keys). Both slots point at it; override
# GEMINI_MODEL per env if a bigger model is wanted for the quality tasks.
_GEMINI_MODEL = _os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
_GEMINI_FAST = _os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")

# Per-provider default model for each task.
TASK_MODEL: Dict[str, Dict[str, str]] = {
    "groq": {
        TASK_LAYOUT: _GROQ_MODEL,
        TASK_IMPROVE: _GROQ_MODEL,
        TASK_QUIZ: _GROQ_MODEL,
        TASK_ENHANCE: _GROQ_MODEL,
        TASK_DIAGRAM: _GROQ_MODEL,
        TASK_VISUAL_DATA: _GROQ_MODEL,
    },
    # Quality-sensitive tasks run on Nemotron 3 Ultra (550B MoE, 55B active).
    # High-volume tasks stay on a small instruct model: Ultra answers a layout
    # classification in ~13 s against Llama-3.1-8B's ~1 s, and the layout stage
    # runs once per chunk. `meta/llama-3.3-70b-instruct` was measured at 158 s
    # per call on this endpoint and is not usable as a failover target.
    "nvidia": {
        TASK_LAYOUT: _NVIDIA_MODEL,
        TASK_IMPROVE: _NVIDIA_MODEL,
        TASK_QUIZ: _NVIDIA_MODEL,
        TASK_ENHANCE: _NVIDIA_MODEL,
        TASK_DIAGRAM: _NVIDIA_MODEL,
        TASK_VISUAL_DATA: _NVIDIA_MODEL,
    },
    "gemini": {
        TASK_LAYOUT: _GEMINI_FAST,
        TASK_IMPROVE: _GEMINI_MODEL,
        TASK_QUIZ: _GEMINI_MODEL,
        TASK_ENHANCE: _GEMINI_FAST,
        TASK_DIAGRAM: _GEMINI_FAST,
        TASK_VISUAL_DATA: _GEMINI_FAST,
    },
}

# Call sites choose their timeout for Groq's small, fast models. A large NIM
# model needs longer, so a provider floor is applied on the way out — without
# it every failover to Nemotron Ultra would time out before it could answer.
PROVIDER_MIN_TIMEOUT: Dict[str, float] = {
    "nvidia": 90.0,
    # Gemini 2.5-flash with thinking disabled answers in 2-6 s, but a cold
    # connection or a thinking fallback can run longer — don't let an 8 s
    # caller timeout kill an otherwise-good call.
    "gemini": 30.0,
}


def _model_fits(provider_name: str, model: str) -> bool:
    """True when a model id belongs to the given provider's namespace."""
    # NVIDIA NIM ids are namespaced under a vendor ("meta/…", "nvidia/…"). Groq
    # also uses namespaced ids now for the hosted OSS models
    # ("openai/gpt-oss-20b", "moonshotai/…"), so match those explicitly rather
    # than treating any "/" as NVIDIA.
    gemini_ns = model.startswith(("gemini", "models/gemini"))
    if provider_name == "gemini":
        return gemini_ns
    if gemini_ns:
        return False
    nvidia_ns = model.startswith(("meta/", "nvidia/", "nv-", "mistralai/", "google/"))
    if provider_name == "nvidia":
        return nvidia_ns
    if provider_name == "groq":
        return not nvidia_ns
    return True


def _is_retryable(exc: Exception) -> bool:
    """True when the error is worth retrying on a different provider."""
    text = f"{type(exc).__name__} {exc}".lower()
    needles = (
        "ratelimit", "rate limit", "429", "quota", "too many requests",
        "resource_exhausted", "resource exhausted",
        "timeout", "timed out", "connection", "unavailable",
        "500", "502", "503", "504",
        "overloaded", "capacity", "deadline exceeded", "deadline_exceeded",
    )
    return any(n in text for n in needles)


class LLMRouter(LLMProvider):
    """Tries each provider in order, falling through on retryable failures."""

    def __init__(self, providers: Optional[List[tuple[str, LLMProvider]]] = None):
        """
        Args:
            providers: ordered ``(name, provider)`` pairs. When None, the chain
                is auto-built from whichever API keys are present.
        """
        self._providers: List[tuple[str, LLMProvider]] = (
            list(providers) if providers is not None else _build_default_chain()
        )
        if self._providers:
            logger.info(
                "LLMRouter ready with %d provider(s): %s",
                len(self._providers),
                ", ".join(name for name, _ in self._providers),
            )
        else:
            logger.warning("LLMRouter has no usable providers — no API keys found.")

    @property
    def available(self) -> bool:
        return bool(self._providers)

    @property
    def provider_names(self) -> List[str]:
        return [name for name, _ in self._providers]

    # ── ordering ─────────────────────────────────────────────────────────────
    def _ordered_for(self, task: Optional[str]) -> List[tuple[str, LLMProvider]]:
        if not task or task not in TASK_PREFERENCE:
            return self._providers
        preference = TASK_PREFERENCE[task]
        rank = {name: i for i, name in enumerate(preference)}
        return sorted(
            self._providers,
            key=lambda pair: rank.get(pair[0], len(preference)),
        )

    # Per-process circuit breaker. A provider that has failed this many times
    # in a row (quota exhausted, endpoint down) is skipped for the rest of the
    # run instead of being retried on every one of the ~200 pipeline calls —
    # that retry storm was adding minutes of dead wait to a single deck.
    _TRIP_AFTER = 4
    _fail_streak: Dict[str, int] = {}

    def _attempt(self, call: Callable[[LLMProvider, dict], str], task: Optional[str],
                 kwargs: dict) -> str:
        chain = self._ordered_for(task)
        if not chain:
            raise RuntimeError(
                "No LLM provider is configured. Set GROQ_API_KEY and/or NVIDIA_API_KEY."
            )

        live = [(n, p) for n, p in chain
                if self._fail_streak.get(n, 0) < self._TRIP_AFTER]
        if not live:  # every provider tripped — give the top one one more try
            self._fail_streak.clear()
            live = chain

        errors: List[str] = []
        for name, provider in live:
            call_kwargs = dict(kwargs)
            requested = call_kwargs.get("model")

            # A caller-pinned model belongs to one vendor. NVIDIA ids are
            # namespaced ("meta/llama-..."), Groq ids are not — so a pinned
            # Groq name would 404 on NVIDIA during failover. Swap in the right
            # id for whichever provider we are actually about to call.
            if requested and not _model_fits(name, requested):
                replacement = TASK_MODEL.get(name, {}).get(task or "")
                if replacement:
                    call_kwargs["model"] = replacement
                else:
                    call_kwargs.pop("model", None)
            elif not requested and task:
                model = TASK_MODEL.get(name, {}).get(task)
                if model:
                    call_kwargs["model"] = model

            floor = PROVIDER_MIN_TIMEOUT.get(name)
            if floor:
                call_kwargs["timeout"] = max(float(call_kwargs.get("timeout") or 0), floor)
            try:
                result = call(provider, call_kwargs)
                self._fail_streak[name] = 0
                return result
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                self._fail_streak[name] = self._fail_streak.get(name, 0) + 1
                tripped = self._fail_streak[name] >= self._TRIP_AFTER
                if _is_retryable(exc) and len(live) > 1:
                    logger.warning(
                        "LLMRouter: %s failed (%s) — falling through to next provider.%s",
                        name, exc,
                        " Circuit opened for the rest of the run." if tripped else "",
                    )
                    continue
                if _is_retryable(exc):
                    # last provider in the chain, but the error is transient —
                    # surface it as retryable so the caller can use its own
                    # heuristic fallback rather than crashing the stage.
                    logger.warning("LLMRouter: %s failed (%s) — no providers left.", name, exc)
                    raise
                logger.error("LLMRouter: %s failed non-retryably: %s", name, exc)
                raise

        raise RuntimeError("All LLM providers failed: " + " | ".join(errors))

    # ── LLMProvider interface ────────────────────────────────────────────────
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str:
        task = kwargs.pop("task", None)
        return self._attempt(
            lambda p, kw: p.generate(prompt, system_prompt=system_prompt, **kw),
            task, kwargs,
        )

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        task = kwargs.pop("task", None)
        return self._attempt(lambda p, kw: p.chat(messages, **kw), task, kwargs)

    def rewrite(self, text: str, instructions: str, **kwargs: Any) -> str:
        task = kwargs.pop("task", None)
        return self._attempt(
            lambda p, kw: p.rewrite(text, instructions, **kw), task, kwargs
        )


def _build_default_chain() -> List[tuple[str, LLMProvider]]:
    """Build the provider chain from whatever credentials are available."""
    chain: List[tuple[str, LLMProvider]] = []

    try:
        from learnova.providers.groq_provider import GroqProvider

        chain.append(("groq", GroqProvider()))
    except Exception as exc:
        logger.info("LLMRouter: Groq unavailable (%s)", exc)

    try:
        from learnova.providers.gemini_provider import GeminiProvider

        chain.append(("gemini", GeminiProvider()))
    except Exception as exc:
        logger.info("LLMRouter: Gemini unavailable (%s)", exc)

    try:
        from learnova.providers.nvidia_provider import NvidiaProvider

        chain.append(("nvidia", NvidiaProvider()))
    except Exception as exc:
        logger.info("LLMRouter: NVIDIA NIM unavailable (%s)", exc)

    return chain


_default_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    """Process-wide shared router (providers hold reusable HTTP sessions)."""
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return _default_router
