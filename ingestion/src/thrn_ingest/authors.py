"""Author upsert logic.

Converts OpenAlex ``authorship`` sub-objects (nested inside a ``work`` record)
into :class:`Author` dataclasses and writes them to PostgreSQL.

Also writes :class:`Authorship` rows (via :func:`db.replace_paper_authors`) to
keep the paper_authors join table consistent with the latest upstream state.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from thrn_ingest.db import upsert_author
from thrn_ingest.models import Author, AuthorPosition, Authorship

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

def _normalise_author_name(name: str) -> str:
    """Lower-case, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_str).strip().lower()


# ---------------------------------------------------------------------------
# Parse OpenAlex authorship objects
# ---------------------------------------------------------------------------

def parse_authorships(
    work: dict[str, Any],
) -> list[AuthorPosition]:
    """Extract AuthorPosition objects from a raw OpenAlex work dict.

    OpenAlex ``authorships`` is a list of objects like::

        {
          "author": {
            "id": "https://openalex.org/A1234",
            "display_name": "Jane Doe",
            "orcid": null
          },
          "author_position": "first",
          "institutions": [...],
          "is_corresponding": false,
          "raw_affiliation_strings": ["University of X"]
        }
    """
    results: list[AuthorPosition] = []
    authorships = work.get("authorships") or []

    for idx, authorship in enumerate(authorships):
        author_obj = authorship.get("author") or {}
        oa_author_id_full = author_obj.get("id") or ""
        oa_author_id = (
            oa_author_id_full.split("/")[-1] if "/" in oa_author_id_full else oa_author_id_full
        )
        if not oa_author_id:
            logger.debug("Skipping authorship with missing author id", extra={"work": work.get("id")})
            continue

        display_name = author_obj.get("display_name") or ""
        orcid_raw = author_obj.get("orcid") or ""
        orcid = orcid_raw if orcid_raw else None

        position_tag = authorship.get("author_position")
        if position_tag not in ("first", "middle", "last"):
            position_tag = None

        is_corresponding = authorship.get("is_corresponding")
        raw_affiliation_list = authorship.get("raw_affiliation_strings") or []
        raw_affiliation = "; ".join(raw_affiliation_list) if raw_affiliation_list else None

        # Institution for last_known_institution
        institutions = authorship.get("institutions") or []
        last_known_institution: str | None = None
        if institutions:
            inst = institutions[0]
            last_known_institution = inst.get("display_name") or None

        results.append(
            AuthorPosition(
                openalex_author_id=oa_author_id,
                display_name=display_name,
                normalized_name=_normalise_author_name(display_name),
                orcid=orcid,
                works_count=None,
                cited_by_count=None,
                last_known_institution=last_known_institution,
                author_position=idx,
                author_position_tag=position_tag,
                is_corresponding=is_corresponding,
                raw_affiliation=raw_affiliation,
                raw_json=authorship,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Upsert all authors for a work; return Authorship rows
# ---------------------------------------------------------------------------

def upsert_authors_for_work(
    conn: Any,
    paper_id: int,
    author_positions: list[AuthorPosition],
    run_ctx: Any,
) -> list[Authorship]:
    """Upsert each author; return Authorship join rows ready for insert."""
    authorships: list[Authorship] = []

    for ap in author_positions:
        author = Author(
            openalex_author_id=ap.openalex_author_id,
            display_name=ap.display_name,
            normalized_name=ap.normalized_name,
            orcid=ap.orcid,
            works_count=ap.works_count,
            cited_by_count=ap.cited_by_count,
            last_known_institution=ap.last_known_institution,
            raw_json=ap.raw_json,
        )
        db_id, inserted = upsert_author(conn, author)
        if db_id < 0:
            logger.warning(
                "Failed to upsert author",
                extra={"openalex_author_id": ap.openalex_author_id},
            )
            continue

        if inserted:
            run_ctx.authors_inserted += 1
        else:
            run_ctx.authors_updated += 1

        authorships.append(
            Authorship(
                paper_id=paper_id,
                author_id=db_id,
                author_position=ap.author_position,
                author_position_tag=ap.author_position_tag,
                is_corresponding=ap.is_corresponding,
                raw_affiliation=ap.raw_affiliation,
            )
        )

    return authorships
