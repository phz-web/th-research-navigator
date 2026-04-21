import type { Metadata } from "next";
import Link from "next/link";
import { JournalCard } from "@/components/journal-card";
import { ErrorState } from "@/components/error-state";
import type { JournalsResponse } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 60;

export const metadata: Metadata = {
  title: "Journals",
  description:
    "Browse the curated whitelist of tourism and hospitality journals.",
};

interface JournalsPageProps {
  searchParams: Record<string, string | string[] | undefined>;
}

async function fetchJournals(
  searchParams: Record<string, string | string[] | undefined>
): Promise<JournalsResponse | null> {
  try {
    const params = new URLSearchParams();
    for (const [key, val] of Object.entries(searchParams)) {
      if (!val) continue;
      if (Array.isArray(val)) {
        val.forEach((v) => params.append(key, v));
      } else {
        params.set(key, val);
      }
    }
    params.set("per_page", "100");
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const res = await fetch(`${baseUrl}/api/journals?${params.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function JournalsPage({
  searchParams,
}: JournalsPageProps) {
  const data = await fetchJournals(searchParams);

  if (!data) {
    return (
      <div className="max-w-content mx-auto px-6 py-10">
        <ErrorState message="Unable to load journals. Please try again." />
      </div>
    );
  }

  // Group by tier
  const core = data.journals.filter((j) => j.tier_flag === "core");
  const extended = data.journals.filter((j) => j.tier_flag === "extended");

  return (
    <div className="max-w-content mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold text-ink mb-2">
          Journal browser
        </h1>
        <p className="text-sm text-ink-muted">
          {data.total} journals across {" "}
          <Link href="/about" className="text-accent hover:underline">
            tourism &amp; hospitality
          </Link>
          . Grouped by curation tier.
        </p>
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap gap-2 mb-8 text-xs">
        {[
          { href: "/journals", label: "All" },
          { href: "/journals?tier=core", label: "Core only" },
          { href: "/journals?tier=extended", label: "Extended only" },
          { href: "/journals?scope_bucket=tourism", label: "Tourism" },
          {
            href: "/journals?scope_bucket=hospitality",
            label: "Hospitality",
          },
          { href: "/journals?scope_bucket=events", label: "Events" },
          { href: "/journals?scope_bucket=destination", label: "Destination" },
          { href: "/journals?scope_bucket=leisure", label: "Leisure" },
        ].map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className="px-3 py-1.5 rounded border border-surface-border text-ink-muted hover:text-ink hover:border-ink-muted transition-colors"
          >
            {label}
          </Link>
        ))}
      </div>

      {core.length > 0 && (
        <section className="mb-12">
          <h2 className="text-xs font-semibold text-ink-muted uppercase tracking-widest mb-4">
            Core journals ({core.length})
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {core.map((j) => (
              <JournalCard key={j.id} journal={j} />
            ))}
          </div>
        </section>
      )}

      {extended.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-ink-muted uppercase tracking-widest mb-4">
            Extended journals ({extended.length})
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {extended.map((j) => (
              <JournalCard key={j.id} journal={j} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
