import { LoadingSkeleton } from "@/components/loading-skeleton";

export default function Loading() {
  return (
    <div className="max-w-content mx-auto px-6 py-12">
      <LoadingSkeleton rows={6} />
    </div>
  );
}
