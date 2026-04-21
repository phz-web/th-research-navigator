import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-content mx-auto px-6 py-24 text-center">
      <p className="text-sm font-medium text-ink-subtle uppercase tracking-widest mb-4">
        404
      </p>
      <h1 className="font-display text-2xl font-semibold text-ink mb-3">
        Page not found
      </h1>
      <p className="text-ink-muted mb-8">
        The page you are looking for does not exist or has been moved.
      </p>
      <Link
        href="/"
        className="inline-block px-5 py-2 rounded border border-accent text-accent hover:bg-accent hover:text-white transition-colors text-sm font-medium"
      >
        Return home
      </Link>
    </div>
  );
}
