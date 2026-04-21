import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Breadcrumb } from "@/components/breadcrumb";
import { TierPill } from "@/components/tier-pill";
import { OaPill } from "@/components/oa-pill";
import { Pagination } from "@/components/pagination";
import type { JournalDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

interface JournalPageProps {
  params: { id: string };
  searchParams: Record<string, string | string[] | undefined>;
}

async function fetchJournal(
  id: string,
  page: number,
  perPage: number
): Promise<JournalDetail | null> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const res = await fetch(
      `${baseUrl}/api/journals/${id}?${params.toString()}`,
      { cache: "no-store" }
    );
    if (res.status === 404) return null;
    if (!res.ok) throw new Error("API error");
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: JournalPageProps): Promise<Metadata> {
  const journal = await fetchJournal(params.id, 1, 1);
  if (!journal) return { title: "Journal not found" };
  return {
    title: journal.display_name,
    description: `${journal.papers_count} papers indexed from ${journal.display_name} (${journal.tier_flag} tier).`,
  };
}

export default async function JournalPage({
  params,
  searchParams,
}: JournalPageProps) {
  const page = parseInt(
    typeof searchParams.page === "string" ? searchParams.page : "1",
    10
  );
  const perPage = 20;

  const journal = await fetchJournal(params.id, page, perPage);
  if (!journal) notFound();

  const yearRange =
    journal.year_min && journal.year_max
      ? `${journal.year_min}–${journal.year_max}`
      : journal.year_min
      ? `from ${journal.year_min}`
      : null;

  const issnDisplay = [journal.issn_print, journal.issn_online]
    .filter(Boolean)
    .join(" / ");

  return (
    <div className="max-w-content mx-auto px-6 py-10">
      <Breadcrumb
        crumbs={[
          { label: "Home", href: "/" },
          { label: "Journals", href: "/journals" },
          { label: journal.display_name },
        ]}
      />

      <div className="max-w-2xl mb-10">
        <div className="flex flex-wrap items-start gap-3 mb-3">
          <h1 className="font-display text-2xl font-bold text-ink leading-tight">
            {journal.display_name}
          </h1>
          <TierPill tier={journal.tier_flag} />
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm mb-4">
          {journal.publisher && (
            <>
              <dt className="text-ink-subtle">Publisher</dt>
              <dd className="text-ink-muted">{journal.publisher}</dd>
            </>
          )}
          <dt className="text-ink-subtle">Scope</dt>
          <dd className="text-ink-muted capitalize">{journal.scope_bucket}</dd>
          {issnDisplay && (
            <>
              <dt className="text-ink-subtle">ISSN</dt>
              <dd className="text-ink-muted font-mono text-xs">{issnDisplay}</dd>
            </>
          )}
          <dt className="text-ink-subtle">Papers indexed</dt>
          <dd className="text-ink-muted">
            {journal.papers_count.toLocaleString()}
            {yearRange && <span className="ml-1 text-ink-subtle">({yearRange})</span>}
          </dd>
        </dl>

        {journal.homepage_url && (
          <a
            href={journal.homepage_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
          >
            <ExternalLink size={14} strokeWidth={1.75} />
            Journal homepage
          </a>
        )}
      </div>

      {/* Papers */}
      <section aria-label="Papers from this journal">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-4 border-t border-surface-border pt-6">
          Recent papers
        </h2>

        {journal.papers.length === 0 ? (
          <p className="text-sm text-ink-muted py-8 text-center">
            No papers indexed yet for this journal.
          </p>
        ) : (
          <>
            <div>
              {journal.papers.map((paper) => (
                <article
                  key={paper.openalex_id}
                  className="py-4 border-b border-surface-border last:border-0"
                >
                  <h3 className="text-sm font-medium leading-snug mb-1">
                    <Link
                      href={`/papers/${paper.openalex_id}`}
                      className="text-ink hover:text-accent transition-colors"
                    >
                      {paper.title}
                    </Link>
                  </h3>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-ink-muted">
                    {paper.publication_year && (
                      <span>{paper.publication_year}</span>
                    )}
                    {paper.cited_by_count > 0 && (
                      <>
                        <span aria-hidden="true">·</span>
                        <span>
                          {paper.cited_by_count.toLocaleString()} citations
                        </span>
                      </>
                    )}
                    <OaPill isOa={paper.is_oa} />
                  </div>
                </article>
              ))}
            </div>

            <Pagination
              page={page}
              perPage={perPage}
              total={journal.papers_total}
            />
          </>
        )}
      </section>
    </div>
  );
}
