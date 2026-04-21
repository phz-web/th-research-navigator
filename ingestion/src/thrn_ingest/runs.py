"""Ingestion run lifecycle helpers.

Each CLI command should:
1. Call ``start_run(conn, command, params)`` to create an ``ingestion_runs`` row.
2. Accumulate counters in the returned :class:`RunContext`.
3. Call ``finish_run(conn, ctx)`` on success or ``fail_run(conn, ctx, err)`` on
   exception.

This ensures that every invocation is auditable and resumable.
"""

from __future__ import annotations

import datetime
import logging
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any

import orjson

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    """Mutable accumulator for a single ingestion run."""

    run_id: uuid.UUID
    command: str
    params: dict[str, Any] = field(default_factory=dict)

    journals_touched: int = 0
    papers_inserted: int = 0
    papers_updated: int = 0
    authors_inserted: int = 0
    authors_updated: int = 0

    # Arbitrary additional stats (pages fetched, bytes written, …)
    stats: dict[str, Any] = field(default_factory=dict)


def start_run(
    conn: Any,
    command: str,
    params: dict[str, Any] | None = None,
) -> RunContext:
    """Create a new ``ingestion_runs`` row with status=running; return RunContext."""
    run_id = uuid.uuid4()
    params = params or {}

    conn.execute(
        """
        INSERT INTO ingestion_runs (id, command, status, params)
        VALUES (%(id)s, %(cmd)s, 'running', %(params)s::jsonb)
        """,
        {
            "id": str(run_id),
            "cmd": command,
            "params": orjson.dumps(params).decode(),
        },
    )
    conn.commit()
    logger.info("Run started", extra={"run_id": str(run_id), "command": command})
    return RunContext(run_id=run_id, command=command, params=params)


def finish_run(conn: Any, ctx: RunContext) -> None:
    """Update the run row to status=success with final counts."""
    now = datetime.datetime.now(datetime.timezone.utc)
    stats_str = orjson.dumps(ctx.stats).decode() if ctx.stats else "{}"
    conn.execute(
        """
        UPDATE ingestion_runs SET
            status           = 'success',
            finished_at      = %(now)s,
            journals_touched = %(jt)s,
            papers_inserted  = %(pi)s,
            papers_updated   = %(pu)s,
            authors_inserted = %(ai)s,
            authors_updated  = %(au)s,
            stats            = %(stats)s::jsonb
        WHERE id = %(id)s
        """,
        {
            "now": now.isoformat(),
            "jt": ctx.journals_touched,
            "pi": ctx.papers_inserted,
            "pu": ctx.papers_updated,
            "ai": ctx.authors_inserted,
            "au": ctx.authors_updated,
            "stats": stats_str,
            "id": str(ctx.run_id),
        },
    )
    conn.commit()
    logger.info(
        "Run finished",
        extra={
            "run_id": str(ctx.run_id),
            "papers_inserted": ctx.papers_inserted,
            "papers_updated": ctx.papers_updated,
        },
    )


def fail_run(conn: Any, ctx: RunContext, exc: BaseException) -> None:
    """Update the run row to status=failed with error_summary."""
    now = datetime.datetime.now(datetime.timezone.utc)
    summary = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1000:]}"
    conn.execute(
        """
        UPDATE ingestion_runs SET
            status        = 'failed',
            finished_at   = %(now)s,
            error_summary = %(summary)s
        WHERE id = %(id)s
        """,
        {
            "now": now.isoformat(),
            "summary": summary[:2000],
            "id": str(ctx.run_id),
        },
    )
    conn.commit()
    logger.error(
        "Run failed",
        extra={"run_id": str(ctx.run_id), "error": str(exc)},
    )
