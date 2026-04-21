import { SearchX } from "lucide-react";

interface EmptyStateProps {
  query?: string;
  tip?: string;
}

export function EmptyState({
  query,
  tip = "Try removing filters or broadening your search terms.",
}: EmptyStateProps) {
  return (
    <div className="py-16 text-center text-ink-muted">
      <SearchX size={36} strokeWidth={1.25} className="mx-auto mb-4 opacity-40" />
      <p className="font-medium text-ink mb-1">
        {query ? `No results for "${query}"` : "No results found"}
      </p>
      <p className="text-sm">{tip}</p>
    </div>
  );
}
