"""
The Gallery — a shared catalogue of ready-made presentations.

* ``catalog``  loads ``data/gallery/catalog.json`` (built by
  ``scripts/gallery/build_catalog.py``).
* ``store``    persists generated gallery decks under a synthetic
  ``__gallery__`` user, reusing ``learnova.storage.deck_library`` wholesale,
  and clones one into a real user's library on "use".
* ``builder``  runs catalogue entries through the pipeline in batch.
"""

from learnova.gallery.catalog import (  # noqa: F401
    GALLERY_USER,
    CatalogEntry,
    get_entry,
    list_entries,
    load_catalog,
    subjects,
)
