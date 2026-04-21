"""Match whitelist journal entries to OpenAlex sources.

Matching strategy (in priority order):

1. **ISSN-first** — GET /sources?filter=issn:<issn_print or issn_online>
   - issn_print exact match: confidence 1.0
   - issn_online exact match: confidence 0.98

2. **Name-fallback** — GET /sources?search=<normalized_name>&filter=type:journal
   - Exact display_name match (case-insensitive citext):  confidence 0.90
   - Trigram similarity heuristic:                        confidence 0.50–0.85

Only candidates with confidence >= min_confidence AND journal.manual_review_flag == False
are auto-accepted.  Every evaluated candidate (accepted or not) is logged to
``source_match_audit``.
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata
import uuid
from typing import Any

from thrn_ingest.models import Journal, SourceMatchCandidate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalise helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace, strip punctuation."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_str = nfkd.encode("ascii", "ignore").decode()
    stripped = re.sub(r"[^\w\s]", " ", ascii_str)
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _issn_from_source(source: dict[str, Any]) -> set[str]:
    """Extract all ISSNs from an OpenAlex source dict (issn_l + issns list)."""
    issns: set[str] = set()
    if source.get("issn_l"):
        issns.add(source["issn_l"].upper())
    for i in source.get("issns", []) or []:
        issns.add(i.upper())
    return issns


# ---------------------------------------------------------------------------
# Trigram similarity score
# ---------------------------------------------------------------------------

def _trigram_score(a: str, b: str) -> float:
    """Return a similarity score in [0, 1] using difflib SequenceMatcher."""
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


# ---------------------------------------------------------------------------
# Score a single candidate
# ---------------------------------------------------------------------------

def _score_candidate(
    journal: Journal,
    source: dict[str, Any],
    issn_used: str | None = None,
    issn_type: str | None = None,
) -> SourceMatchCandidate | None:
    """Return a SourceMatchCandidate with confidence, or None if source has no id."""
    oa_id = source.get("id")
    if not oa_id:
        return None
    # OpenAlex ids come as full URLs; extract the short form.
    short_id = oa_id.split("/")[-1] if "/" in oa_id else oa_id

    display = source.get("display_name", "")
    source_issns = _issn_from_source(source)

    confidence = 0.0
    method = "name_trigram"

    if issn_type == "issn_print" and journal.issn_print and journal.issn_print.upper() in source_issns:
        confidence = 1.0
        method = "issn_print"
    elif issn_type == "issn_online" and journal.issn_online and journal.issn_online.upper() in source_issns:
        confidence = 0.98
        method = "issn_online"
    elif journal.issn_print and journal.issn_print.upper() in source_issns:
        confidence = 1.0
        method = "issn_print"
    elif journal.issn_online and journal.issn_online.upper() in source_issns:
        confidence = 0.98
        method = "issn_online"
    else:
        # Name-based scoring
        norm_display = _norm(display)
        norm_whitelist = _norm(journal.display_name)
        if norm_display == norm_whitelist:
            confidence = 0.90
            method = "name_exact"
        else:
            sim = _trigram_score(display, journal.display_name)
            # Scale similarity into [0.50, 0.85] range
            confidence = 0.50 + (sim * 0.35)
            method = "name_trigram"

    return SourceMatchCandidate(
        openalex_source_id=short_id,
        display_name=display,
        issn_l=source.get("issn_l"),
        issn_list=source.get("issns") or [],
        match_method=method,
        confidence=round(confidence, 3),
        raw_json=source,
    )


# ---------------------------------------------------------------------------
# Main matcher
# ---------------------------------------------------------------------------

def find_best_match(
    journal: Journal,
    client: Any,  # OpenAlexClient — avoid circular import
    min_confidence: float = 0.85,
) -> tuple[SourceMatchCandidate | None, list[SourceMatchCandidate]]:
    """Attempt to match *journal* to an OpenAlex source.

    Returns:
        A (best, all_candidates) tuple.
        ``best`` is the top-confidence candidate if it meets min_confidence AND
        the journal is not flagged manual_review; otherwise None.
        ``all_candidates`` lists every candidate evaluated, for audit logging.
    """
    all_candidates: list[SourceMatchCandidate] = []

    # --- 1. ISSN-first ---------------------------------------------------
    for issn_val, issn_type in [
        (journal.issn_print, "issn_print"),
        (journal.issn_online, "issn_online"),
    ]:
        if not issn_val:
            continue
        try:
            results = client.get_source_by_issn(issn_val)
        except Exception as exc:
            logger.warning(
                "ISSN lookup failed",
                extra={"issn": issn_val, "error": str(exc)},
            )
            continue

        for source in results:
            cand = _score_candidate(journal, source, issn_used=issn_val, issn_type=issn_type)
            if cand:
                all_candidates.append(cand)

    # --- 2. Name fallback ------------------------------------------------
    try:
        name_results = client.search_sources_by_name(journal.display_name)
    except Exception as exc:
        logger.warning(
            "Name search failed",
            extra={"journal": journal.display_name, "error": str(exc)},
        )
        name_results = []

    for source in name_results:
        cand = _score_candidate(journal, source)
        if cand:
            # Don't double-count if already found via ISSN
            existing_ids = {c.openalex_source_id for c in all_candidates}
            if cand.openalex_source_id not in existing_ids:
                all_candidates.append(cand)

    # --- Rank by confidence ---------------------------------------------
    all_candidates.sort(key=lambda c: c.confidence, reverse=True)

    if not all_candidates:
        logger.warning(
            "No candidates found",
            extra={"journal": journal.display_name},
        )
        return None, []

    best = all_candidates[0]
    logger.info(
        "Top candidate",
        extra={
            "journal": journal.display_name,
            "candidate": best.openalex_source_id,
            "method": best.match_method,
            "confidence": best.confidence,
        },
    )

    if journal.manual_review_flag:
        logger.warning(
            "Journal is flagged manual_review — not auto-accepting",
            extra={"journal": journal.display_name},
        )
        return None, all_candidates

    if best.confidence < min_confidence:
        logger.warning(
            "Best candidate below min_confidence threshold",
            extra={
                "journal": journal.display_name,
                "confidence": best.confidence,
                "threshold": min_confidence,
            },
        )
        return None, all_candidates

    return best, all_candidates
