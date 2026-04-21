# File Tree

Concrete repository layout with responsibilities. Files listed below are the **target** layout across all stages; folders that are empty in Stage 1 are marked with `(empty in Stage 1)`.

```
th-research-navigator/
├── README.md
├── .env.example
├── .gitignore
│
├── docs/
│   ├── product-definition.md        # Stage 1
│   ├── architecture.md              # Stage 1
│   ├── build-plan.md                # Stage 1
│   ├── file-tree.md                 # Stage 1 (this file)
│   ├── journal-curation.md          # Stage 2
│   ├── data-model.md                # Stage 3
│   ├── ingestion.md                 # Stage 4
│   ├── search-index.md              # Stage 5
│   ├── api-contracts.md             # Stage 6
│   ├── search-quality.md            # Stage 8
│   ├── future-ai.md                 # Stage 9
│   ├── deployment.md                # Stage 10
│   └── troubleshooting.md           # Stage 10
│
├── data/
│   ├── seed/                        # Curated inputs, committed to git
│   │   └── journal_whitelist.csv    # Stage 2
│   └── raw/                         # Per-run OpenAlex payloads, gitignored
│       └── <run_id>/                # Stage 4+
│
├── infra/                           # Local + deploy infrastructure
│   ├── docker-compose.yml           # Stage 3
│   ├── postgres/
│   │   └── init.sql                 # Stage 3 (migrations or bootstrap)
│   └── typesense/
│       └── README.md                # Stage 3 (config notes)
│
├── ingestion/                       # Python package
│   ├── pyproject.toml               # Stage 4
│   ├── requirements.txt             # Stage 4
│   ├── src/                         # Library code
│   │   ├── __init__.py
│   │   ├── config.py                # env loading, OpenAlex contact email
│   │   ├── openalex_client.py       # polite-pool HTTP client with retries
│   │   ├── whitelist.py             # load + normalize seed CSV
│   │   ├── match_sources.py         # ISSN-first, name-fallback matcher
│   │   ├── ingest_works.py          # paginated harvest + upsert
│   │   ├── db.py                    # psycopg connection pool + helpers
│   │   ├── models.py                # dataclasses / typed rows
│   │   └── runs.py                  # ingestion_runs logging
│   ├── cli/                         # Click/argparse entry points
│   │   ├── __init__.py
│   │   ├── bootstrap_journals.py
│   │   ├── enrich_journals.py
│   │   ├── ingest_works.py
│   │   ├── refresh_recent.py
│   │   └── reindex_search.py        # delegates to search/ scripts
│   └── tests/                       # Pytest
│       └── (unit tests)
│
├── search/                          # Typesense layer
│   ├── schemas/
│   │   ├── papers.json              # Stage 5
│   │   ├── authors.json             # Stage 5
│   │   └── journals.json            # Stage 5
│   └── scripts/
│       ├── create_collections.py    # Stage 5
│       ├── reindex_papers.py        # Stage 5
│       ├── reindex_authors.py       # Stage 5
│       ├── reindex_journals.py      # Stage 5
│       └── partial_update.py        # Stage 5
│
├── api/                             # (notes only; runtime code lives in web/app/api)
│   └── README.md                    # Stage 6: contract conventions
│
├── web/                             # Next.js App Router + TypeScript
│   ├── package.json                 # Stage 7
│   ├── tsconfig.json                # Stage 7
│   ├── next.config.mjs              # Stage 7
│   ├── tailwind.config.ts           # Stage 7 (or equivalent)
│   ├── app/
│   │   ├── layout.tsx               # root layout, theme, nav
│   │   ├── page.tsx                 # home + search
│   │   ├── papers/
│   │   │   ├── page.tsx             # results
│   │   │   └── [id]/page.tsx        # paper detail
│   │   ├── authors/
│   │   │   └── [id]/page.tsx
│   │   ├── journals/
│   │   │   └── [id]/page.tsx
│   │   ├── about/page.tsx
│   │   └── api/                     # route handlers
│   │       ├── papers/route.ts
│   │       ├── papers/[id]/route.ts
│   │       ├── authors/route.ts
│   │       ├── authors/[id]/route.ts
│   │       ├── journals/route.ts
│   │       ├── journals/[id]/route.ts
│   │       └── health/route.ts
│   ├── components/                  # shared UI
│   │   ├── SearchBar.tsx
│   │   ├── ResultCard.tsx
│   │   ├── Filters.tsx
│   │   ├── FacetChips.tsx
│   │   ├── Pagination.tsx
│   │   └── (empty/error/loading states)
│   ├── lib/                         # client wrappers + types
│   │   ├── typesense.ts             # server-only admin client
│   │   ├── db.ts                    # pg client (server only)
│   │   ├── types.ts                 # shared response types
│   │   └── flags.ts                 # feature flags (AI off in v1)
│   └── public/                      # static assets
│
└── scripts/                         # developer ergonomics
    ├── reset-db.sh                  # Stage 3
    ├── reindex.sh                   # Stage 5
    ├── run-ingest.sh                # Stage 4
    └── health.sh                    # Stage 3+
```

---

## Folder responsibilities at a glance

| Folder        | Owns                                                                 | Does not own                      |
|---------------|----------------------------------------------------------------------|-----------------------------------|
| `docs/`       | All prose documentation                                              | Code or runtime configuration     |
| `data/seed/`  | Curated inputs (whitelist)                                           | Upstream payloads                 |
| `data/raw/`   | Per-run OpenAlex payloads (gitignored)                               | Anything committed to git         |
| `infra/`      | Local infra definitions                                              | Application code                  |
| `ingestion/`  | Python harvest + normalize + upsert                                  | Reading from Typesense, frontend  |
| `search/`     | Typesense schemas + reindex scripts                                  | Upstream HTTP, frontend           |
| `api/`        | Contract docs only (runtime lives in `web/app/api/`)                 | Runtime API code                  |
| `web/`        | Next.js frontend and route handlers                                  | Ingestion, reindex, upstream HTTP |
| `scripts/`    | Thin shell wrappers for common dev tasks                             | Business logic                    |

---

## Naming conventions

- **Python:** `snake_case` modules, `PascalCase` classes, `snake_case` functions and variables.
- **TypeScript:** `PascalCase` components, `camelCase` functions, `PascalCase` type aliases.
- **SQL:** `snake_case` tables and columns, plural table names (`papers`, `authors`).
- **Env vars:** `SCREAMING_SNAKE_CASE`, prefixed by domain (`POSTGRES_`, `TYPESENSE_`, `OPENALEX_`, `WEB_`).
- **Docs:** kebab-case filenames (`data-model.md`, `search-quality.md`).
