"""
Job store for asynchronous pipeline runs.

The pipeline takes far longer than an HTTP request should, so the API returns
a job id immediately and the client polls for stage progress.

Execution is in-process threads, bounded by a semaphore (``LEARNOVA_MAX_JOBS``, default 2) so a burst of uploads
queues instead of starving the machine. State is mirrored to SQLite (``job_db``), so a restart keeps a user's
uploaded document and reports an interrupted build honestly instead of "job not found". A single process is still
assumed; swap the semaphore for a real queue if this ever runs multi-worker.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from learnova.errors import friendly_error
from learnova.logging_config import logger
from learnova.pipeline import job_db
from learnova.pipeline.orchestrator import (
    STAGES,
    PipelineConfig,
    PipelineResult,
    build_markdown,
    generate,
)


@dataclass
class Job:
    id: str
    source_name: str
    # Owner's Clerk user id. "" means anonymous (auth not configured).
    user_id: str = ""
    status: str = "pending"        # pending | running | done | failed
    stage: str = ""
    stage_status: str = ""
    progress: float = 0.0
    detail: str = ""
    error: Optional[str] = None
    markdown: str = ""
    created_at: float = field(default_factory=time.time)
    result: Optional[PipelineResult] = None
    source_type: str = ""
    _markdown_doc: Any = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict:
        payload: Dict[str, Any] = {
            "id": self.id,
            "source_name": self.source_name,
            "user_id": self.user_id,
            "status": self.status,
            "stage": self.stage,
            "stage_status": self.stage_status,
            "progress": round(self.progress, 3),
            "detail": self.detail,
            "error": self.error,
            "stages": STAGES,
            "created_at": self.created_at,
        }
        if self.result is not None:
            payload["result"] = self.result.summary()
        return payload


class JobCancelled(Exception):
    """Raised inside the worker when the user cancels a build."""


MAX_PAGES = int(os.getenv("LEARNOVA_MAX_PAGES", "400"))
_SLOTS = threading.BoundedSemaphore(max(1, int(os.getenv("LEARNOVA_MAX_JOBS", "2"))))


class JobStore:
    """Thread-safe registry of jobs.

    In-memory and single-process by design (see module docstring). To keep it
    from growing without bound it self-prunes on every ``create``: finished /
    failed jobs past ``_TTL_SECONDS`` are dropped, and the newest
    ``_MAX_JOBS`` are kept regardless.
    """

    _TTL_SECONDS = 6 * 3600
    _MAX_JOBS = 200
    _GEN_TIMEOUT_SECONDS = 20 * 60

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._waiting = 0
        n = job_db.recover_interrupted("The server restarted while this deck was being built. Your document is kept — press Generate again.")
        if n:
            logger.info("marked %d interrupted job(s) as failed after restart", n)

    def _prune_locked(self) -> None:
        now = time.time()
        done = {"done", "failed", "awaiting_review"}
        stale = [
            jid for jid, j in self._jobs.items()
            if j.status in done and now - j.created_at > self._TTL_SECONDS
        ]
        for jid in stale:
            self._jobs.pop(jid, None)
        if len(self._jobs) > self._MAX_JOBS:
            # Keep running jobs + the most recent ones.
            keep_running = {jid for jid, j in self._jobs.items() if j.status == "running"}
            by_age = sorted(self._jobs.items(), key=lambda kv: kv[1].created_at, reverse=True)
            keep = keep_running | {jid for jid, _ in by_age[: self._MAX_JOBS]}
            for jid in list(self._jobs):
                if jid not in keep:
                    self._jobs.pop(jid, None)

    def create(self, source_name: str, user_id: str = "") -> Job:
        job = Job(id=uuid.uuid4().hex[:16], source_name=source_name, user_id=user_id)
        with self._lock:
            self._prune_locked()
            self._jobs[job.id] = job
        job_db.save(job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None:
            return job
        return self._rehydrate(job_id)

    def _rehydrate(self, job_id: str) -> Optional[Job]:
        """A job that survived a restart: rebuilt from its saved row (the document's images are not kept)."""
        row = job_db.load(job_id)
        if not row:
            return None
        from learnova.parsers.markdown_converter import MarkdownDocument

        job = Job(id=row["id"], source_name=row["source_name"], user_id=row["user_id"], status=row["status"], stage=row["stage"],
                  progress=row["progress"], detail=row["detail"], error=row["error"], markdown=row["markdown"],
                  created_at=row["created_at"], source_type=row["source_type"])
        if job.markdown:
            job._markdown_doc = MarkdownDocument(markdown=job.markdown, source_name=job.source_name,
                                                 source_type=row["source_type"] or "typed", converter="restored")
        with self._lock:
            self._jobs.setdefault(job.id, job)
            return self._jobs[job.id]

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.status not in {"running", "pending"}:
            return False
        job._cancel.set()
        job.detail = "Cancelling…"
        return True

    def queue_depth(self) -> int:
        return self._waiting

    def all(self, user_id: Optional[str] = None) -> List[Job]:
        """Live jobs, plus (for one user) saved ones from before the last restart."""
        with self._lock:
            live = list(self._jobs.values())
        if user_id is not None:
            have = {j.id for j in live}
            for row in job_db.list_for_user(user_id):
                if row["id"] not in have:
                    j = self._rehydrate(row["id"])
                    if j:
                        live.append(j)
        return live

    def delete(self, job_id: str) -> bool:
        with self._lock:
            hit = self._jobs.pop(job_id, None) is not None
        job_db.delete(job_id)
        return hit

    # ── Execution ────────────────────────────────────────────────────────────
    def start_conversion(self, job: Job, path: str, config: PipelineConfig) -> None:
        """Run only the markdown conversion, so the user can review/edit it.

        ``path`` is a caller-owned temp upload; it is deleted once conversion
        has read it (success or failure) so uploads don't leak onto disk.
        """

        def _work() -> None:
            import os as _os

            job.status = "running"
            job.stage = "convert"
            job.stage_status = "running"
            job_db.save(job)
            try:
                _check_page_limit(path)
                doc = build_markdown(path, source_name=job.source_name, config=config)
                job._markdown_doc = doc
                job.markdown = doc.markdown
                job.source_type = getattr(doc, "source_type", "") or job.source_type
                if not job.markdown.strip():
                    raise ValueError("no text could be read from this document")
                job.status = "awaiting_review"
                job.stage_status = "ok"
                job.progress = 1.0 / len(STAGES)
            except Exception as exc:
                logger.error("job %s conversion failed: %s", job.id, exc, exc_info=True)
                job.status = "failed"
                job.stage_status = "failed"
                job.error = friendly_error(exc, context=f"convert {job.id}")
            finally:
                job_db.save(job, job.source_type)
                try:
                    _os.unlink(path)
                except OSError:
                    pass

        threading.Thread(target=_work, daemon=True, name=f"convert-{job.id}").start()

    def start_generation(
        self,
        job: Job,
        config: PipelineConfig,
        markdown_override: Optional[str] = None,
        on_complete: Optional[Callable[[Job], None]] = None,
    ) -> None:
        """
        Run the expensive half, optionally against user-edited markdown.

        ``on_complete`` fires on the worker thread after a successful run — the
        API uses it to persist the deck into the owner's library.
        """
        if job._markdown_doc is None:
            raise ValueError("conversion has not completed for this job")

        if markdown_override is not None:
            job._markdown_doc.markdown = markdown_override
            job.markdown = markdown_override

        job._cancel.clear()
        last_saved = {"stage": None}

        def _progress(stage: str, status: str, fraction: float, detail: str) -> None:
            if job._cancel.is_set():
                raise JobCancelled()
            job.stage = stage
            job.stage_status = status
            job.progress = fraction
            job.detail = detail
            if stage != last_saved["stage"]:               # persist on stage change, not on every tick
                last_saved["stage"] = stage
                job_db.save(job, job.source_type)

        def _work() -> None:
            job.status = "running"
            job.error = None
            # Bounded concurrency: wait for a slot, telling the client where it stands in the line.
            got = _SLOTS.acquire(blocking=False)
            if not got:
                with self._lock:
                    self._waiting += 1
                try:
                    while not got:
                        if job._cancel.is_set():
                            raise JobCancelled()
                        job.detail = f"Waiting for a free worker ({self._waiting} in line)"
                        got = _SLOTS.acquire(timeout=0.5)
                except JobCancelled:
                    job.status, job.stage_status, job.error = "failed", "failed", "Cancelled."
                    job_db.save(job, job.source_type)
                    return
                finally:
                    with self._lock:
                        self._waiting -= 1
            try:
                job.result = generate(job._markdown_doc, config=config, progress=_progress)
                # Persist before flipping to "done": the client navigates to the
                # editor as soon as it sees "done", and the editor / figure /
                # history routes read from the saved library entry.
                if on_complete:
                    try:
                        on_complete(job)
                    except Exception:
                        # Persisting is best-effort; never fail a good deck.
                        logger.error("job %s post-completion hook failed", job.id, exc_info=True)
                job.status = "done"
                job.progress = 1.0
                job.detail = ""
            except JobCancelled:
                job.status, job.stage_status, job.error = "failed", "failed", "Cancelled."
            except Exception as exc:
                logger.error("job %s generation failed: %s", job.id, exc, exc_info=True)
                job.status = "failed"
                job.stage_status = "failed"
                job.error = friendly_error(exc, context=f"generate {job.id}")
            finally:
                _SLOTS.release()
                job_db.save(job, job.source_type)

        worker = threading.Thread(target=_work, daemon=True, name=f"generate-{job.id}")
        worker.start()

        # Watchdog: a wedged provider or subprocess must not leave a job
        # "running" forever. The daemon worker keeps going, but the job is
        # reported failed so the client stops polling.
        def _watchdog() -> None:
            worker.join(self._GEN_TIMEOUT_SECONDS)
            if worker.is_alive() and job.status == "running":
                logger.error("job %s generation exceeded %ds — marking failed",
                             job.id, self._GEN_TIMEOUT_SECONDS)
                job.status = "failed"
                job.error = friendly_error("timed out", context=f"watchdog {job.id}")
                job_db.save(job, job.source_type)

        threading.Thread(target=_watchdog, daemon=True, name=f"watchdog-{job.id}").start()


def _check_page_limit(path: str) -> None:
    """Reject absurdly long PDFs early, with a message the user can act on."""
    if not path.lower().endswith(".pdf"):
        return
    try:
        import fitz

        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise ValueError("password-protected PDF")
            if doc.page_count > MAX_PAGES:
                raise ValueError(f"too many pages ({doc.page_count}; limit {MAX_PAGES})")
    except ValueError:
        raise
    except Exception:
        return          # not our job to diagnose a broken file here; the converter reports it


_store: Optional[JobStore] = None


def get_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store


__all__ = ["Job", "JobStore", "JobCancelled", "get_store"]
