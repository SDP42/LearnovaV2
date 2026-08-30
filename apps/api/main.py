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

from learnova.auth import AuthError, user_id_from_header
from learnova.config import MAX_FILE_SIZE_MB, auth_enabled, ensure_dirs
from learnova.logging_config import logger
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
    "http://localhost:3000",
] + [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_SUFFIXES = {".pptx", ".pdf"}
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
    try:
        return user_id_from_header(authorization)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _require_own_job(job_id: str, user_id: str) -> Job:
    """Fetch a job, 404-ing if it is missing *or* owned by someone else."""
    job = get_store().get(job_id)
    # Deliberately 404 rather than 403 so ids cannot be probed for existence.
    if job is None or (job.user_id or ANONYMOUS_USER) != user_id:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# ── Models ────────────────────────────────────────────────────────────────────
class MarkdownUpdate(BaseModel):
    markdown: str


class TypedInput(BaseModel):
    text: str
    title: str = "Typed Syllabus"


class ThemeSpec(BaseModel):
    primary: Optional[str] = None
    secondary: Optional[str] = None
    background: Optional[str] = None
    font_id: Optional[str] = None
    name: Optional[str] = None


class GenerateRequest(BaseModel):
    theme_id: str = "auto"
    theme_spec: Optional[ThemeSpec] = None
    quiz_frequency: int = 4
    quiz_positions: Optional[list[int]] = None
    quiz_style: str = "inline"
    enable_vision_ocr: bool = True
    enable_quizzes: bool = True
    build_pptx: bool = True
    build_html: bool = True
    content_mode: str = "compress"
    text_density: str = "medium"
    enable_enhancement: bool = True
    markdown: Optional[str] = None
    # Advisory visual-family bias from the studio's "Visual style" picker
    # (e.g. "PROCESS_LINEAR", "TIMELINE"). Consumed by a future biasing pass in
    # the visual planner; accepted now so the UI contract is stable.
    visual_hint: Optional[str] = None


def _config_from(request: GenerateRequest, textbook_mode: bool = False) -> PipelineConfig:
    spec = request.theme_spec.model_dump(exclude_none=True) if request.theme_spec else None
    return PipelineConfig(
        theme_id=request.theme_id,
        theme_spec=spec or None,
        quiz_frequency=request.quiz_frequency,
        quiz_positions=request.quiz_positions or None,
        quiz_style=request.quiz_style,
        textbook_mode=textbook_mode,
        enable_vision_ocr=request.enable_vision_ocr,
        enable_quizzes=request.enable_quizzes,
        build_pptx=request.build_pptx,
        build_html=request.build_html,
        content_mode=request.content_mode,
        text_density=request.text_density,
        enable_enhancement=request.enable_enhancement,
    )


# ── Meta ──────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "stages": STAGES, "auth_enabled": auth_enabled()}


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


@app.get("/api/themes")
def themes() -> dict:
    return {
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

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name

    store = get_store()
    job = store.create(source_name=file.filename or "document", user_id=user_id)
    store.start_conversion(job, tmp_path, PipelineConfig(textbook_mode=textbook_mode))
    logger.info("job %s created for %s (%.1f MB)", job.id, file.filename, size_mb)
    return job.to_dict()


@app.post("/api/jobs/typed", status_code=201)
def create_typed_job(payload: TypedInput, user_id: str = Depends(current_user)) -> dict:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    store = get_store()
    job = store.create(source_name=payload.title, user_id=user_id)
    doc = from_typed_text(payload.text, source_name=payload.title)
    job._markdown_doc = doc
    job.markdown = doc.markdown
    job.status = "awaiting_review"
    return job.to_dict()


# ── Job inspection ────────────────────────────────────────────────────────────
@app.get("/api/jobs")
def list_jobs(user_id: str = Depends(current_user)) -> dict:
    return {
        "jobs": [
            job.to_dict()
            for job in get_store().all()
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
        record = deck_library.save_deck(
            user_id=finished.user_id or ANONYMOUS_USER,
            result=finished.result,
            theme_id=config.theme_id,
            theme_spec=config.theme_spec,
            title=finished.source_name,
            slides_payload=payload,
            editable_slides=editable,
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
