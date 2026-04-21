import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Breadcrumb } from "@/components/breadcrumb";
import { OaPill } from "@/components/oa-pill";
import type { AuthorDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

interface AuthorPageProps {
  params: { id: string };
}

async function fetchAuthor(id: string): Promise<AuthorDetail | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const res = await fetch(`${baseUrl}/api/authors/${id}`, {
      cache: "no-store",
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error("API error");
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: AuthorPageProps): Promise<Metadata> {
  const author = await fetchAuthor(params.id);
  if (!author) return { title: "Author not found" };
  return {
    title: author.display_name,
    description: `Papers by ${author.display_name} in the Tourism & Hospitality Research Navigator.`,
  };
}

export default async function AuthorPage({ params }: AuthorPageProps) {
  const author = await fetchAuthor(params.id);
  if (!author) notFound();

  // Group papers by year
  const byYear = new Map<number | null, typeof author.papers>();
  for (const paper of author.papers) {
    const yr = paper.publication_year;
    if (!byYear.has(yr)) byYear.set(yr, []);
    byYear.get(yr)!.push(paper);
  }
  const sortedYears = [...byYear.keys()].sort((a, b) => {
    if (a === null) return 1;
    if (b === null) return -1;
    return b - a;
  });

  return (
    <div className="max-w-content mx-auto px-6 py-10">
      <Breadcrumb
        crumbs={[
          { label: "Home", href: "/" },
          { label: "Authors", href: "/authors" },
          { label: author.display_name },
        ]}
      />

      <div className="max-w-2xl">
        <h1 className="font-display text-2xl font-bold text-ink mb-3">
          {author.display_name}
        </h1>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm mb-8">
          {author.last_known_institution && (
            <>
              <dt className="text-ink-subtle">Institution</dt>
              <dd className="text-ink-muted">{author.last_known_institution}</dd>
            </>
          )}
          {author.works_count !== null && (
            <>
              <dt className="text-ink-subtle">Total works</dt>
              <dd className="text-ink-muted">{author.works_count.toLocaleString()}</dd>
            </>
          )}
          {author.cited_by_count !== null && (
            <>
              <dt className="text-ink-subtle">Total citations</dt>
              <dd className="text-ink-muted">{author.cited_by_count.toLocaleString()}</dd>
            </>
          )}
          {author.orcid && (
            <>
              <dt className="text-ink-subtle">ORCID</dt>
              <dd>
                <a
                  href={`https://orcid.org/${author.orcid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-accent hover:underline text-sm"
                >
                  {author.orcid}
                  <ExternalLink size={12} strokeWidth={1.75} />
                </a>
              </dd>
            </>
          )}
        </dl>

        {/* Papers */}
        {author.papers.length === 0 ? (
          <p className="text-sm text-ink-muted">
            No papers found for this author in the current corpus.
          </p>
        ) : (
          <section aria-label="Papers by this author">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-subtle mb-5 border-t border-surface-border pt-6">
              Papers in corpus ({author.papers.length})
            </h2>

            {sortedYears.map((year) => {
              const papers = byYear.get(year)!;
              return (
                <div key={String(year)} className="mb-6">
                  <h3 className="text-xs font-semibold text-ink-subtle uppercase tracking-widest mb-3">
                    {year ?? "Year unknown"}
                  </h3>
                  <ul className="space-y-3 list-none m-0 p-0">
                    {papers.map((p) => (
                      <li
                        key={p.openalex_id}
                        className="border-l-2 border-surface-border pl-4 py-0.5"
                      >
                        <Link
                          href={`/papers/${p.openalex_id}`}
                          className="text-sm font-medium text-ink hover:text-accent transition-colors"
                        >
                          {p.title}
                        </Link>
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-xs text-ink-muted">
                          <Link
                            href={`/journals/${p.journal_id}`}
                            className="italic hover:text-accent transition-colors"
                          >
                            {p.journal_name}
                          </Link>
                          {p.cited_by_count > 0 && (
                            <>
                              <span aria-hidden="true">·</span>
                              <span>{p.cited_by_count.toLocaleString()} citations</span>
                            </>
                          )}
                          <OaPill isOa={p.is_oa} />
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </section>
        )}
      </div>
    </div>
  );
}
