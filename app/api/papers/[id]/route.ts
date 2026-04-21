import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/server/db";
import type { PaperDetail } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface PaperRow {
  id: number;
  openalex_id: string;
  doi: string | null;
  title: string;
  abstract: string | null;
  publication_year: number | null;
  publication_date: string | null;
  volume: string | null;
  issue: string | null;
  first_page: string | null;
  last_page: string | null;
  cited_by_count: number;
  is_oa: boolean | null;
  primary_topic: string | null;
  language: string | null;
  landing_page_url: string | null;
  journal_id: number;
  journal_display_name: string;
  journal_scope_bucket: string;
  journal_tier_flag: string;
  journal_openalex_source_id: string | null;
}

interface AuthorRow {
  openalex_author_id: string;
  display_name: string;
  author_position: number;
  author_position_tag: string | null;
}

export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse<PaperDetail | { error: string }>> {
  const { id } = params;

  const paperRows = await query<PaperRow>(
    `SELECT
       p.id, p.openalex_id, p.doi, p.title, p.abstract,
       p.publication_year, p.publication_date::text AS publication_date,
       p.volume, p.issue, p.first_page, p.last_page,
       p.cited_by_count, p.is_oa, p.primary_topic, p.language, p.landing_page_url,
       j.id            AS journal_id,
       j.display_name  AS journal_display_name,
       j.scope_bucket  AS journal_scope_bucket,
       j.tier_flag     AS journal_tier_flag,
       j.openalex_source_id AS journal_openalex_source_id
     FROM papers p
     JOIN journals j ON j.id = p.journal_id
     WHERE p.openalex_id = $1`,
    [id]
  );

  if (paperRows.length === 0) {
    return NextResponse.json({ error: "Paper not found" }, { status: 404 });
  }

  const paper = paperRows[0];

  const authorRows = await query<AuthorRow>(
    `SELECT
       a.openalex_author_id, a.display_name,
       pa.author_position, pa.author_position_tag
     FROM paper_authors pa
     JOIN authors a ON a.id = pa.author_id
     WHERE pa.paper_id = $1
     ORDER BY pa.author_position ASC`,
    [paper.id]
  );

  const detail: PaperDetail = {
    id: paper.openalex_id,
    openalex_id: paper.openalex_id,
    doi: paper.doi,
    title: paper.title,
    abstract: paper.abstract,
    publication_year: paper.publication_year,
    publication_date: paper.publication_date,
    volume: paper.volume,
    issue: paper.issue,
    first_page: paper.first_page,
    last_page: paper.last_page,
    cited_by_count: paper.cited_by_count,
    is_oa: paper.is_oa,
    primary_topic: paper.primary_topic,
    language: paper.language,
    landing_page_url: paper.landing_page_url,
    journal: {
      id: paper.journal_id,
      display_name: paper.journal_display_name,
      scope_bucket: paper.journal_scope_bucket,
      tier_flag: paper.journal_tier_flag,
      openalex_source_id: paper.journal_openalex_source_id,
    },
    authors: authorRows.map((a) => ({
      openalex_author_id: a.openalex_author_id,
      display_name: a.display_name,
      position: a.author_position,
      position_tag: a.author_position_tag,
    })),
  };

  return NextResponse.json(detail);
}
