import Link from "next/link";
import type { AuthorHit } from "@/lib/types";

interface AuthorCardProps {
  author: AuthorHit;
}

export function AuthorCard({ author }: AuthorCardProps) {
  return (
    <article className="py-4 border-b border-surface-border last:border-0">
      <h2 className="text-sm font-semibold mb-1">
        <Link
          href={`/authors/${author.id}`}
          className="text-ink hover:text-accent transition-colors"
        >
          {author.display_name}
        </Link>
      </h2>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink-muted">
        {author.last_known_institution && (
          <span>{author.last_known_institution}</span>
        )}
        {author.works_count !== null && author.works_count > 0 && (
          <span>{author.works_count.toLocaleString()} works</span>
        )}
        {author.cited_by_count !== null && author.cited_by_count > 0 && (
          <span>{author.cited_by_count.toLocaleString()} citations</span>
        )}
        {author.orcid && (
          <a
            href={`https://orcid.org/${author.orcid}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-accent transition-colors"
            aria-label={`ORCID profile for ${author.display_name}`}
          >
            ORCID
          </a>
        )}
      </div>
    </article>
  );
}
