"""Load and normalise the journal whitelist CSV.

The whitelist lives at ``data/seed/journal_whitelist.csv`` relative to the
repo root.  This module reads it and returns a list of :class:`Journal`
dataclass instances ready for upsert.

Normalisation rules applied here (mirror what the DB citext stores):
- ``normalized_name``: strip leading/trailing whitespace, collapse internal
  whitespace, convert to lower-case.
- ISSNs: strip hyphens and whitespace; store as canonical ``XXXX-XXXX``.
- Empty strings → None for nullable fields.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Sequence

from thrn_ingest.models import Journal

logger = logging.getLogger(__name__)

_ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dXx]$")


def _normalise_name(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip()).lower()


def _normalise_issn(raw: str) -> str | None:
    """Return canonical XXXX-XXXX form, or None if blank/invalid."""
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "")
    if len(cleaned) == 8 and "-" not in cleaned:
        cleaned = f"{cleaned[:4]}-{cleaned[4:]}"
    if _ISSN_RE.match(cleaned):
        return cleaned.upper()
    logger.warning("Ignoring malformed ISSN", extra={"raw": raw})
    return None


def _empty_to_none(val: str) -> str | None:
    stripped = val.strip()
    return stripped if stripped else None


def load_whitelist(csv_path: Path) -> list[Journal]:
    """Parse *csv_path* and return a list of Journal dataclasses.

    Raises ``FileNotFoundError`` if the file does not exist.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Journal whitelist not found: {csv_path}")

    journals: list[Journal] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=1):
            try:
                j = Journal(
                    display_name=row["journal_name"].strip(),
                    normalized_name=_normalise_name(row.get("normalized_name") or row["journal_name"]),
                    issn_print=_normalise_issn(row.get("issn_print", "")),
                    issn_online=_normalise_issn(row.get("issn_online", "")),
                    publisher=_empty_to_none(row.get("publisher", "")),
                    scimago_category=_empty_to_none(row.get("scimago_category", "")),
                    scope_bucket=row.get("scope_bucket", "mixed").strip() or "mixed",
                    tier_flag=row.get("tier_flag", "extended").strip() or "extended",
                    active_flag=True,
                    manual_review_flag=(
                        row.get("manual_review_flag", "false").strip().lower() == "true"
                    ),
                    inclusion_reason=_empty_to_none(row.get("inclusion_reason", "")),
                    notes=_empty_to_none(row.get("notes", "")),
                )
                journals.append(j)
            except (KeyError, ValueError) as exc:
                logger.error(
                    "Skipping malformed whitelist row",
                    extra={"row_num": i, "error": str(exc)},
                )

    logger.info(
        "Loaded whitelist",
        extra={"path": str(csv_path), "count": len(journals)},
    )
    return journals


def validate_whitelist(journals: Sequence[Journal]) -> list[str]:
    """Return a list of warning strings for entries that need attention.

    Does NOT raise; caller decides what to do with warnings.
    """
    warnings: list[str] = []
    seen_names: set[str] = set()
    seen_print: dict[str, str] = {}
    seen_online: dict[str, str] = {}

    for j in journals:
        if j.normalized_name in seen_names:
            warnings.append(f"Duplicate normalized_name: {j.normalized_name!r}")
        seen_names.add(j.normalized_name)

        if not j.issn_print and not j.issn_online:
            warnings.append(
                f"Journal has no ISSN — name-fallback only: {j.display_name!r}"
            )

        if j.issn_print:
            if j.issn_print in seen_print:
                warnings.append(
                    f"Duplicate issn_print {j.issn_print}: "
                    f"{seen_print[j.issn_print]!r} and {j.display_name!r}"
                )
            seen_print[j.issn_print] = j.display_name

        if j.issn_online:
            if j.issn_online in seen_online:
                warnings.append(
                    f"Duplicate issn_online {j.issn_online}: "
                    f"{seen_online[j.issn_online]!r} and {j.display_name!r}"
                )
            seen_online[j.issn_online] = j.display_name

    return warnings
