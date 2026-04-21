import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-surface-border bg-surface/95 backdrop-blur-sm">
      <div className="max-w-content mx-auto px-6 h-14 flex items-center justify-between gap-6">
        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-2.5 text-sm font-semibold text-ink hover:text-accent transition-colors shrink-0"
          aria-label="Tourism & Hospitality Research Navigator — home"
        >
          {/* Inline SVG logo */}
          <svg
            aria-hidden="true"
            viewBox="0 0 32 32"
            width="28"
            height="28"
            fill="none"
            className="shrink-0"
          >
            {/* Compass rose mark */}
            <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="16" cy="16" r="4" fill="currentColor" opacity="0.18" />
            <circle cx="16" cy="16" r="2" fill="currentColor" />
            {/* N cardinal */}
            <line x1="16" y1="2" x2="16" y2="10" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
            <line x1="16" y1="22" x2="16" y2="30" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" opacity="0.45" />
            <line x1="2" y1="16" x2="10" y2="16" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" opacity="0.45" />
            <line x1="22" y1="16" x2="30" y2="16" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" opacity="0.45" />
          </svg>
          <span className="hidden sm:inline">THRN</span>
        </Link>

        {/* Nav */}
        <nav aria-label="Main navigation">
          <ul className="flex items-center gap-1 list-none m-0 p-0">
            {[
              { href: "/papers", label: "Papers" },
              { href: "/authors", label: "Authors" },
              { href: "/journals", label: "Journals" },
              { href: "/about", label: "About" },
            ].map(({ href, label }) => (
              <li key={href}>
                <Link
                  href={href}
                  className="px-3 py-1.5 rounded text-sm text-ink-muted hover:text-ink hover:bg-surface-raised transition-colors"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Theme toggle — client island */}
        <ThemeToggle />
      </div>
    </header>
  );
}
