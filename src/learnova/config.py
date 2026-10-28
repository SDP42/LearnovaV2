"""
Central configuration for Learnova.

Single source of truth for filesystem paths, environment flags and API keys.
Import this instead of scattering ``os.getenv`` and ``os.path`` maths through
the codebase.

The thread-limiting environment variables must be applied *before* numpy,
PyMuPDF, lxml or any other C-extension is imported, which is why
``apply_runtime_env()`` exists as an explicit call rather than an import
side effect — entry points invoke it as their very first statement.
"""

from __future__ import annotations

import os
import pathlib
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
# config.py lives at src/learnova/config.py, so the project root is 3 levels up.
PACKAGE_DIR = pathlib.Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

LOG_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / ".cache"
DATA_DIR = PROJECT_ROOT / ".data"          # per-user saved decks
TESTS_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures"

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 50
DEFAULT_QUIZ_FREQUENCY = 4

# ── Runtime safety flags ──────────────────────────────────────────────────────
# Pinning every numeric library to a single thread, plus disabling the Obj-C
# fork check, is what keeps the PPTX/HTML build subprocesses from segfaulting.
RUNTIME_ENV: dict[str, str] = {
    "PYDANTIC_DISABLE_PLUGINS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "KMP_DUPLICATE_LIB_OK": "TRUE",
    "OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "YES",
    "TOKENIZERS_PARALLELISM": "false",
    "PYTHONFAULTHANDLER": "1",
}


def apply_runtime_env() -> None:
    """Apply the C-extension safety flags. Call first, before heavy imports."""
    for key, value in RUNTIME_ENV.items():
        os.environ.setdefault(key, value)
    try:                       # keys from the project's .env for every entry point (scripts too); never overrides a set variable
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env", override=False)
    except Exception:
        pass


def ensure_dirs() -> None:
    """Create the writable directories the app expects."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── API keys ──────────────────────────────────────────────────────────────────
def get_gemini_key() -> Optional[str]:
    pool = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    return os.getenv("GEMINI_API_KEY") or (pool[0] if pool else None)


def get_groq_key() -> Optional[str]:
    return os.getenv("GROQ_API_KEY") or None


def get_nvidia_key() -> Optional[str]:
    return os.getenv("NVIDIA_API_KEY") or None


NVIDIA_BASE_URL = os.getenv(
    "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
)


# ── Clerk ─────────────────────────────────────────────────────────────────────
def get_clerk_publishable_key() -> Optional[str]:
    """
    Clerk publishable key.

    Accepts the Vite name first, then the Next.js name, so a .env copied from
    Clerk's Next.js quickstart still works against this Vite frontend.
    """
    return (
        os.getenv("VITE_CLERK_PUBLISHABLE_KEY")
        or os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
        or os.getenv("CLERK_PUBLISHABLE_KEY")
        or None
    )


def get_clerk_secret_key() -> Optional[str]:
    return os.getenv("CLERK_SECRET_KEY") or None


def get_clerk_issuer() -> Optional[str]:
    """Explicit issuer override; otherwise derived from the publishable key."""
    return os.getenv("CLERK_ISSUER") or None


def auth_enabled() -> bool:
    """
    Auth is enforced by default (phone + OTP). Set LEARNOVA_AUTH=off to run the
    API as a single anonymous user, e.g. for the VITE_DEMO frontend or tests.
    """
    return os.getenv("LEARNOVA_AUTH", "on").lower() not in ("off", "0", "false")
