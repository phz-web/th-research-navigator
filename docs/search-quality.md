# Search quality — retrieval evaluation (Stage 8)

This document defines how we judge whether the Typesense-backed search layer is
"good enough" for v1 release. It covers the evaluation protocol, the 20-query
test set, the tuning ladder, indicative pass/fail rubrics, known limitations,
and the acceptance criterion for Stage 8 sign-off.

The authoritative ranking baseline lives in
[docs/search-index.md](./search-index.md). Anything below describes *deltas* or
*tuning knobs* on top of that baseline.

---

## Why evaluation matters

Tourism and hospitality research uses a small vocabulary of heavily-overloaded
terms ("smart tourism", "sharing economy", "destination branding",
"servicescape"). A generic search engine will cheerfully return a paper about
"smart locks in hotel rooms" for the query `smart tourism` because both share
tokens. The only way to confirm the ranking is field-appropriate is to hand-
curate a query set and inspect the top results against domain intent.

We intentionally do **not** attempt an automated MRR or nDCG score in v1. The
corpus is too small, the relevance judgements are too subjective, and the
evaluator (you) knows the literature. A structured human-rated rubric is more
useful than a false-precision numeric score.

---

## Evaluation set

**Location:** [`search/evaluation/queries.yaml`](../search/evaluation/queries.yaml)

Twenty queries covering the breadth of the field, chosen so that a reasonable
tourism/hospitality PhD student would recognise each as a legitimate research
query. Each entry records:

| Field           | Purpose                                                              |
|-----------------|----------------------------------------------------------------------|
| `id`            | Stable identifier (Q01–Q20) for cross-run comparison                 |
| `query`         | Exact string passed to Typesense (`q=` parameter)                    |
| `intent`        | One-sentence description of what the searcher wants                  |
| `must_contain`  | Keywords/concepts that top-10 results *should* substantively address |
| `sub_area`      | Broad topical bucket — conceptual / methodological / thematic / etc. |

### Coverage map

| Sub-area                    | Queries                                  |
|-----------------------------|------------------------------------------|
| Core conceptual             | Q01 smart tourism, Q09 destination image |
| Consumer behaviour          | Q02 hotel loyalty programs               |
| Sharing / platform economy  | Q03 Airbnb sharing economy               |
| Crisis & recovery           | Q04 COVID-19 tourism recovery            |
| Sustainability              | Q05 sustainable tourism development, Q14 overtourism |
| Service quality methods     | Q06 SERVQUAL hospitality                 |
| Technology adoption         | Q07 revenue management hotels, Q13 technology acceptance tourism |
| Experience & co-creation    | Q08 tourist experience co-creation       |
| Niche segments              | Q10 dark tourism, Q17 wellness tourism, Q19 MICE industry |
| Destination governance      | Q11 destination branding, Q15 destination competitiveness |
| Workforce                   | Q12 hospitality employee turnover        |
| Food / gastronomy           | Q16 food tourism motivations             |
| Regional                    | Q18 Chinese outbound tourism             |
| Methodology                 | Q20 structural equation modeling tourism |

If a new sub-area becomes important (e.g. generative AI in tourism, climate
adaptation), extend `queries.yaml` with a new `Qxx` — do not replace an existing
row, so historical runs stay comparable.

---

## Evaluation protocol

**Location:** [`search/evaluation/eval_search.py`](../search/evaluation/eval_search.py)
· [`search/evaluation/README.md`](../search/evaluation/README.md)

For each query in the set, the runner:

1. Calls Typesense `/collections/papers/documents/search` with the active
   ranking configuration (`query_by`, `query_by_weights`, `sort_by`,
   `num_typos`, `prefix`, etc.).
2. Records the top 10 hits: rank, paper title, venue, year, citation count,
   Typesense `text_match` score.
3. Emits three artefacts per run into `search/evaluation/runs/<label>/`:
   - `results_<timestamp>.json` — full raw hits for reproducibility
   - `report_<timestamp>.md` — human-readable per-query report with a verdict
     column the curator fills in (`pass` / `fail`, or `partial` via notes)
   - `summary_<timestamp>.csv` — flat one-row-per-query summary for diffing runs

   Timestamps are `YYYYMMDD_HHMMSS`. Multiple runs under the same `--label`
   accumulate side-by-side so historical runs stay intact.

`<label>` is a short, caller-supplied tag, e.g. `baseline`, `title-heavy`,
`with-synonyms`. Runs are never overwritten — each label creates its own
subdirectory.

### Pass / partial / fail rubric

Scored by a human reviewer on the top-10 returned papers.

| Verdict  | Criterion                                                                                              |
|----------|--------------------------------------------------------------------------------------------------------|
| PASS     | ≥ 7 of 10 hits are clearly relevant to the stated intent, and at least one of the top 3 is a core paper |
| PARTIAL  | 4–6 hits are relevant, OR ≥ 7 are relevant but the top 3 are weak                                       |
| FAIL     | ≤ 3 hits are relevant, OR the top hit is clearly off-topic (e.g. a different discipline)                |

"Relevant" means: a field-appropriate reader would include this paper on a
reading list for the query. A peripheral mention of the keyword is **not**
relevance.

### Acceptance criterion (Stage 8 sign-off)

**≥ 15 of 20 queries must earn PASS with a further ≤ 2 FAILs.**

Equivalently: PASS ≥ 15, PARTIAL + PASS ≥ 18, FAIL ≤ 2.

If the criterion is not met, iterate on the tuning ladder below until it is,
or explicitly document why a particular query is accepted at PARTIAL (e.g.
extremely small sub-corpus). Do not lower the bar silently.

---

## Tuning ladder

Apply changes one at a time. Each rung has a label to use with `eval_search.py`
so runs stay distinguishable.

### Rung 0 — baseline (committed default)

```
query_by         = title,abstract,authors_text,journal_name
query_by_weights = 8,2,3,2
sort_by          = _text_match:desc,cited_by_count:desc
num_typos        = 1
prefix           = true,true,false,false
drop_tokens_threshold = 1
```

Run: `python eval_search.py --label baseline`

Expected: title matches dominate, exact phrases work, misspelled author names
still match, abstract-only matches surface below title hits. Acronym queries
(`MICE`, `SERVQUAL`) may under-recall until synonyms are loaded.

### Rung 1 — title-heavy (if abstract noise dominates)

Use if you observe off-topic papers ranked high because they mention the query
keyword once in a long abstract.

```
query_by_weights = 10,1,3,2         # bump title to 10, cut abstract to 1
```

Run: `python eval_search.py --label title-heavy`

Trade-off: improves precision on polysemous terms (`smart`, `sharing`,
`recovery`); may hurt recall on papers whose titles are vague and whose
abstracts carry the real topic. Inspect Q04 (COVID recovery) and Q15
(competitiveness) carefully before adopting.

### Rung 2 — with synonyms

Load [`search/evaluation/synonyms.json`](../search/evaluation/synonyms.json)
into Typesense. Each entry is a one-way or multi-way synonym group, covering:

- Acronym ↔ expansion: `SERVQUAL ↔ service quality`, `MICE ↔ meetings
  incentives conferences exhibitions`, `F&B ↔ food and beverage`.
- Near-synonym concepts: `smart tourism ↔ smart destinations ↔ ICT tourism`,
  `overtourism ↔ tourism overcrowding`, `destination image ↔ place image`.
- Regional spelling / variants where relevant.

Install the synonyms into Typesense once, then run the evaluation:

```bash
# From search/evaluation/
python install_synonyms.py            # upserts synonyms.json into `papers`
python eval_search.py --label with-synonyms
```

To remove them later: `python install_synonyms.py --remove`.

Trade-off: synonyms increase recall for abbreviations and near-variants, and
usually help Q06 (SERVQUAL), Q19 (MICE), Q01 (smart tourism), Q14
(overtourism). They can occasionally over-match (e.g. `place image` pulling in
urban-planning papers). Review the diff against the prior run before
committing.

### Rung 3 — promote authoritative journals (optional)

If a Tier-1 journal paper (e.g. *Tourism Management*, *Annals of Tourism
Research*) is consistently outranked by a lower-tier paper with a higher text
match score, consider a light bias:

```
sort_by = _text_match:desc,journal_tier_rank:asc,cited_by_count:desc
```

where `journal_tier_rank` is a pre-computed int (`core=0, extended=1`) pushed
into the papers collection at index time. Only adopt this rung if Rungs 1–2
are insufficient — it makes ranking less transparent.

### Choosing a "production" ranking

After running Rungs 0–2, compare the three `summary_*.csv` files. The
recommended production configuration is the one with the highest PASS count
*and* the fewest surprising regressions. In our experience with tourism/
hospitality corpora, this is usually **Rung 2 (baseline weights + synonyms)**.
Record the chosen configuration in [docs/search-index.md](./search-index.md)
if it differs from the committed baseline.

---

## Known limitations

- **Small-corpus noise.** For narrow queries (Q10 dark tourism, Q17 wellness
  tourism) there may be only 15–40 in-corpus papers total. Top-10 evaluation is
  sensitive to a single mis-tagged abstract. Treat these queries as advisory,
  not authoritative.
- **OpenAlex abstract quality.** Abstracts are reconstructed from an inverted
  index and occasionally contain token-order artefacts. This affects phrase
  matching in the abstract field more than the title field — another argument
  for keeping `title` weighted heavily.
- **No query-level personalisation.** v1 does not track per-user behaviour; the
  ranking is identical for every visitor. Queries that would benefit from
  user context (e.g. "methodology" would ideally adapt to a qual vs. quant
  researcher) are explicitly out of scope.
- **Acronym recall depends on synonyms being loaded.** The evaluation will
  under-report acronym queries at Rung 0. This is expected — do not treat it
  as a bug in the baseline ranking.
- **Citation-count bias.** The secondary sort on `cited_by_count` rewards
  older papers. For queries about emerging topics (Q04 COVID-19, recent Q01
  smart tourism work) consider a recency-biased alternate sort exposed via
  the API `sort_by` parameter rather than changing the default.

---

## How to run the evaluation

See [`search/evaluation/README.md`](../search/evaluation/README.md) for full
invocation examples. Quick reference:

```bash
# Prerequisites: Typesense is running and the papers collection is populated.
cd search/evaluation

# Baseline run
python eval_search.py --label baseline

# Install synonyms once, then run with them
python install_synonyms.py
python eval_search.py --label with-synonyms

# Compare two labelled runs at the summary level (use the latest summary_*.csv
# in each directory)
ls runs/baseline/summary_*.csv | tail -1
ls runs/with-synonyms/summary_*.csv | tail -1
```

Open `runs/<label>/report_<timestamp>.md`, fill in the `Human verdict` column
for each query (`pass` / `fail` per the rubric; note `partial` cases), and
record the PASS total in the Summary section. Commit the reviewed report to
preserve the audit trail.

---

## What to do when the acceptance criterion is met

1. Record the chosen production ranking (usually Rung 2) in
   [docs/search-index.md](./search-index.md) — only the delta if different
   from the committed baseline.
2. Commit the reviewed `report_*.md` for the production run.
3. Mark Stage 8 complete in [docs/build-plan.md](./build-plan.md) and proceed
   to Stage 9.

## What to do when it is not met

1. Do **not** proceed to Stage 9 — AI synthesis on top of a bad retrieval
   layer will only amplify the problem (see
   [docs/future-ai.md](./future-ai.md)).
2. Inspect the FAIL queries first. Common causes: missing synonyms, abstract
   tokenisation artefacts, over-broad journal whitelist, gaps in the corpus.
3. Consider whether the fix belongs in retrieval (this document), ingestion
   (re-run `refresh-recent` to pick up newer OpenAlex data), or curation
   (adjust the whitelist).
