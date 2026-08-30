"""
Storage for Gallery decks.

Generated gallery decks live under the synthetic user ``__gallery__`` so they
reuse every ``deck_library`` primitive (markdown, pptx, html, slides payload,
editable list, meta, versions). ``clone_to_user`` copies one deck directory
into a real user's library with a fresh id, so "Use this deck" produces a
normal, fully-editable deck the user owns.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from typing import Dict, List, Optional

from learnova.gallery.catalog import GALLERY_USER, load_catalog
from learnova.logging_config import logger
from learnova.storage import deck_library as dl


def _gallery_dir(slug: str):
    return dl._deck_dir(GALLERY_USER, slug)  # noqa: SLF001 — same package intent


def has_deck(slug: str) -> bool:
    return (_gallery_dir(slug) / dl.META_FILE).is_file()


def get_deck_meta(slug: str) -> Optional[dict]:
    return dl.get_deck(GALLERY_USER, slug)


def read_slides(slug: str) -> Optional[dict]:
    return dl.read_slides(GALLERY_USER, slug)


def ready_slugs() -> set[str]:
    root = dl._user_dir(GALLERY_USER)  # noqa: SLF001
    if not root.is_dir():
        return set()
    return {p.name for p in root.iterdir() if (p / dl.META_FILE).is_file()}


def catalog_with_decks(entries) -> List[dict]:
    ready = ready_slugs()
    metas: Dict[str, dict] = {}
    for slug in ready:
        m = dl.get_deck(GALLERY_USER, slug)
        if m:
            metas[slug] = m
    return [e.to_dict(metas.get(e.slug)) for e in entries]


def clone_to_user(slug: str, user_id: str) -> Optional[str]:
    """Copy a gallery deck into ``user_id``'s library. Returns the new deck id."""
    src = _gallery_dir(slug)
    if not (src / dl.META_FILE).is_file():
        return None

    new_id = uuid.uuid4().hex[:16]
    dst = dl._deck_dir(user_id, new_id)  # noqa: SLF001
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    meta_path = dst / dl.META_FILE
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {}
    meta["id"] = new_id
    meta["user_id"] = user_id
    meta["created_at"] = time.time()
    meta["from_gallery"] = slug
    meta["version"] = 1
    meta["versions"] = []
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # drop copied version history so the user starts clean
    vdir = dst / dl.VERSIONS_DIR
    if vdir.is_dir():
        shutil.rmtree(vdir, ignore_errors=True)

    logger.info("cloned gallery deck %s -> user %s deck %s", slug, user_id, new_id)
    return new_id
