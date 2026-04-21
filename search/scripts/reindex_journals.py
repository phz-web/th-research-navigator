"""Full reindex of the ``journals`` Typesense collection from PostgreSQL.

Usage::

    python reindex_journals.py
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
    COALESCE(j.openalex_source_id, j.id::text)  AS id,
    j.display_name,
    j.publisher,
    j.scope_bucket,
    j.tier_flag,
    j.issn_print,
    j.issn_online,
    j.active_flag,
    COUNT(p.id)::int                             AS papers_count
FROM journals j
LEFT JOIN papers p ON p.journal_id = j.id
GROUP BY j.id
ORDER BY j.id
"""


def _row_to_doc(row: tuple) -> dict:
    id_, display_name, publisher, scope_bucket, tier_flag, issn_print, issn_online, active_flag, papers_count = row

    doc: dict = {
        "id": str(id_),
        "display_name": display_name or "",
        "scope_bucket": scope_bucket or "",
        "tier_flag": tier_flag or "",
        "active_flag": bool(active_flag),
        "papers_count": int(papers_count) if papers_count else 0,
    }
    if publisher:
        doc["publisher"] = publisher
    if issn_print:
        doc["issn_print"] = issn_print
    if issn_online:
        doc["issn_online"] = issn_online
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
                    client.collections["journals"].documents.import_(
                        batch, {"action": "upsert"}
                    )
                    total += len(batch)
                    print(f"  Upserted {total} journals so far…")
                    batch = []

    if batch:
        client.collections["journals"].documents.import_(batch, {"action": "upsert"})
        total += len(batch)

    elapsed = time.perf_counter() - t0
    print(f"journals: {total} documents indexed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
