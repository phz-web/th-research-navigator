import type { Metadata } from "next";
import Link from "next/link";
import { SearchBar } from "@/components/search-bar";
import { JournalCard } from "@/components/journal-card";
import { query } from "@/lib/server/db";
import type { JournalSummary } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 60;

export const metadata: Metadata = {
  title: "Tourism & Hospitality Research Navigator",
  description:
    "Search papers, authors, and journals across a curated whitelist of field-specific journals.",
};

interface StatRow {
  papers: string;
  authors: string;
  journals: string;
}

interface JournalRow {
  id: number;
  openalex_source_id: string | null;
  display_name: string;
  publisher: string | null;
  scope_bucket: string;
  tier_flag: string;
  issn_print: string | null;
  issn_online: string | null;
  homepage_url: string | null;
  papers_count: string;
}

async function getStats() {
  try {
    const rows = await query<StatRow>(
      `SELECT
         (SELECT COUNT(*)::text FROM papers)   AS papers,
         (SELECT COUNT(*)::text FROM authors)  AS authors,
         (SELECT COUNT(*)::text FROM journals WHERE active_flag = TRUE) AS journals`
    );
    const r = rows[0];
    return {
      papers: parseInt(r?.papers ?? "0", 10),
      authors: parseInt(r?.authors ?? "0", 10),
      journals: parseInt(r?.journals ?? "0", 10),
    };
  } catch {
    return { papers: 0, authors: 0, journals: 0 };
  }
}

async function getFeaturedJournals(): Promise<JournalSummary[]> {
  try {
    const rows = await query<JournalRow>(
      `SELECT
         j.id, j.openalex_source_id, j.display_name, j.publisher,
         j.scope_bucket, j.tier_flag, j.issn_print, j.issn_online, j.homepage_url,
         COUNT(p.id)::text AS papers_count
       FROM journals j
       LEFT JOIN papers p ON p.journal_id = j.id
       WHERE j.active_flag = TRUE AND j.tier_flag = 'core'
       GROUP BY j.id
       ORDER BY j.display_name ASC
       LIMIT 8`
    );
    return rows.map((r) => ({
      id: r.id,
      openalex_source_id: r.openalex_source_id,
      display_name: r.display_name,
      publisher: r.publisher,
      scope_bucket: r.scope_bucket,
      tier_flag: r.tier_flag,
      issn_print: r.issn_print,
      issn_online: r.issn_online,
      homepage_url: r.homepage_url,
      papers_count: parseInt(r.papers_count, 10),
    }));
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const [stats, featuredJournals] = await Promise.all([
    getStats(),
    getFeaturedJournals(),
  ]);

  return (
    <>
      {/* Hero */}
      <section className="max-w-content mx-auto px-6 pt-20 pb-16 text-center">
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-ink mb-4 leading-tight">
          Tourism &amp; hospitality research, navigated.
        </h1>
        <p className="text-ink-muted text-base sm:text-lg max-w-xl mx-auto mb-10">
          Search papers, authors, and journals across a curated whitelist of
          field-specific journals.
        </p>
        <div className="flex justify-center">
          <SearchBar size="large" placeholder="Search papers…" autoFocus />
        </div>
        <div className="flex flex-wrap justify-center gap-4 mt-5 text-sm text-ink-muted">
          <Link href="/authors" className="hover:text-accent transition-colors">
            Search authors
          </Link>
          <span aria-hidden="true" className="text-ink-subtle">·</span>
          <Link href="/journals" className="hover:text-accent transition-colors">
            Browse journals
          </Link>
          <span aria-hidden="true" className="text-ink-subtle">·</span>
          <Link href="/about" className="hover:text-accent transition-colors">
            About the corpus
          </Link>
        </div>
      </section>

      {/* Stats */}
      {(stats.papers > 0 || stats.authors > 0 || stats.journals > 0) && (
        <section
          aria-label="Corpus statistics"
          className="max-w-content mx-auto px-6 pb-16"
        >
          <div className="grid grid-cols-3 gap-4 max-w-lg mx-auto">
            {[
              { label: "Papers indexed", value: stats.papers },
              { label: "Authors", value: stats.authors },
              { label: "Journals", value: stats.journals },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="text-center rounded border border-surface-border bg-surface-raised py-5 px-3"
              >
                <p className="text-2xl font-bold text-ink mb-0.5">
                  {value.toLocaleString()}
                </p>
                <p className="text-xs text-ink-muted">{label}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Featured journals */}
      {featuredJournals.length > 0 && (
        <section className="max-w-content mx-auto px-6 pb-20">
          <div className="flex items-baseline justify-between mb-5">
            <h2 className="text-sm font-semibold text-ink-muted uppercase tracking-widest">
              Core journals
            </h2>
            <Link
              href="/journals"
              className="text-xs text-accent hover:underline"
            >
              View all journals
            </Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {featuredJournals.map((j) => (
              <JournalCard key={j.id} journal={j} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
