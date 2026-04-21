"""Dataclasses representing the domain entities used by the ingestion pipeline.

These mirror the PostgreSQL schema defined in infra/postgres/migrations/0001_init.sql
but are intentionally lightweight — no ORM, no validators beyond Python types.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

@dataclass
class Journal:
    """Corresponds to the ``journals`` table row after enrichment."""

    id: int | None = None
    openalex_source_id: str | None = None
    display_name: str = ""
    normalized_name: str = ""
    issn_print: str | None = None
    issn_online: str | None = None
    publisher: str | None = None
    homepage_url: str | None = None
    scimago_category: str | None = None
    scope_bucket: str = "mixed"
    tier_flag: str = "extended"
    active_flag: bool = True
    manual_review_flag: bool = False
    inclusion_reason: str | None = None
    notes: str | None = None
    raw_json: dict[str, Any] | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None


# ---------------------------------------------------------------------------
# Author
# ---------------------------------------------------------------------------

@dataclass
class Author:
    """Corresponds to the ``authors`` table row."""

    id: int | None = None
    openalex_author_id: str = ""
    display_name: str = ""
    normalized_name: str = ""
    orcid: str | None = None
    works_count: int | None = None
    cited_by_count: int | None = None
    last_known_institution: str | None = None
    raw_json: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# AuthorPosition (represents a single authorship record)
# ---------------------------------------------------------------------------

@dataclass
class AuthorPosition:
    """One authorship slot for a paper (used to build paper_authors rows)."""

    openalex_author_id: str
    display_name: str
    normalized_name: str
    orcid: str | None
    works_count: int | None
    cited_by_count: int | None
    last_known_institution: str | None
    author_position: int          # 0-based index in the authorships list
    author_position_tag: str | None  # 'first' | 'middle' | 'last'
    is_corresponding: bool | None
    raw_affiliation: str | None
    raw_json: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Authorship (thin join row)
# ---------------------------------------------------------------------------

@dataclass
class Authorship:
    """Represents a row in paper_authors (uses DB surrogate IDs)."""

    paper_id: int
    author_id: int
    author_position: int
    author_position_tag: str | None
    is_corresponding: bool | None
    raw_affiliation: str | None


# ---------------------------------------------------------------------------
# Paper
# ---------------------------------------------------------------------------

@dataclass
class Paper:
    """Corresponds to the ``papers`` table row."""

    id: int | None = None
    openalex_id: str = ""
    doi: str | None = None
    title: str = ""
    abstract: str | None = None
    publication_year: int | None = None
    publication_date: datetime.date | None = None
    journal_id: int | None = None
    volume: str | None = None
    issue: str | None = None
    first_page: str | None = None
    last_page: str | None = None
    cited_by_count: int = 0
    is_oa: bool | None = None
    primary_topic: str | None = None
    language: str | None = None
    landing_page_url: str | None = None
    pdf_url: str | None = None
    raw_json: dict[str, Any] | None = None
    content_hash: str | None = None  # MD5/SHA of key fields for change detection


# ---------------------------------------------------------------------------
# IngestionRun
# ---------------------------------------------------------------------------

@dataclass
class IngestionRun:
    """Corresponds to the ``ingestion_runs`` table row."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    command: str = ""
    status: str = "running"
    started_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    finished_at: datetime.datetime | None = None
    journals_touched: int = 0
    papers_inserted: int = 0
    papers_updated: int = 0
    authors_inserted: int = 0
    authors_updated: int = 0
    error_summary: str | None = None
    params: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# SourceMatchCandidate
# ---------------------------------------------------------------------------

@dataclass
class SourceMatchCandidate:
    """A candidate OpenAlex source proposed for a whitelist journal."""

    openalex_source_id: str
    display_name: str
    issn_l: str | None
    issn_list: list[str]
    match_method: str   # 'issn_print' | 'issn_online' | 'name_exact' | 'name_trigram'
    confidence: float
    raw_json: dict[str, Any] | None = None
