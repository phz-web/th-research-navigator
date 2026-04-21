"""CLI commands for the THRN ingestion pipeline.

All commands are grouped under the ``thrn`` Typer app.

Commands
--------
bootstrap-journals  Seed journals table from whitelist CSV.
enrich-journals     Match journals to OpenAlex sources.
ingest-works        Harvest papers for all active journals.
refresh-recent      Short-cut: ingest works from the last N days.
reindex-search      Rebuild Typesense collections from PostgreSQL.
status              Show recent ingestion_runs.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(
    name="thrn",
    help="Tourism & Hospitality Research Navigator — ingestion pipeline CLI.",
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup() -> None:
    """Bootstrap logging once per command invocation."""
    from thrn_ingest.config import Config
    from thrn_ingest.logging_setup import setup_logging

    setup_logging(Config.log_level)


def _get_conn():  # type: ignore[return]  # returns psycopg connection
    from thrn_ingest.db import get_pool

    return get_pool().connection()


# ---------------------------------------------------------------------------
# 1. bootstrap-journals
# ---------------------------------------------------------------------------

@app.command("bootstrap-journals")
def bootstrap_journals(
    csv_path: Annotated[
        Optional[Path],
        typer.Option("--csv", help="Path to journal_whitelist.csv"),
    ] = None,
) -> None:
    """Upsert rows from the journal whitelist CSV into the journals table.

    Idempotent: safe to run multiple times. Deduplication key is
    (normalized_name, issn_print, issn_online).
    """
    _setup()
    from thrn_ingest.config import Config
    from thrn_ingest.db import upsert_journal
    from thrn_ingest.runs import fail_run, finish_run, start_run
    from thrn_ingest.whitelist import load_whitelist, validate_whitelist

    resolved_csv = csv_path or Config.journal_whitelist_csv
    typer.echo(f"Loading whitelist from: {resolved_csv}")

    journals = load_whitelist(resolved_csv)

    warnings = validate_whitelist(journals)
    for w in warnings:
        typer.secho(f"  WARN: {w}", fg=typer.colors.YELLOW)

    with _get_conn() as conn:
        run_ctx = start_run(conn, "bootstrap-journals", {"csv": str(resolved_csv)})
        try:
            inserted = 0
            for journal in journals:
                db_id = upsert_journal(conn, journal)
                if db_id > 0:
                    inserted += 1
            conn.commit()
            run_ctx.journals_touched = len(journals)
            finish_run(conn, run_ctx)
        except Exception as exc:
            fail_run(conn, run_ctx, exc)
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    typer.secho(
        f"Done. {len(journals)} rows processed, {inserted} new inserts.",
        fg=typer.colors.GREEN,
    )


# ---------------------------------------------------------------------------
# 2. enrich-journals
# ---------------------------------------------------------------------------

@app.command("enrich-journals")
def enrich_journals(
    only_missing: Annotated[
        bool,
        typer.Option("--only-missing/--all", help="Enrich only journals lacking openalex_source_id"),
    ] = True,
    min_confidence: Annotated[
        float,
        typer.Option("--min-confidence", help="Minimum confidence to auto-accept a match"),
    ] = 0.85,
) -> None:
    """Match journal whitelist entries to OpenAlex sources.

    Uses ISSN-first matching, falling back to name search. Auto-accepts
    candidates above --min-confidence unless manual_review_flag is set.
    All evaluated candidates are logged to source_match_audit.
    """
    _setup()
    from thrn_ingest.db import log_source_match_audit, update_journal_openalex
    from thrn_ingest.match_sources import find_best_match
    from thrn_ingest.models import Journal
    from thrn_ingest.openalex_client import get_client
    from thrn_ingest.runs import fail_run, finish_run, start_run

    with _get_conn() as conn:
        run_ctx = start_run(
            conn,
            "enrich-journals",
            {"only_missing": only_missing, "min_confidence": min_confidence},
        )
        try:
            if only_missing:
                rows = conn.execute(
                    "SELECT id, display_name, normalized_name, issn_print, issn_online, "
                    "manual_review_flag FROM journals WHERE openalex_source_id IS NULL AND active_flag = TRUE"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, display_name, normalized_name, issn_print, issn_online, "
                    "manual_review_flag FROM journals WHERE active_flag = TRUE"
                ).fetchall()

            client = get_client()
            accepted_count = 0

            for row in rows:
                jid, display, norm, issn_p, issn_o, manual_review = row
                journal = Journal(
                    id=jid,
                    display_name=display,
                    normalized_name=norm,
                    issn_print=issn_p,
                    issn_online=issn_o,
                    manual_review_flag=bool(manual_review),
                )
                typer.echo(f"  Matching: {display}")

                best, all_candidates = find_best_match(
                    journal, client, min_confidence=min_confidence
                )

                # Log all candidates to audit
                for cand in all_candidates:
                    is_best_accepted = (best is not None and cand.openalex_source_id == best.openalex_source_id)
                    log_source_match_audit(
                        conn,
                        run_ctx.run_id,
                        jid,
                        display,
                        cand,
                        accepted=is_best_accepted,
                    )

                if best is None and not all_candidates:
                    log_source_match_audit(
                        conn,
                        run_ctx.run_id,
                        jid,
                        display,
                        None,
                        accepted=False,
                        notes="No candidates found",
                    )

                if best is not None:
                    update_journal_openalex(conn, jid, best.openalex_source_id, best.raw_json or {})
                    accepted_count += 1
                    typer.secho(
                        f"    ✓ {best.openalex_source_id} (confidence={best.confidence:.3f}, "
                        f"method={best.match_method})",
                        fg=typer.colors.GREEN,
                    )
                else:
                    typer.secho(
                        f"    ✗ No auto-accepted match (manual_review={journal.manual_review_flag})",
                        fg=typer.colors.YELLOW,
                    )

                conn.commit()
                run_ctx.journals_touched += 1

            finish_run(conn, run_ctx)

        except Exception as exc:
            fail_run(conn, run_ctx, exc)
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    typer.secho(
        f"Done. {len(rows)} journals evaluated, {accepted_count} auto-accepted.",
        fg=typer.colors.GREEN,
    )


# ---------------------------------------------------------------------------
# 3. ingest-works
# ---------------------------------------------------------------------------

@app.command("ingest-works")
def ingest_works(
    since: Annotated[
        Optional[str],
        typer.Option("--since", help="Only ingest works published on/after YYYY-MM-DD"),
    ] = None,
    journal_id: Annotated[
        Optional[list[int]],
        typer.Option("--journal-id", help="Limit to specific journal DB ids (repeatable)"),
    ] = None,
    max_pages: Annotated[
        Optional[int],
        typer.Option("--max-pages", help="Safety cap on API pages per journal"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print what would be done without writing"),
    ] = False,
) -> None:
    """Harvest works from OpenAlex for all active, enriched journals.

    Implements idempotent upserts: running twice with no upstream changes
    produces 0 new inserts and 0 content-changing updates.
    """
    _setup()
    from thrn_ingest.ingest_works import ingest_works_for_journal
    from thrn_ingest.openalex_client import get_client
    from thrn_ingest.runs import fail_run, finish_run, start_run

    since_date: datetime.date | None = None
    if since:
        try:
            since_date = datetime.date.fromisoformat(since)
        except ValueError:
            typer.secho(f"Invalid --since date: {since!r} — use YYYY-MM-DD", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    params: dict = {
        "since": since,
        "journal_ids": journal_id,
        "max_pages": max_pages,
        "dry_run": dry_run,
    }

    with _get_conn() as conn:
        run_ctx = start_run(conn, "ingest-works", params)
        try:
            # Fetch active, enriched journals from DB
            q = (
                "SELECT id, display_name, openalex_source_id FROM journals "
                "WHERE active_flag = TRUE AND openalex_source_id IS NOT NULL"
            )
            if journal_id:
                placeholders = ", ".join(f"%(jid_{i})s" for i in range(len(journal_id)))
                q += f" AND id IN ({placeholders})"
                q_params = {f"jid_{i}": v for i, v in enumerate(journal_id)}
            else:
                q_params = {}

            journals = conn.execute(q, q_params).fetchall()

            if not journals:
                typer.secho("No active enriched journals found.", fg=typer.colors.YELLOW)
                finish_run(conn, run_ctx)
                return

            typer.echo(f"Ingesting works for {len(journals)} journal(s)...")
            client = get_client()

            for jid, jname, oa_source_id in journals:
                typer.echo(f"  → {jname} ({oa_source_id})")
                ingest_works_for_journal(
                    conn=conn,
                    client=client,
                    run_ctx=run_ctx,
                    journal_id=int(jid),
                    openalex_source_id=oa_source_id,
                    journal_display_name=jname,
                    since=since_date,
                    max_pages=max_pages,
                    dry_run=dry_run,
                )

            finish_run(conn, run_ctx)

        except Exception as exc:
            fail_run(conn, run_ctx, exc)
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    typer.secho(
        f"Done. inserted={run_ctx.papers_inserted} updated={run_ctx.papers_updated} "
        f"authors_inserted={run_ctx.authors_inserted}",
        fg=typer.colors.GREEN,
    )


# ---------------------------------------------------------------------------
# 4. refresh-recent
# ---------------------------------------------------------------------------

@app.command("refresh-recent")
def refresh_recent(
    days: Annotated[
        int,
        typer.Option("--days", help="Ingest works published within the last N days"),
    ] = 30,
) -> None:
    """Ingest works published in the last N days for all active journals.

    Equivalent to: thrn ingest-works --since=<today - N days>
    """
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    typer.echo(f"refresh-recent: since={since}")
    # Delegate to ingest-works by calling the underlying logic
    from typer.testing import CliRunner  # only imported at runtime for delegation

    # Use Python-level invocation to avoid subprocess overhead
    from thrn_ingest.config import Config  # noqa: F401
    from thrn_ingest.logging_setup import setup_logging

    setup_logging(Config.log_level)

    from thrn_ingest.db import get_pool
    from thrn_ingest.ingest_works import ingest_works_for_journal
    from thrn_ingest.openalex_client import get_client
    from thrn_ingest.runs import fail_run, finish_run, start_run

    since_date = datetime.date.fromisoformat(since)

    with get_pool().connection() as conn:
        run_ctx = start_run(conn, "refresh-recent", {"days": days, "since": since})
        try:
            journals = conn.execute(
                "SELECT id, display_name, openalex_source_id FROM journals "
                "WHERE active_flag = TRUE AND openalex_source_id IS NOT NULL"
            ).fetchall()

            client = get_client()
            for jid, jname, oa_source_id in journals:
                typer.echo(f"  → {jname}")
                ingest_works_for_journal(
                    conn=conn,
                    client=client,
                    run_ctx=run_ctx,
                    journal_id=int(jid),
                    openalex_source_id=oa_source_id,
                    journal_display_name=jname,
                    since=since_date,
                )

            finish_run(conn, run_ctx)

        except Exception as exc:
            fail_run(conn, run_ctx, exc)
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    typer.secho(
        f"Done. inserted={run_ctx.papers_inserted} updated={run_ctx.papers_updated}",
        fg=typer.colors.GREEN,
    )


# ---------------------------------------------------------------------------
# 5. reindex-search
# ---------------------------------------------------------------------------

@app.command("reindex-search")
def reindex_search(
    collection: Annotated[
        str,
        typer.Option(
            "--collection",
            help="Collection(s) to reindex: papers|authors|journals|all",
        ),
    ] = "all",
    full: Annotated[
        bool,
        typer.Option("--full/--partial", help="Full reindex vs partial (updated only)"),
    ] = True,
) -> None:
    """Rebuild Typesense collections from PostgreSQL.

    Delegates to the Python scripts in search/scripts/.
    Prints per-collection counts and timings.
    """
    _setup()
    import time

    from thrn_ingest.config import Config

    scripts_dir = Config.search_scripts_dir

    targets: list[str]
    if collection == "all":
        targets = ["papers", "authors", "journals"]
    elif collection in ("papers", "authors", "journals"):
        targets = [collection]
    else:
        typer.secho(f"Unknown collection: {collection!r}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    script_map = {
        "papers": "reindex_papers.py",
        "authors": "reindex_authors.py",
        "journals": "reindex_journals.py",
    }
    partial_script = scripts_dir / "partial_update.py"

    for target in targets:
        if full:
            script = scripts_dir / script_map[target]
        else:
            # partial_update handles all collections via --collection flag
            script = partial_script

        if not script.exists():
            typer.secho(
                f"  Script not found: {script} — skipping {target}",
                fg=typer.colors.YELLOW,
            )
            continue

        t0 = time.perf_counter()
        typer.echo(f"  Reindexing {target} ({'full' if full else 'partial'})...")
        extra_args = ["--collection", target] if not full else []
        result = subprocess.run(
            [sys.executable, str(script)] + extra_args,
            capture_output=False,
        )
        elapsed = time.perf_counter() - t0

        if result.returncode != 0:
            typer.secho(
                f"  {target}: FAILED (exit {result.returncode}) in {elapsed:.1f}s",
                fg=typer.colors.RED,
            )
        else:
            typer.secho(
                f"  {target}: done in {elapsed:.1f}s",
                fg=typer.colors.GREEN,
            )


# ---------------------------------------------------------------------------
# 6. status
# ---------------------------------------------------------------------------

@app.command("status")
def status(
    last: Annotated[
        int,
        typer.Option("--last", help="Show last N ingestion runs"),
    ] = 10,
) -> None:
    """Show recent ingestion_runs with counts and status."""
    _setup()

    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, command, status, started_at, finished_at,
                   papers_inserted, papers_updated, error_summary
            FROM ingestion_runs
            ORDER BY started_at DESC
            LIMIT %(n)s
            """,
            {"n": last},
        ).fetchall()

    if not rows:
        typer.echo("No ingestion runs found.")
        return

    header = (
        f"{'Run ID':<38}  {'Command':<20}  {'Status':<8}  "
        f"{'Started':<20}  {'Inserted':>8}  {'Updated':>8}  Error"
    )
    typer.echo(header)
    typer.echo("-" * len(header))

    for r in rows:
        run_id, command, run_status, started_at, finished_at, pi, pu, err = r
        started_str = str(started_at)[:19] if started_at else "—"
        err_str = (err[:40] + "…") if err and len(err) > 40 else (err or "")
        color = (
            typer.colors.GREEN
            if run_status == "success"
            else (typer.colors.RED if run_status == "failed" else typer.colors.YELLOW)
        )
        typer.secho(
            f"{str(run_id):<38}  {command:<20}  {run_status:<8}  "
            f"{started_str:<20}  {(pi or 0):>8}  {(pu or 0):>8}  {err_str}",
            fg=color,
        )
