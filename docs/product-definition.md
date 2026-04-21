# Product Definition

## One-paragraph product definition

**Tourism & Hospitality Research Navigator** is a search-first web application that helps tourism and hospitality scholars discover peer-reviewed research within a manually curated whitelist of field-specific journals. It indexes paper, author, and journal metadata from OpenAlex — titles, abstracts, authorships, venues, citation counts, DOIs — and exposes it through a fast faceted search interface with drill-down pages for papers, authors, and journals. v1 deliberately limits itself to metadata and abstracts; full-text retrieval, PDF handling, and AI literature synthesis are explicitly deferred until the retrieval experience is stable and the corpus boundary is trusted by end users.

---

## Target users

| # | User                         | Primary need                                                             |
|---|------------------------------|--------------------------------------------------------------------------|
| 1 | Tourism/hospitality PhDs and postdocs | Find recent and canonical work in a bounded, trustworthy corpus.  |
| 2 | Faculty preparing SLRs       | Scope a field, identify core journals, and triage candidate papers.      |
| 3 | Journal editors and reviewers | Check coverage, recent citation trends, and author profiles at a glance. |
| 4 | Industry researchers and consultants | Navigate academic work on destinations, brands, and services.     |
| 5 | Master's students            | Enter the field through curated journals rather than generic search.     |

Note: v1 does not gate access by role — anyone can use the public site. The distinction above shapes UX priorities, not authentication.

---

## Top 5 v1 use cases

1. **Topic search** — "destination branding social media" returns field-relevant papers sorted by relevance, filterable by year, journal, and scope bucket.
2. **Paper triage** — Open a paper detail page to read the abstract, see authorship and venue, click through to the DOI, and browse related papers.
3. **Author lookup** — Search an author name, see their papers within the curated corpus, and view basic metadata (works count, cited-by).
4. **Journal exploration** — Open a journal page to browse its recent indexed papers and scope metadata (tier, scope bucket, publisher).
5. **Field orientation** — Use the About/Data page to understand which journals are in scope, why they were included, and what the update cadence is.

---

## Explicit scope (v1)

**In scope**
- OpenAlex-sourced metadata for works, sources, and authorships
- A curated tourism/hospitality journal whitelist (core + extended tiers)
- PostgreSQL as relational source of truth, Typesense as search layer
- Three search entities: papers, authors, journals
- Facets: year, journal, scope bucket, open-access flag
- Sorts: relevance, publication year, cited-by count
- Simple related-items on paper detail (same journal / shared primary topic)
- Idempotent, resumable ingestion with run-level auditing
- Public, read-only web UI with light/dark mode

**Explicitly out of scope for v1**
- Full-text ingestion, PDF storage, or OCR
- AI-generated summaries, answers, or literature syntheses (scaffold only, feature-flagged OFF)
- User accounts, saved searches, email alerts, export to Zotero
- Citation-graph visualization
- Recommendation engines beyond deterministic related-items
- Multi-language UI (English only in v1; content may be multilingual as provided by OpenAlex)
- Admin console beyond a read-only ingestion-runs status view

---

## Success criteria

The Stage 1 scaffold is successful if the next builder can start without asking questions. The v1 product is successful if:

1. **Corpus credibility.** A tourism/hospitality scholar reviewing the whitelist agrees it reflects the field — no obvious omissions among core journals, no obvious noise from adjacent management titles.
2. **Retrieval quality.** On a 20-query evaluation set (see Stage 8), at least 15 queries return clearly relevant results in the top 10.
3. **Operational reliability.** Ingestion can be re-run safely without duplicates; failed runs are logged with enough context to resume.
4. **UX feel.** The interface reads as a research tool, not a startup demo. Search is the primary interaction on every page.
5. **Honest AI posture.** No AI features are advertised or active in v1. The deferred scaffold is documented but disabled.
6. **Reproducible handoff.** A second engineer can set up the project from the README in under 60 minutes.

---

## Non-requirements worth naming

These are things a reasonable reader might expect but which v1 will **not** deliver, to keep scope honest:

- No login, no paywall, no per-user personalization.
- No guaranteed real-time freshness. Incremental refresh runs on a cadence (TBD in Stage 4), not on demand per user.
- No claim of exhaustive field coverage. The whitelist is curated and precision-biased; extension is a manual curation task.
- No claim of citation completeness. Cited-by counts come from OpenAlex and inherit its coverage.
- No guarantees about OA PDF availability. The product links out to publisher landing pages and DOIs; it does not host content.

---

## Brand and tone

- **Name:** Tourism & Hospitality Research Navigator
- **Tone:** Credible, academic, restrained, search-first
- **Visual direction:** Neutral surfaces, one accent color, serif or humanist-sans typography, no gradients, no stock illustrations
- **Copy direction:**
  - Home headline: "Search tourism and hospitality research by paper, author, journal, and topic."
  - Secondary: "A curated navigator for tourism and hospitality scholarship."
  - About: "Built on structured metadata from selected journals."

Do not use phrases like "unlock the power of knowledge," "AI-powered research assistant," or any copy that implies generative AI capability in v1.
