"""Write raw OpenAlex API payloads to data/raw/<run_id>/<entity>/<page>.json.gz.

Preserving raw payloads enables:
- Forensic replay when the schema changes.
- Debugging failed upserts by inspecting the upstream data.
- Compliance with OpenAlex's attribution policy.

File layout::

    data/raw/<run_id>/
        works/<journal_slug>/<page:04d>.json.gz
        sources/<page:04d>.json.gz

Each file is a gzip-compressed UTF-8 JSON document (the raw ``page`` dict
returned by the OpenAlex API — i.e. with ``results``, ``meta``, etc.).
"""

from __future__ import annotations

import gzip
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import orjson

from thrn_ingest.config import Config

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert *text* to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:80]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


class RawAuditWriter:
    """Writes gzipped page payloads organised under data/raw/<run_id>/."""

    def __init__(self, run_id: uuid.UUID) -> None:
        self._base = Config.data_raw_dir / str(run_id)
        self._counters: dict[str, int] = {}

    def _next_page(self, sub_path: str) -> int:
        key = sub_path
        n = self._counters.get(key, 0)
        self._counters[key] = n + 1
        return n

    def write_page(
        self,
        entity: str,
        page_data: dict[str, Any],
        sub_key: str | None = None,
    ) -> Path:
        """Persist *page_data* as gzipped JSON and return the written path.

        Args:
            entity:   Top-level entity name, e.g. ``works`` or ``sources``.
            page_data: The raw JSON dict for this page (must be JSON-serialisable).
            sub_key:  Optional sub-directory key, e.g. journal slug.
        """
        if sub_key:
            slug = _slugify(sub_key)
            rel_dir = entity + "/" + slug
        else:
            rel_dir = entity

        dest_dir = self._base / rel_dir
        _ensure_dir(dest_dir)

        page_num = self._next_page(rel_dir)
        dest_file = dest_dir / f"{page_num:04d}.json.gz"

        blob = orjson.dumps(page_data)
        with gzip.open(dest_file, "wb") as fh:
            fh.write(blob)

        logger.debug(
            "Wrote raw page",
            extra={"path": str(dest_file), "bytes": len(blob)},
        )
        return dest_file

    def base_path(self) -> Path:
        return self._base
