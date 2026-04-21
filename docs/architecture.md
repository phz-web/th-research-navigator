# Architecture

## Guiding principles

1. **Clean separation of concerns.** Ingestion, relational storage, search indexing, and presentation are independently deployable and independently testable.
2. **PostgreSQL is the source of truth.** Typesense is a derived index that can be dropped and rebuilt at any time.
3. **OpenAlex is the only upstream metadata source in v1.** No parallel scraping, no Crossref joins, no Scopus. One source, fully owned.
4. **Idempotency everywhere.** Every ingestion and indexing command must be safely re-runnable.
5. **Auditability over cleverness.** Raw upstream payloads are preserved in `raw_json` columns and in `data/raw/` for forensic replay.
6. **AI is deferred.** No model calls in v1. The retrieval foundation must be credible before any generation layer is built on top.

---

## System context (data flow)

```
                   ┌─────────────────────────────────────────┐
                   │                OpenAlex                 │
                   │   (works + sources + authorships API)   │
                   └─────────────────┬───────────────────────┘
                                     │  HTTPS (polite pool, contact email)
                                     │  pagination + backoff + retries
                                     ▼
┌───────────────────────────┐   ┌─────────────────────────────────────────┐
│  data/seed/               │   │           ingestion/ (Python)           │
│  journal_whitelist.csv    │──▶│  • match_sources (whitelist → source_id)│
│  (curated, tier-flagged)  │   │  • ingest_works (paginated harvest)     │
└───────────────────────────┘   │  • upsert to PostgreSQL (idempotent)    │
                                │  • write ingestion_runs + audit rows    │
                                └─────────────────┬───────────────────────┘
                                                  │
                                                  ▼
                                ┌─────────────────────────────────────────┐
                                │           PostgreSQL (SoT)              │
                                │  journals, papers, authors,             │
                                │  paper_authors, ingestion_runs,         │
                                │  source_match_audit  (+ raw_json)       │
                                └─────────────────┬───────────────────────┘
                                                  │  reindex / partial update
                                                  ▼
                                ┌─────────────────────────────────────────┐
                                │          search/ (Python scripts)       │
                                │  SQL → Typesense documents              │
                                └─────────────────┬───────────────────────┘
                                                  │
                                                  ▼
                                ┌─────────────────────────────────────────┐
                                │             Typesense                   │
                                │  collections: papers, authors, journals │
                                │  field weights + facets + sorts         │
                                └─────────────────┬───────────────────────┘
                                                  │  typed client calls
                                                  ▼
                                ┌─────────────────────────────────────────┐
                                │       web/ (Next.js App Router, TS)     │
                                │  route handlers → Typesense + Postgres  │
                                │  pages: search, paper, author, journal  │
                                └─────────────────────────────────────────┘
```

---

## Component responsibilities

### `ingestion/` (Python)
- Read the curated whitelist from `data/seed/journal_whitelist.csv`.
- Resolve each whitelist row to an OpenAlex `source` (venue) using ISSN-first matching, falling back to normalized-name matching with an explicit confidence score.
- Harvest `works` for each matched source, paginated via OpenAlex cursors.
- Parse authorships into normalized `authors` and `paper_authors` rows.
- Upsert into PostgreSQL using natural keys (`openalex_id`, `doi`).
- Write an `ingestion_runs` row for every invocation with counts, timings, and error summary.
- Preserve raw upstream JSON in both `raw_json` columns and dated files in `data/raw/`.

**Why Python:** best-in-class for data cleaning, retry orchestration (tenacity), and pandas-based manual review of ambiguous matches.

### `search/`
- Define Typesense collection schemas as code (`search/schemas/*.json`).
- Provide a reindex script that streams from PostgreSQL and upserts documents into Typesense.
- Provide a partial-update script for incremental refreshes driven by `papers.updated_at`.

Typesense is treated as disposable: dropping a collection and rebuilding from PostgreSQL is the supported recovery path.

### `web/` (Next.js App Router)
- Server components query Typesense (via the official JS client) and PostgreSQL (via a thin query layer).
- Route handlers in `web/app/api/` expose typed JSON contracts (see Stage 6).
- No client-side API keys. The Typesense admin key lives server-side; the browser never talks to Typesense directly in v1.
- Pages are search-first and desktop-first; mobile is responsive but secondary.

### `infra/`
- `docker-compose.yml` for local PostgreSQL and Typesense.
- SQL migrations applied by a simple migrator (choice deferred to Stage 3; candidates: raw SQL + `psql`, Alembic, or node-pg-migrate).

### `scripts/`
- Developer ergonomics: `reset-db.sh`, `reindex.sh`, `health.sh`, `run-ingest.sh`.

---

## Why this stack

| Decision                        | Reason                                                                                              |
|--------------------------------|-----------------------------------------------------------------------------------------------------|
| OpenAlex as sole upstream       | Open, structured, covers tourism/hospitality journals adequately, well-documented filter API.       |
| Curated whitelist (not discipline filter) | Field precision matters more than recall. SCImago category + human curation is defensible.  |
| PostgreSQL as SoT               | Rich relational modeling, `jsonb` for raw payload audit, mature tooling, boring and reliable.       |
| Typesense as search             | Fast, self-hostable, explicit field weighting + facets + exact-match controls, great DX.            |
| Next.js App Router              | Server components simplify secret handling and data fetching; file-based routing fits the page set. |
| TypeScript end-to-end on the web | Shared types between route handlers and pages reduce contract drift.                               |
| Python ingestion                | Data-cleaning ergonomics, tenacity for retries, easier manual review of ambiguous matches.          |
| docker-compose for infra        | One-command local bring-up, mirrors production services without runtime lock-in.                    |

---

## Boundaries and invariants

- **Typesense never writes to PostgreSQL.** Data only flows PG → Typesense.
- **The frontend never writes to PostgreSQL or Typesense.** v1 is read-only.
- **The frontend never calls OpenAlex.** All upstream calls go through `ingestion/`.
- **`raw_json` is append-on-upsert.** Older payloads may be overwritten on refresh; truly historical audit trails live in `data/raw/` files named by run ID.
- **Whitelist is the only corpus boundary.** A paper is in-corpus if and only if its journal is in the whitelist with `active_flag = true`. No paper-level inclusion overrides in v1.

---

## Deployment posture (v1 target)

- Local-first. `docker compose up` + `pnpm dev` is the primary experience.
- Cloud deployment deferred to Stage 10. Plausible targets: managed PostgreSQL (Neon/Supabase/RDS), Typesense Cloud or self-hosted on a small VM, Vercel for the Next.js app. No decision made yet.

---

## Risks and mitigations

| Risk                                                   | Mitigation                                                                      |
|--------------------------------------------------------|---------------------------------------------------------------------------------|
| OpenAlex coverage gaps in tourism/hospitality journals | Document gaps in `docs/search-quality.md`; accept as a known limitation in v1.  |
| Ambiguous journal-to-source matches                    | `source_match_audit` table + manual review flag; no silent guessing.            |
| Author name disambiguation                             | Trust OpenAlex `author_id` as the key; do not attempt custom disambiguation.    |
| Abstract quality and language mix                      | Store as-is; document language distribution in Stage 8; no translation in v1.   |
| Rate limits / transient errors                         | Tenacity-based exponential backoff; cursor-resumable harvest.                   |
| Scope creep toward AI features                         | Feature flag OFF, no model dependency in `package.json` or `requirements.txt`.  |
