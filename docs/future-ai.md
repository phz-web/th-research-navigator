# Future: retrieval-grounded AI synthesis (Stage 9 — deferred)

> **Status in v1: disabled.** The feature flag `FEATURE_AI_SYNTHESIS_ENABLED`
> is off by default, no LLM SDK is installed, no API key is configured, and the
> About page advises visitors that AI synthesis is not available. This document
> is a *design intent*, not a shipping feature.

This document exists so that a future maintainer — yourself in six months, a
new collaborator, or a student engineer — has a clear, constrained blueprint
for adding an AI synthesis layer *without* turning this project into another
hallucination-prone chat-over-documents demo.

The non-negotiable rule: **every claim the AI makes must be grounded in a
document that currently lives in the local PostgreSQL corpus.** If the
retrieval layer cannot surface supporting evidence, the AI must decline to
answer. No open-domain LLM knowledge is permitted in user-facing output.

---

## Why this is deferred

Three reasons, all intentional.

1. **Retrieval quality dominates synthesis quality.** An AI synthesis built on
   a weak search layer produces confident summaries of the wrong papers. The
   Stage 8 evaluation exists specifically to gate this: AI synthesis does not
   ship until the retrieval acceptance criterion
   (PASS ≥ 15 / 20, FAIL ≤ 2 — see [docs/search-quality.md](./search-quality.md))
   is consistently met.
2. **Field trust.** Tourism and hospitality scholars — the target audience —
   are rightly sceptical of AI tools that invent citations or misattribute
   claims. Shipping a half-working synthesis layer does real reputational
   damage to the tool.
3. **Scope discipline.** The v1 brief is "a credible, curated,
   metadata-and-abstracts navigator". Adding synthesis before the core
   navigator is solid would violate that brief.

When every condition in §8 ("Activation checklist") is met, this document
becomes the implementation plan.

---

## Design principles

1. **Corpus-only citations.** Every claim must cite a paper that exists in
   `papers` today. No web fetches at inference time, no external knowledge
   base, no fabricated DOIs. If the top-k retrieval returns nothing useful,
   the correct response is `"no strong evidence in this corpus"`.
2. **Retrieval-grounded, not free-form.** The LLM receives a carefully
   constructed context pack of top-k paper chunks. It does not have internet
   access and cannot browse. Prompt engineering enforces "quote or paraphrase
   only from provided context".
3. **Citations are first-class.** Every sentence in the output must link to at
   least one corpus paper. Rendered output uses the paper detail page URL and
   shows the paper title on hover. A claim without a citation is a bug.
4. **Transparent refusal.** When evidence is thin, say so explicitly. Never
   paper over a gap with confident-sounding prose.
5. **No hidden retraining.** User queries may be logged for evaluation but are
   never used to fine-tune a model, never sent to third parties outside the
   LLM provider, and never associated with personal identifiers (v1 has no
   accounts).
6. **Graceful degradation.** If the LLM provider is unreachable, the search
   page continues to work. AI synthesis is strictly additive — the rest of
   the product must never depend on it.

---

## Architecture

```
┌──────────────────────┐     ┌──────────────────────┐
│  user query          │     │  flag disabled?      │
│  + optional filters  │──┬──▶│  → hide UI, 404      │
└──────────────────────┘  │  └──────────────────────┘
                          │  ┌──────────────────────┐
                          └─▶│  retriever           │
                             │  Typesense search    │
                             │  (papers, top-k=12)  │
                             └──────────┬───────────┘
                                        │
                                        ▼
                          ┌──────────────────────┐
                          │  context pack        │
                          │  title + abstract +  │
                          │  citation metadata   │
                          │  per hit             │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  LLM call (server)   │
                          │  system prompt       │
                          │  enforces grounding  │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  post-validator      │
                          │  every citation id   │
                          │  is in context pack  │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  render: synthesis   │
                          │  + inline citations  │
                          │  + source papers     │
                          │  + "why these?" link │
                          └──────────────────────┘
```

### Retriever

- Same Typesense `papers` collection as the main search, same ranking
  baseline (see [docs/search-index.md](./search-index.md)).
- Top-k = 10 to 12 (balance context budget vs. recall). Request
  `include_fields=id,title,abstract,authors_text,journal_name,publication_year,cited_by_count,doi`.
- Hard filter: only results above a minimum `_text_match` score. If the best
  hit is below threshold, short-circuit and return "no strong evidence".
- Optional second-pass rerank with a cross-encoder (e.g. cohere rerank,
  voyage rerank) if budget allows. Not required in Phase 1.

### Context pack

Build one text block per hit of the form:

```
[S1] Title. Authors (Year). Journal. DOI.
Abstract: <= 1200 chars, truncated on sentence boundary.
```

`[S1]..[Sk]` are the citation anchors the LLM is required to use. Pass the
pack in a deterministic order and an explicit citation policy in the system
prompt.

### LLM call

- Server-side only. API keys live in environment variables; never shipped to
  the browser.
- Model choice is an adapter pattern — start with one provider (e.g. OpenAI
  gpt-4-class or Anthropic Claude-3-class) behind a narrow interface. No
  hardcoded vendor calls in business logic.
- Temperature low (≤ 0.3). Determinism matters more than stylistic range.
- Max output tokens clamped so a single synthesis never exceeds ~400 words.

### Post-validator

Before rendering, parse the LLM output for citation markers (`[S1]`, `[S3]`,
etc.) and check:

1. Every marker maps to a paper in the retrieved context pack.
2. Every paragraph has at least one citation marker.
3. The output contains no marker not present in the pack.

If any check fails, fall back to a templated "we could not generate a
reliable synthesis — here are the top results" view.

### Rendering

- Inline citations: `[S1]` rendered as a superscript hyperlink to
  `/papers/<openalex_id>`.
- A "Sources" block beneath the synthesis listing every cited paper as a link
  card.
- A subtle "Why these papers?" affordance that reveals the retrieval
  parameters and ranked list — transparency is part of the trust story.

---

## UX placement

- **Route:** `/synthesis` (gated on the feature flag; returns 404 if off).
  Never surface it as a default search behaviour — the navigator stays
  search-first.
- **Entry points:** an opt-in "Summarise these results" affordance above
  the paper search results, *only* when the query returns at least 5 hits
  above the relevance threshold.
- **Forbidden:** auto-triggering synthesis on every query, on page load, or
  as the first thing a visitor sees. The default experience remains raw,
  ranked metadata search.

---

## Content policy in the prompt

Non-negotiable clauses to embed in the system prompt:

1. "Answer only using the numbered sources provided. Every sentence must cite
   one or more source IDs like `[S1]` or `[S1, S3]`."
2. "If the sources do not collectively support an answer, reply: _The
   provided corpus does not contain strong evidence on this question._ Do
   not fall back on general knowledge."
3. "Do not invent authors, years, journal names, DOIs, or paper titles.
   Never cite a source ID that is not in the provided list."
4. "Prefer direct quotation or close paraphrase from abstracts. Do not
   extrapolate beyond what the abstracts state."
5. "Neutral, academic tone. Do not editorialise."

These clauses are mechanical enforcement, not vibes. The post-validator
backs them up.

---

## Feature-flag wiring (already in place)

The flag is already wired from env to client code — no v1 code depends on the
feature, so turning it on is a single-line change followed by building the
retrieval path.

- **Env var**: `FEATURE_AI_SYNTHESIS_ENABLED` in `.env.example` (default `false`)
- **Flag module**: [`web/lib/flags.ts`](../web/lib/flags.ts) exports
  `FEATURE_AI_SYNTHESIS_ENABLED` — safe to import from client or server.
- **Usage today**: the About page
  ([`web/app/about/page.tsx`](../web/app/about/page.tsx)) renders the note
  *"AI synthesis is not available in v1."* only when the flag is false. The
  flag is never consulted elsewhere in v1 — there is no hidden scaffold, no
  stubbed route, nothing a curious user could discover.

When building Phase 1, the pattern is:

```tsx
import { FEATURE_AI_SYNTHESIS_ENABLED } from "@/lib/flags";

if (!FEATURE_AI_SYNTHESIS_ENABLED) {
  notFound();                                   // /synthesis returns 404
}
```

Add no new server routes under `app/api/synthesis/*` until the flag is true
locally and the Stage 8 retrieval checks have passed.

---

## Activation checklist

AI synthesis may be built only when *all* of these are met. This is the
checkpoint that unblocks Phase 1.

- [ ] Stage 8 retrieval evaluation has PASS ≥ 15 / 20 and FAIL ≤ 2, with the
      reviewed `report_*.md` committed under `search/evaluation/runs/`.
- [ ] A Typesense `_text_match` minimum threshold has been empirically chosen
      (`min_score_for_synthesis`) and documented alongside the ranking config.
- [ ] An LLM provider and model have been selected, with a written rationale
      covering cost, latency, determinism, and data-handling terms.
- [ ] Budget, rate limits, and a kill switch (environment override that
      forces the flag to false in production) are in place.
- [ ] A dedicated evaluation set exists for synthesis quality — at least 20
      grounded-QA pairs with expected source IDs. These are *different* from
      the retrieval queries.
- [ ] Citation fidelity is measured: for each evaluation prompt, verify that
      every marker in the output maps to a retrieved paper and that no marker
      is hallucinated. Target ≥ 98 % fidelity.
- [ ] The post-validator described above is implemented and unit-tested.
- [ ] The About page is updated to describe the AI behaviour, the grounding
      rule, and the "evidence insufficient" refusal path.

Until every box is checked, keep the flag off.

---

## What is explicitly *not* planned, even in Phase 1

- Chatbot / open-ended chat UI. The feature is query → synthesis, not a
  conversation.
- Personalisation. No user history, no per-user tuning.
- Generative writing assistance (outline generators, "write my lit review").
  This is a retrieval-grounded summariser, not a writing tool.
- Agents that call external APIs. The LLM is a sealed box taking text in and
  emitting text out.
- Fine-tuning on the corpus. Retrieval + grounded generation is enough.
- Any feature that requires storing user content in our database.

If a future stakeholder requests any of the above, re-open the product
definition; do not smuggle it into this workstream.

---

## Related documents

- [docs/product-definition.md](./product-definition.md) — v1 scope and non-goals
- [docs/architecture.md](./architecture.md) — data-flow diagram the AI layer slots into
- [docs/search-index.md](./search-index.md) — Typesense schemas and committed ranking
- [docs/search-quality.md](./search-quality.md) — retrieval evaluation that gates this feature
