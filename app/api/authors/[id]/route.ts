import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/server/db";
import type { AuthorDetail, AuthorPaper } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface AuthorRow {
  id: number;
  openalex_author_id: string;
  display_name: string;
  orcid: string | null;
  works_count: number | null;
  cited_by_count: number | null;
  last_known_institution: string | null;
}

interface PaperRow {
  openalex_id: string;
  title: string;
  publication_year: number | null;
  cited_by_count: number;
  is_oa: boolean | null;
  doi: string | null;
  journal_id: number;
  journal_name: string;
}

export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse<AuthorDetail | { error: string }>> {
  const { id } = params;

  const authorRows = await query<AuthorRow>(
    `SELECT id, openalex_author_id, display_name, orcid,
            works_count, cited_by_count, last_known_institution
     FROM authors
     WHERE openalex_author_id = $1`,
    [id]
  );

  if (authorRows.length === 0) {
    return NextResponse.json({ error: "Author not found" }, { status: 404 });
  }

  const author = authorRows[0];

  const paperRows = await query<PaperRow>(
    `SELECT
       p.openalex_id, p.title, p.publication_year, p.cited_by_count,
       p.is_oa, p.doi,
       j.id AS journal_id, j.display_name AS journal_name
     FROM papers p
     JOIN paper_authors pa ON pa.paper_id = p.id
     JOIN journals j ON j.id = p.journal_id
     WHERE pa.author_id = $1
     ORDER BY p.publication_year DESC NULLS LAST
     LIMIT 100`,
    [author.id]
  );

  const papers: AuthorPaper[] = paperRows.map((p) => ({
    openalex_id: p.openalex_id,
    title: p.title,
    publication_year: p.publication_year,
    cited_by_count: p.cited_by_count,
    is_oa: p.is_oa,
    doi: p.doi,
    journal_name: p.journal_name,
    journal_id: p.journal_id,
  }));

  const detail: AuthorDetail = {
    id: author.openalex_author_id,
    openalex_author_id: author.openalex_author_id,
    display_name: author.display_name,
    orcid: author.orcid,
    works_count: author.works_count,
    cited_by_count: author.cited_by_count,
    last_known_institution: author.last_known_institution,
    papers,
  };

  return NextResponse.json(detail);
}
