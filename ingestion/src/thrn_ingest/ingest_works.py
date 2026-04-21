"""Paginated OpenAlex works harvest and PostgreSQL upsert.

For each active journal with an ``openalex_source_id``:
1. Paginate ``/works?filter=primary_location.source.id:Sxxx`` (cursor-based).
2. Reconstruct ``abstract`` from the inverted index (OpenAlex does not serve
   raw abstracts in the free tier; it provides the token → position mapping).
3. Build a :class:`Paper` dataclass and upsert it.
4. Upsert authors; write ``paper_authors`` rows (delete-then-insert).
5. Preserve each raw page as a gzip file under ``data/raw/<run_id>/``.

Running this function twice with no upstream changes produces 0 inserts and
0 content updates (timestamps may change only for truly modified rows).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from thrn_ingest.authors import parse_authorships, upsert_authors_for_work
from thrn_ingest.db import replace_paper_authors, upsert_paper
from thrn_ingest.models import Paper
from thrn_ingest.raw_audit import RawAuditWriter
from thrn_ingest.runs import RunContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract reconstruction from inverted index
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Reconstruct plain-text abstract from OpenAlex abstract_inverted_index.

    OpenAlex represents abstracts as ``{word: [position, ...], ...}``.
    We sort by position and join to recover the original word sequence.

    Returns None if the index is absent or empty.
    """
    if not inverted_index:
        return None

    # Build position → word mapping
    pos_word: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            pos_word.append((pos, word))

    if not pos_word:
        return None

    pos_word.sort(key=lambda t: t[0])
    return " ".join(w for _, w in pos_word)


# ---------------------------------------------------------------------------
# Parse a single work dict into a Paper dataclass
# ---------------------------------------------------------------------------

def _parse_work(work: dict[str, Any], journal_id: int) -> Paper | None:
    """Extract fields from a raw OpenAlex work dict into a Paper.

    Returns None if the work lacks an id or title (considered unparseable).
    """
    oa_id_full = work.get("id") or ""
    oa_id = oa_id_full.split("/")[-1] if "/" in oa_id_full else oa_id_full
    if not oa_id:
        return None

    title = (work.get("title") or "").strip()
    if not title:
        logger.debug("Skipping work with empty title", extra={"oa_id": oa_id})
        return None

    # DOI
    doi_raw = work.get("doi") or ""
    doi: str | None = doi_raw.replace("https://doi.org/", "").strip() or None

    # Abstract
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    # Dates
    pub_year: int | None = work.get("publication_year")
    pub_date_str: str | None = work.get("publication_date")
    pub_date: datetime.date | None = None
    if pub_date_str:
        try:
            pub_date = datetime.date.fromisoformat(pub_date_str)
        except ValueError:
            logger.debug("Unparseable publication_date", extra={"raw": pub_date_str})

    # Location / OA info
    primary_loc = work.get("primary_location") or {}
    landing_page_url = primary_loc.get("landing_page_url")
    pdf_url = primary_loc.get("pdf_url")
    is_oa_loc: bool | None = primary_loc.get("is_oa")
    oa_info = work.get("open_access") or {}
    is_oa: bool | None = oa_info.get("is_oa") if "is_oa" in oa_info else is_oa_loc

    # Biblio
    biblio = work.get("biblio") or {}

    # Topic
    topics = work.get("topics") or []
    primary_topic: str | None = None
    if topics:
        primary_topic = (topics[0].get("display_name") or "").strip() or None

    return Paper(
        openalex_id=oa_id,
        doi=doi,
        title=title,
        abstract=abstract,
        publication_year=pub_year,
        publication_date=pub_date,
        journal_id=journal_id,
        volume=biblio.get("volume"),
        issue=biblio.get("issue"),
        first_page=biblio.get("first_page"),
        last_page=biblio.get("last_page"),
        cited_by_count=work.get("cited_by_count") or 0,
        is_oa=is_oa,
        primary_topic=primary_topic,
        language=work.get("language"),
        landing_page_url=landing_page_url,
        pdf_url=pdf_url,
        raw_json=work,
    )


# ---------------------------------------------------------------------------
# Main ingest function for one journal
# ---------------------------------------------------------------------------

def ingest_works_for_journal(
    conn: Any,
    client: Any,
    run_ctx: RunContext,
    journal_id: int,
    openalex_source_id: str,
    journal_display_name: str,
    since: datetime.date | None = None,
    max_pages: int | None = None,
    dry_run: bool = False,
) -> None:
    """Harvest and upsert all works for one journal.

    Args:
        conn:                 psycopg 3 connection (from pool).
        client:               OpenAlexClient instance.
        run_ctx:              RunContext accumulating stats.
        journal_id:           DB surrogate id for the journal.
        openalex_source_id:   OpenAlex ``Sxxx`` source id.
        journal_display_name: Human-readable name (for logging and raw path).
        since:                Only fetch works published on or after this date.
        max_pages:            Safety cap on number of API pages.
        dry_run:              If True, log what would happen but write nothing.
    """
    writer = RawAuditWriter(run_ctx.run_id)

    filter_str = f"primary_location.source.id:{openalex_source_id}"
    if since:
        filter_str += f",from_publication_date:{since.isoformat()}"

    extra_params: dict[str, Any] = {
        "filter": filter_str,
        "select": (
            "id,doi,title,publication_year,publication_date,"
            "abstract_inverted_index,primary_location,open_access,"
            "cited_by_count,authorships,biblio,topics,language"
        ),
    }

    pages_fetched = 0
    for page_data in client.paginate(
        "/works",
        extra_params=extra_params,
        per_page=200,
        max_pages=max_pages,
    ):
        pages_fetched += 1
        writer.write_page("works", page_data, sub_key=journal_display_name)

        results = page_data.get("results") or []
        logger.info(
            "Processing page",
            extra={
                "journal": journal_display_name,
                "page": pages_fetched,
                "results": len(results),
            },
        )

        for work in results:
            paper = _parse_work(work, journal_id)
            if paper is None:
                continue

            if dry_run:
                logger.info(
                    "[DRY RUN] Would upsert paper",
                    extra={"openalex_id": paper.openalex_id, "title": paper.title[:60]},
                )
                continue

            paper_db_id, inserted, updated = upsert_paper(conn, paper)
            if paper_db_id < 0:
                logger.warning(
                    "Paper upsert returned no id",
                    extra={"openalex_id": paper.openalex_id},
                )
                continue

            if inserted:
                run_ctx.papers_inserted += 1
            elif updated:
                run_ctx.papers_updated += 1

            # Authors
            author_positions = parse_authorships(work)
            authorships = upsert_authors_for_work(conn, paper_db_id, author_positions, run_ctx)
            replace_paper_authors(conn, paper_db_id, authorships)

        if not dry_run:
            conn.commit()

    run_ctx.journals_touched += 1
    run_ctx.stats[f"pages_{journal_display_name[:30]}"] = pages_fetched
    logger.info(
        "Journal ingestion complete",
        extra={
            "journal": journal_display_name,
            "pages_fetched": pages_fetched,
            "papers_inserted": run_ctx.papers_inserted,
            "papers_updated": run_ctx.papers_updated,
        },
    )
