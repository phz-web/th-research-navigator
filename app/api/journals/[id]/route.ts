import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/server/db";
import { JournalPapersQuerySchema } from "@/lib/server/validation";
import { ZodError } from "zod";
import type { JournalDetail, JournalPaper } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface JournalRow {
  id: number;
  openalex_source_id: string | null;
  display_name: string;
  publisher: string | null;
  scope_bucket: string;
  tier_flag: string;
  issn_print: string | null;
  issn_online: string | null;
  homepage_url: string | null;
  active_flag: boolean;
  papers_count: string;
  year_min: number | null;
  year_max: number | null;
}

interface PaperRow {
  openalex_id: string;
  title: string;
  publication_year: number | null;
  cited_by_count: number;
  is_oa: boolean | null;
  doi: string | null;
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse<JournalDetail | { error: string; details?: unknown }>> {
  const { id } = params;

  // Parse pagination params
  const searchParams = Object.fromEntries(request.nextUrl.searchParams.entries());
  let pagination;
  try {
    pagination = JournalPapersQuerySchema.parse(searchParams);
  } catch (err) {
    if (err instanceof ZodError) {
      return NextResponse.json(
        { error: "Invalid query parameters", details: err.errors },
        { status: 400 }
      );
    }
    throw err;
  }

  // Detect whether `id` is an OpenAlex source id (prefix "S") or a DB numeric id
  const isOpenAlexId = id.startsWith("S");
  const whereClause = isOpenAlexId
    ? "j.openalex_source_id = $1"
    : "j.id = $1";
  const idParam = isOpenAlexId ? id : parseInt(id, 10);

  if (!isOpenAlexId && isNaN(idParam as number)) {
    return NextResponse.json({ error: "Invalid journal id" }, { status: 400 });
  }

  // Fetch journal meta + paper stats
  const journalRows = await query<JournalRow>(
    `SELECT
       j.id, j.openalex_source_id, j.display_name, j.publisher,
       j.scope_bucket, j.tier_flag,
       j.issn_print, j.issn_online, j.homepage_url, j.active_flag,
       COUNT(p.id)::text AS papers_count,
       MIN(p.publication_year) AS year_min,
       MAX(p.publication_year) AS year_max
     FROM journals j
     LEFT JOIN papers p ON p.journal_id = j.id
     WHERE ${whereClause}
     GROUP BY j.id`,
    [idParam]
  );

  if (journalRows.length === 0) {
    return NextResponse.json({ error: "Journal not found" }, { status: 404 });
  }

  const journal = journalRows[0];
  const offset = (pagination.page - 1) * pagination.per_page;

  // Fetch paginated papers for this journal
  const paperRows = await query<PaperRow>(
    `SELECT p.openalex_id, p.title, p.publication_year,
            p.cited_by_count, p.is_oa, p.doi
     FROM papers p
     WHERE p.journal_id = $1
     ORDER BY p.publication_year DESC NULLS LAST, p.cited_by_count DESC
     LIMIT $2 OFFSET $3`,
    [journal.id, pagination.per_page, offset]
  );

  const papers: JournalPaper[] = paperRows.map((p) => ({
    openalex_id: p.openalex_id,
    title: p.title,
    publication_year: p.publication_year,
    cited_by_count: p.cited_by_count,
    is_oa: p.is_oa,
    doi: p.doi,
    authors: [], // Not loaded here for performance; use /api/papers/[id] for full detail
  }));

  const detail: JournalDetail = {
    id: journal.id,
    openalex_source_id: journal.openalex_source_id,
    display_name: journal.display_name,
    publisher: journal.publisher,
    scope_bucket: journal.scope_bucket,
    tier_flag: journal.tier_flag,
    issn_print: journal.issn_print,
    issn_online: journal.issn_online,
    homepage_url: journal.homepage_url,
    active_flag: journal.active_flag,
    papers_count: parseInt(journal.papers_count, 10),
    year_min: journal.year_min,
    year_max: journal.year_max,
    papers,
    papers_total: parseInt(journal.papers_count, 10),
    papers_page: pagination.page,
    papers_per_page: pagination.per_page,
  };

  return NextResponse.json(detail);
}
