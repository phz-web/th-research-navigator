# API Contracts (Stage 6)

All endpoints live under `/api`. Route handlers are in `web/app/api/`. All responses are `Content-Type: application/json`.

**Base URL (local dev):** `http://localhost:3000/api`

**General conventions:**
- All endpoints are read-only (GET only).
- `400` — invalid or missing query parameters (Zod validation failure). Body: `{ "error": "…", "details": [...] }`.
- `404` — resource not found. Body: `{ "error": "…" }`.
- `502` — upstream service (Typesense or PostgreSQL) unavailable. Body: `{ "error": "…" }`.
- Empty result sets return `200` with `hits: []` / `journals: []`, never `404`.
- Pagination is 1-indexed.

---

## 1. `GET /api/health`

Liveness/dependency check. Returns immediately; never returns a non-200 HTTP status.

**Query parameters:** none

**Response `200`:**

```json
{
  "status": "ok",
  "db": "ok",
  "typesense": "ok",
  "ts": "2024-11-15T14:23:00.000Z"
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | `"ok"` | Always `"ok"` (endpoint-level health) |
| `db` | `"ok" \| "down"` | PostgreSQL ping result |
| `typesense` | `"ok" \| "down"` | Typesense health check result |
| `ts` | ISO 8601 string | Server timestamp |

**Example:**
```bash
curl http://localhost:3000/api/health
```

---

## 2. `GET /api/papers`

Full-text search over the papers Typesense collection. Returns facets alongside hits.

**Query parameters:**

| Param | Type | Required | Default | Notes |
|---|---|---|---|---|
| `q` | string | no | — | Free-text query. Omit or leave empty for browse mode (uses `*`). |
| `year_min` | integer (4-digit) | no | — | Inclusive lower bound on `publication_year`. |
| `year_max` | integer (4-digit) | no | — | Inclusive upper bound on `publication_year`. |
| `journal_id` | integer (repeatable) | no | — | Filter to one or more journal IDs. Repeat param for multi-select: `?journal_id=3&journal_id=7`. |
| `scope_bucket` | enum (repeatable) | no | — | One of `tourism`, `hospitality`, `events`, `leisure`, `destination`, `mixed`. Repeatable. |
| `is_oa` | `"true"` \| `"false"` | no | — | Filter open-access status. |
| `tier` | `"core"` \| `"extended"` | no | — | Filter journal tier. |
| `sort` | enum | no | `relevance` (if `q`), `year_desc` (if no `q`) | One of `relevance`, `year_desc`, `year_asc`, `citations_desc`. |
| `page` | integer ≥ 1 | no | `1` | |
| `per_page` | integer 1–50 | no | `20` | |

**Response `200`:**

```json
{
  "hits": [
    {
      "id": "W2052483477",
      "title": "Destination branding through social media: an empirical analysis",
      "abstract_snippet": "This study investigates how destinations leverage Instagram and Twitter to construct brand identities…",
      "authors": ["María García", "James Smith"],
      "journal_name": "Tourism Management",
      "journal_id": 1,
      "publication_year": 2021,
      "cited_by_count": 143,
      "is_oa": true,
      "doi": "10.1016/j.tourman.2021.104310",
      "primary_topic": "Destination Marketing and Branding",
      "scope_bucket": "tourism",
      "tier": "core"
    }
  ],
  "total": 2840,
  "page": 1,
  "per_page": 20,
  "facets": {
    "publication_year": [
      { "value": "2023", "count": 312 },
      { "value": "2022", "count": 298 }
    ],
    "journal_name": [
      { "value": "Tourism Management", "count": 890 }
    ],
    "scope_bucket": [
      { "value": "tourism", "count": 1240 },
      { "value": "hospitality", "count": 780 }
    ],
    "tier": [
      { "value": "core", "count": 2100 },
      { "value": "extended", "count": 740 }
    ],
    "is_oa": [
      { "value": "true", "count": 1050 },
      { "value": "false", "count": 1790 }
    ]
  }
}
```

**Hit object fields:**

| Field | Type | Notes |
|---|---|---|
| `id` | string | OpenAlex work id (e.g. `W2052483477`) |
| `title` | string | |
| `abstract_snippet` | string \| null | First ≤240 characters of abstract, or null |
| `authors` | string[] | Author display names |
| `journal_name` | string | |
| `journal_id` | integer | DB surrogate id |
| `publication_year` | integer | |
| `cited_by_count` | integer | |
| `is_oa` | boolean | |
| `doi` | string \| null | |
| `primary_topic` | string \| null | OpenAlex primary topic label |
| `scope_bucket` | string | Journal scope bucket |
| `tier` | string | `core` or `extended` |

**Error responses:**
- `400` — invalid params (e.g. non-integer page, unknown scope_bucket)
- `502` — Typesense unreachable

**Examples:**
```bash
# Full-text search
curl "http://localhost:3000/api/papers?q=destination+branding&sort=relevance&per_page=10"

# Browse newest in hospitality, open-access only
curl "http://localhost:3000/api/papers?scope_bucket=hospitality&is_oa=true&sort=year_desc"

# Multi-value: two journals
curl "http://localhost:3000/api/papers?journal_id=1&journal_id=3"

# Year range filter
curl "http://localhost:3000/api/papers?q=smart+hotel&year_min=2019&year_max=2023"
```

---

## 3. `GET /api/papers/[id]`

Full detail for a single paper. Source of truth is PostgreSQL (not Typesense).

**Path parameter:**
- `id` — OpenAlex work id, e.g. `W2052483477`

**Response `200`:**

```json
{
  "id": "W2052483477",
  "openalex_id": "W2052483477",
  "doi": "10.1016/j.tourman.2021.104310",
  "title": "Destination branding through social media: an empirical analysis",
  "abstract": "Full abstract text here…",
  "publication_year": 2021,
  "publication_date": "2021-03-01",
  "volume": "84",
  "issue": null,
  "first_page": "104310",
  "last_page": null,
  "cited_by_count": 143,
  "is_oa": true,
  "primary_topic": "Destination Marketing and Branding",
  "language": "en",
  "landing_page_url": "https://www.sciencedirect.com/science/article/pii/S026151771900xxxx",
  "journal": {
    "id": 1,
    "display_name": "Tourism Management",
    "scope_bucket": "tourism",
    "tier_flag": "core",
    "openalex_source_id": "S205292342"
  },
  "authors": [
    {
      "openalex_author_id": "A2054684321",
      "display_name": "María García",
      "position": 1,
      "position_tag": "first"
    },
    {
      "openalex_author_id": "A1987654321",
      "display_name": "James Smith",
      "position": 2,
      "position_tag": "last"
    }
  ]
}
```

**Response `404`:**
```json
{ "error": "Paper not found" }
```

**Example:**
```bash
curl http://localhost:3000/api/papers/W2052483477
```

---

## 4. `GET /api/papers/[id]/related`

Up to 8 related papers from the same journal, ordered by citation count descending. If `primary_topic` is available on the requested paper, prefers papers that share it; falls back to same-journal regardless of topic.

**Path parameter:**
- `id` — OpenAlex work id

**Response `200`:** Array of paper hit objects (same shape as hits in `GET /api/papers`).

```json
[
  {
    "id": "W2041234567",
    "title": "Tourism destination image and visitor behaviour",
    "abstract_snippet": null,
    "authors": [],
    "journal_name": "Tourism Management",
    "journal_id": 1,
    "publication_year": 2020,
    "cited_by_count": 211,
    "is_oa": false,
    "doi": "10.1016/j.tourman.2020.103900",
    "primary_topic": "Destination Marketing and Branding",
    "scope_bucket": "tourism",
    "tier": "core"
  }
]
```

Note: `abstract_snippet` and `authors` are `null`/`[]` in this endpoint — use `GET /api/papers/[id]` for full detail.

**Response `404`:**
```json
{ "error": "Paper not found" }
```

**Example:**
```bash
curl http://localhost:3000/api/papers/W2052483477/related
```

---

## 5. `GET /api/authors`

Search authors by name using Typesense.

**Query parameters:**

| Param | Type | Required | Default | Notes |
|---|---|---|---|---|
| `q` | string | **yes** | — | Author name query. At least 1 character required. |
| `page` | integer ≥ 1 | no | `1` | |
| `per_page` | integer 1–50 | no | `20` | |
| `sort` | enum | no | `relevance` | One of `relevance`, `works_desc`, `citations_desc`. |

**Response `200`:**

```json
{
  "hits": [
    {
      "id": "A2054684321",
      "display_name": "María García",
      "orcid": "0000-0002-1234-5678",
      "works_count": 42,
      "cited_by_count": 1830,
      "last_known_institution": "University of Barcelona"
    }
  ],
  "total": 14,
  "page": 1,
  "per_page": 20
}
```

**Author hit fields:**

| Field | Type | Notes |
|---|---|---|
| `id` | string | OpenAlex author id (e.g. `A2054684321`) |
| `display_name` | string | |
| `orcid` | string \| null | ORCID without URL prefix |
| `works_count` | integer | Total works in OpenAlex (not just this corpus) |
| `cited_by_count` | integer | Total citations in OpenAlex |
| `last_known_institution` | string \| null | |

**Error responses:**
- `400` — missing or invalid params (e.g. missing `q`)
- `502` — Typesense unavailable

**Example:**
```bash
curl "http://localhost:3000/api/authors?q=smith&sort=citations_desc"
```

---

## 6. `GET /api/authors/[id]`

Full author detail from PostgreSQL, including their papers in this corpus.

**Path parameter:**
- `id` — OpenAlex author id, e.g. `A2054684321`

**Response `200`:**

```json
{
  "id": "A2054684321",
  "openalex_author_id": "A2054684321",
  "display_name": "María García",
  "orcid": "0000-0002-1234-5678",
  "works_count": 42,
  "cited_by_count": 1830,
  "last_known_institution": "University of Barcelona",
  "papers": [
    {
      "openalex_id": "W2052483477",
      "title": "Destination branding through social media",
      "publication_year": 2021,
      "cited_by_count": 143,
      "is_oa": true,
      "doi": "10.1016/j.tourman.2021.104310",
      "journal_name": "Tourism Management",
      "journal_id": 1
    }
  ]
}
```

Papers are ordered by `publication_year DESC`, limited to 100. All papers in this corpus (not all OpenAlex works).

**Response `404`:**
```json
{ "error": "Author not found" }
```

**Example:**
```bash
curl http://localhost:3000/api/authors/A2054684321
```

---

## 7. `GET /api/journals`

Browse all active journals from PostgreSQL. Small dataset (~36 journals), no Typesense needed. Includes live paper count via SQL COUNT.

**Query parameters:**

| Param | Type | Required | Default | Notes |
|---|---|---|---|---|
| `q` | string | no | — | Case-insensitive name search (ILIKE match on `normalized_name`). |
| `scope_bucket` | enum | no | — | One of `tourism`, `hospitality`, `events`, `leisure`, `destination`, `mixed`. |
| `tier` | `"core"` \| `"extended"` | no | — | |
| `page` | integer ≥ 1 | no | `1` | |
| `per_page` | integer 1–100 | no | `50` | |

**Response `200`:**

```json
{
  "journals": [
    {
      "id": 1,
      "openalex_source_id": "S205292342",
      "display_name": "Tourism Management",
      "publisher": "Elsevier",
      "scope_bucket": "tourism",
      "tier_flag": "core",
      "issn_print": "0261-5177",
      "issn_online": "1879-3193",
      "homepage_url": "https://www.journals.elsevier.com/tourism-management",
      "papers_count": 3421
    }
  ],
  "total": 36,
  "page": 1,
  "per_page": 50
}
```

Results are ordered: `tier_flag ASC` (core before extended) then `display_name ASC`.

**Example:**
```bash
# All journals
curl http://localhost:3000/api/journals

# Core hospitality journals only
curl "http://localhost:3000/api/journals?scope_bucket=hospitality&tier=core"
```

---

## 8. `GET /api/journals/[id]`

Journal detail with paginated papers list.

**Path parameter:**
- `id` — DB numeric id (e.g. `1`) **or** OpenAlex source id starting with `S` (e.g. `S205292342`). The handler auto-detects by prefix.

**Query parameters (for papers pagination):**

| Param | Type | Required | Default | Notes |
|---|---|---|---|---|
| `page` | integer ≥ 1 | no | `1` | |
| `per_page` | integer 1–100 | no | `20` | |

**Response `200`:**

```json
{
  "id": 1,
  "openalex_source_id": "S205292342",
  "display_name": "Tourism Management",
  "publisher": "Elsevier",
  "scope_bucket": "tourism",
  "tier_flag": "core",
  "issn_print": "0261-5177",
  "issn_online": "1879-3193",
  "homepage_url": "https://www.journals.elsevier.com/tourism-management",
  "active_flag": true,
  "papers_count": 3421,
  "year_min": 1980,
  "year_max": 2024,
  "papers": [
    {
      "openalex_id": "W2052483477",
      "title": "Destination branding through social media",
      "publication_year": 2021,
      "cited_by_count": 143,
      "is_oa": true,
      "doi": "10.1016/j.tourman.2021.104310",
      "authors": []
    }
  ],
  "papers_total": 3421,
  "papers_page": 1,
  "papers_per_page": 20
}
```

Note: `papers[].authors` is always `[]` in this endpoint. Use `GET /api/papers/[id]` for full authorship.

**Response `404`:**
```json
{ "error": "Journal not found" }
```

**Examples:**
```bash
# By numeric id
curl http://localhost:3000/api/journals/1

# By OpenAlex source id
curl http://localhost:3000/api/journals/S205292342

# With pagination
curl "http://localhost:3000/api/journals/1?page=2&per_page=20"
```

---

## Error shape reference

All error responses follow one of these shapes:

```json
{ "error": "Human-readable message" }
```

```json
{
  "error": "Invalid query parameters",
  "details": [
    { "code": "invalid_enum_value", "path": ["scope_bucket"], "message": "Invalid enum value." }
  ]
}
```

HTTP status codes used:
- `200` — success (even for empty results)
- `400` — client error (bad params, missing required field)
- `404` — resource not found
- `502` — upstream (Typesense or PostgreSQL) unavailable
