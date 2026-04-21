# THRN Ingestion — Quickstart

**Python 3.11+ required.**

---

## 1. Install

```bash
# From the ingestion/ directory:
pip install -r requirements.txt
# Or install the package in editable mode:
pip install -e .
```

Install dev dependencies (tests):
```bash
pip install pytest
```

---

## 2. Set up `.env`

Copy the repo-root example file and fill in real values:

```bash
cp ../.env.example ../.env
```

Minimum required variables:

| Variable                   | Description                                        |
|----------------------------|----------------------------------------------------|
| `OPENALEX_CONTACT_EMAIL`   | Your email (sent in every OpenAlex request)        |
| `DATABASE_URL`             | PostgreSQL DSN, e.g. `postgresql://thrn:pw@localhost:5432/thrn` |

Optional:

| Variable                   | Default                          | Description                  |
|----------------------------|----------------------------------|------------------------------|
| `OPENALEX_BASE_URL`        | `https://api.openalex.org`       | Override for testing         |
| `TYPESENSE_HOST`           | `localhost`                      |                              |
| `TYPESENSE_PORT`           | `8108`                           |                              |
| `TYPESENSE_ADMIN_API_KEY`  | `change-me-locally`              |                              |
| `LOG_LEVEL`                | `INFO`                           | `DEBUG`, `INFO`, `WARNING`   |
| `DB_MIN_CONNECTIONS`       | `1`                              | Pool sizing                  |
| `DB_MAX_CONNECTIONS`       | `5`                              | Pool sizing                  |

---

## 3. Standard ingestion sequence

Run these three commands in order on a fresh database (after applying migrations):

### Step 1 — Bootstrap journals

Seed the `journals` table from the curated whitelist:

```bash
# From ingestion/ with PYTHONPATH set:
PYTHONPATH=src:cli python -m thrn bootstrap-journals
# Or with a custom CSV:
PYTHONPATH=src:cli python -m thrn bootstrap-journals --csv /path/to/journal_whitelist.csv
```

Expected output: `Done. 36 rows processed, 36 new inserts.`

### Step 2 — Enrich journals (resolve OpenAlex source IDs)

```bash
PYTHONPATH=src:cli python -m thrn enrich-journals --only-missing --min-confidence 0.85
```

This step queries the OpenAlex `/sources` endpoint for each journal. Journals
flagged `manual_review_flag=true` in the CSV are never auto-accepted; their
candidates are logged to `source_match_audit` for human review.

### Step 3 — Ingest works

```bash
# Full historical ingest (may be slow for large journals):
PYTHONPATH=src:cli python -m thrn ingest-works

# With a date filter:
PYTHONPATH=src:cli python -m thrn ingest-works --since 2020-01-01

# Dry run (no writes):
PYTHONPATH=src:cli python -m thrn ingest-works --dry-run

# Limit pages (useful for testing):
PYTHONPATH=src:cli python -m thrn ingest-works --max-pages 2
```

### Ongoing refresh

```bash
# Ingest works published in the last 30 days:
PYTHONPATH=src:cli python -m thrn refresh-recent --days 30
```

---

## 4. Check status

```bash
PYTHONPATH=src:cli python -m thrn status --last 10
```

---

## 5. Rebuild Typesense index

```bash
PYTHONPATH=src:cli python -m thrn reindex-search --collection all --full
```

---

## 6. Running tests

```bash
# From the repo root:
pytest ingestion/tests -q
```

Tests are offline — no live DB or network required.

---

## 7. Exact `python -m thrn` invocation

From the `ingestion/` directory:

```bash
cd ingestion
PYTHONPATH=src:cli python -m thrn --help
```

This should print all six subcommands. The `PYTHONPATH` setting makes both
the `thrn_ingest` library (in `src/`) and the `thrn` CLI package (in `cli/`)
importable without a full `pip install`.
