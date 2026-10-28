"""
Learnova REST API (FastAPI).

Drives the same ``learnova.pipeline.orchestrator`` as the Streamlit app. The
pipeline far outlives an HTTP request, so uploads return a job id immediately
and the client polls ``GET /api/jobs/{id}`` for stage progress.

Auth: the React app sends Clerk's session JWT as ``Authorization: Bearer ...``.
It is verified against Clerk's JWKS — the user id is never taken from the
client. When Clerk is not configured the API runs in anonymous single-user
mode so local development still works.

Run with:  uvicorn apps.api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from learnova.config import apply_runtime_env

apply_runtime_env()

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from learnova.auth import AuthError, phone as phone_auth, user_id_from_header
from learnova.auth.phone import PhoneAuthError
from learnova.config import MAX_FILE_SIZE_MB, auth_enabled, ensure_dirs, get_clerk_publishable_key
from learnova.logging_config import logger
from learnova.security import RateLimitMiddleware
from learnova.parsers.markdown_converter import from_typed_text, split_sections
from learnova.pipeline.jobs import Job, get_store
from learnova.pipeline.orchestrator import STAGES, PipelineConfig
from learnova.pipeline.density import PROFILES
from learnova.rendering.deck_payload import payload_to_editable, slides_payload as _slides_payload
from learnova.rendering.theme_engine import FONT_CHOICES, THEMES
from learnova.storage import deck_library

ensure_dirs()

app = FastAPI(
    title="Learnova API",
    version="1.0.0",
    description="Transform text-heavy PPTX/PDF documents into visual decks.",
)

# Dev origins by default; CORS_ORIGINS (comma-separated) adds deployed frontends.
_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5190",
    "http://127.0.0.1:5190",
    "http://localhost:3000",
] + [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)  # toggled per request via LEARNOVA_RATE_LIMIT=off

ALLOWED_SUFFIXES = {".pptx", ".pdf", ".docx", ".md", ".markdown", ".txt"}
ANONYMOUS_USER = "anonymous"


# ── Auth ──────────────────────────────────────────────────────────────────────
def current_user(authorization: Optional[str] = Header(default=None)) -> str:
    """
    Resolve the caller's user id from a verified Clerk token.

    With Clerk unconfigured everything collapses to a single anonymous user, so
    the API stays usable locally without keys.
    """
    if not auth_enabled():
        return ANONYMOUS_USER
    token = _bearer(authorization)
    uid = phone_auth.user_id_from_token(token)
    if uid:
        return uid
    if get_clerk_publishable_key():  # legacy Clerk sessions still accepted
        try:
            return user_id_from_header(authorization)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    raise HTTPException(status_code=401, detail="Sign in to continue")


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _require_own_job(job_id: str, user_id: str) -> Job:
    """Fetch a job, 404-ing if it is missing *or* owned by someone else."""
    job = get_store().get(job_id)
    # Deliberately 404 rather than 403 so ids cannot be probed for existence.
    if job is None or (job.user_id or ANONYMOUS_USER) != user_id:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# ── Phone / OTP auth ──────────────────────────────────────────────────────────
class OtpRequest(BaseModel):
    phone: str


class OtpVerify(BaseModel):
    phone: str
    code: str


class ProfileUpdate(BaseModel):
    full_name: str
    email: str = ""
    role: str = ""
    organization: str = ""
    avatar_color: str = ""


@app.exception_handler(PhoneAuthError)
async def _phone_auth_error(_: Request, exc: PhoneAuthError) -> JSONResponse:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return JSONResponse({"detail": str(exc)}, status_code=exc.status, headers=headers)


@app.post("/api/auth/otp/request")
def auth_request_otp(body: OtpRequest) -> dict:
    return phone_auth.request_otp(body.phone)


@app.post("/api/auth/otp/verify")
def auth_verify_otp(body: OtpVerify, request: Request) -> dict:
    return phone_auth.verify_otp(body.phone, body.code, request.headers.get("user-agent", ""))


@app.get("/api/auth/me")
def auth_me(user_id: str = Depends(current_user)) -> dict:
    user = phone_auth.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user


@app.put("/api/auth/profile")
def auth_update_profile(body: ProfileUpdate, user_id: str = Depends(current_user)) -> dict:
    return phone_auth.update_profile(user_id, **body.model_dump())


@app.post("/api/auth/logout", status_code=204)
def auth_logout(authorization: Optional[str] = Header(default=None)) -> Response:
    token = _bearer(authorization)
    if token:
        phone_auth.logout(token)
    return Response(status_code=204)


class EventIn(BaseModel):
    name: str
    path: str = ""
    props: dict = {}


class ClientError(BaseModel):
    message: str
    stack: str = ""
    path: str = ""
    source: str = "client"


def _optional_user(authorization: Optional[str]) -> Optional[str]:
    return phone_auth.user_id_from_token(_bearer(authorization))


@app.post("/api/events", status_code=204)
def track_event(body: EventIn, authorization: Optional[str] = Header(default=None)) -> Response:
    """First-party, privacy-friendly analytics: no cookies, no third party."""
    phone_auth.record_event(body.name, body.path, body.props, _optional_user(authorization))
    return Response(status_code=204)


@app.post("/api/errors", status_code=204)
def report_client_error(body: ClientError, authorization: Optional[str] = Header(default=None)) -> Response:
    phone_auth.record_error(body.source, body.message, body.stack, body.path, _optional_user(authorization))
    return Response(status_code=204)


@app.post("/api/auth/logout-all", status_code=204)
def auth_logout_all(user_id: str = Depends(current_user)) -> Response:
    phone_auth.logout_all(user_id)
    return Response(status_code=204)


@app.delete("/api/auth/account", status_code=204)
def auth_delete_account(user_id: str = Depends(current_user)) -> Response:
    phone_auth.delete_account(user_id)
    return Response(status_code=204)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    try:
        phone_auth.record_error("server", f"{type(exc).__name__}: {exc}", path=request.url.path)
    except Exception:  # never let logging mask the real failure
        pass
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


# ── Models ────────────────────────────────────────────────────────────────────
class MarkdownUpdate(BaseModel):
    markdown: str


class TypedInput(BaseModel):
    text: str
    title: str = "Typed Syllabus"
    expand: bool = True            # a short request ("Gradient descent for beginners") is written out into a full lesson
    audience: str = ""
    tone: str = ""
    detail: str = "balanced"       # compact | balanced | detailed — how many sections the written lesson has


class ThemeSpec(BaseModel):
    primary: Optional[str] = None
    secondary: Optional[str] = None
    background: Optional[str] = None
    font_id: Optional[str] = None
    name: Optional[str] = None
    template_id: Optional[str] = None


class GenerateRequest(BaseModel):
    theme_id: str = "auto"                 # "auto", a curated preset, or any palette id from /api/palettes
    template_id: Optional[str] = None      # structural template from /api/templates (header, title slide, cards, footer)
    theme_spec: Optional[ThemeSpec] = None
    quiz_frequency: int = 4
    quiz_positions: Optional[list[int]] = None
    quiz_style: str = "slide"
    enable_vision_ocr: bool = True
    enable_quizzes: bool = True
    enable_illustrations: bool = True
    images: str = "auto"                   # auto | vector | ai | off — "ai" and "auto" use a generated image when an image key is configured
    build_pptx: bool = True
    build_html: bool = True
    content_mode: str = "preserve"
    slide_detail: str = "balanced"
    text_density: str = "medium"
    enable_enhancement: bool = True
    markdown: Optional[str] = None
    # Advisory visual-family bias from the studio's "Visual style" picker
    # (e.g. "PROCESS_LINEAR", "TIMELINE"). Consumed by a future biasing pass in
    # the visual planner; accepted now so the UI contract is stable.
    visual_hint: Optional[str] = None


def _config_from(request: GenerateRequest, textbook_mode: bool = False) -> PipelineConfig:
    spec = request.theme_spec.model_dump(exclude_none=True) if request.theme_spec else {}
    if request.template_id:
        spec = {**spec, "template_id": request.template_id}
    spec = spec or None
    return PipelineConfig(
        theme_id=request.theme_id,
        theme_spec=spec or None,
        quiz_frequency=request.quiz_frequency,
        quiz_positions=request.quiz_positions or None,
        quiz_style=request.quiz_style,
        enable_illustrations=request.enable_illustrations,
        image_mode=request.images if request.images in {"auto", "vector", "ai", "off"} else "auto",
        textbook_mode=textbook_mode,
        enable_vision_ocr=request.enable_vision_ocr,
        enable_quizzes=request.enable_quizzes,
        build_pptx=request.build_pptx,
        build_html=request.build_html,
        content_mode=request.content_mode,
        slide_detail=request.slide_detail,
        text_density=request.text_density,
        enable_enhancement=request.enable_enhancement,
    )


# ── Meta ──────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict:
    """Liveness plus the facts an operator (or a demo audience) wants: queue, storage, optional engines."""
    import shutil

    from learnova.pipeline import job_db

    db_ok = True
    try:
        with job_db._db() as c:
            c.execute("SELECT 1").fetchone()
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded", "stages": STAGES, "auth_enabled": auth_enabled(),
        "queue": {"waiting": get_store().queue_depth()}, "database": db_ok,
        "libreoffice": bool(shutil.which("soffice") or os.path.exists("/Applications/LibreOffice.app")),
    }


@app.get("/api/config")
def config_status() -> dict:
    """Which optional integrations are configured (booleans only — no values)."""
    from learnova.config import get_gemini_key, get_groq_key, get_nvidia_key

    groq, nvidia, gemini = (
        bool(get_groq_key()), bool(get_nvidia_key()), bool(get_gemini_key()),
    )
    return {
        "providers": {"groq": groq, "nvidia": nvidia, "gemini": gemini},
        # Gemini is a first-class text provider in the router chain, so any one
        # of the three means the LLM path is usable.
        "llm_available": groq or nvidia or gemini,
        "flags": {
            "master_prompt": os.getenv("LEARNOVA_MASTER_PROMPT", "").lower() in {"1", "true", "yes", "on"},
            "class_segmentation": os.getenv("LEARNOVA_USE_CLASS", "").lower() in {"1", "true", "yes", "on"},
            "pptx_animation": os.getenv("LEARNOVA_PPTX_ANIM", "").lower() in {"1", "true", "yes", "on"},
        },
        "auth_enabled": auth_enabled(),
    }


@app.get("/api/palettes")
def palettes(q: str = "", category: str = "", mode: str = "", limit: int = 60, offset: int = 0) -> dict:
    """The 240-palette library, searchable (name, category, mode) and paged. Every palette is contrast-checked."""
    from learnova.rendering.palettes import CATEGORIES, search_palettes

    limit = max(1, min(240, limit))
    found = search_palettes(q=q, category=category, mode=mode)
    return {"total": len(found), "offset": offset, "limit": limit, "categories": CATEGORIES,
            "palettes": [p.to_dict() for p in found[max(0, offset): max(0, offset) + limit]]}


@app.get("/api/templates")
def templates() -> dict:
    from learnova.rendering.templates import DEFAULT_TEMPLATE_ID, list_templates

    return {"default": DEFAULT_TEMPLATE_ID, "templates": list_templates()}


@app.get("/api/themes")
def themes() -> dict:
    from learnova.rendering.palettes import CATEGORIES, PALETTES
    from learnova.rendering.templates import list_templates

    return {
        "palette_total": len(PALETTES), "palette_categories": CATEGORIES, "templates": list_templates(),
        "themes": [{"id": "auto", "name": "Auto-Detect from Topic"}]
        + [
            {
                "id": key,
                "name": palette.name,
                "primary": palette.primary_hex,
                "secondary": palette.accent_hex,
                "background": palette.bg_hex,
            }
            for key, palette in THEMES.items()
        ],
        "fonts": [
            {"id": key, "label": value["label"],
             "heading": value["heading"], "body": value["body"]}
            for key, value in FONT_CHOICES.items()
        ],
        "densities": [
            {
                "id": profile.id,
                "label": profile.label,
                "description": profile.description,
                "max_bullets": profile.max_bullets,
                "max_words_per_bullet": profile.max_words_per_bullet,
                "includes_enhancement": profile.include_enhancement,
            }
            for profile in PROFILES.values()
        ],
    }


# ── Job creation ──────────────────────────────────────────────────────────────
@app.post("/api/jobs", status_code=202)
async def create_job(
    file: UploadFile = File(...),
    textbook_mode: bool = Form(False),
    user_id: str = Depends(current_user),
) -> dict:
    suffix = pathlib.Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {suffix or 'none'}")

    payload = await file.read()
    size_mb = len(payload) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"file is {size_mb:.1f} MB; maximum is {MAX_FILE_SIZE_MB} MB",
        )
    if not payload.strip():
        raise HTTPException(status_code=400, detail="the file is empty")
    from learnova.parsers import text_inputs as ti

    if not ti.looks_like(payload, suffix):
        raise HTTPException(status_code=400, detail=f"this does not look like a real {suffix} file — re-export it and try again")

    store = get_store()
    job = store.create(source_name=file.filename or "document", user_id=user_id)
    if suffix in ti.TEXT_SUFFIXES or suffix == ti.DOCX_SUFFIX:
        # Text-like inputs are converted on the spot (milliseconds), then wait for review like any other upload.
        from learnova.errors import friendly_error
        from learnova.parsers.markdown_converter import MarkdownDocument

        try:
            md = ti.docx_to_markdown(payload) if suffix == ti.DOCX_SUFFIX else (
                ti.decode_text(payload) if suffix != ".txt" else ti.plain_text_to_markdown(ti.decode_text(payload)))
            if not md.strip():
                raise ValueError("no text found")
            doc = from_typed_text(md, source_name=pathlib.Path(file.filename or "document").stem)
            doc.source_type = suffix.lstrip(".")
            job._markdown_doc, job.markdown, job.status, job.source_type = doc, doc.markdown, "awaiting_review", doc.source_type
            job.progress = 1.0 / len(STAGES)
        except Exception as exc:
            job.status, job.error = "failed", friendly_error(exc, context="upload")
        from learnova.pipeline import job_db

        job_db.save(job, job.source_type)
        return job.to_dict()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name

    store.start_conversion(job, tmp_path, PipelineConfig(textbook_mode=textbook_mode))
    logger.info("job %s created for %s (%.1f MB)", job.id, file.filename, size_mb)
    return job.to_dict()


@app.post("/api/jobs/typed", status_code=201)
def create_typed_job(payload: TypedInput, user_id: str = Depends(current_user)) -> dict:
    text = payload.text
    if not text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    if len(text) > 400_000:
        raise HTTPException(status_code=413, detail="that is too much text for one deck (limit 400,000 characters) — split it into parts")

    from learnova.ai import lesson_writer
    from learnova.pipeline import job_db

    title, expansion = payload.title, None
    if payload.expand and lesson_writer.is_prompt(text):
        result = lesson_writer.expand(text, audience=payload.audience, tone=payload.tone, detail=payload.detail)
        text, expansion = result.markdown, result.to_dict()
        if title in {"", "Typed Syllabus"}:
            m = __import__("re").match(r"#\s+(.+)", text)
            title = m.group(1).strip() if m else title

    store = get_store()
    job = store.create(source_name=title, user_id=user_id)
    doc = from_typed_text(text, source_name=title)
    job._markdown_doc = doc
    job.markdown = doc.markdown
    job.status = "awaiting_review"
    job.source_type = "typed"
    job.expansion = expansion
    job_db.save(job, "typed")
    return job.to_dict()


# ── Job inspection ────────────────────────────────────────────────────────────
@app.get("/api/jobs")
def list_jobs(user_id: str = Depends(current_user)) -> dict:
    return {
        "jobs": [
            job.to_dict()
            for job in get_store().all(user_id)
            if (job.user_id or ANONYMOUS_USER) == user_id
        ]
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, user_id: str = Depends(current_user)) -> dict:
    return _require_own_job(job_id, user_id).to_dict()


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, user_id: str = Depends(current_user)) -> Response:
    _require_own_job(job_id, user_id)
    get_store().delete(job_id)
    return Response(status_code=204)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user_id: str = Depends(current_user)) -> dict:
    job = _require_own_job(job_id, user_id)
    return {"id": job.id, "cancelling": get_store().cancel(job_id), "status": job.status}


# ── Markdown IR ───────────────────────────────────────────────────────────────
@app.get("/api/jobs/{job_id}/markdown")
def get_markdown(job_id: str, user_id: str = Depends(current_user)) -> dict:
    job = _require_own_job(job_id, user_id)
    if job.status in {"pending", "running"} and not job.markdown:
        raise HTTPException(status_code=409, detail="conversion still in progress")
    sections = split_sections(job.markdown, max_level=2)
    return {
        "job_id": job.id,
        "markdown": job.markdown,
        "section_count": len(sections),
        "sections": [{"title": s["title"], "level": s["level"]} for s in sections],
    }


@app.put("/api/jobs/{job_id}/markdown")
def put_markdown(
    job_id: str, payload: MarkdownUpdate, user_id: str = Depends(current_user)
) -> dict:
    job = _require_own_job(job_id, user_id)
    if job._markdown_doc is None:
        raise HTTPException(status_code=409, detail="conversion has not completed")
    job._markdown_doc.markdown = payload.markdown
    job.markdown = payload.markdown
    from learnova.pipeline import job_db

    job_db.save(job, job.source_type)
    return {"job_id": job.id, "saved": True, "length": len(payload.markdown)}


# ── Generation ────────────────────────────────────────────────────────────────
@app.post("/api/jobs/{job_id}/generate", status_code=202)
def start_generate(
    job_id: str, request: GenerateRequest, user_id: str = Depends(current_user)
) -> dict:
    job = _require_own_job(job_id, user_id)
    if job.status == "running":
        raise HTTPException(status_code=409, detail="job is already running")

    config = _config_from(request)

    def _persist(finished: Job) -> None:
        try:
            payload = _slides_payload(finished.result.final_deck)
        except Exception:
            payload = None
        editable = payload_to_editable(payload) if payload else None
        try:
            from learnova.analysis import build_analysis

            analysis = build_analysis(finished.result)
            try:
                from learnova.analysis.accessibility import audit as _a11y
                from learnova.rendering.theme_engine import resolve_theme

                analysis["accessibility"] = _a11y(payload or [], resolve_theme(finished.source_name, config.theme_id, config.theme_spec))
            except Exception:
                logger.warning("accessibility audit failed", exc_info=True)
        except Exception:
            logger.exception("analysis failed")
            analysis = None
        record = deck_library.save_deck(
            user_id=finished.user_id or ANONYMOUS_USER,
            result=finished.result,
            theme_id=config.theme_id,
            theme_spec=config.theme_spec,
            title=finished.source_name,
            slides_payload=payload,
            editable_slides=editable,
            analysis=analysis,
            # Reuse the job id so /api/decks/{id}/* (editor, history, figures)
            # resolve with the same id the client already has.
            deck_id=finished.id,
        )
        # Persist each slide's figure so it survives an edit / re-render.
        try:
            figures: dict = {}
            for i, entry in enumerate(finished.result.final_deck):
                img = (entry.get("original") or {}).get("image") or {}
                if img.get("bytes"):
                    figures[i] = (img["bytes"], img.get("ext", "png"))
            if figures:
                deck_library.save_images(
                    record.user_id, record.id, figures
                )
        except Exception:
            logger.warning("could not persist deck figures", exc_info=True)

    try:
        get_store().start_generation(
            job, config, markdown_override=request.markdown, on_complete=_persist
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job.to_dict()


@app.get("/api/jobs/{job_id}/deck")
def get_deck(job_id: str, user_id: str = Depends(current_user)) -> JSONResponse:
    job = _require_own_job(job_id, user_id)
    if job.result is None:
        raise HTTPException(status_code=409, detail="no result yet")

    return JSONResponse(
        {
            "job_id": job.id,
            "summary": job.result.summary(),
            "slides": _slides_payload(job.result.final_deck),
            "quizzes": job.result.quizzes,
            "scores": job.result.scores,
        }
    )


def _artifact_response(data: bytes, artifact: str, stem: str) -> Response:
    if artifact == "pptx":
        return Response(
            content=data,
            media_type=(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            headers={
                "Content-Disposition": f'attachment; filename="Learnova_Visual_{stem}.pptx"'
            },
        )
    return Response(
        content=data,
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="Learnova_Interactive_{stem}.html"'
        },
    )


@app.get("/api/jobs/{job_id}/download/{artifact}")
def download(job_id: str, artifact: str, user_id: str = Depends(current_user)) -> Response:
    job = _require_own_job(job_id, user_id)
    if job.result is None:
        raise HTTPException(status_code=409, detail="no result yet")
    if artifact not in {"pptx", "html"}:
        raise HTTPException(status_code=400, detail="artifact must be 'pptx' or 'html'")

    data = job.result.pptx_bytes if artifact == "pptx" else job.result.html_bytes
    if not data:
        raise HTTPException(status_code=404, detail=f"{artifact} was not built")
    return _artifact_response(data, artifact, pathlib.Path(job.source_name or "deck").stem)


# ── Saved deck library (per user) ─────────────────────────────────────────────
@app.get("/api/decks")
def list_my_decks(user_id: str = Depends(current_user)) -> dict:
    return {"decks": deck_library.list_decks(user_id)}


@app.get("/api/decks/{deck_id}")
def get_my_deck(deck_id: str, user_id: str = Depends(current_user)) -> dict:
    record = deck_library.get_deck(user_id, deck_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deck not found")
    return record


@app.get("/api/decks/{deck_id}/thumb")
def get_my_deck_thumb(deck_id: str, user_id: str = Depends(current_user)) -> Response:
    """16:9 PNG title card for deck grids (owner-only, cacheable)."""
    if deck_library.get_deck(user_id, deck_id) is None:
        raise HTTPException(status_code=404, detail="deck not found")
    data = deck_library.read_thumb(user_id, deck_id)
    if data is None:
        rec = deck_library.get_deck(user_id, deck_id) or {}
        from learnova.rendering.thumbnail import title_card_png

        data = title_card_png(str(rec.get("title") or "Untitled deck"), int(rec.get("slide_count") or 0))
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


# ── AI assist (optional: needs an LLM provider; every route says so plainly when there is none) ──────────
class AssistSlide(BaseModel):
    title: str = ""
    bullets: list[str] = []
    instruction: str = "Make it clearer and more concise."
    audience: str = ""


class AssistPrompt(BaseModel):
    text: str


class ProviderKey(BaseModel):
    provider: str
    key: str


_PROVIDER_INFO = {
    "gemini": ("Google Gemini", "Rewriting, quizzes, the tutor and (with the image model) generated pictures. Free key at aistudio.google.com."),
    "groq": ("Groq", "Fast rewriting and quizzes. Free key at console.groq.com."),
    "nvidia": ("NVIDIA NIM", "Higher-quality rewriting; automatic fallback. Free key at build.nvidia.com."),
    "gemini_image": ("Image generation key", "Optional separate Gemini key used only for slide pictures; falls back to the Gemini key above."),
}


def _providers_state() -> dict:
    from learnova.ai import assist, image_providers

    st = image_providers.status()
    return {
        "llm": assist.llm_available(), "image_ai": st["configured"], "image_provider": st["provider"], "image_model": st["model"],
        "editable": _keys_editable(),
        "providers": [{"id": k, "name": v[0], "hint": v[1], "configured": bool(os.getenv(image_providers.key_vars()[k]))} for k, v in _PROVIDER_INFO.items()],
    }


def _keys_editable() -> bool:
    return os.getenv("OTP_DEV_MODE", "1") == "1" or os.getenv("LEARNOVA_ALLOW_KEY_UI", "") == "1"


@app.get("/api/providers")
def providers_status(user_id: str = Depends(current_user)) -> dict:
    return _providers_state()


@app.post("/api/providers")
def providers_save(body: ProviderKey, user_id: str = Depends(current_user)) -> dict:
    """Store an API key on this server (never echoed back or logged) and switch the matching features on."""
    from learnova.ai import image_providers

    if not _keys_editable():
        raise HTTPException(status_code=403, detail="Keys are configured on the server (.env) in this deployment.")
    provider, key = body.provider.strip().lower(), body.key.strip()
    if provider not in _PROVIDER_INFO:
        raise HTTPException(status_code=400, detail="unknown provider")
    if not (16 <= len(key) <= 300) or re.search(r"\s", key):
        raise HTTPException(status_code=400, detail="that does not look like an API key")
    verified = image_providers.verify_key(provider, key)
    if verified is False:
        raise HTTPException(status_code=400, detail="the provider rejected this key — check it and try again")
    image_providers.save_key(provider, key)
    logger.info("api key saved for provider %s (verified=%s)", provider, verified)
    return {**_providers_state(), "verified": verified}


@app.delete("/api/providers/{provider}")
def providers_remove(provider: str, user_id: str = Depends(current_user)) -> dict:
    from learnova.ai import image_providers

    if not _keys_editable():
        raise HTTPException(status_code=403, detail="Keys are configured on the server (.env) in this deployment.")
    if provider not in _PROVIDER_INFO:
        raise HTTPException(status_code=400, detail="unknown provider")
    image_providers.remove_key(provider)
    return _providers_state()


@app.get("/api/assist/status")
def assist_status(user_id: str = Depends(current_user)) -> dict:
    from learnova.ai import assist
    from learnova.providers.router import get_router

    try:
        providers = get_router().provider_names
    except Exception:
        providers = []
    return {"llm": assist.llm_available(), "providers": providers,
            "image_ai": __import__("learnova.ai.image_providers", fromlist=["x"]).status()["configured"]}


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    message: str
    persona: str = "teacher"
    history: list[ChatTurn] = []


@app.get("/api/tutor/personas")
def tutor_personas(user_id: str = Depends(current_user)) -> dict:
    from learnova.ai import tutor

    return {"personas": tutor.list_personas(), "default": tutor.DEFAULT_PERSONA}


@app.post("/api/decks/{deck_id}/chat")
def deck_chat(deck_id: str, body: ChatIn, user_id: str = Depends(current_user)) -> dict:
    """Persona-based tutor grounded in one deck (LLM when a key is set; own logic otherwise)."""
    from learnova.ai import tutor

    if deck_library.get_deck(user_id, deck_id) is None:
        raise HTTPException(status_code=404, detail="deck not found")
    stored = deck_library.read_slides(user_id, deck_id) or {}
    return tutor.answer(body.message[:1200], stored.get("slides") or [], body.persona,
                        [t.model_dump() for t in body.history][-12:])


@app.post("/api/assist/slide")
def assist_slide(body: AssistSlide, user_id: str = Depends(current_user)) -> dict:
    from learnova.ai import assist

    out = assist.improve_slide(body.title, body.bullets, body.instruction, body.audience)
    if out is None:
        raise HTTPException(status_code=503, detail="No AI provider is configured (set GROQ_API_KEY, NVIDIA_API_KEY or GEMINI_API_KEY).")
    return out


@app.post("/api/assist/prompt")
def assist_prompt(body: AssistPrompt, user_id: str = Depends(current_user)) -> dict:
    from learnova.ai import assist

    return assist.improve_prompt(body.text)


@app.get("/api/decks/{deck_id}/analysis")
def get_my_deck_analysis(deck_id: str, user_id: str = Depends(current_user)) -> JSONResponse:
    """Before/after comparison against the source, written when the deck was generated."""
    if deck_library.get_deck(user_id, deck_id) is None:
        raise HTTPException(status_code=404, detail="deck not found")
    data = deck_library.read_analysis(user_id, deck_id)
    if data is None:
        raise HTTPException(status_code=404, detail="No analysis for this deck — regenerate it to create one.")
    return JSONResponse(data, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/jobs/{job_id}/analysis")
def get_job_analysis(job_id: str, user_id: str = Depends(current_user)) -> JSONResponse:
    job = _require_own_job(job_id, user_id)
    if job.result is None:
        raise HTTPException(status_code=409, detail="deck not generated yet")
    from learnova.analysis import build_analysis

    return JSONResponse(build_analysis(job.result))


@app.get("/api/decks/{deck_id}/markdown")
def get_my_deck_markdown(deck_id: str, user_id: str = Depends(current_user)) -> dict:
    markdown = deck_library.read_markdown(user_id, deck_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail="markdown not found")
    return {"deck_id": deck_id, "markdown": markdown}


@app.get("/api/decks/{deck_id}/deck")
def get_my_deck_slides(deck_id: str, user_id: str = Depends(current_user)) -> JSONResponse:
    """Slides payload for a saved deck — the job-less counterpart of
    ``/api/jobs/{id}/deck`` so Preview / Present / the diagram editor open a
    library deck without a live job."""
    record = deck_library.get_deck(user_id, deck_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deck not found")
    stored = deck_library.read_slides(user_id, deck_id) or {}
    return JSONResponse(
        {
            "job_id": deck_id,
            "summary": {
                "source_name": record.get("title", ""),
                "slide_count": record.get("slide_count", 0),
                "quiz_count": record.get("quiz_count", 0),
                "overall_score": record.get("overall_score", 0),
            },
            "slides": stored.get("slides", []),
            "quizzes": stored.get("quizzes", []),
            "scores": stored.get("scores", {}),
        }
    )


@app.get("/api/decks/{deck_id}/download/{artifact}")
def download_my_deck(
    deck_id: str, artifact: str, user_id: str = Depends(current_user)
) -> Response:
    if artifact not in {"pptx", "html"}:
        raise HTTPException(status_code=400, detail="artifact must be 'pptx' or 'html'")
    data = deck_library.read_artifact(user_id, deck_id, artifact)
    if not data:
        raise HTTPException(status_code=404, detail=f"{artifact} not found for this deck")
    record = deck_library.get_deck(user_id, deck_id) or {}
    stem = pathlib.Path(record.get("title", "deck")).stem or "deck"
    return _artifact_response(data, artifact, stem)


# ── Study pack exports ────────────────────────────────────────────────────────
_EXPORTS = {
    "flashcards": ("text/csv", "csv"), "flashcards_anki": ("text/plain", "txt"), "quiz_csv": ("text/csv", "csv"),
    "quiz_json": ("application/json", "json"), "cheatsheet": ("text/html", "html"), "script": ("text/markdown", "md"),
}


@app.get("/api/decks/{deck_id}/export/{kind}")
def export_study_pack(deck_id: str, kind: str, user_id: str = Depends(current_user)) -> Response:
    """Flashcards (CSV / Anki), quiz bank (CSV / JSON), a one-page cheat sheet and a narration script — all built from the deck."""
    from learnova.export import study_pack as sp

    if kind not in _EXPORTS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {sorted(_EXPORTS)}")
    record = deck_library.get_deck(user_id, deck_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deck not found")
    slides = (deck_library.read_slides(user_id, deck_id) or {}).get("slides") or []
    title = record.get("title") or "Deck"
    if kind == "flashcards":
        body = sp.flashcards_csv(sp.flashcards(slides))
    elif kind == "flashcards_anki":
        body = sp.flashcards_csv(sp.flashcards(slides), anki=True)
    elif kind == "quiz_csv":
        body = sp.quiz_csv(sp.quiz_bank(slides))
    elif kind == "quiz_json":
        body = sp.to_json(sp.quiz_bank(slides))
    elif kind == "cheatsheet":
        body = sp.cheatsheet_html(slides, title)
    else:
        body = sp.narration_markdown(sp.narration(slides, title), title)
    media, ext = _EXPORTS[kind]
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", pathlib.Path(title).stem)[:40] or "deck"
    return Response(content=body.encode("utf-8-sig") if ext == "csv" else body.encode("utf-8"), media_type=f"{media}; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{stem}_{kind}.{ext}"'})


@app.get("/api/decks/{deck_id}/narration")
def deck_narration(deck_id: str, user_id: str = Depends(current_user)) -> dict:
    """Per-slide spoken script with timings (the app reads it aloud with the browser's text-to-speech)."""
    from learnova.export import study_pack as sp

    record = deck_library.get_deck(user_id, deck_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deck not found")
    slides = (deck_library.read_slides(user_id, deck_id) or {}).get("slides") or []
    script = sp.narration(slides, record.get("title") or "")
    return {"slides": script, "total_seconds": sum(x["seconds"] for x in script)}


# ── Step-by-step explainers ───────────────────────────────────────────────────
class ExplainIn(BaseModel):
    problem: str


_EXPLAIN_HELP = ("I can solve linear and quadratic equations, systems of equations, percentages, interest, averages, probability, "
                 "Bayes' rule, derivatives, integrals, geometry formulas and CYK parsing. Write the problem with its numbers, "
                 "e.g. “Solve 3x + 5 = 20”.")


@app.post("/api/explain")
def explain_problem(body: ExplainIn, user_id: str = Depends(current_user)) -> dict:
    """Solve one problem the way a patient tutor would: every number is computed exactly, every step carries its reason.

    Returns the structured steps (for the app's own stepper) and a self-contained HTML page that can be dropped into a deck."""
    from learnova.explain import explainer_html, solve_text

    problem = (body.problem or "").strip()
    if len(problem) < 3:
        raise HTTPException(status_code=422, detail="Type the problem you want solved.")
    ex = solve_text(problem[:2000])
    if ex is None:
        from learnova.explain.llm import llm_explain

        ex = llm_explain(problem[:2000])                 # only when an AI key is set; marked as not computed by Learnova
    if ex is None:
        raise HTTPException(status_code=422, detail=_EXPLAIN_HELP)
    return {"explainer": ex.to_dict(), "html": explainer_html(ex)}


def _deck_explainers(user_id: str, deck_id: str) -> tuple[dict, list]:
    record = deck_library.get_deck(user_id, deck_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deck not found")
    slides = (deck_library.read_slides(user_id, deck_id) or {}).get("slides") or []
    return record, [s for s in slides if isinstance(s.get("explainer"), dict)]


@app.get("/api/decks/{deck_id}/explainers")
def list_deck_explainers(deck_id: str, user_id: str = Depends(current_user)) -> dict:
    """The solved, step-by-step problems that appear in this deck."""
    _, found = _deck_explainers(user_id, deck_id)
    return {"explainers": [{"slide": s.get("index"), "title": s.get("title", ""), "kind": s["explainer"].get("kind", ""),
                            "problem": s["explainer"].get("problem", ""), "answer": s["explainer"].get("answer", ""),
                            "steps": len(s["explainer"].get("steps") or [])} for s in found]}


@app.get("/api/decks/{deck_id}/explainers/{slide}")
def download_deck_explainer(deck_id: str, slide: int, user_id: str = Depends(current_user)) -> Response:
    """One solved problem as a standalone interactive HTML page (open it, share it, or embed it in another deck)."""
    from learnova.explain import Explainer, explainer_html

    record, found = _deck_explainers(user_id, deck_id)
    match = next((s for s in found if s.get("index") == slide), None)
    if match is None:
        raise HTTPException(status_code=404, detail="no step-by-step solution on that slide")
    ex = Explainer.from_dict(match["explainer"])
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{pathlib.Path(record.get('title') or 'deck').stem}_slide{slide + 1}")[:60]
    return Response(content=explainer_html(ex, None, match.get("title", "")).encode("utf-8"), media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{stem}_explainer.html"'})


# ── Interactive labs ──────────────────────────────────────────────────────────
class LabIn(BaseModel):
    id: str
    topics: List[str]
    html: str


@app.get("/api/labs")
def list_labs() -> dict:
    """Interactive labs and the topics that bring each one into a deck."""
    from learnova import labs

    return {"labs": labs.catalog()}


@app.get("/api/art/{art_id}")
def open_art(art_id: str) -> Response:
    """One slide illustration as a page, public so the picture in a PowerPoint can link to it."""
    from learnova.ai.topic_art import art_page

    page = art_page(art_id)
    if page is None:
        raise HTTPException(status_code=404, detail="no such illustration")
    return Response(content=page.encode("utf-8"), media_type="text/html; charset=utf-8", headers={"X-Robots-Tag": "noindex"})


@app.get("/api/labs/{lab_id}")
def open_lab(lab_id: str) -> Response:
    """A lab page, public so a PowerPoint button can open it without signing in."""
    from learnova import labs

    page = labs.lab_html(lab_id)
    if page is None:
        raise HTTPException(status_code=404, detail="no such lab")
    return Response(content=page.encode("utf-8"), media_type="text/html; charset=utf-8", headers={"X-Robots-Tag": "noindex"})


@app.post("/api/labs", status_code=201)
def add_lab(body: LabIn, user_id: str = Depends(current_user)) -> dict:
    """Add your own interactive lab (one self-contained HTML page) and the topics it explains."""
    from learnova import labs

    try:
        return labs.save_lab(body.id.strip().lower(), body.html, body.topics)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Share links ───────────────────────────────────────────────────────────────
class ShareIn(BaseModel):
    days: Optional[int] = 30


@app.post("/api/decks/{deck_id}/shares", status_code=201)
def create_share(deck_id: str, body: ShareIn, request: Request, user_id: str = Depends(current_user)) -> dict:
    from learnova.storage import shares

    if deck_library.get_deck(user_id, deck_id) is None:
        raise HTTPException(status_code=404, detail="deck not found")
    made = shares.create(user_id, deck_id, max(1, min(365, body.days)) if body.days else None)
    base = str(request.base_url).rstrip("/")
    return {**made, "url": f"{base}/api/share/{made['token']}"}


@app.get("/api/decks/{deck_id}/shares")
def list_shares(deck_id: str, user_id: str = Depends(current_user)) -> dict:
    from learnova.storage import shares

    return {"shares": shares.list_for_deck(user_id, deck_id)}


@app.delete("/api/decks/{deck_id}/shares/{token}", status_code=204)
def revoke_share(deck_id: str, token: str, user_id: str = Depends(current_user)) -> Response:
    from learnova.storage import shares

    shares.revoke(user_id, deck_id, token)
    return Response(status_code=204)


@app.get("/api/share/{token}")
def open_share(token: str) -> Response:
    """Public, read-only slideshow for a share link. No account, no editing, not indexed."""
    from learnova.storage import shares

    row = shares.resolve(token)
    if row is None:
        raise HTTPException(status_code=404, detail="This link has expired or was turned off.")
    data = deck_library.read_artifact(row["user_id"], row["deck_id"], "html")
    if not data:
        raise HTTPException(status_code=404, detail="deck not found")
    return Response(content=data, media_type="text/html; charset=utf-8",
                    headers={"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@app.delete("/api/decks/{deck_id}", status_code=204)
def delete_my_deck(deck_id: str, user_id: str = Depends(current_user)) -> Response:
    if not deck_library.delete_deck(user_id, deck_id):
        raise HTTPException(status_code=404, detail="deck not found")
    return Response(status_code=204)


# ── Deck editor ───────────────────────────────────────────────────────────────
@app.get("/api/decks/{deck_id}/editable")
def get_editable_slides(deck_id: str, user_id: str = Depends(current_user)) -> dict:
    record = deck_library.get_deck(user_id, deck_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deck not found")
    slides = deck_library.read_editable(user_id, deck_id) or []
    have_images = sorted(deck_library.read_all_images(user_id, deck_id).keys())
    return {
        "deck_id": deck_id,
        "title": record.get("title", ""),
        "version": record.get("version", 1),
        "versions": record.get("versions", []),
        "image_slides": have_images,
        "slides": slides,
    }


class SlidesEdit(BaseModel):
    slides: list[dict]
    note: str = "edited"


@app.put("/api/decks/{deck_id}/slides")
def save_deck_slides(
    deck_id: str, body: SlidesEdit, user_id: str = Depends(current_user)
) -> JSONResponse:
    record = deck_library.get_deck(user_id, deck_id)
    if record is None:
        raise HTTPException(status_code=404, detail="deck not found")
    if not body.slides:
        raise HTTPException(status_code=400, detail="no slides")

    from learnova.storage import deck_edit

    try:
        built = deck_edit.rebuild(
            body.slides,
            title=record.get("title", "Presentation"),
            theme_id=record.get("theme_id", "auto"),
            theme_spec=record.get("theme_spec"),
            images=deck_library.read_all_images(user_id, deck_id),
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"re-render failed: {exc}") from exc

    meta = deck_library.save_edit(
        user_id, deck_id,
        editable_slides=body.slides,
        slides_payload=built["slides_payload"],
        html_bytes=built["html_bytes"],
        pptx_bytes=built["pptx_bytes"],
        scores=built["scores"],
        quizzes=built["quizzes"],
        note=body.note,
    )
    if meta is None:
        raise HTTPException(status_code=404, detail="deck not found")
    return JSONResponse({
        "deck_id": deck_id,
        "version": meta.get("version"),
        "summary": {
            "source_name": meta.get("title", ""),
            "slide_count": meta.get("slide_count", 0),
            "quiz_count": meta.get("quiz_count", 0),
            "overall_score": meta.get("overall_score", 0),
        },
        "slides": built["slides_payload"],
    })


@app.post("/api/decks/{deck_id}/versions/{v}/restore")
def restore_deck_version(
    deck_id: str, v: int, user_id: str = Depends(current_user)
) -> dict:
    meta = deck_library.restore_version(user_id, deck_id, v)
    if meta is None:
        raise HTTPException(status_code=404, detail="version not found")
    return {"deck_id": deck_id, "version": meta.get("version")}


# ── Slide figures (view + re-crop / annotate) ────────────────────────────────
_IMG_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
             "webp": "image/webp", "gif": "image/gif"}


@app.get("/api/decks/{deck_id}/images/{slide}")
def get_slide_image(
    deck_id: str, slide: int, user_id: str = Depends(current_user)
) -> Response:
    if deck_library.get_deck(user_id, deck_id) is None:
        raise HTTPException(status_code=404, detail="deck not found")
    got = deck_library.read_image(user_id, deck_id, slide)
    if not got:
        raise HTTPException(status_code=404, detail="no figure on this slide")
    data, ext = got
    return Response(content=data, media_type=_IMG_MIME.get(ext, "image/png"),
                    headers={"Cache-Control": "no-store"})


@app.put("/api/decks/{deck_id}/images/{slide}")
async def put_slide_image(
    deck_id: str, slide: int, request: Request,
    user_id: str = Depends(current_user),
) -> dict:
    if deck_library.get_deck(user_id, deck_id) is None:
        raise HTTPException(status_code=404, detail="deck not found")
    ctype = request.headers.get("content-type", "")
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
           "image/gif": "gif"}.get(ctype.split(";")[0].strip(), "png")
    body = await request.body()
    if not body or len(body) > 8_000_000:
        raise HTTPException(status_code=400, detail="empty or oversized image")
    if not deck_library.save_one_image(user_id, deck_id, slide, body, ext):
        raise HTTPException(status_code=500, detail="could not save image")
    return {"deck_id": deck_id, "slide": slide, "bytes": len(body)}


# ── AI Assistant layer ───────────────────────────────────────────────────────
# See docs/ASSISTANT_MASTER_PROMPT.md. The orchestrator is transport-agnostic
# and returns a typed action for the frontend to execute; the backend only
# validates + resolves references, never fabricates results.
from learnova.assistant.orchestrator import handle as _assistant_handle
from learnova.assistant.registry import registry_payload as _registry_payload
from learnova.assistant.session import get_session_store as _session_store


class AssistantQuery(BaseModel):
    text: str
    session_id: str = "default"


@app.get("/api/assistant/registry")
def assistant_registry(user_id: str = Depends(current_user)) -> dict:
    """The presentation registry (stable ids, display numbers, aliases)."""
    return _registry_payload(user_id)


@app.get("/api/assistant/intents")
def assistant_intents() -> dict:
    from learnova.assistant.intents import dump_intents_json

    return {"intents": dump_intents_json()}


@app.post("/api/assistant/query")
def assistant_query(body: AssistantQuery, user_id: str = Depends(current_user)) -> dict:
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    session = _session_store().get(body.session_id, user_id)
    resp = _assistant_handle(body.text, session)
    return {"response": resp.to_dict(), "context": session.to_dict()}


@app.get("/api/assistant/session/{session_id}")
def assistant_session(session_id: str, user_id: str = Depends(current_user)) -> dict:
    return _session_store().get(session_id, user_id).to_dict()


# ── Gallery — shared catalogue of ready-made presentations ────────────────────
# See scripts/gallery/build_catalog.py + learnova.gallery. Decks live under a
# synthetic user; "use" clones one into the caller's own library.
from learnova.gallery import catalog as _gcat
from learnova.gallery import store as _gstore


@app.get("/api/gallery")
def gallery_list(
    subject: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    ready: bool = False,
    limit: int = 120,
    offset: int = 0,
) -> dict:
    entries = _gcat.list_entries(subject=subject, category=category, query=q, ready_only=ready)
    rows = _gstore.catalog_with_decks(entries)
    if ready:
        rows = [r for r in rows if r["has_deck"]]
    # ready decks first, then by title
    rows.sort(key=lambda r: (not r["has_deck"], r["title"].lower()))
    total = len(rows)
    page = rows[offset:offset + max(1, min(limit, 500))]
    return {
        "entries": page,
        "total": total,
        "ready_total": sum(1 for r in rows if r["has_deck"]),
        "subjects": _gcat.subjects(),
    }


@app.get("/api/gallery/{slug}")
def gallery_entry(slug: str) -> dict:
    entry = _gcat.get_entry(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown gallery topic")
    return entry.to_dict(_gstore.get_deck_meta(slug))


@app.get("/api/gallery/{slug}/deck")
def gallery_deck(slug: str) -> JSONResponse:
    entry = _gcat.get_entry(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown gallery topic")
    meta = _gstore.get_deck_meta(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="no pre-built deck for this topic yet")
    stored = _gstore.read_slides(slug) or {}
    return JSONResponse({
        "job_id": slug,
        "summary": {
            "source_name": meta.get("title", entry.title),
            "slide_count": meta.get("slide_count", 0),
            "quiz_count": meta.get("quiz_count", 0),
            "overall_score": meta.get("overall_score", 0),
        },
        "slides": stored.get("slides", []),
        "quizzes": stored.get("quizzes", []),
        "scores": stored.get("scores", {}),
    })


@app.get("/api/gallery/{slug}/download/{artifact}")
def gallery_download(slug: str, artifact: str) -> Response:
    if artifact not in {"pptx", "html"}:
        raise HTTPException(status_code=400, detail="artifact must be 'pptx' or 'html'")
    from learnova.gallery.catalog import GALLERY_USER

    data = deck_library.read_artifact(GALLERY_USER, slug, artifact)
    if not data:
        raise HTTPException(status_code=404, detail=f"no {artifact} for this topic yet")
    entry = _gcat.get_entry(slug)
    stem = pathlib.Path((entry.title if entry else slug)).stem or slug
    return _artifact_response(data, artifact, stem)


class GalleryUse(BaseModel):
    slug: str


@app.post("/api/gallery/{slug}/use", status_code=201)
def gallery_use(slug: str, user_id: str = Depends(current_user)) -> dict:
    if _gcat.get_entry(slug) is None:
        raise HTTPException(status_code=404, detail="unknown gallery topic")
    new_id = _gstore.clone_to_user(slug, user_id)
    if new_id is None:
        raise HTTPException(status_code=404, detail="no pre-built deck for this topic yet")
    return {"deck_id": new_id}
