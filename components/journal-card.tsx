import Link from "next/link";
import type { JournalSummary } from "@/lib/types";
import { TierPill } from "./tier-pill";

interface JournalCardProps {
  journal: JournalSummary;
}

export function JournalCard({ journal }: JournalCardProps) {
  return (
    <Link
      href={`/journals/${journal.id}`}
      className="block rounded border border-surface-border bg-surface p-5 hover:border-accent hover:shadow-sm transition-all group"
    >
      <h2 className="text-sm font-semibold text-ink group-hover:text-accent transition-colors leading-snug mb-2">
        {journal.display_name}
      </h2>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <TierPill tier={journal.tier_flag} />
        <span className="text-xs text-ink-subtle capitalize">
          {journal.scope_bucket}
        </span>
      </div>
      <div className="text-xs text-ink-muted space-y-0.5">
        {journal.publisher && <p>{journal.publisher}</p>}
        <p>
          {journal.papers_count.toLocaleString()}{" "}
          {journal.papers_count === 1 ? "paper" : "papers"} indexed
        </p>
      </div>
    </Link>
  );
}
