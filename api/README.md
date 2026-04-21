# API Notes

> **API contracts are defined in Stage 6 under `web/app/api`; this folder is notes-only.**

The route handlers for the Tourism & Hospitality Research Navigator API live in
`web/app/api/` as Next.js App Router route files. This `api/` directory at the
repo root is documentation-only — it contains no runtime code.

For contract definitions, request/response schemas, and usage examples, see:
- `docs/api-contracts.md` (delivered in Stage 6)

For the data sources that API handlers query, see:
- `docs/data-model.md` — PostgreSQL schema
- `docs/search-index.md` — Typesense collection schemas and ranking

## Planned endpoints (Stage 6)

| Method | Path                    | Description                                    |
|--------|-------------------------|------------------------------------------------|
| GET    | `/api/papers`           | Search papers (query + facet filters)          |
| GET    | `/api/papers/[id]`      | Paper detail (metadata + authors + journal)    |
| GET    | `/api/authors`          | Search authors                                 |
| GET    | `/api/authors/[id]`     | Author detail (profile + paper list)           |
| GET    | `/api/journals`         | Browse/search journals                         |
| GET    | `/api/journals/[id]`    | Journal detail (info + papers)                 |
| GET    | `/api/health`           | Health check (DB + Typesense connectivity)     |
