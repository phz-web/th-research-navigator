"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  page: number;
  perPage: number;
  total: number;
}

export function Pagination({ page, perPage, total }: PaginationProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const totalPages = Math.ceil(total / perPage);
  if (totalPages <= 1) return null;

  function goTo(p: number) {
    const params = new URLSearchParams(searchParams.toString());
    if (p === 1) {
      params.delete("page");
    } else {
      params.set("page", String(p));
    }
    router.push(`${pathname}?${params.toString()}`);
  }

  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  // Build page window: show current ±2 pages
  const windowPages: number[] = [];
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, page + 2);
  for (let i = start; i <= end; i++) windowPages.push(i);

  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1 mt-8">
      <button
        onClick={() => goTo(page - 1)}
        disabled={!hasPrev}
        aria-label="Previous page"
        className="p-1.5 rounded border border-surface-border text-ink-muted hover:text-ink hover:border-ink-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronLeft size={15} />
      </button>

      {start > 1 && (
        <>
          <button
            onClick={() => goTo(1)}
            className="px-3 py-1.5 rounded text-sm border border-surface-border text-ink-muted hover:text-ink hover:border-ink-muted transition-colors"
          >
            1
          </button>
          {start > 2 && (
            <span className="px-1 text-ink-subtle text-sm">…</span>
          )}
        </>
      )}

      {windowPages.map((p) => (
        <button
          key={p}
          onClick={() => goTo(p)}
          aria-current={p === page ? "page" : undefined}
          className={`px-3 py-1.5 rounded text-sm border transition-colors ${
            p === page
              ? "border-accent bg-accent text-white"
              : "border-surface-border text-ink-muted hover:text-ink hover:border-ink-muted"
          }`}
        >
          {p}
        </button>
      ))}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && (
            <span className="px-1 text-ink-subtle text-sm">…</span>
          )}
          <button
            onClick={() => goTo(totalPages)}
            className="px-3 py-1.5 rounded text-sm border border-surface-border text-ink-muted hover:text-ink hover:border-ink-muted transition-colors"
          >
            {totalPages}
          </button>
        </>
      )}

      <button
        onClick={() => goTo(page + 1)}
        disabled={!hasNext}
        aria-label="Next page"
        className="p-1.5 rounded border border-surface-border text-ink-muted hover:text-ink hover:border-ink-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronRight size={15} />
      </button>
    </nav>
  );
}
