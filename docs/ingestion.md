# Ingestion Pipeline (Stage 4)

The ingestion pipeline harvests paper metadata from OpenAlex and upserts it into
PostgreSQL. It is the only component that calls external services; all other
components consume PostgreSQL as the source of truth.

Source: [`ingestion/`](../ingestion/)

---

## Purpose

Transform the curated journal whitelist (CSV) into a live, growing corpus of
tourism and hospitality research papers, authors, and journal metadata stored
in PostgreSQL.

---

## Environment variables

| Variable                   | Required | Default                        | Purpose                                                |
|----------------------------|----------|--------------------------------|--------------------------------------------------------|
| `OPENALEX_CONTACT_EMAIL`   | **Yes**  | —                              | Sent as `mailto=` on every API request (polite pool)   |
| `DATABASE_URL`             | **Yes**  | —                              | PostgreSQL connection string                           |
| `OPENALEX_BASE_URL`        | No       | `https://api.openalex.org`     | Override for testing against a mock server             |
| `TYPESENSE_HOST`           | No       | `localhost`                    | Used by `reindex-search` subcommand                    |
| `TYPESENSE_PORT`           | No       | `8108`                         |                                                        |
| `TYPESENSE_ADMIN_API_KEY`  | No       | `change-me-locally`            |                                                        |
| `LOG_LEVEL`                | No       | `INFO`                         | `DEBUG` / `INFO` / `WARNING` / `ERROR`                 |
| `DB_MIN_CONNECTIONS`       | No       | `1`                            | psycopg_pool minimum pool size                         |
| `DB_MAX_CONNECTIONS`       | No       | `5`                            | psycopg_pool maximum pool size                         |

All variables are loaded from `.env` at the repo root via `python-dotenv`.

---

## Data flow

```
data/seed/journal_whitelist.csv
        │
        ▼
  thrn bootstrap-journals
        │   (upserts rows into journals table)
        ▼
  journals (DB, openalex_source_id = NULL)
        │
        ▼
  thrn enrich-journals
        │   (GET /sources?filter=issn:<issn>)
        │   (GET /sources?search=<name>&filter=type:journal)
        │   (confidence scoring)
        │   (writes openalex_source_id + raw_json)
        │   (appends to source_match_audit)
        ▼
  journals (DB, openalex_source_id = Sxxx)
        │
        ▼
  thrn ingest-works
        │   (cursor-paginated GET /works?filter=primary_location.source.id:Sxxx)
        │   (abstract reconstruction from abstract_inverted_index)
        │   (upserts papers, authors, paper_authors)
        │   (writes data/raw/<run_id>/works/<journal>/<page>.json.gz)
        ▼
  papers + authors + paper_authors (DB)
        │
        ▼
  thrn reindex-search
        │   (delegates to search/scripts/)
        ▼
  Typesense collections
```

---

## Source-matching rules

The `enrich-journals` step maps each whitelist journal to an OpenAlex `source`
object using the following strategy (in priority order):

### 1. ISSN-first lookup

Queries `GET /sources?filter=issn:<issn_print>` and then
`GET /sources?filter=issn:<issn_online>`.

| Match type          | Confidence |
|---------------------|-----------|
| `issn_print` exact  | 1.000     |
| `issn_online` exact | 0.980     |

### 2. Name-fallback

Queries `GET /sources?search=<display_name>&filter=type:journal`.

| Match type                 | Confidence   |
|----------------------------|--------------|
| Exact display_name (citext)| 0.900        |
| Trigram similarity         | 0.500–0.850  |

Trigram score is computed via Python's `difflib.SequenceMatcher` after
normalising both names (lower-case, strip accents, collapse whitespace).

### Acceptance rule

A candidate is auto-accepted if **both** conditions hold:
- `confidence >= min_confidence` (default 0.85)
- `journal.manual_review_flag == FALSE`

If either condition fails the candidate is logged to `source_match_audit` with
`accepted = FALSE` for human review.

---

## CLI reference

| Command             | Description                                                         |
|---------------------|---------------------------------------------------------------------|
| `bootstrap-journals`| Seed/update `journals` table from whitelist CSV. Idempotent.        |
| `enrich-journals`   | Resolve `openalex_source_id` via ISSN/name matching.               |
| `ingest-works`      | Paginated harvest + upsert for all active, enriched journals.       |
| `refresh-recent`    | Shortcut: `ingest-works --since=<today - N days>`.                  |
| `reindex-search`    | Delegate to `search/scripts/` to rebuild Typesense collections.     |
| `status`            | Show last N `ingestion_runs` rows with counts and status.           |

### `bootstrap-journals`

```
thrn bootstrap-journals [--csv PATH]
```

- `--csv PATH` — Path to whitelist CSV. Default: `data/seed/journal_whitelist.csv`.
- Deduplication key: `(normalized_name, issn_print, issn_online)`.

### `enrich-journals`

```
thrn enrich-journals [--only-missing | --all] [--min-confidence FLOAT]
```

- `--only-missing` (default) — Only process journals without `openalex_source_id`.
- `--all` — Re-process all active journals.
- `--min-confidence FLOAT` — Auto-accept threshold (default 0.85).

### `ingest-works`

```
thrn ingest-works [--since YYYY-MM-DD] [--journal-id ID]... [--max-pages INT] [--dry-run]
```

- `--since` — Only fetch works published on or after this date.
- `--journal-id` — Limit to specific journal DB ids (repeatable).
- `--max-pages` — Safety cap on API pages per journal.
- `--dry-run` — Log what would be written without writing anything.

### `refresh-recent`

```
thrn refresh-recent [--days INT]
```

- `--days` — Look back N calendar days (default 30).

### `reindex-search`

```
thrn reindex-search [--collection papers|authors|journals|all] [--full | --partial]
```

### `status`

```
thrn status [--last INT]
```

---

## Known limitations

### OpenAlex abstract coverage

OpenAlex provides abstracts as an `abstract_inverted_index` rather than plain
text. Reconstruction is 100% accurate for the token content but word order is
derived from position integers that OpenAlex computes at index time — typically
correct but occasionally reordered for very long abstracts.

Approximately 15–25% of older tourism/hospitality papers lack abstract data
entirely in OpenAlex. These are ingested with `abstract = NULL`.

### Author disambiguation trust

v1 trusts OpenAlex's author disambiguation (`author_id`) without additional
validation. Cases where OpenAlex incorrectly splits or merges author records
will propagate to the database. Correction requires either an upstream fix or
a manual override (future Stage).

### Rate-limit posture

OpenAlex polite-pool requests are unlimited but subject to a soft rate limit of
~10 req/s for polite-pool callers. The ingestion pipeline uses `tenacity`
exponential backoff (2 s min, 60 s max, 5 retries) for 429 and 5xx responses.
For a full ingest of all 36 whitelisted journals this typically takes 30–120
minutes depending on journal sizes.

### Language mix

Papers are stored in their original language. OpenAlex provides a `language`
field but it is not always populated for older papers. No translation is
attempted in v1.

### ISSN missing / unverified

Eight whitelist journals have `manual_review_flag = TRUE` due to unverified
ISSNs (see `docs/journal-curation.md`). These journals require manual
`source_match_audit` review before their `openalex_source_id` is set.

---

## Recovery procedures

### Re-run after partial failure

Every command creates an `ingestion_runs` row. Check status:

```bash
thrn status --last 10
```

A partial run can be safely retried — all upserts are idempotent. To re-run
for a specific journal:

```bash
thrn ingest-works --journal-id 5 --since 2020-01-01
```

### Wipe and rerun

To wipe all ingested paper/author data and start fresh (keeps journals table):

```sql
TRUNCATE paper_authors, papers, authors RESTART IDENTITY CASCADE;
DELETE FROM ingestion_runs WHERE command IN ('ingest-works', 'refresh-recent');
```

Then re-run:

```bash
thrn ingest-works
```

### Re-enrich journals

To force re-matching of all journals (including already-enriched ones):

```bash
thrn enrich-journals --all --min-confidence 0.85
```

### Inspect raw payloads

Raw API responses are stored as gzipped JSON in `data/raw/<run_id>/`. Inspect:

```bash
gunzip -c data/raw/<run_id>/works/<journal>/<page>.json.gz | python -m json.tool | head -100
```

### Rebuild Typesense from scratch

Typesense is a derived index. If it becomes inconsistent:

```bash
thrn reindex-search --collection all --full
```

This drops and recreates each collection, then streams from PostgreSQL.
