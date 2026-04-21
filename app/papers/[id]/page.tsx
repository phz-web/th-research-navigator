import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Breadcrumb } from "@/components/breadcrumb";
import { OaPill } from "@/components/oa-pill";
import { ResultCard } from "@/components/result-card";
import type { PaperDetail, PaperHit } from "@/lib/types";

export const dynamic = "force-dynamic";

interface PaperPageProps {
  params: { id: string };
}

async function fetchPaper(id: string): Promise<PaperDetail | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const res = await fetch(`${baseUrl}/api/papers/${id}`, {
      cache: "no-store",
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error("API error");
    return res.json();
  } catch {
    return null;
  }
}

async function fetchRelated(id: string): Promise<PaperHit[]> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const res = await fetch(`${baseUrl}/api/papers/${id}/related`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: PaperPageProps): Promise<Metadata> {
  const paper = await fetchPaper(params.id);
  if (!paper) return { title: "Paper not found" };
  return {
    title: paper.title,
    description: paper.abstract?.slice(0, 200) ?? undefined,
  };
}

export default async function PaperPage({ params }: PaperPageProps) {
  const [paper, related] = await Promise.all([
    fetchPaper(params.id),
    fetchRelated(params.id),
  ]);

  if (!paper) notFound();

  const doiUrl = paper.doi
    ? paper.doi.startsWith("http")
      ? paper.doi
      : `https://doi.org/${paper.doi}`
    : null;

  const pages =
    paper.first_page && paper.last_page
      ? `pp. ${paper.first_page}–${paper.last_page}`
      : paper.first_page
      ? `p. ${paper.first_page}`
      : null;

  const volIssue = [
    paper.volume ? `Vol. ${paper.volume}` : null,
    paper.issue ? `No. ${paper.issue}` : null,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div className="max-w-content mx-auto px-6 py-10">
      <Breadcrumb
        crumbs={[
          { label: "Home", href: "/" },
          { label: "Papers", href: "/papers" },
          { label: paper.title },
        ]}
      />

      <article>
        {/* Title */}
        <h1 className="font-display text-2xl font-bold text-ink leading-tight mb-4 max-w-3xl">
          {paper.title}
        </h1>

        {/* Authors */}
        {paper.authors.length > 0 && (
          <p className="text-sm text-ink-muted mb-4">
            {paper.authors.map((a, i) => (
              <span key={a.openalex_author_id}>
                {i > 0 && ", "}
                <Link
                  href={`/authors/${a.openalex_author_id}`}
                  className="hover:text-accent transition-colors"
                >
                  {a.display_name}
                </Link>
              </span>
            ))}
          </p>
        )}

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted mb-6">
          <Link
            href={`/journals/${paper.journal.id}`}
            className="italic hover:text-accent transition-colors"
          >
            {paper.journal.display_name}
          </Link>
          {paper.publication_year && (
            <>
              <span aria-hidden="true">·</span>
              <span>{paper.publication_year}</span>
            </>
          )}
          {volIssue && (
            <>
              <span aria-hidden="true">·</span>
              <span>{volIssue}</span>
            </>
          )}
          {pages && (
            <>
              <span aria-hidden="true">·</span>
              <span>{pages}</span>
            </>
          )}
          {paper.cited_by_count > 0 && (
            <>
              <span aria-hidden="true">·</span>
              <span>{paper.cited_by_count.toLocaleString()} citations</span>
            </>
          )}
          <OaPill isOa={paper.is_oa} />
        </div>

        {/* Abstract */}
        {paper.abstract && (
          <section aria-label="Abstract" className="mb-8 max-w-3xl">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-3">
              Abstract
            </h2>
            <p className="text-sm text-ink-muted leading-relaxed">
              {paper.abstract}
            </p>
          </section>
        )}

        {/* External links */}
        <div className="flex flex-wrap gap-3 mb-10">
          {doiUrl && (
            <a
              href={doiUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
            >
              <ExternalLink size={14} strokeWidth={1.75} />
              View on DOI
            </a>
          )}
          {paper.landing_page_url && paper.landing_page_url !== doiUrl && (
            <a
              href={paper.landing_page_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
            >
              <ExternalLink size={14} strokeWidth={1.75} />
              Publisher page
            </a>
          )}
        </div>
      </article>

      {/* Related papers */}
      {related.length > 0 && (
        <section aria-label="Related papers">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-4 border-t border-surface-border pt-8">
            Related papers
          </h2>
          <div>
            {related.map((r) => (
              <ResultCard key={r.id} paper={r} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
