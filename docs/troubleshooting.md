# Troubleshooting runbook

A practical guide to the failure modes you will actually hit while running
the Tourism & Hospitality Research Navigator. Organised by layer:
PostgreSQL, Typesense, OpenAlex ingestion, the web app, and end-to-end
behaviour.

Keep this document blunt and honest. If you hit a new failure mode,
document it here rather than solving it silently.

---

## First moves (always)

Before diving into any layer, gather the three pieces of information that
disambiguate 80 % of issues:

```bash
# 1. Which services are actually running?
docker compose -f infra/docker-compose.yml ps

# 2. Are they responding?
./scripts/health.sh

# 3. What does the ingestion pipeline think the world looks like?
export PYTHONPATH=ingestion/src:ingestion/cli
python -m thrn status
```

Capture the output before changing anything. Most "it's broken" reports turn
out to be "the containers are up but the reindex never ran" or "the web app
is pointed at a different Typesense than ingestion wrote to".

---

## PostgreSQL

### Symptom: `psql: error: connection refused` / web app 500s with `ECONNREFUSED`

**Likely causes**

1. Container is not running.
2. The host/port in `DATABASE_URL` does not match `infra/docker-compose.yml`.
3. Host firewall or Docker network issue.

**Checks**

```bash
docker compose -f infra/docker-compose.yml ps postgres
docker logs thrn-postgres --tail 50
psql "$DATABASE_URL" -c "SELECT 1;"
```

**Fix**

```bash
docker compose -f infra/docker-compose.yml up -d postgres
# If the container is up but refusing connections, the data volume may be
# corrupted (rare, usually after a forced shutdown). Recover:
docker compose -f infra/docker-compose.yml down
# Back up the volume directory first if the data matters:
cp -a infra/postgres/data infra/postgres/data.bak
docker compose -f infra/docker-compose.yml up -d postgres
```

### Symptom: `relation "papers" does not exist`

Migration never ran in this database.

```bash
./scripts/reset-db.sh              # idempotent
# Or manually:
psql "$DATABASE_URL" -f infra/postgres/migrations/0001_init.sql
```

### Symptom: `./scripts/reset-db.sh --destroy` won't drop the DB

A client (ingestion, `psql`, the web app) still holds a connection.

```bash
# Find them
psql "$DATABASE_URL" -c \
  "SELECT pid, application_name, state FROM pg_stat_activity WHERE datname='thrn';"

# Terminate and retry
psql "$DATABASE_URL" -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity \
   WHERE datname='thrn' AND pid <> pg_backend_pid();"
./scripts/reset-db.sh --destroy
```

### Symptom: `CHECK constraint violation` loading the whitelist

One of the 36 whitelist rows has a value not permitted by a CHECK in
`0001_init.sql` (e.g. a `tier_flag` outside `{core, extended, flagged}` or
a `scope_bucket` outside the allowed vocabulary).

```bash
# Identify the offending row without loading:
python -c "
import csv
allowed_tiers = {'core','extended','flagged'}
with open('data/seed/journal_whitelist.csv') as f:
    for i, row in enumerate(csv.DictReader(f), start=2):
        if row['tier_flag'] not in allowed_tiers:
            print(i, row['journal_name'], row['tier_flag'])
"
```

Fix the CSV or extend the CHECK deliberately — don't relax the constraint to
paper over a bad value.

### Symptom: `duplicate key value violates unique constraint` during ingestion

Ingestion is designed to be idempotent, so this means the upsert path is
wrong or the unique key changed. Check:

```bash
# Which OpenAlex id is already present?
psql "$DATABASE_URL" -c \
  "SELECT openalex_id, count(*) FROM papers GROUP BY 1 HAVING count(*) > 1 LIMIT 5;"
```

If duplicates exist, fix them with a deliberate `DELETE` query, then re-run
the ingestion command. Do not relax unique constraints.

### Symptom: slow queries on large corpora

Check the composite indexes defined in `0001_init.sql` are present:

```bash
psql "$DATABASE_URL" -c "\d papers"
```

If an index is missing (shouldn't happen with a clean migration but can
happen on restored backups), reapply the migration; CREATE INDEX IF NOT
EXISTS is idempotent.

---

## Typesense

### Symptom: `Connection refused` or `Typesense client cannot connect`

**Checks**

```bash
docker compose -f infra/docker-compose.yml ps typesense
curl -sf http://localhost:8108/health
docker logs thrn-typesense --tail 50
```

**Fix**

```bash
docker compose -f infra/docker-compose.yml up -d typesense
```

If the container keeps crashing, check available disk space under
`infra/typesense/data` — Typesense refuses to boot on full disks.

### Symptom: `404 — collection not found`

The collection was never created, or it was recreated and the app is
pointed at a stale name.

```bash
curl -s "http://localhost:8108/collections" \
  -H "X-TYPESENSE-API-KEY: $TYPESENSE_ADMIN_API_KEY" | jq '.[].name'

# Create collections from schemas if missing:
python search/scripts/create_collections.py
```

### Symptom: results are stale compared to PostgreSQL

The index is behind the source of truth. Two fixes depending on how far
behind:

```bash
export PYTHONPATH=ingestion/src:ingestion/cli

# Partial update — only rows changed since last indexed_at
python -m thrn reindex-search --collection papers

# Full rebuild — when partial-update state is lost or the schema changed
python -m thrn reindex-search --collection all --full
```

To force a full catch-up, delete the partial-update state file:

```bash
rm -f data/index_state.json
python -m thrn reindex-search --collection all
```

### Symptom: a search returns no hits but the paper is clearly in the DB

Usually one of:

1. Collection is empty. Check `GET /collections/papers` `num_documents`.
2. The filter string is excluding everything. Strip filters and retry.
3. Synonyms over-matched or under-matched. See
   [docs/search-quality.md](./search-quality.md) — install or remove with
   `search/evaluation/install_synonyms.py`.
4. The paper's `abstract`, `title`, or `authors_text` is NULL. Check the
   row in PostgreSQL and re-ingest.

Debug query (bypass app layer entirely):

```bash
curl -s "http://localhost:8108/collections/papers/documents/search" \
  -H "X-TYPESENSE-API-KEY: $TYPESENSE_ADMIN_API_KEY" \
  -G --data-urlencode "q=smart tourism" \
  --data-urlencode "query_by=title,abstract,authors_text,journal_name" | jq
```

### Symptom: `Authorization failed` / 401

The web app is using a different `TYPESENSE_ADMIN_API_KEY` from the one the
container booted with. Typesense only accepts keys set on the CLI flag at
startup — it does not read them from env at request time.

```bash
# Restart Typesense so it picks up the current .env value
docker compose -f infra/docker-compose.yml up -d --force-recreate typesense
```

### Symptom: Typesense container restarts in a loop

Usually a data-dir version mismatch after a minor version bump, or a full
disk. Check logs:

```bash
docker logs thrn-typesense --tail 100
df -h infra/typesense/data
```

If the data dir is incompatible (rare on 0.25.x), nuke it and reindex:

```bash
docker compose -f infra/docker-compose.yml down typesense
rm -rf infra/typesense/data
docker compose -f infra/docker-compose.yml up -d typesense
python -m thrn reindex-search --collection all --full
```

---

## OpenAlex ingestion

### Symptom: `HTTP 429 Too Many Requests`

Polite pool is happy to throttle clients without a valid contact email, and
bursty clients regardless.

**Fixes**

1. Confirm `OPENALEX_CONTACT_EMAIL` is set and is a real, monitored inbox.
2. The client already uses `tenacity` with exponential backoff; let it retry.
3. Lower parallelism if you added any (ingestion is single-threaded per
   command by default — don't parallelise without reading OpenAlex's polite
   pool guidance).

### Symptom: `HTTP 403` or `HTTP 401`

OpenAlex does not require API keys in v1, so this is almost always a bad
request shape — usually a malformed `filter=` clause after editing the
ingestion code. Inspect the URL printed in the log and validate against
the [OpenAlex API docs](https://docs.openalex.org/).

### Symptom: `HTTP 5xx` from OpenAlex

Their side. The retry logic will ride it out. If it persists > 1 hour,
check their [status page](https://status.openalex.org/) and simply try
again later — there is no fallback data source in v1 by design.

### Symptom: `ingest-works` exits with `--since` errors or rate-limit loops

The command is resumable. Re-running it is safe:

```bash
python -m thrn ingest-works --since 2018-01-01
```

Progress is tracked in the `ingestion_runs` table; `python -m thrn status`
shows the last successful cursor.

### Symptom: abstracts look garbled

OpenAlex serves abstracts as an inverted index which we reconstruct at
ingest time. Occasional token-order artefacts are expected and not
fixable from our side. If a specific paper's abstract is useless, it's
usually useless at OpenAlex too.

### Symptom: a paper is missing after ingestion

Work through the filter funnel:

1. Does OpenAlex have it? Check
   `https://api.openalex.org/works/doi:<doi>`.
2. Is its source (journal) in our whitelist and enriched with an OpenAlex
   source ID?
   ```sql
   SELECT * FROM journals WHERE display_name ILIKE '%Tourism Management%';
   ```
3. Is the paper's publication year inside the ingestion window (`--since`)?
4. Has the work type been filtered out (we index articles; editorials and
   retractions are skipped)?

If 1–4 all pass and the paper is still missing, run `refresh-recent` with
a wider window and reindex.

### Symptom: the CLI crashes on `enrich-journals`

Most commonly a journal name that OpenAlex doesn't recognise. Check the
row flagged `manual_review_flag=true` in `data/seed/journal_whitelist.csv`
and either add an ISSN or remove it. The enrich step is allowed to have
partial failures — it logs and continues — so a crash is unusual. Capture
the stack trace and check whether the CSV was edited in a way that broke
the header row.

---

## Web app (Next.js)

### Symptom: `npm install` fails

- Confirm Node.js ≥ 20. `node -v`.
- Delete `web/node_modules` and `web/.next`, then retry.

### Symptom: `npm run build` fails type-check

The committed code compiles cleanly against Next.js 14.2.x and TypeScript
5.6+. A new compile error is almost always from an edit on your branch.
Run:

```bash
cd web && npm run typecheck
```

and fix the named error. Do not turn off `strict` in `tsconfig.json`.

### Symptom: home page loads but `/papers?q=…` returns 500

Almost always:

1. `DATABASE_URL` is unset or wrong in the web app's env.
2. `TYPESENSE_*` env vars are wrong.
3. Typesense is up but the `papers` collection is empty.

```bash
./scripts/health.sh
python -m thrn status
```

### Symptom: `/about` renders but journal list is empty

The web app can't reach PostgreSQL. The page handles that gracefully (see
`getWhitelist`'s try/except) and shows "not yet available". Check
`DATABASE_URL` and run `./scripts/health.sh`.

### Symptom: Dark/light theme doesn't toggle

The app uses a cookie-based theme (not `next-themes`, despite the package
being in `dependencies`). If the toggle button appears broken, clear the
`thrn-theme` cookie and reload.

### Symptom: `/synthesis` or other AI routes return a 404

Expected. `FEATURE_AI_SYNTHESIS_ENABLED=false` in v1. See
[docs/future-ai.md](./future-ai.md).

---

## End-to-end behaviour

### Symptom: a paper is in PG but not in search results

1. `python -m thrn reindex-search --collection papers` (partial update).
2. If still missing, full rebuild: `--full`.
3. If still missing, the paper's journal may be marked inactive or its
   fields may be NULL. Inspect:
   ```sql
   SELECT p.openalex_id, p.title, j.active_flag, p.abstract IS NOT NULL AS has_abs
   FROM papers p JOIN journals j ON p.journal_id = j.id
   WHERE p.openalex_id = '<id>';
   ```

### Symptom: citation counts lag what you see on OpenAlex

Expected up to 24 hours. `refresh-recent` updates citation counts for works
published in the last N days; older citation counts require a broader
refresh. For a full citation refresh, re-run `ingest-works` with a wider
`--since` (it upserts idempotently).

### Symptom: the evaluation report shows regressions after a tuning change

See [docs/search-quality.md](./search-quality.md). Roll back the ranking
change, re-run the affected rung, and commit the diff along with a note
about *why* the change was reverted. Don't silently adopt regressions.

---

## Getting unstuck

If the problem is not in this runbook:

1. Reproduce with the smallest possible command (one query, one paper).
2. Capture logs from all three layers (PostgreSQL, Typesense, the web app
   or CLI).
3. Add a short section to this file describing the failure mode and the
   fix. Future you will thank present you.

---

## Related docs

- [docs/deployment.md](./deployment.md) — what a healthy setup looks like
- [docs/ingestion.md](./ingestion.md) — ingestion parameters and retry logic
- [docs/search-index.md](./search-index.md) — Typesense schemas and ranking
- [docs/search-quality.md](./search-quality.md) — retrieval evaluation
