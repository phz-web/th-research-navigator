# Deployment

This document covers how to run the Tourism & Hospitality Research Navigator
in three environments:

1. **Local development** (the default and most-tested path)
2. **A single small VM** (simplest production)
3. **Managed cloud services** (Neon + Typesense Cloud + Vercel)

Pick whichever matches the operational appetite. None of this changes what
the application does — the stack is identical in every environment.

---

## 1 · Local development

Everything runs on your laptop. Two service containers, one Python pipeline,
one Next.js dev server.

### Prerequisites

- Docker + Docker Compose (for PostgreSQL 16 and Typesense 0.25)
- Python 3.11+ (for ingestion and search reindex)
- Node.js 20+ and npm (or pnpm) for the web app
- `OPENALEX_CONTACT_EMAIL` — a real address for the OpenAlex polite pool

### First-time setup

```bash
# 1. Clone and configure
git clone <repo-url> th-research-navigator
cd th-research-navigator
cp .env.example .env
# Edit .env: at minimum set OPENALEX_CONTACT_EMAIL. Change Typesense API keys.

# 2. Start infrastructure
docker compose -f infra/docker-compose.yml up -d
./scripts/health.sh                          # verifies PG + Typesense are up

# 3. Apply the database schema (first-time + after pulls)
./scripts/reset-db.sh                        # idempotent; --destroy for a full reset

# 4. Install Python deps for ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r ingestion/requirements.txt

# 5. Run the ingestion pipeline
export PYTHONPATH=ingestion/src:ingestion/cli
python -m thrn bootstrap-journals data/seed/journal_whitelist.csv
python -m thrn enrich-journals                  # fetches OpenAlex source IDs
python -m thrn ingest-works --since 2018-01-01  # may take a while
python -m thrn reindex-search --collection all --full

# 6. Install and start the web app
cd web
npm install
npm run dev                                    # http://localhost:3000
```

### Daily development

```bash
# Bring services up
docker compose -f infra/docker-compose.yml up -d

# In one shell — the Next.js dev server
cd web && npm run dev

# In another — occasional partial refresh + reindex
export PYTHONPATH=ingestion/src:ingestion/cli
python -m thrn refresh-recent --days 14
python -m thrn reindex-search --collection papers   # partial-update mode
```

### Health checks

```bash
./scripts/health.sh                # PG + Typesense
python -m thrn status              # row counts, last ingest run, schema version
curl -sf http://localhost:3000/api/journals | jq '. | length'
```

### Environment variables

See `.env.example` for the authoritative list. The critical ones:

| Variable                       | Purpose                                       | Default                         |
|--------------------------------|-----------------------------------------------|---------------------------------|
| `OPENALEX_CONTACT_EMAIL`       | Polite-pool identity; **set a real address**  | —                               |
| `DATABASE_URL`                 | Used by ingestion and web                     | `postgresql://thrn:…@localhost` |
| `TYPESENSE_HOST/PORT/PROTOCOL` | Typesense endpoint                            | `localhost` / `8108` / `http`   |
| `TYPESENSE_ADMIN_API_KEY`      | Admin key for indexing; **rotate in prod**    | `change-me-locally`             |
| `WEB_APP_BASE_URL`             | Absolute URL used in server components        | `http://localhost:3000`         |
| `FEATURE_AI_SYNTHESIS_ENABLED` | Leave `false` in v1 (see docs/future-ai.md)   | `false`                         |
| `LOG_LEVEL`                    | `info` / `debug` / `warning`                  | `info`                          |

---

## 2 · Single small VM (simple production)

A single 2 vCPU / 4 GB VM with Docker installed is more than enough for a
v1 corpus. Suitable providers: Hetzner CX22, DigitalOcean basic droplet,
Linode Nanode 2 GB, AWS Lightsail 2 GB.

### Recommended layout

- Docker Compose stack on the VM: `postgres`, `typesense`, and a
  reverse-proxy (Caddy or nginx + Let's Encrypt).
- The Next.js web app either baked into a small container or deployed
  separately (Vercel is simpler; see §3).
- Ingestion runs on a cron (systemd timer or plain `crontab -e`).

### Steps

```bash
# On the VM
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker "$USER" && newgrp docker

git clone <repo-url> /opt/thrn && cd /opt/thrn
cp .env.example .env
# Edit .env: set strong TYPESENSE_ADMIN_API_KEY, strong POSTGRES_PASSWORD,
# real OPENALEX_CONTACT_EMAIL, WEB_APP_BASE_URL=https://your-domain.

docker compose -f infra/docker-compose.yml up -d
./scripts/reset-db.sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r ingestion/requirements.txt
export PYTHONPATH=ingestion/src:ingestion/cli
python -m thrn bootstrap-journals data/seed/journal_whitelist.csv
python -m thrn enrich-journals
python -m thrn ingest-works --since 2018-01-01
python -m thrn reindex-search --collection all --full

# Next.js — if hosting it on the same VM:
cd web && npm ci && npm run build && npm run start -- -p 3000
```

Expose only 443 publicly; keep 5432 and 8108 firewalled. Terminate TLS at
Caddy / nginx; proxy to `http://127.0.0.1:3000`.

### Daily cron (ingestion refresh)

```cron
# /etc/cron.d/thrn-refresh — daily 03:15 server time
15 3 * * *  root  cd /opt/thrn && source .venv/bin/activate && \
  PYTHONPATH=ingestion/src:ingestion/cli \
  python -m thrn refresh-recent --days 14 >> /var/log/thrn-refresh.log 2>&1 && \
  python -m thrn reindex-search --collection papers >> /var/log/thrn-refresh.log 2>&1
```

### Backups

- **PostgreSQL:** nightly `pg_dump` of the `thrn` database to object storage
  (S3, Backblaze B2). Retain ≥ 14 days.
- **Typesense:** rebuildable from PostgreSQL via
  `python -m thrn reindex-search --collection all --full`. Back up the
  snapshot if you want faster recovery but it is not required.
- **Journal whitelist:** in Git; no separate backup needed.

A disaster-recovery drill is one command:

```bash
# Worst case: both service containers are dead, volumes gone
docker compose -f infra/docker-compose.yml up -d
./scripts/reset-db.sh --destroy
psql "$DATABASE_URL" < backups/thrn-YYYYMMDD.sql
python -m thrn reindex-search --collection all --full
```

---

## 3 · Managed services (Neon + Typesense Cloud + Vercel)

Best fit when you want zero VM maintenance and the corpus fits comfortably in
free / starter tiers.

| Layer          | Managed option                 | What changes                                          |
|----------------|--------------------------------|-------------------------------------------------------|
| PostgreSQL     | Neon, Supabase, AWS RDS        | Swap `DATABASE_URL`; ensure `citext`/extensions exist |
| Typesense      | Typesense Cloud                | Swap host/port/protocol/API keys                      |
| Web app        | Vercel (recommended), Netlify  | `web/` is a self-contained Next.js project            |
| Ingestion      | A small VM, GitHub Actions cron, or Fly.io machine | Same Python CLI, different trigger          |

### PostgreSQL (Neon example)

1. Create a project and a branch. Copy the pooled connection string.
2. Set `DATABASE_URL` on Vercel (and wherever ingestion runs) to that string.
3. Run the migrations manually:
   ```bash
   psql "$DATABASE_URL" -f infra/postgres/migrations/0001_init.sql
   ```
   (Or run `./scripts/reset-db.sh` with `DATABASE_URL` pointed at Neon.)

### Typesense Cloud

1. Create a cluster. Note `host`, `port`, `protocol` (always `https`), and
   two API keys — an admin key for ingestion and a search-only key.
2. Set these env vars wherever ingestion runs and on Vercel:
   - `TYPESENSE_HOST=<clusterid>.a1.typesense.net`
   - `TYPESENSE_PORT=443`
   - `TYPESENSE_PROTOCOL=https`
   - `TYPESENSE_ADMIN_API_KEY=<admin>`
3. Create the collections once from your workstation:
   ```bash
   python search/scripts/create_collections.py
   ```

### Vercel (web app)

1. Import the repository. Set the **Root Directory** to `web/`.
2. Framework preset: Next.js. Build command: `npm run build`. Output: (auto).
3. Environment variables to set in Vercel (Production + Preview):
   - `DATABASE_URL`
   - `TYPESENSE_HOST`, `TYPESENSE_PORT`, `TYPESENSE_PROTOCOL`,
     `TYPESENSE_ADMIN_API_KEY`
   - `WEB_APP_BASE_URL` — your Vercel deployment URL
   - `FEATURE_AI_SYNTHESIS_ENABLED=false`
4. Deploy. First boot will connect to Neon + Typesense Cloud and render.

> **On API routes:** route handlers under `web/app/api/*` run as Vercel
> serverless functions. Cold starts hit PostgreSQL — Neon's pooled connection
> string is important to keep TCP churn low.

### Ingestion

Option A — small always-on VM: identical to §2 but only runs the cron; the
services are elsewhere.

Option B — GitHub Actions scheduled workflow: good for daily refreshes, not
ideal for the initial backfill (long-running, rate-limited). Use Option A
for the backfill, then cut over.

Option C — Fly.io machine with a scheduled task: simplest fully-managed
option. Use `fly machine run` with a cron.

Whichever you choose, ingestion needs:

- `DATABASE_URL` pointed at Neon
- `TYPESENSE_*` pointed at Typesense Cloud
- `OPENALEX_CONTACT_EMAIL` set to a real inbox
- Network access to `api.openalex.org` (always open on the public internet)

---

## Ingestion schedule (any environment)

| Command                                      | Cadence         | Runtime (rough) |
|----------------------------------------------|-----------------|-----------------|
| `bootstrap-journals` (one-time)              | Once, at setup  | seconds         |
| `enrich-journals`                            | Quarterly       | minutes         |
| `ingest-works --since <earliest-year>`       | Initial backfill| hours           |
| `refresh-recent --days 14`                   | Daily           | minutes         |
| `reindex-search --collection papers` (partial)| Daily, after refresh | seconds–minutes |
| `reindex-search --collection all --full`     | After schema changes only | ~order of corpus size |

See [docs/ingestion.md](./ingestion.md) for parameter details and retry
semantics.

---

## Deployment checklist

Use before and after any environment change.

### Before deploy

- [ ] `.env` complete and secrets rotated from the `change-me-locally` defaults
- [ ] `OPENALEX_CONTACT_EMAIL` is a real, monitored inbox
- [ ] `FEATURE_AI_SYNTHESIS_ENABLED` is `false` (v1 invariant)
- [ ] Database migration applied cleanly (`./scripts/reset-db.sh` is idempotent)
- [ ] `python -m thrn status` reports non-zero rows in `journals` and `papers`
- [ ] Typesense collections exist (`papers`, `authors`, `journals`)
- [ ] `npm run build` in `web/` succeeds with zero errors
- [ ] `./scripts/health.sh` is green

### After deploy

- [ ] `/` home page loads and renders the journal whitelist summary
- [ ] `/papers?q=smart%20tourism` returns results
- [ ] `/authors` and `/journals` list pages render
- [ ] `/about` shows the correct number of whitelisted journals
- [ ] `/about` contains the note "AI synthesis is not available in v1."
- [ ] No server errors in logs for 10 minutes post-deploy
- [ ] Scheduled refresh job fired at least once and exited 0

If any check fails, consult [docs/troubleshooting.md](./troubleshooting.md).

---

## Related docs

- [docs/architecture.md](./architecture.md) — overall data flow
- [docs/ingestion.md](./ingestion.md) — pipeline parameters
- [docs/search-index.md](./search-index.md) — Typesense schemas and ranking
- [docs/troubleshooting.md](./troubleshooting.md) — common failure modes
