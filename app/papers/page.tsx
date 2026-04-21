import type { Metadata } from "next";
import { Suspense } from "react";
import { SearchBar } from "@/components/search-bar";
import { FilterSidebar } from "@/components/filter-sidebar";
import { ResultCard } from "@/components/result-card";
import { Pagination } from "@/components/pagination";
import { ActiveFilterChips } from "@/components/active-filter-chips";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import type { PapersResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Papers",
  description: "Search and browse tourism and hospitality research papers.",
};

interface PapersPageProps {
  searchParams: Record<string, string | string[] | undefined>;
}

async function fetchPapers(
  searchParams: Record<string, string | string[] | undefined>
): Promise<PapersResponse | null> {
  try {
    // Build URL params — must happen server-side (no browser fetch)
    const params = new URLSearchParams();
    for (const [key, val] of Object.entries(searchParams)) {
      if (!val) continue;
      if (Array.isArray(val)) {
        val.forEach((v) => params.append(key, v));
      } else {
        params.set(key, val);
      }
    }

    // Server-side fetch to own route handler
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const res = await fetch(`${baseUrl}/api/papers?${params.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json() as Promise<PapersResponse>;
  } catch {
    return null;
  }
}

async function PapersResults({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const data = await fetchPapers(searchParams);
  const q =
    typeof searchParams.q === "string" ? searchParams.q : undefined;
  const page = parseInt(
    typeof searchParams.page === "string" ? searchParams.page : "1",
    10
  );

  if (!data) {
    return <ErrorState message="Search is temporarily unavailable. Please try again." />;
  }

  if (data.hits.length === 0) {
    return <EmptyState query={q} />;
  }

  return (
    <>
      <p className="text-xs text-ink-subtle mb-4">
        {data.total.toLocaleString()} result{data.total !== 1 ? "s" : ""}
        {q && (
          <>
            {" "}for <span className="font-medium text-ink">&ldquo;{q}&rdquo;</span>
          </>
        )}
      </p>

      <div>
        {data.hits.map((paper) => (
          <ResultCard key={paper.id} paper={paper} />
        ))}
      </div>

      <Pagination page={page} perPage={data.per_page} total={data.total} />
    </>
  );
}

export default function PapersPage({ searchParams }: PapersPageProps) {
  const q =
    typeof searchParams.q === "string" ? searchParams.q : undefined;

  return (
    <div className="max-w-content mx-auto px-6 py-8">
      {/* Search bar */}
      <div className="mb-8">
        <SearchBar defaultValue={q ?? ""} placeholder="Search papers…" />
      </div>

      <div className="flex gap-8 items-start">
        {/* Sidebar */}
        <div className="hidden lg:block w-52 shrink-0">
          <Suspense fallback={null}>
            <FilterSidebar />
          </Suspense>
        </div>

        {/* Results */}
        <div className="flex-1 min-w-0">
          {/* Active filter chips */}
          <Suspense fallback={null}>
            <div className="mb-4">
              <ActiveFilterChips />
            </div>
          </Suspense>

          <Suspense fallback={<LoadingSkeleton rows={8} />}>
            <PapersResults searchParams={searchParams} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
