#!/usr/bin/env python3
"""Retrieval quality evaluation runner for the `papers` Typesense collection.

Loads queries from ``queries.yaml``, executes each against a live Typesense
using the project's default ``query_by`` / ``query_by_weights`` (overridable
via CLI), and writes:

    * ``results_<timestamp>.json``  — raw top-10 hits per query
    * ``report_<timestamp>.md``     — human-readable markdown for review
    * ``summary_<timestamp>.csv``   — one row per query with automated metrics

Metrics are INDICATIVE, not ground-truth. A human still reviews the markdown
report and fills in the Pass/Fail column before the stage-8 checkpoint is
considered met.

Usage::

    python search/evaluation/eval_search.py \
        --query-by "title,abstract,authors_text,journal_name" \
        --query-by-weights "8,2,3,2" \
        --label baseline

    python search/evaluation/eval_search.py \
        --query-by "title,abstract,authors_text,journal_name" \
        --query-by-weights "10,1,3,2" \
        --label title-heavy

Artifacts land in ``search/evaluation/runs/<label>/``.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# We reuse the project's Typesense client singleton so env vars line up.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "search" / "scripts"))

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    print("PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

try:
    from typesense_client import get_client  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"Could not import typesense_client: {e}", file=sys.stderr)
    print("Make sure search/scripts/typesense_client.py is present and env is configured.", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Scoring helpers (indicative — human makes final call).
# ---------------------------------------------------------------------------
def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).lower()


def score_hit(hit: dict[str, Any], must_contain: list[str]) -> bool:
    """A hit is *weakly relevant* if at least one `must_contain` term is a
    substring of title OR abstract (case-insensitive).

    This intentionally uses `any()` not `all()` — the query-set declares
    must_contain in OR-semantics because many queries have several valid
    surface forms (e.g. "china" OR "chinese").
    """
    if not must_contain:
        return True
    haystack = _norm(hit.get("title")) + " " + _norm(hit.get("abstract"))
    return any(term.lower() in haystack for term in must_contain)


def precision_at_k(hits: list[dict[str, Any]], must_contain: list[str], k: int) -> float:
    if not hits:
        return 0.0
    top = hits[: min(k, len(hits))]
    rel = sum(1 for h in top if score_hit(h, must_contain))
    return rel / len(top)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
DEFAULT_QUERY_BY = "title,abstract,authors_text,journal_name"
DEFAULT_QUERY_BY_WEIGHTS = "8,2,3,2"
DEFAULT_SORT_BY = "_text_match:desc,cited_by_count:desc"
DEFAULT_PER_PAGE = 10


def load_queries(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        data = yaml.safe_load(f)
    queries = data.get("queries") or []
    if not queries:
        raise SystemExit(f"No queries found in {path}")
    return queries


def run_one(client, query: str, *, query_by: str, query_by_weights: str, sort_by: str, per_page: int) -> dict[str, Any]:
    params = {
        "q": query,
        "query_by": query_by,
        "query_by_weights": query_by_weights,
        "sort_by": sort_by,
        "per_page": per_page,
        "include_fields": "id,title,abstract,authors_text,journal_name,publication_year,cited_by_count,is_oa,doi,primary_topic",
    }
    return client.collections["papers"].documents.search(params)


def truncate_abstract(a: str | None, n: int = 180) -> str:
    if not a:
        return ""
    a = re.sub(r"\s+", " ", a).strip()
    return (a[: n - 1] + "…") if len(a) > n else a


def build_markdown(label: str, timestamp: str, config: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append(f"# Retrieval Quality Evaluation — `{label}`")
    lines.append("")
    lines.append(f"- **Run timestamp:** {timestamp}")
    lines.append(f"- **Collection:** papers")
    lines.append(f"- **query_by:** `{config['query_by']}`")
    lines.append(f"- **query_by_weights:** `{config['query_by_weights']}`")
    lines.append(f"- **sort_by:** `{config['sort_by']}`")
    lines.append(f"- **per_page:** {config['per_page']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Query | P@10 | Hits | Latency (ms) | Human verdict |")
    lines.append("|---|-------|------|------|--------------|---------------|")
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['query']} | {r['p_at_10']:.2f} | {r['total_hits']} | {r['search_time_ms']} |  |"
        )
    lines.append("")
    lines.append("> Fill the **Human verdict** column with `pass` / `fail` after reviewing the per-query results below.")
    lines.append(">")
    lines.append("> The stage-8 checkpoint is met when ≥ 15 / 20 queries are `pass`.")
    lines.append("")
    lines.append("## Per-query detail")
    lines.append("")
    for r in rows:
        lines.append(f"### {r['id']} — `{r['query']}`")
        lines.append("")
        lines.append(f"- **Intent:** {r['intent']}")
        lines.append(f"- **P@10 (indicative):** {r['p_at_10']:.2f}")
        lines.append(f"- **Hits returned:** {r['total_hits']}   • **Latency:** {r['search_time_ms']} ms")
        lines.append("")
        if not r["hits"]:
            lines.append("_No results._")
            lines.append("")
            continue
        lines.append("| Rank | Relevant? | Year | Cites | Title | Journal |")
        lines.append("|------|-----------|------|-------|-------|---------|")
        for rank, h in enumerate(r["hits"], start=1):
            flag = "✓" if h["_indicative_relevant"] else "·"
            title = h.get("title", "").replace("|", "\\|")
            journal = h.get("journal_name", "").replace("|", "\\|")
            lines.append(
                f"| {rank} | {flag} | {h.get('publication_year','')} | {h.get('cited_by_count',0)} | {title} | {journal} |"
            )
        lines.append("")
        # Include top-3 abstract snippets for human judgement
        lines.append("**Top-3 abstract snippets:**")
        lines.append("")
        for rank, h in enumerate(r["hits"][:3], start=1):
            snippet = truncate_abstract(h.get("abstract"), 220)
            if snippet:
                lines.append(f"{rank}. {snippet}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run retrieval quality evaluation")
    p.add_argument("--queries", default=str(_HERE / "queries.yaml"))
    p.add_argument("--label", required=True, help="Run label, e.g. 'baseline' or 'title-heavy'")
    p.add_argument("--query-by", default=DEFAULT_QUERY_BY)
    p.add_argument("--query-by-weights", default=DEFAULT_QUERY_BY_WEIGHTS)
    p.add_argument("--sort-by", default=DEFAULT_SORT_BY)
    p.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE)
    args = p.parse_args(argv)

    queries = load_queries(Path(args.queries))
    client = get_client()

    # Sanity: confirm the papers collection exists and has docs.
    try:
        coll = client.collections["papers"].retrieve()
    except Exception as e:
        print(f"Could not retrieve `papers` collection: {e}", file=sys.stderr)
        return 2
    print(f"Collection `papers` has {coll.get('num_documents', '?')} documents.")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = _HERE / "runs" / args.label
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for q in queries:
        result = run_one(
            client,
            q["query"],
            query_by=args.query_by,
            query_by_weights=args.query_by_weights,
            sort_by=args.sort_by,
            per_page=args.per_page,
        )
        hits = [h["document"] for h in result.get("hits", [])]
        for h in hits:
            h["_indicative_relevant"] = score_hit(h, q.get("must_contain") or [])
        rows.append(
            {
                "id": q["id"],
                "query": q["query"],
                "intent": q["intent"],
                "sub_area": q.get("sub_area", ""),
                "total_hits": result.get("found", 0),
                "search_time_ms": result.get("search_time_ms", 0),
                "p_at_10": precision_at_k(hits, q.get("must_contain") or [], k=10),
                "hits": hits,
            }
        )
        print(
            f"{q['id']:>4}  P@10={rows[-1]['p_at_10']:.2f}  "
            f"hits={rows[-1]['total_hits']:>5}  "
            f"ms={rows[-1]['search_time_ms']:>4}   {q['query']}"
        )

    # Write raw JSON
    (run_dir / f"results_{timestamp}.json").write_text(
        json.dumps(
            {
                "label": args.label,
                "timestamp": timestamp,
                "config": {
                    "query_by": args.query_by,
                    "query_by_weights": args.query_by_weights,
                    "sort_by": args.sort_by,
                    "per_page": args.per_page,
                },
                "rows": rows,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    # Write markdown report
    config = {
        "query_by": args.query_by,
        "query_by_weights": args.query_by_weights,
        "sort_by": args.sort_by,
        "per_page": args.per_page,
    }
    (run_dir / f"report_{timestamp}.md").write_text(build_markdown(args.label, timestamp, config, rows))

    # Write CSV summary
    with (run_dir / f"summary_{timestamp}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "query", "sub_area", "p_at_10", "total_hits", "search_time_ms"])
        for r in rows:
            w.writerow([r["id"], r["query"], r["sub_area"], f"{r['p_at_10']:.3f}", r["total_hits"], r["search_time_ms"]])

    # Overall indicative average
    avg = sum(r["p_at_10"] for r in rows) / len(rows)
    print(f"\nMean indicative P@10 across {len(rows)} queries: {avg:.3f}")
    print(f"Artifacts written to: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
