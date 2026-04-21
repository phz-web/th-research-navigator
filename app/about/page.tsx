import type { Metadata } from "next";
import { query } from "@/lib/server/db";
import { FEATURE_AI_SYNTHESIS_ENABLED } from "@/lib/flags";
import { TierPill } from "@/components/tier-pill";

export const dynamic = "force-dynamic";
export const revalidate = 3600;

export const metadata: Metadata = {
  title: "About & Data",
  description:
    "About the Tourism & Hospitality Research Navigator: scope, data sources, journal whitelist, and v1 limitations.",
};

interface JournalWhitelistRow {
  id: number;
  display_name: string;
  publisher: string | null;
  scope_bucket: string;
  tier_flag: string;
  issn_print: string | null;
  issn_online: string | null;
  active_flag: boolean;
}

async function getWhitelist(): Promise<JournalWhitelistRow[]> {
  try {
    return query<JournalWhitelistRow>(
      `SELECT id, display_name, publisher, scope_bucket, tier_flag,
              issn_print, issn_online, active_flag
       FROM journals
       ORDER BY tier_flag ASC, display_name ASC`
    );
  } catch {
    return [];
  }
}

export default async function AboutPage() {
  const journals = await getWhitelist();
  const core = journals.filter((j) => j.tier_flag === "core");
  const extended = journals.filter((j) => j.tier_flag === "extended");

  return (
    <div className="max-w-content mx-auto px-6 py-10">
      <div className="max-w-2xl">
        <h1 className="font-display text-2xl font-bold text-ink mb-2">
          About &amp; Data
        </h1>
        <p className="text-sm text-ink-muted mb-10">
          A curated navigator for tourism and hospitality scholarship.
        </p>

        {/* Product scope */}
        <section className="mb-10">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-4">
            Product scope
          </h2>
          <div className="prose prose-sm text-ink-muted max-w-none space-y-3">
            <p>
              Tourism &amp; Hospitality Research Navigator is a search-first web
              application for discovering peer-reviewed research within a
              manually curated whitelist of field-specific journals. It indexes
              paper, author, and journal metadata from OpenAlex — titles,
              abstracts, authorships, venues, citation counts, and DOIs.
            </p>
            <p>
              The corpus boundary is defined by a whitelist of{" "}
              <strong>{journals.length} journals</strong> ({core.length} core,{" "}
              {extended.length} extended). A paper is in-corpus if and only if
              it was published in an active whitelisted journal.
            </p>
            <p>
              <strong>In scope:</strong> Metadata and abstracts only. Paper,
              author, and journal search and detail pages. Curated journal
              whitelist with core/extended tiers.
            </p>
            <p>
              <strong>Out of scope (v1):</strong> Full-text ingestion, PDF
              storage, user accounts, saved searches, citation-graph
              visualization, and AI-generated literature synthesis.
            </p>
          </div>
        </section>

        {/* Data source */}
        <section className="mb-10">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-4">
            Data source
          </h2>
          <div className="text-sm text-ink-muted space-y-3">
            <p>
              All metadata is sourced from{" "}
              <a
                href="https://openalex.org"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                OpenAlex
              </a>
              , an open scholarly knowledge graph released under the Creative
              Commons CC0 1.0 license.
            </p>
            <p>
              OpenAlex is used as the sole upstream source in v1 — no Crossref
              joins, no Scopus, no PDF fetching. Author disambiguation trusts
              OpenAlex author IDs; no custom merging is applied.
            </p>
          </div>
        </section>

        {/* Update cadence */}
        <section className="mb-10">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-4">
            Update cadence
          </h2>
          <p className="text-sm text-ink-muted">
            The corpus is refreshed once daily via the OpenAlex polite-pool
            API. Ingestion is idempotent and resumable; each run is logged with
            counts and timings. Citation counts and metadata may lag OpenAlex by
            up to 24 hours.
          </p>
        </section>

        {/* V1 limitations */}
        <section className="mb-10">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-4">
            v1 limitations
          </h2>
          <ul className="text-sm text-ink-muted space-y-2 list-disc list-inside marker:text-ink-subtle">
            <li>Metadata and abstracts only — no full-text, no PDFs.</li>
            <li>
              No claim of exhaustive coverage. The whitelist is
              precision-biased; extension is a manual curation task.
            </li>
            <li>
              Citation counts come from OpenAlex and inherit its coverage
              limitations.
            </li>
            <li>
              The OA status flag reflects OpenAlex&rsquo;s assessment; it does
              not guarantee a PDF is available.
            </li>
            <li>
              Content may be multilingual; the interface is English-only in v1.
            </li>
          </ul>

          {/* AI synthesis flag */}
          {!FEATURE_AI_SYNTHESIS_ENABLED && (
            <p className="mt-4 text-sm text-ink-muted border-l-2 border-surface-border pl-4">
              AI synthesis is not available in v1.
            </p>
          )}
        </section>

        {/* Journal whitelist */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-4">
            Journal whitelist
          </h2>
          <p className="text-sm text-ink-muted mb-6">
            Journals are seeded from SCImago&rsquo;s Tourism, Leisure and
            Hospitality Management category, refined with domain knowledge.
            Core tier = field-defining SSCI-indexed outlets; extended tier =
            specialist outlets covering events, heritage, technology, and
            adjacent disciplines.
          </p>

          {journals.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-surface-border">
                    <th className="text-left text-ink-subtle font-semibold uppercase tracking-wider py-2 pr-4">
                      Journal
                    </th>
                    <th className="text-left text-ink-subtle font-semibold uppercase tracking-wider py-2 pr-4">
                      Tier
                    </th>
                    <th className="text-left text-ink-subtle font-semibold uppercase tracking-wider py-2 pr-4">
                      Scope
                    </th>
                    <th className="text-left text-ink-subtle font-semibold uppercase tracking-wider py-2 pr-4">
                      Publisher
                    </th>
                    <th className="text-left text-ink-subtle font-semibold uppercase tracking-wider py-2">
                      ISSN
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {journals.map((j) => (
                    <tr
                      key={j.id}
                      className={`border-b border-surface-border hover:bg-surface-raised transition-colors ${
                        !j.active_flag ? "opacity-50" : ""
                      }`}
                    >
                      <td className="py-2.5 pr-4 text-ink font-medium leading-snug">
                        {j.display_name}
                        {!j.active_flag && (
                          <span className="ml-1.5 text-ink-subtle">(inactive)</span>
                        )}
                      </td>
                      <td className="py-2.5 pr-4">
                        <TierPill tier={j.tier_flag} />
                      </td>
                      <td className="py-2.5 pr-4 text-ink-muted capitalize">
                        {j.scope_bucket}
                      </td>
                      <td className="py-2.5 pr-4 text-ink-muted">
                        {j.publisher ?? "—"}
                      </td>
                      <td className="py-2.5 font-mono text-ink-subtle">
                        {[j.issn_print, j.issn_online]
                          .filter(Boolean)
                          .join(" / ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-ink-muted">
              Whitelist not yet available (database not connected).
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
