# Journal Curation Memo (Stage 2)

## Purpose

Define the corpus boundary for Tourism & Hospitality Research Navigator. The whitelist is the single source of truth that determines which OpenAlex works are ingested. Everything downstream (ingestion, search, UI) inherits this decision. Corpus precision matters more than corpus recall in v1.

## Source of the seed

Seeded from SCImago's **"Tourism, Leisure and Hospitality Management"** category, refined with domain knowledge of tourism/hospitality scholarship. SCImago is used only as a starting boundary, not as the final arbiter.

Reference: [SCImago — Tourism, Leisure and Hospitality Management](https://www.scimagojr.com/journalrank.php?category=1409).

## Inclusion rules

A journal is included in v1 if **all** of the following are true:

1. **Category fit.** The journal is listed under SCImago's Tourism, Leisure and Hospitality Management category, **or** is unambiguously a specialist tourism/hospitality/events journal even if categorised elsewhere.
2. **Peer-reviewed scholarly outlet.** Book-series, magazines, industry bulletins, and practitioner newsletters are excluded.
3. **Identifiable in OpenAlex.** The journal can plausibly be matched to an OpenAlex `source` via ISSN or normalized name. Journals with no reliable ISSN are flagged for manual review.
4. **Active or recently active.** Journals that have ceased publication are excluded unless they are historically foundational and likely still returning citations.

## Exclusion rules

A journal is **excluded** from v1 if **any** of the following is true:

1. **Adjacent but not field-specific.** Generic management, marketing, consumer-behaviour, or services journals are excluded even when they publish tourism/hospitality papers. They dilute field precision and are better handled at the paper level later.
2. **Predatory or low-credibility venues.** Excluded regardless of SCImago listing.
3. **Primarily medical / clinical.** Excluded unless mobility/health-tourism is explicitly in scope. `Journal of Travel Medicine` is flagged for review on this basis.
4. **Regional/industry trade publications** without peer review.

## Tiering: core vs extended

| Tier      | Definition                                                                                   | Count in v1 |
|-----------|----------------------------------------------------------------------------------------------|-------------|
| `core`    | Field-defining specialist journals that any tourism/hospitality scholar would expect to find in an SLR. SSCI-indexed (or widely treated as flagship). | 16          |
| `extended`| Legitimate specialist outlets that round out the field (events, heritage, technology, regional focus, leisure-adjacent). | 20          |

Total journals in v1 seed: **36** (16 core + 20 extended). Core-only operation is supported via `tier_flag = 'core'` filtering if the curator wants a tighter corpus.

## Scope buckets

Each journal is tagged with exactly one `scope_bucket`:

| Bucket       | Meaning                                                                  |
|--------------|--------------------------------------------------------------------------|
| `tourism`    | Primarily tourism-focused (behaviour, geography, sustainability, etc.)   |
| `hospitality`| Primarily hospitality/hotel/restaurant management                        |
| `events`     | Events and festivals management                                          |
| `leisure`    | Leisure studies (adjacent; only when SCImago-listed in the category)     |
| `destination`| Destination marketing / place branding / urban tourism                   |
| `mixed`      | Broad-scope tourism+hospitality or genuinely interdisciplinary           |

Rationale: scope buckets give users a meaningful facet without forcing a fake hierarchy. They are curator-assigned, not derived from OpenAlex.

## `manual_review_flag` — what it means

`true` means the row needs human verification before being used in ingestion. Reasons vary:

- **ISSN not independently verified** in this curation session (e.g. Journal of Travel and Tourism Marketing, several Taylor & Francis outlets).
- **Borderline scope** (leisure studies, travel medicine, themed/practitioner journals).
- **OpenAlex match ambiguity expected** (common in older titles or titles with frequent renames).

Stage 4 ingestion must respect this flag: ambiguous source matches for flagged journals go to the `source_match_audit` table and are **not** auto-promoted to active ingestion.

## Notable judgement calls

### Included with confidence (core)
- **Annals of Tourism Research** and **Tourism Management** anchor the corpus. Omitting either would make the product indefensible.
- **Cornell Hospitality Quarterly** retained despite its hybrid Hospitality/Sociology SSCI listing — historically and currently a field pillar.
- **Journal of Travel and Tourism Marketing** is included as core despite the ISSN verification flag because it is a top marketing outlet in tourism; curator should verify before ingestion.

### Included with caution (extended, flagged)
- **Leisure Sciences** and **Journal of Leisure Research** are in SCImago's category but their centre of gravity is leisure studies, not tourism/hospitality. They are flagged so the curator can decide whether the product should present leisure studies as part of its identity.
- **Journal of Travel Medicine** is flagged because it is fundamentally a medical journal and including it would mislead users about the product's scope.
- **Worldwide Hospitality and Tourism Themes** is flagged because it is a themed/practitioner journal with a different rigor profile.

### Deliberate exclusions
- **Service Industries Journal, Journal of Services Marketing, Journal of Business Research, Industrial Marketing Management** — major outlets for tourism/hospitality papers but not field-specific. Excluded to maintain corpus precision.
- **Tourism Economics** — a strong case for inclusion; excluded from v1 seed pending curator decision because its economics orientation is narrower than the product's general-field posture. Trivial to add in Stage 2.5 if desired.
- **Asia Pacific Journal of Marketing and Logistics, Journal of Services Marketing, International Journal of Bank Marketing** — explicitly not field-specific.
- **Anatolia, Tourism Planning & Development, Journal of Policy Research in Tourism Leisure and Events, Tourism Review, Journal of Hospitality and Tourism Insights, International Journal of Tourism Sciences, e-Review of Tourism Research** — plausible extended-tier candidates. **Intentionally deferred** to avoid ISSN guessing in v1; add in a Stage 2.5 pass after ISSN verification.

## Known gaps you may want to close in Stage 2.5

Before Stage 4 ingestion, consider adding (with verified ISSNs):

- Tourism Economics (Sage) — if tourism economics is in scope
- Journal of Hospitality and Tourism Insights (Emerald)
- Tourism Review (Emerald)
- Anatolia: An International Journal of Tourism and Hospitality Research
- Tourism Planning & Development (Taylor & Francis)
- Journal of Policy Research in Tourism, Leisure and Events (Taylor & Francis)
- Journal of Tourism and Cultural Change (Taylor & Francis)

These are plausible extended-tier additions; they were held out of v1 only because their ISSNs were not verified in this curation session.

## Operating principles

1. **Precision over recall.** Easier to expand a tight whitelist than to clean up a noisy one.
2. **Transparent flags beat silent decisions.** Every borderline judgement has a `manual_review_flag` and a written rationale.
3. **The whitelist is versioned.** Changes must be committed with a note in this memo's changelog.
4. **The whitelist is not a quality ranking.** Tier reflects *scope centrality*, not journal prestige.

## Changelog

| Date       | Change                                                      |
|------------|-------------------------------------------------------------|
| 2026-04-19 | Initial seed: 16 core + 20 extended; 10 rows flagged.       |
