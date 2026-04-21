interface LoadingSkeletonProps {
  rows?: number;
}

export function LoadingSkeleton({ rows = 5 }: LoadingSkeletonProps) {
  return (
    <div className="space-y-5 animate-pulse" aria-label="Loading…" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="py-5 border-b border-surface-border last:border-0">
          <div className="h-4 bg-surface-border rounded w-3/4 mb-2" />
          <div className="h-3 bg-surface-border rounded w-1/3 mb-3 opacity-70" />
          <div className="h-3 bg-surface-border rounded w-full opacity-50" />
          <div className="h-3 bg-surface-border rounded w-5/6 mt-1 opacity-50" />
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div
      className="rounded border border-surface-border p-5 animate-pulse"
      aria-label="Loading…"
      aria-busy="true"
    >
      <div className="h-4 bg-surface-border rounded w-3/4 mb-3" />
      <div className="h-3 bg-surface-border rounded w-1/2 mb-2 opacity-70" />
      <div className="h-3 bg-surface-border rounded w-1/4 opacity-50" />
    </div>
  );
}
