# Build Plan

A 10-stage workflow with explicit checkpoints. **Do not advance a stage until its acceptance criteria are satisfied.** Each stage has a go/no-go checkpoint in plain language and a short list of artifacts that must exist.

---

## Stage 1 — Product framing and architecture  ← **current**

**Goal.** Freeze scope, stack, and repo layout before any code is written.

**Artifacts**
- `README.md` (skeleton)
- `docs/product-definition.md`
- `docs/architecture.md`
- `docs/build-plan.md` (this file)
- `docs/file-tree.md`
- `.env.example`
- `.gitignore`

**Checkpoint**
- Positioning is explicitly tourism/hospitality, not generic.
- Stack is named with one canonical option per layer.
- Non-goals are listed.
- Repo structure is concrete enough for a second engineer to start building without reinterpretation.

**No application code yet.** Stage 1 is documentation and directory scaffolding only.

---

## Stage 2 — Journal whitelist

**Goal.** Produce a curated, field-credible tourism and hospitality journal whitelist.

**Deliverables**
- `data/seed/journal_whitelist.csv` with fields:
  `journal_name, normalized_name, issn_print, issn_online, scimago_category, scope_bucket, tier_flag, inclusion_reason, manual_review_flag, notes`
- `docs/journal-curation.md` describing inclusion/exclusion rules and listing borderline cases.

**Checkpoint.** A tourism/hospitality scholar reviewing the list agrees it represents the field: core specialist journals are present, adjacent-management noise is absent, ambiguous titles are flagged rather than silently included.

**Acceptance criteria**
- At least one explicit distinction between `core` and `extended` tiers.
- Scope buckets are consistent (`tourism`, `hospitality`, `events`, `leisure`, `destination`, `mixed`).
- Every row has either an ISSN or an explicit reason for missing ISSN.
- Inclusion/exclusion rules are written as prose, not implied.

---

## Stage 3 — Schema and local infrastructure

**Goal.** One-command local startup with a migrated PostgreSQL schema.

**Deliverables**
- `infra/docker-compose.yml` (PostgreSQL 16 + Typesense latest)
- Migration files for tables: `journals`, `papers`, `authors`, `paper_authors`, `ingestion_runs`, `source_match_audit`
- `docs/data-model.md` with ER diagram (Mermaid) and field-by-field notes

**Checkpoint.** `docker compose up` starts cleanly; migrations apply from empty; tables exist with expected indexes and constraints.

**Acceptance criteria**
- Unique constraints on `papers.openalex_id`, `papers.doi` (nullable-unique), `journals.openalex_source_id`, `authors.openalex_author_id`.
- `raw_json jsonb` columns on `papers`, `journals`, `authors`.
- Timestamps on all primary entities.
- Reset path documented (`scripts/reset-db.sh`).

---

## Stage 4 — OpenAlex ingestion

**Goal.** Idempotent, resumable ingestion of sources and works for the whitelist.

**Deliverables**
- `ingestion/` Python package with CLI commands:
  `bootstrap-journals`, `enrich-journals`, `ingest-works`, `refresh-recent`, `reindex-search` (stub for Stage 5)
- `docs/ingestion.md` with assumptions, matching rules, known metadata gaps

**Checkpoint.** Running `ingest-works` twice produces the same row counts. Failed runs are logged with enough context to resume. Ambiguous source matches are flagged, not guessed.

**Acceptance criteria**
- ISSN-first, name-fallback matching with confidence scoring.
- Cursor-based pagination with exponential backoff.
- `OPENALEX_CONTACT_EMAIL` sent on every request (polite pool).
- `ingestion_runs` row per invocation; counts, duration, error summary.
- Raw payloads preserved in `data/raw/<run_id>/`.

---

## Stage 5 — Typesense indexing

**Goal.** A search index sourced from PostgreSQL that returns stable, scholarly results.

**Deliverables**
- `search/schemas/papers.json`, `authors.json`, `journals.json`
- `search/scripts/reindex_papers.py`, etc.
- `docs/search-index.md` with ranking settings and rationale

**Checkpoint.** Searching a known paper title returns it in the top 3. Facets return stable counts. Reindexing is safe to re-run.

**Acceptance criteria**
- Title weighted higher than abstract.
- Author names and journal names searchable from the paper collection.
- Facets: `publication_year`, `journal_name`, `scope_bucket`, `is_oa`.
- Sorts: `_text_match:desc`, `publication_year:desc`, `cited_by_count:desc`.

---

## Stage 6 — API / query layer

**Goal.** Typed, documented endpoints that cleanly feed the frontend.

**Deliverables**
- Route handlers under `web/app/api/` for: paper search, paper detail, author search, author detail, journal search, journal detail, health.
- `docs/api-contracts.md` with request/response schemas.

**Checkpoint.** A second frontend developer could build the UI from `docs/api-contracts.md` without reading server code.

**Acceptance criteria**
- Query-parameter validation with typed errors.
- Pagination and filter contracts documented.
- Empty states return 200 with empty arrays, not 404.
- No raw Typesense responses leaked; all responses are mapped to stable shapes.

---

## Stage 7 — Next.js frontend

**Goal.** An end-to-end navigable search app with real data.

**Deliverables**
- Pages: `/` (home+search), `/papers` (results), `/papers/[id]`, `/authors/[id]`, `/journals/[id]`, `/about`
- Shared components: search bar, result card, filters, facet chips, pagination, empty/error/loading states
- Light/dark mode

**Checkpoint.** A user can search, open a paper, navigate to its author and journal, and return — all with real data.

**Acceptance criteria**
- Semantic HTML, keyboard navigable, accessible labels.
- Desktop-first layout, mobile responsive.
- No fake placeholder data once real data is connected.
- No AI widgets present.

---

## Stage 8 — Search quality tuning

**Goal.** A written retrieval evaluation report with targeted fixes applied.

**Deliverables**
- `docs/search-quality.md` with 20-query evaluation, observed issues, fixes, and known limitations.
- Tuned `query_by`, `query_by_weights`, `sort_by`, and optional synonyms.

**Checkpoint.** At least 15 of 20 realistic tourism/hospitality queries produce clearly relevant top-10 results.

**Acceptance criteria**
- Query set covers destination branding, hospitality marketing, hotel tech, service robots, sustainability, tourist behavior, social media, sharing economy, smart tourism, events.
- Each tuning change is justified in the doc.
- Synonyms (if added) are listed with rationale.

---

## Stage 9 — Deferred AI scaffold

**Goal.** Clear, honest deferral of AI synthesis.

**Deliverables**
- Feature flag (env var + server-side check), default OFF.
- `docs/future-ai.md` describing retrieval-grounded design, corpus-only citation policy, top-k retrieval.
- Optional disabled UI placeholder explicitly labeled as future functionality.

**Checkpoint.** No model API is called. No generation endpoint exists. The codebase is honest about the absence of AI in v1.

**Acceptance criteria**
- No LLM SDKs in dependencies.
- Feature flag is read but has no active code path in v1.
- Documentation states the dependency on Stage 8 retrieval quality.

---

## Stage 10 — Deployment and handoff

**Goal.** A second engineer can run and deploy the project from the README.

**Deliverables**
- Finalized `README.md` with prerequisites, env vars, local startup, migration, ingestion, indexing, frontend run commands.
- `docs/deployment.md` and `docs/troubleshooting.md`.
- Handoff checklist.

**Checkpoint.** Fresh-clone setup completes in under 60 minutes on a clean machine.

**Acceptance criteria**
- Every script used during development is documented.
- Troubleshooting covers PostgreSQL, Typesense, and OpenAlex ingestion issues.
- Environment variables are exhaustively listed in `.env.example`.

---

## Between-stage governance

Use these meta-prompts between stages:

- **Review.** List what is complete, missing, risky, and should be fixed before advancing.
- **Refactor.** Improve naming, file organization, duplicate logic, config hygiene, and docs without adding features.
- **Validate.** Confirm the stage can run, rerun safely, has documented outputs, and explicit assumptions.

Do not skip governance after stages 2, 4, 5, and 8 — these are the stages where silent mistakes compound.
