"""Full reindex of the ``authors`` Typesense collection from PostgreSQL.

Usage::

    python reindex_authors.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from typesense_client import get_client


def _get_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "thrn")
    user = os.environ.get("POSTGRES_USER", "thrn")
    pw = os.environ.get("POSTGRES_PASSWORD", "change-me-locally")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


_BATCH_SIZE = 200

_QUERY = """
SELECT
    a.openalex_author_id        AS id,
    a.display_name,
    a.normalized_name::text,
    a.orcid,
    COALESCE(a.works_count, 0)       AS works_count,
    COALESCE(a.cited_by_count, 0)    AS cited_by_count,
    a.last_known_institution
FROM authors a
ORDER BY a.id
"""


def _row_to_doc(row: tuple) -> dict:
    id_, display_name, normalized_name, orcid, works_count, cited_by_count, institution = row

    doc: dict = {
        "id": str(id_),
        "display_name": display_name or "",
        "normalized_name": normalized_name or "",
        "works_count": int(works_count) if works_count else 0,
        "cited_by_count": int(cited_by_count) if cited_by_count else 0,
    }
    if orcid:
        doc["orcid"] = orcid
    if institution:
        doc["last_known_institution"] = institution
    return doc


def main() -> None:
    import psycopg  # type: ignore[import-untyped]

    client = get_client()
    db_url = _get_db_url()

    t0 = time.perf_counter()
    total = 0
    batch: list[dict] = []

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(_QUERY)
            while True:
                rows = cur.fetchmany(_BATCH_SIZE)
                if not rows:
                    break
                for row in rows:
                    batch.append(_row_to_doc(row))

                if len(batch) >= _BATCH_SIZE:
                    client.collections["authors"].documents.import_(
                        batch, {"action": "upsert"}
                    )
                    total += len(batch)
                    print(f"  Upserted {total} authors so far…")
                    batch = []

    if batch:
        client.collections["authors"].documents.import_(batch, {"action": "upsert"})
        total += len(batch)

    elapsed = time.perf_counter() - t0
    print(f"authors: {total} documents indexed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
