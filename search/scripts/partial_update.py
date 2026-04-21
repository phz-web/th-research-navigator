"""Partial / incremental Typesense reindex.

Only reindexes papers (and their join-derived fields) where
``papers.updated_at > last_indexed_at``.

State is persisted in ``data/index_state.json`` at the repo root.
This file stores a timestamp per collection so it can be updated
independently without schema churn.

The last_indexed_at timestamp is updated to ``now()`` *before* querying,
not after, to avoid a window where new updates could be missed.

Usage::

    python partial_update.py --collection papers
    python partial_update.py --collection all
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from typesense_client import get_client

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent.parent
_STATE_FILE = _REPO_ROOT / "data" / "index_state.json"

_EPOCH = "1970-01-01T00:00:00+00:00"
_BATCH_SIZE = 200


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if _STATE_FILE.exists():
        with _STATE_FILE.open() as fh:
            return json.load(fh)
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _STATE_FILE.open("w") as fh:
        json.dump(state, fh, indent=2)


def _get_last_indexed(state: dict, collection: str) -> str:
    return state.get(collection, {}).get("last_indexed_at", _EPOCH)


def _set_last_indexed(state: dict, collection: str, ts: str) -> None:
    if collection not in state:
        state[collection] = {}
    state[collection]["last_indexed_at"] = ts


# ---------------------------------------------------------------------------
# PostgreSQL
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


# ---------------------------------------------------------------------------
# Papers partial update
# ---------------------------------------------------------------------------

_PAPERS_QUERY = """
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
WHERE p.updated_at > %(since)s
GROUP BY p.id, j.id
ORDER BY p.id
"""


def _row_to_paper_doc(row: tuple) -> dict:
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


def partial_update_papers(client, conn, since: str) -> int:
    total = 0
    batch: list[dict] = []
    with conn.cursor() as cur:
        cur.execute(_PAPERS_QUERY, {"since": since})
        while True:
            rows = cur.fetchmany(_BATCH_SIZE)
            if not rows:
                break
            for row in rows:
                batch.append(_row_to_paper_doc(row))
            if len(batch) >= _BATCH_SIZE:
                client.collections["papers"].documents.import_(
                    batch, {"action": "upsert"}
                )
                total += len(batch)
                batch = []
    if batch:
        client.collections["papers"].documents.import_(batch, {"action": "upsert"})
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Authors partial update (updated_at threshold)
# ---------------------------------------------------------------------------

_AUTHORS_QUERY = """
SELECT
    a.openalex_author_id       AS id,
    a.display_name,
    a.normalized_name::text,
    a.orcid,
    COALESCE(a.works_count, 0)     AS works_count,
    COALESCE(a.cited_by_count, 0)  AS cited_by_count,
    a.last_known_institution
FROM authors a
WHERE a.updated_at > %(since)s
ORDER BY a.id
"""


def _row_to_author_doc(row: tuple) -> dict:
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


def partial_update_authors(client, conn, since: str) -> int:
    total = 0
    batch: list[dict] = []
    with conn.cursor() as cur:
        cur.execute(_AUTHORS_QUERY, {"since": since})
        while True:
            rows = cur.fetchmany(_BATCH_SIZE)
            if not rows:
                break
            for row in rows:
                batch.append(_row_to_author_doc(row))
            if len(batch) >= _BATCH_SIZE:
                client.collections["authors"].documents.import_(
                    batch, {"action": "upsert"}
                )
                total += len(batch)
                batch = []
    if batch:
        client.collections["authors"].documents.import_(batch, {"action": "upsert"})
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Journals partial update (updated_at threshold)
# ---------------------------------------------------------------------------

_JOURNALS_QUERY = """
SELECT
    COALESCE(j.openalex_source_id, j.id::text) AS id,
    j.display_name,
    j.publisher,
    j.scope_bucket,
    j.tier_flag,
    j.issn_print,
    j.issn_online,
    j.active_flag,
    COUNT(p.id)::int                           AS papers_count
FROM journals j
LEFT JOIN papers p ON p.journal_id = j.id
WHERE j.updated_at > %(since)s
GROUP BY j.id
ORDER BY j.id
"""


def _row_to_journal_doc(row: tuple) -> dict:
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


def partial_update_journals(client, conn, since: str) -> int:
    total = 0
    batch: list[dict] = []
    with conn.cursor() as cur:
        cur.execute(_JOURNALS_QUERY, {"since": since})
        while True:
            rows = cur.fetchmany(_BATCH_SIZE)
            if not rows:
                break
            for row in rows:
                batch.append(_row_to_journal_doc(row))
            if len(batch) >= _BATCH_SIZE:
                client.collections["journals"].documents.import_(
                    batch, {"action": "upsert"}
                )
                total += len(batch)
                batch = []
    if batch:
        client.collections["journals"].documents.import_(batch, {"action": "upsert"})
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Partial Typesense reindex for THRN")
    parser.add_argument(
        "--collection",
        default="papers",
        choices=["papers", "authors", "journals", "all"],
        help="Which collection(s) to reindex",
    )
    args = parser.parse_args()

    import psycopg  # type: ignore[import-untyped]

    client = get_client()
    db_url = _get_db_url()
    state = _load_state()

    targets = (
        ["papers", "authors", "journals"] if args.collection == "all" else [args.collection]
    )

    # Snapshot 'now' before any queries so newly-arriving updates aren't skipped
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with psycopg.connect(db_url) as conn:
        for target in targets:
            since = _get_last_indexed(state, target)
            t0 = time.perf_counter()

            if target == "papers":
                count = partial_update_papers(client, conn, since)
            elif target == "authors":
                count = partial_update_authors(client, conn, since)
            else:
                count = partial_update_journals(client, conn, since)

            elapsed = time.perf_counter() - t0
            print(f"  {target}: {count} documents upserted in {elapsed:.1f}s (since {since[:19]})")

            _set_last_indexed(state, target, now_ts)

    _save_state(state)
    print("Partial update complete. State saved to", _STATE_FILE)


if __name__ == "__main__":
    main()
