-- =========================================================================
-- Tourism & Hospitality Research Navigator — initial schema
-- Migration 0001: create core tables, indexes, and constraints.
-- Safe to re-run: uses IF NOT EXISTS guards throughout.
-- =========================================================================

BEGIN;

-- Extensions ---------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- trigram search for name fallback matching
CREATE EXTENSION IF NOT EXISTS citext;        -- case-insensitive text for normalized names
CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- gen_random_uuid() for surrogate keys

-- Helper: updated_at trigger -----------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================================
-- journals
-- Canonical journal records. Seeded from data/seed/journal_whitelist.csv
-- and enriched with OpenAlex source metadata via the ingestion pipeline.
-- =========================================================================
CREATE TABLE IF NOT EXISTS journals (
    id                  BIGSERIAL PRIMARY KEY,
    openalex_source_id  TEXT UNIQUE,                    -- e.g. S1234567890; NULL until enriched
    display_name        TEXT NOT NULL,
    normalized_name     CITEXT NOT NULL,
    issn_print          TEXT,
    issn_online         TEXT,
    publisher           TEXT,
    homepage_url        TEXT,
    scimago_category    TEXT,
    scope_bucket        TEXT NOT NULL
        CHECK (scope_bucket IN ('tourism','hospitality','events','leisure','destination','mixed')),
    tier_flag           TEXT NOT NULL
        CHECK (tier_flag IN ('core','extended')),
    active_flag         BOOLEAN NOT NULL DEFAULT TRUE,  -- false = journal excluded from ingestion/search
    manual_review_flag  BOOLEAN NOT NULL DEFAULT FALSE,
    inclusion_reason    TEXT,
    notes               TEXT,
    raw_json            JSONB,                          -- raw OpenAlex source payload
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_journals_normalized_name     ON journals (normalized_name);
CREATE INDEX IF NOT EXISTS ix_journals_issn_print          ON journals (issn_print)     WHERE issn_print  IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_journals_issn_online         ON journals (issn_online)    WHERE issn_online IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_journals_active              ON journals (active_flag);
CREATE INDEX IF NOT EXISTS ix_journals_tier                ON journals (tier_flag);
CREATE INDEX IF NOT EXISTS ix_journals_scope               ON journals (scope_bucket);
CREATE INDEX IF NOT EXISTS ix_journals_normalized_name_trgm ON journals USING gin (normalized_name gin_trgm_ops);

DROP TRIGGER IF EXISTS trg_journals_updated_at ON journals;
CREATE TRIGGER trg_journals_updated_at BEFORE UPDATE ON journals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =========================================================================
-- authors
-- One row per OpenAlex author_id. We trust OpenAlex disambiguation in v1.
-- =========================================================================
CREATE TABLE IF NOT EXISTS authors (
    id                      BIGSERIAL PRIMARY KEY,
    openalex_author_id      TEXT NOT NULL UNIQUE,       -- e.g. A1234567890
    display_name            TEXT NOT NULL,
    normalized_name         CITEXT NOT NULL,
    orcid                   TEXT,
    works_count             INTEGER,
    cited_by_count          INTEGER,
    last_known_institution  TEXT,
    raw_json                JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_authors_normalized_name       ON authors (normalized_name);
CREATE INDEX IF NOT EXISTS ix_authors_orcid                 ON authors (orcid) WHERE orcid IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_authors_normalized_name_trgm  ON authors USING gin (normalized_name gin_trgm_ops);

DROP TRIGGER IF EXISTS trg_authors_updated_at ON authors;
CREATE TRIGGER trg_authors_updated_at BEFORE UPDATE ON authors
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =========================================================================
-- papers
-- One row per OpenAlex work, scoped to journals.active_flag = TRUE.
-- =========================================================================
CREATE TABLE IF NOT EXISTS papers (
    id                  BIGSERIAL PRIMARY KEY,
    openalex_id         TEXT NOT NULL UNIQUE,           -- e.g. W1234567890
    doi                 TEXT,
    title               TEXT NOT NULL,
    abstract            TEXT,
    publication_year    INTEGER,
    publication_date    DATE,
    journal_id          BIGINT NOT NULL REFERENCES journals(id) ON DELETE RESTRICT,
    volume              TEXT,
    issue               TEXT,
    first_page          TEXT,
    last_page           TEXT,
    cited_by_count      INTEGER NOT NULL DEFAULT 0,
    is_oa               BOOLEAN,
    primary_topic       TEXT,
    language            TEXT,
    landing_page_url    TEXT,
    pdf_url             TEXT,                           -- metadata-only; never fetched
    raw_json            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DOI is unique when present, but many papers have NULL DOI.
CREATE UNIQUE INDEX IF NOT EXISTS ux_papers_doi ON papers (doi) WHERE doi IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_papers_journal_id            ON papers (journal_id);
CREATE INDEX IF NOT EXISTS ix_papers_publication_year      ON papers (publication_year);
CREATE INDEX IF NOT EXISTS ix_papers_cited_by_count        ON papers (cited_by_count);
CREATE INDEX IF NOT EXISTS ix_papers_updated_at            ON papers (updated_at);
CREATE INDEX IF NOT EXISTS ix_papers_primary_topic         ON papers (primary_topic) WHERE primary_topic IS NOT NULL;

DROP TRIGGER IF EXISTS trg_papers_updated_at ON papers;
CREATE TRIGGER trg_papers_updated_at BEFORE UPDATE ON papers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =========================================================================
-- paper_authors
-- Many-to-many join with author_position preserved from OpenAlex.
-- =========================================================================
CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id            BIGINT NOT NULL REFERENCES papers(id)  ON DELETE CASCADE,
    author_id           BIGINT NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    author_position     INTEGER NOT NULL,
    author_position_tag TEXT
        CHECK (author_position_tag IN ('first','middle','last') OR author_position_tag IS NULL),
    is_corresponding    BOOLEAN,
    raw_affiliation     TEXT,
    PRIMARY KEY (paper_id, author_id, author_position)
);

CREATE INDEX IF NOT EXISTS ix_paper_authors_author_id  ON paper_authors (author_id);
CREATE INDEX IF NOT EXISTS ix_paper_authors_paper_id   ON paper_authors (paper_id);

-- =========================================================================
-- ingestion_runs
-- One row per CLI invocation of the ingestion pipeline.
-- =========================================================================
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    command             TEXT NOT NULL,              -- bootstrap-journals | enrich-journals | ingest-works | refresh-recent
    status              TEXT NOT NULL
        CHECK (status IN ('running','success','partial','failed')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    journals_touched    INTEGER NOT NULL DEFAULT 0,
    papers_inserted     INTEGER NOT NULL DEFAULT 0,
    papers_updated      INTEGER NOT NULL DEFAULT 0,
    authors_inserted    INTEGER NOT NULL DEFAULT 0,
    authors_updated     INTEGER NOT NULL DEFAULT 0,
    error_summary       TEXT,
    params              JSONB,                       -- CLI arguments, date ranges, filters
    stats               JSONB                        -- additional counts / timings
);

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_started_at ON ingestion_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS ix_ingestion_runs_command    ON ingestion_runs (command);
CREATE INDEX IF NOT EXISTS ix_ingestion_runs_status     ON ingestion_runs (status);

-- =========================================================================
-- source_match_audit
-- Forensic trail for whitelist → OpenAlex source matching. Never overwritten.
-- =========================================================================
CREATE TABLE IF NOT EXISTS source_match_audit (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              UUID REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    journal_id          BIGINT REFERENCES journals(id) ON DELETE SET NULL,
    whitelist_name      TEXT NOT NULL,
    candidate_openalex_id TEXT,
    candidate_display_name TEXT,
    match_method        TEXT NOT NULL
        CHECK (match_method IN ('issn_print','issn_online','name_exact','name_trigram','manual','unmatched')),
    confidence          NUMERIC(4,3),                -- 0.000 – 1.000
    accepted            BOOLEAN NOT NULL,
    notes               TEXT,
    raw_candidate_json  JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_source_match_audit_journal_id ON source_match_audit (journal_id);
CREATE INDEX IF NOT EXISTS ix_source_match_audit_run_id     ON source_match_audit (run_id);

COMMIT;
