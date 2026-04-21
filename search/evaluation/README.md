# Retrieval evaluation harness

CLI tooling to evaluate the Typesense-backed paper search against a curated
20-query set. Companion to [docs/search-quality.md](../../docs/search-quality.md).

## Files

| File              | Purpose                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `queries.yaml`    | 20 tourism/hospitality evaluation queries (Q01–Q20) with intent + must_contain |
| `synonyms.json`   | 15 Typesense synonym groups covering acronyms and near-synonym concepts |
| `eval_search.py`  | CLI runner: issues each query, emits per-run `results/report/summary` files |
| `install_synonyms.py` | Upserts `synonyms.json` into the Typesense `papers` collection      |
| `runs/<label>/`   | Generated output — one subdirectory per labelled run                     |

## Prerequisites

- Typesense is running and reachable (e.g. `docker compose up typesense`).
- `papers` collection is populated (run the ingestion + reindex pipeline first).
- Python dependencies: `typesense`, `pyyaml`. Install with
  `pip install typesense pyyaml` if not already present.
- Environment variables set (typically from the project root `.env`):
  - `TYPESENSE_HOST`, `TYPESENSE_PORT`, `TYPESENSE_PROTOCOL`,
    `TYPESENSE_ADMIN_API_KEY`

## Quick start

From the repo root:

```bash
cd search/evaluation

# Rung 0 — committed baseline ranking
python eval_search.py --label baseline

# Rung 2 — install synonyms once, then evaluate with them
python install_synonyms.py
python eval_search.py --label with-synonyms
```

Each invocation creates `runs/<label>/`:

```
runs/
├── baseline/
│   ├── results_<timestamp>.json       # raw top-10 hits per query
│   ├── report_<timestamp>.md          # human-readable report; fill in Human verdict column
│   └── summary_<timestamp>.csv        # flat one-row-per-query summary
└── with-synonyms/
    └── ...
```

Filenames include a `YYYYMMDD_HHMMSS` timestamp so successive runs under the
same label accumulate side-by-side.

## Invocation reference

```
python eval_search.py [OPTIONS]

Options:
  --label TEXT              Run label; used as the output subdirectory name.
                            [required]
  --queries PATH            Path to the queries YAML.
                            [default: ./queries.yaml]
  --per-page INTEGER        Number of hits to fetch per query.  [default: 10]
  --query-by TEXT           Override query_by (comma-separated field list).
                            [default: title,abstract,authors_text,journal_name]
  --query-by-weights TEXT   Override query_by_weights (comma-separated ints).
                            [default: 8,2,3,2]
  --sort-by TEXT            Override sort_by.
                            [default: _text_match:desc,cited_by_count:desc]
  -h, --help                Show help and exit.
```

```
python install_synonyms.py [--remove]

  Upserts every entry in synonyms.json into the `papers` collection.
  Pass --remove to delete every synonym previously installed from this file.
```

Any of the `--query-by*` / `--sort-by` overrides lets you explore a tuning
rung without editing code. If omitted, the runner uses the committed
defaults from [docs/search-index.md](../../docs/search-index.md).

## Typical workflows

### 1. Baseline vs. synonyms (recommended first pass)

```bash
python eval_search.py --label baseline
python install_synonyms.py
python eval_search.py --label with-synonyms
diff "$(ls -t runs/baseline/summary_*.csv | head -1)" \
     "$(ls -t runs/with-synonyms/summary_*.csv | head -1)"
```

Open both `report_*.md` files, grade each query (PASS / PARTIAL / FAIL),
and compare totals.

### 2. Title-heavy precision test

```bash
python eval_search.py \
  --label title-heavy \
  --query-by title,abstract,authors_text,journal_name \
  --query-by-weights 10,1,3,2
```

Useful when baseline surfaces too many papers that only mention the query
keyword in a long abstract.

### 3. Recency-biased spot check

For queries about emerging topics (COVID recovery, recent smart-tourism work)
where citation-count-biased sorting hides recent papers:

```bash
python eval_search.py \
  --label recency \
  --sort-by "_text_match:desc,publication_year:desc"
```

## Reading the report

`report_<timestamp>.md` contains a Summary table followed by one section per
query, each with:

1. Query string, intent, and indicative P@10.
2. A table of top hits: rank, indicative relevance flag, year, citations,
   title, journal.
3. The top-3 abstract snippets for fast human judgement.

**You fill in** the `Human verdict` column in the Summary table with `pass`
or `fail` per the rubric in
[docs/search-quality.md](../../docs/search-quality.md). Annotate `partial`
cases in-line.

After grading, tally the verdicts at the top of the report. The Stage 8
acceptance criterion is **PASS ≥ 15, FAIL ≤ 2**.

## Commit policy

- Commit `queries.yaml` and `synonyms.json` changes via normal review.
- Commit reviewed reports (`runs/<label>/report_<timestamp>.md`) — they are
  the audit trail showing why Stage 8 was signed off.
- `results_*.json` is reproducible from the inputs; commit it only for the
  final accepted production run.
- Do not commit `__pycache__/` or stray `runs/_tmp*` directories
  (gitignored at the repo root).

## Related docs

- [docs/search-quality.md](../../docs/search-quality.md) — protocol, rubric,
  tuning ladder, acceptance criterion
- [docs/search-index.md](../../docs/search-index.md) — Typesense schemas and
  committed ranking baseline
