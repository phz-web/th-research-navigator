import type { Metadata } from "next";
import { SearchBar } from "@/components/search-bar";
import { AuthorCard } from "@/components/author-card";
import { Pagination } from "@/components/pagination";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import type { AuthorsResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Authors",
  description: "Search tourism and hospitality research authors.",
};

interface AuthorsPageProps {
  searchParams: Record<string, string | string[] | undefined>;
}

async function fetchAuthors(
  q: string,
  page: number,
  sort: string
): Promise<AuthorsResponse | null> {
  if (!q.trim()) return null;
  try {
    const params = new URLSearchParams({ q, page: String(page), sort });
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const res = await fetch(`${baseUrl}/api/authors?${params.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function AuthorsPage({ searchParams }: AuthorsPageProps) {
  const q =
    typeof searchParams.q === "string" ? searchParams.q.trim() : "";
  const page = parseInt(
    typeof searchParams.page === "string" ? searchParams.page : "1",
    10
  );
  const sort =
    typeof searchParams.sort === "string" ? searchParams.sort : "relevance";

  const data = q ? await fetchAuthors(q, page, sort) : null;

  return (
    <div className="max-w-content mx-auto px-6 py-8">
      <div className="mb-8">
        <SearchBar
          defaultValue={q}
          placeholder="Search authors by name…"
          action="/authors"
        />
      </div>

      {!q && (
        <p className="text-sm text-ink-muted text-center py-12">
          Enter an author name to search.
        </p>
      )}

      {q && !data && (
        <ErrorState message="Author search is temporarily unavailable." />
      )}

      {q && data && (
        <>
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs text-ink-subtle">
              {data.total.toLocaleString()} result{data.total !== 1 ? "s" : ""}{" "}
              for <span className="font-medium text-ink">&ldquo;{q}&rdquo;</span>
            </p>
            <label className="flex items-center gap-2 text-xs text-ink-muted">
              Sort
              <select
                value={sort}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                onChange={(e: any) => {
                  const url = new URL(window.location.href);
                  url.searchParams.set("sort", e.target.value);
                  url.searchParams.delete("page");
                  window.location.href = url.toString();
                }}
                className="rounded border border-surface-border bg-surface-raised text-ink text-xs px-2 py-1 focus:outline-none focus:border-accent"
              >
                <option value="relevance">Relevance</option>
                <option value="citations_desc">Most cited</option>
                <option value="works_desc">Most works</option>
              </select>
            </label>
          </div>

          {data.hits.length === 0 ? (
            <EmptyState query={q} />
          ) : (
            <>
              <div>
                {data.hits.map((author) => (
                  <AuthorCard key={author.id} author={author} />
                ))}
              </div>
              <Pagination
                page={page}
                perPage={data.per_page}
                total={data.total}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
