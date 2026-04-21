# Search Index (Stage 5)

Typesense is the search layer for the Tourism & Hospitality Research Navigator.
It is a *derived index* — all data flows from PostgreSQL into Typesense, never
the other direction. Dropping and rebuilding from PostgreSQL is the supported
recovery path.

Source: [`search/`](../search/)

---

## Collections

### `papers`

The primary searchable collection. One document per ingested paper.

| Field                 | Type       | Facet | Sort | Notes                                                   |
|-----------------------|------------|-------|------|---------------------------------------------------------|
| `id`                  | string     |       |      | Natural key: OpenAlex work id (`Wxxx`)                  |
| `title`               | string     |       |      | Full title for full-text search                         |
| `abstract`            | string     |       |      | Reconstructed from inverted index; optional             |
| `authors_text`        | string[]   |       |      | Display names of all authors; searchable multi-value    |
| `journal_id`          | int64      |       |      | PostgreSQL surrogate journal id (for JOINs in API)      |
| `journal_name`        | string     | yes   |      | Facet: filter by journal                                |
| `journal_scope_bucket`| string     | yes   |      | Facet: `tourism`, `hospitality`, `events`, …            |
| `journal_tier`        | string     | yes   |      | Facet: `core` or `extended`                             |
| `publication_year`    | int32      | yes   | yes  | Facet + sort by year                                    |
| `publication_date`    | string     |       |      | ISO 8601 date string; optional                          |
| `cited_by_count`      | int32      | yes   | yes  | Sort by citation count (default sort)                   |
| `is_oa`               | bool       | yes   |      | Open-access filter                                      |
| `primary_topic`       | string     | yes   |      | OpenAlex primary topic; optional                        |
| `doi`                 | string     |       |      | Optional; `token_separators` enable `10.1234/…` search  |
| `landing_page_url`    | string     |       |      | Optional link to publisher page                         |

- **`default_sorting_field`**: `cited_by_count`
- **`token_separators`**: `["-", "/", "."]` — enables DOI and ISSN tokenisation
- **`symbols_to_index`**: `[]`

### `authors`

| Field                    | Type    | Facet | Sort | Notes                                          |
|--------------------------|---------|-------|------|------------------------------------------------|
| `id`                     | string  |       |      | OpenAlex author id (`Axxx`)                    |
| `display_name`           | string  |       |      | Primary search target                          |
| `normalized_name`        | string  |       |      | Lowercased, accent-stripped                    |
| `orcid`                  | string  |       |      | Optional                                       |
| `works_count`            | int32   |       | yes  | Total works in OpenAlex                        |
| `cited_by_count`         | int32   |       | yes  | Default sort                                   |
| `last_known_institution` | string  | yes   |      | From most recent authorship; facet by org      |

- **`default_sorting_field`**: `cited_by_count`

### `journals`

| Field          | Type    | Facet | Sort | Notes                                           |
|----------------|---------|-------|------|-------------------------------------------------|
| `id`           | string  |       |      | `openalex_source_id` if enriched, else DB id    |
| `display_name` | string  |       |      | Primary search target                           |
| `publisher`    | string  | yes   |      | Facet by publisher; optional                    |
| `scope_bucket` | string  | yes   |      | Facet: `tourism`, `hospitality`, etc.           |
| `tier_flag`    | string  | yes   |      | Facet: `core` or `extended`                     |
| `issn_print`   | string  |       |      | Optional                                        |
| `issn_online`  | string  |       |      | Optional                                        |
| `active_flag`  | bool    | yes   |      | Filter inactive journals from browse view       |
| `papers_count` | int32   |       | yes  | Count of papers in corpus; default sort         |

- **`default_sorting_field`**: `papers_count`

---

## Ranking posture

### Papers

The primary use-case is an academic finding papers by topic, so title matches
are weighted most heavily.

**Recommended `query_by` and `query_by_weights`:**

```
query_by: title,abstract,authors_text,journal_name
query_by_weights: 8,2,3,2
```

Rationale:
- `title` (weight 8): The most precise signal. A title match almost always
  indicates strong relevance.
- `authors_text` (weight 3): Researcher name search is a common use-case; weight
  above abstract to surface name hits quickly.
- `abstract` (weight 2): Broader semantic coverage; lower weight than title.
- `journal_name` (weight 2): Useful for partial-name journal lookups, e.g.
  "Annals" matching papers from "Annals of Tourism Research".

**Default sort:**

```
sort_by: _text_match:desc,cited_by_count:desc
```

This ensures the most textually relevant results appear first, with citation
count as a secondary quality signal.

**Alternative sorts available** (exposed via API `sort_by` parameter):
- `publication_year:desc` — most recent first
- `cited_by_count:desc` — most cited first

### Authors

```
query_by: display_name,normalized_name
sort_by: _text_match:desc,cited_by_count:desc
```

### Journals

```
query_by: display_name,publisher
sort_by: _text_match:desc,papers_count:desc
```

---

## Reindex commands

### Full reindex (via CLI)

```bash
# From ingestion/:
PYTHONPATH=src:cli python -m thrn reindex-search --collection all --full
```

### Full reindex (direct scripts)

```bash
cd search/scripts

# Create collections (idempotent: skips if already exist):
python create_collections.py

# Drop and recreate collections (destroys existing data):
python create_collections.py --recreate

# Reindex each collection:
python reindex_papers.py
python reindex_authors.py
python reindex_journals.py
```

### Partial update (incremental)

```bash
cd search/scripts

# Update only papers changed since last run:
python partial_update.py --collection papers

# Update all collections:
python partial_update.py --collection all
```

State is stored in `data/index_state.json` at the repo root. Each entry records
the timestamp of the last successful partial update per collection.

---

## Partial-update strategy

The `partial_update.py` script queries PostgreSQL for rows with
`updated_at > last_indexed_at` (stored in `data/index_state.json`).

The "last indexed" timestamp is updated to `now()` *before* the query executes.
This ensures that rows inserted or updated *during* the partial run are captured
on the next run (no gap), at the cost of at most one duplicate upsert on
restart.

The Typesense `upsert` import action means re-indexing an unchanged document
is safe — it simply overwrites with identical data.

---

## Recovery

### Full rebuild after collection corruption

```bash
# From search/scripts/:
python create_collections.py --recreate   # drops + recreates all collections
python reindex_papers.py
python reindex_authors.py
python reindex_journals.py
```

Or via the CLI:

```bash
PYTHONPATH=src:cli python -m thrn reindex-search --collection all --full
```

### Reset partial-update state

To force a full catch-up on the next partial run:

```bash
rm data/index_state.json
python partial_update.py --collection all
```

This re-indexes all rows updated since the Unix epoch (i.e. everything).

---

## Field rationale decisions

| Decision                               | Reason                                                                                              |
|----------------------------------------|-----------------------------------------------------------------------------------------------------|
| `authors_text` as string[]             | Typesense multi-value field enables individual author name matching without aggregating into a blob. |
| `journal_scope_bucket` and `tier_flag` | Two of the most common filters in a field-specific navigator; pre-denormalised to avoid JOIN cost.  |
| `default_sorting_field: cited_by_count`| Citation count is the most objective quality proxy for academic content in v1.                      |
| `token_separators: ["-", "/", "."]`    | Enables tokenisation of DOIs (`10.1016/j.tourman.2020.01.001`) and ISSNs.                          |
| Optional fields for `abstract`, etc.  | Some papers lack these; optional prevents import errors on NULL values.                              |
| `id` from `openalex_id`                | Stable natural key; makes upsert idempotent without needing an internal sequence.                   |
