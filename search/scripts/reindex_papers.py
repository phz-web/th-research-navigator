"""Full reindex of the ``papers`` Typesense collection from PostgreSQL.

Streams rows from PostgreSQL in batches of 200, builds Typesense documents,
and bulk-imports them with ``action=upsert``.

Usage::

    python reindex_papers.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from typesense_client import get_client

# ---------------------------------------------------------------------------
# PostgreSQL connection
# ---------------------------------------------------------------------------

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
    p.openalex_id                              AS id,
    p.title,
    COALESCE(p.abstract, '')                   AS abstract,
    COALESCE(
        array_agg(DISTINCT a.display_name)
            FILTER (WHERE a.display_name IS NOT NULL),
        '{}'
    )                                          AS authors_text,
    p.journal_id,
    j.display_name                             AS journal_name,
    j.scope_bucket                             AS journal_scope_bucket,
    j.tier_flag                                AS journal_tier,
    COALESCE(p.publication_year, 0)            AS publication_year,
    COALESCE(p.publication_date::text, '')     AS publication_date,
    COALESCE(p.cited_by_count, 0)              AS cited_by_count,
    COALESCE(p.is_oa, false)                   AS is_oa,
    p.primary_topic,
    p.doi,
    p.landing_page_url
FROM papers p
JOIN journals j ON j.id = p.journal_id
LEFT JOIN paper_authors pa ON pa.paper_id = p.id
LEFT JOIN authors a ON a.id = pa.author_id
GROUP BY p.id, j.id
ORDER BY p.id
"""


def _row_to_doc(row: tuple) -> dict:
    (
        id_, title, abstract, authors_text,
        journal_id, journal_name, journal_scope_bucket, journal_tier,
        publication_year, publication_date, cited_by_count, is_oa,
        primary_topic, doi, landing_page_url,
    ) = row

    doc: dict = {
        "id": str(id_),
        "title": title or "",
        "abstract": abstract or "",
        "authors_text": list(authors_text) if authors_text else [],
        "journal_id": int(journal_id),
        "journal_name": journal_name or "",
        "journal_scope_bucket": journal_scope_bucket or "",
        "journal_tier": journal_tier or "",
        "publication_year": int(publication_year) if publication_year else 0,
        "publication_date": str(publication_date) if publication_date else "",
        "cited_by_count": int(cited_by_count) if cited_by_count else 0,
        "is_oa": bool(is_oa),
    }
    if primary_topic:
        doc["primary_topic"] = primary_topic
    if doi:
        doc["doi"] = doi
    if landing_page_url:
        doc["landing_page_url"] = landing_page_url
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
                    resp = client.collections["papers"].documents.import_(
                        batch, {"action": "upsert"}
                    )
                    total += len(batch)
                    print(f"  Upserted {total} papers so far…")
                    batch = []

    if batch:
        client.collections["papers"].documents.import_(batch, {"action": "upsert"})
        total += len(batch)

    elapsed = time.perf_counter() - t0
    print(f"papers: {total} documents indexed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
