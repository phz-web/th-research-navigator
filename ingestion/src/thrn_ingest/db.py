"""PostgreSQL connection pool and upsert helpers using psycopg 3.

A module-level connection pool is lazily initialised on first access via
``get_pool()``.  All upserts go through the helpers defined here so that
ON CONFLICT … DO UPDATE behaviour is centralised.

Usage::

    from thrn_ingest.db import get_pool

    with get_pool().connection() as conn:
        upsert_journal(conn, journal)
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from contextlib import contextmanager
from typing import Any, Generator

import orjson

logger = logging.getLogger(__name__)

# Pool is initialised lazily; importable without a live DB for tests.
_pool: Any = None  # psycopg_pool.ConnectionPool | None


def get_pool() -> Any:
    """Return (and lazily create) the module-level connection pool."""
    global _pool
    if _pool is None:
        from psycopg_pool import ConnectionPool  # type: ignore[import-untyped]

        from thrn_ingest.config import Config

        _pool = ConnectionPool(
            conninfo=Config.database_url,
            min_size=Config.db_min_connections,
            max_size=Config.db_max_connections,
            open=True,
        )
        logger.info("DB pool opened", extra={"dsn_hint": Config.database_url[:40]})
    return _pool


def close_pool() -> None:
    """Close the pool. Call at process exit or test teardown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_conn() -> Generator[Any, None, None]:
    """Context manager yielding a pooled connection."""
    with get_pool().connection() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Content hash (for change detection — avoids spurious updated_at bumps)
# ---------------------------------------------------------------------------

def compute_paper_hash(row: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest of the fields that matter for change detection."""
    fields = {
        "title": row.get("title"),
        "abstract": row.get("abstract"),
        "cited_by_count": row.get("cited_by_count"),
        "is_oa": row.get("is_oa"),
        "primary_topic": row.get("primary_topic"),
        "landing_page_url": row.get("landing_page_url"),
    }
    blob = orjson.dumps(fields, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------
# Journal upserts
# ---------------------------------------------------------------------------

def upsert_journal(conn: Any, journal: Any) -> int:
    """Upsert a Journal dataclass row; return the DB surrogate id."""
    from thrn_ingest.models import Journal  # local to avoid circular

    assert isinstance(journal, Journal)
    raw_bytes = orjson.dumps(journal.raw_json) if journal.raw_json else None

    row = conn.execute(
        """
        INSERT INTO journals (
            display_name, normalized_name, issn_print, issn_online,
            publisher, homepage_url, scimago_category,
            scope_bucket, tier_flag, active_flag, manual_review_flag,
            inclusion_reason, notes
        )
        VALUES (
            %(display_name)s, %(normalized_name)s, %(issn_print)s, %(issn_online)s,
            %(publisher)s, %(homepage_url)s, %(scimago_category)s,
            %(scope_bucket)s, %(tier_flag)s, %(active_flag)s, %(manual_review_flag)s,
            %(inclusion_reason)s, %(notes)s
        )
        ON CONFLICT (normalized_name, issn_print, issn_online) DO NOTHING
        RETURNING id
        """,
        {
            "display_name": journal.display_name,
            "normalized_name": journal.normalized_name,
            "issn_print": journal.issn_print,
            "issn_online": journal.issn_online,
            "publisher": journal.publisher,
            "homepage_url": journal.homepage_url,
            "scimago_category": journal.scimago_category,
            "scope_bucket": journal.scope_bucket,
            "tier_flag": journal.tier_flag,
            "active_flag": journal.active_flag,
            "manual_review_flag": journal.manual_review_flag,
            "inclusion_reason": journal.inclusion_reason,
            "notes": journal.notes,
        },
    ).fetchone()

    if row:
        return int(row[0])

    # Row already exists — fetch id
    existing = conn.execute(
        """
        SELECT id FROM journals
        WHERE normalized_name = %(normalized_name)s
          AND (issn_print IS NOT DISTINCT FROM %(issn_print)s)
          AND (issn_online IS NOT DISTINCT FROM %(issn_online)s)
        """,
        {
            "normalized_name": journal.normalized_name,
            "issn_print": journal.issn_print,
            "issn_online": journal.issn_online,
        },
    ).fetchone()
    return int(existing[0]) if existing else -1


def update_journal_openalex(
    conn: Any,
    journal_id: int,
    openalex_source_id: str,
    raw_json: dict[str, Any],
) -> None:
    """Write openalex_source_id and raw_json onto a journal row."""
    conn.execute(
        """
        UPDATE journals
        SET openalex_source_id = %(oa_id)s,
            raw_json            = %(raw)s::jsonb
        WHERE id = %(jid)s
        """,
        {
            "oa_id": openalex_source_id,
            "raw": orjson.dumps(raw_json).decode(),
            "jid": journal_id,
        },
    )


# ---------------------------------------------------------------------------
# Author upserts
# ---------------------------------------------------------------------------

def upsert_author(conn: Any, author: Any) -> tuple[int, bool]:
    """Upsert an Author; return (db_id, inserted:bool)."""
    raw_bytes = orjson.dumps(author.raw_json).decode() if author.raw_json else None

    row = conn.execute(
        """
        INSERT INTO authors (
            openalex_author_id, display_name, normalized_name,
            orcid, works_count, cited_by_count, last_known_institution, raw_json
        )
        VALUES (
            %(oa_id)s, %(display_name)s, %(normalized_name)s,
            %(orcid)s, %(works_count)s, %(cited_by_count)s,
            %(last_known_institution)s, %(raw_json)s::jsonb
        )
        ON CONFLICT (openalex_author_id) DO UPDATE SET
            display_name            = EXCLUDED.display_name,
            normalized_name         = EXCLUDED.normalized_name,
            orcid                   = COALESCE(EXCLUDED.orcid, authors.orcid),
            works_count             = EXCLUDED.works_count,
            cited_by_count          = EXCLUDED.cited_by_count,
            last_known_institution  = COALESCE(EXCLUDED.last_known_institution,
                                               authors.last_known_institution),
            raw_json                = EXCLUDED.raw_json
        RETURNING id, (xmax = 0) AS inserted
        """,
        {
            "oa_id": author.openalex_author_id,
            "display_name": author.display_name,
            "normalized_name": author.normalized_name,
            "orcid": author.orcid,
            "works_count": author.works_count,
            "cited_by_count": author.cited_by_count,
            "last_known_institution": author.last_known_institution,
            "raw_json": raw_bytes,
        },
    ).fetchone()

    return int(row[0]), bool(row[1])


# ---------------------------------------------------------------------------
# Paper upserts
# ---------------------------------------------------------------------------

def upsert_paper(conn: Any, paper: Any) -> tuple[int, bool, bool]:
    """Upsert a Paper; return (db_id, inserted:bool, updated:bool).

    Content-hash comparison is used to skip no-op updates.
    """
    content_hash = compute_paper_hash(
        {
            "title": paper.title,
            "abstract": paper.abstract,
            "cited_by_count": paper.cited_by_count,
            "is_oa": paper.is_oa,
            "primary_topic": paper.primary_topic,
            "landing_page_url": paper.landing_page_url,
        }
    )

    pub_date_str: str | None = (
        paper.publication_date.isoformat() if paper.publication_date else None
    )
    raw_str = orjson.dumps(paper.raw_json).decode() if paper.raw_json else None
    doi_val = paper.doi.strip().lower() if paper.doi else None

    row = conn.execute(
        """
        INSERT INTO papers (
            openalex_id, doi, title, abstract,
            publication_year, publication_date, journal_id,
            volume, issue, first_page, last_page,
            cited_by_count, is_oa, primary_topic, language,
            landing_page_url, pdf_url, raw_json
        )
        VALUES (
            %(openalex_id)s, %(doi)s, %(title)s, %(abstract)s,
            %(pub_year)s, %(pub_date)s, %(journal_id)s,
            %(volume)s, %(issue)s, %(first_page)s, %(last_page)s,
            %(cited_by_count)s, %(is_oa)s, %(primary_topic)s, %(language)s,
            %(landing_page_url)s, %(pdf_url)s, %(raw_json)s::jsonb
        )
        ON CONFLICT (openalex_id) DO UPDATE SET
            doi                 = EXCLUDED.doi,
            title               = EXCLUDED.title,
            abstract            = EXCLUDED.abstract,
            publication_year    = EXCLUDED.publication_year,
            publication_date    = EXCLUDED.publication_date,
            journal_id          = EXCLUDED.journal_id,
            volume              = EXCLUDED.volume,
            issue               = EXCLUDED.issue,
            first_page          = EXCLUDED.first_page,
            last_page           = EXCLUDED.last_page,
            cited_by_count      = EXCLUDED.cited_by_count,
            is_oa               = EXCLUDED.is_oa,
            primary_topic       = EXCLUDED.primary_topic,
            language            = EXCLUDED.language,
            landing_page_url    = EXCLUDED.landing_page_url,
            pdf_url             = EXCLUDED.pdf_url,
            raw_json            = EXCLUDED.raw_json
        WHERE papers.title        IS DISTINCT FROM EXCLUDED.title
           OR papers.abstract     IS DISTINCT FROM EXCLUDED.abstract
           OR papers.cited_by_count IS DISTINCT FROM EXCLUDED.cited_by_count
           OR papers.is_oa        IS DISTINCT FROM EXCLUDED.is_oa
           OR papers.primary_topic IS DISTINCT FROM EXCLUDED.primary_topic
           OR papers.landing_page_url IS DISTINCT FROM EXCLUDED.landing_page_url
        RETURNING id, (xmax = 0) AS inserted
        """,
        {
            "openalex_id": paper.openalex_id,
            "doi": doi_val,
            "title": paper.title,
            "abstract": paper.abstract,
            "pub_year": paper.publication_year,
            "pub_date": pub_date_str,
            "journal_id": paper.journal_id,
            "volume": paper.volume,
            "issue": paper.issue,
            "first_page": paper.first_page,
            "last_page": paper.last_page,
            "cited_by_count": paper.cited_by_count or 0,
            "is_oa": paper.is_oa,
            "primary_topic": paper.primary_topic,
            "language": paper.language,
            "landing_page_url": paper.landing_page_url,
            "pdf_url": paper.pdf_url,
            "raw_json": raw_str,
        },
    ).fetchone()

    if row:
        return int(row[0]), bool(row[1]), not bool(row[1])

    # No row returned means nothing changed — fetch existing id
    existing = conn.execute(
        "SELECT id FROM papers WHERE openalex_id = %(oid)s",
        {"oid": paper.openalex_id},
    ).fetchone()
    db_id = int(existing[0]) if existing else -1
    return db_id, False, False


# ---------------------------------------------------------------------------
# paper_authors (delete-then-insert per paper)
# ---------------------------------------------------------------------------

def replace_paper_authors(conn: Any, paper_id: int, authorships: list[Any]) -> None:
    """Delete all paper_authors rows for paper_id then insert fresh ones."""
    conn.execute(
        "DELETE FROM paper_authors WHERE paper_id = %(pid)s",
        {"pid": paper_id},
    )
    for auth in authorships:
        conn.execute(
            """
            INSERT INTO paper_authors (
                paper_id, author_id, author_position, author_position_tag,
                is_corresponding, raw_affiliation
            )
            VALUES (
                %(paper_id)s, %(author_id)s, %(author_position)s,
                %(author_position_tag)s, %(is_corresponding)s, %(raw_affiliation)s
            )
            ON CONFLICT (paper_id, author_id, author_position) DO NOTHING
            """,
            {
                "paper_id": paper_id,
                "author_id": auth.author_id,
                "author_position": auth.author_position,
                "author_position_tag": auth.author_position_tag,
                "is_corresponding": auth.is_corresponding,
                "raw_affiliation": auth.raw_affiliation,
            },
        )


# ---------------------------------------------------------------------------
# source_match_audit
# ---------------------------------------------------------------------------

def log_source_match_audit(
    conn: Any,
    run_id: uuid.UUID,
    journal_id: int | None,
    whitelist_name: str,
    candidate: Any | None,
    accepted: bool,
    notes: str | None = None,
) -> None:
    """Append a row to source_match_audit."""
    from thrn_ingest.models import SourceMatchCandidate  # noqa: F401

    if candidate is not None:
        raw_cand_str = (
            orjson.dumps(candidate.raw_json).decode() if candidate.raw_json else None
        )
        conn.execute(
            """
            INSERT INTO source_match_audit (
                run_id, journal_id, whitelist_name,
                candidate_openalex_id, candidate_display_name,
                match_method, confidence, accepted, notes, raw_candidate_json
            )
            VALUES (
                %(run_id)s, %(journal_id)s, %(whitelist_name)s,
                %(cand_id)s, %(cand_name)s,
                %(method)s, %(confidence)s, %(accepted)s, %(notes)s,
                %(raw_cand)s::jsonb
            )
            """,
            {
                "run_id": str(run_id),
                "journal_id": journal_id,
                "whitelist_name": whitelist_name,
                "cand_id": candidate.openalex_source_id,
                "cand_name": candidate.display_name,
                "method": candidate.match_method,
                "confidence": candidate.confidence,
                "accepted": accepted,
                "notes": notes,
                "raw_cand": raw_cand_str,
            },
        )
    else:
        conn.execute(
            """
            INSERT INTO source_match_audit (
                run_id, journal_id, whitelist_name,
                match_method, confidence, accepted, notes
            )
            VALUES (
                %(run_id)s, %(journal_id)s, %(whitelist_name)s,
                'unmatched', 0, %(accepted)s, %(notes)s
            )
            """,
            {
                "run_id": str(run_id),
                "journal_id": journal_id,
                "whitelist_name": whitelist_name,
                "accepted": accepted,
                "notes": notes,
            },
        )
