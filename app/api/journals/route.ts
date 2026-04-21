import { NextRequest, NextResponse } from "next/server";
import { ZodError } from "zod";
import { query } from "@/lib/server/db";
import { JournalsQuerySchema, type JournalsQuery } from "@/lib/server/validation";
import type { JournalsResponse, JournalSummary } from "@/lib/types";

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
  papers_count: string; // COUNT returns bigint as string in pg
}

export async function GET(
  request: NextRequest
): Promise<NextResponse<JournalsResponse | { error: string; details?: unknown }>> {
  const searchParams = Object.fromEntries(request.nextUrl.searchParams.entries());

  let params: JournalsQuery;
  try {
    params = JournalsQuerySchema.parse(searchParams);
  } catch (err) {
    if (err instanceof ZodError) {
      return NextResponse.json(
        { error: "Invalid query parameters", details: err.errors },
        { status: 400 }
      );
    }
    throw err;
  }

  // Build WHERE clauses
  const conditions: string[] = ["j.active_flag = TRUE"];
  const qParams: (string | number)[] = [];
  let idx = 1;

  if (params.q) {
    conditions.push(`j.normalized_name ILIKE $${idx}`);
    qParams.push(`%${params.q}%`);
    idx++;
  }

  if (params.scope_bucket) {
    conditions.push(`j.scope_bucket = $${idx}`);
    qParams.push(params.scope_bucket);
    idx++;
  }

  if (params.tier) {
    conditions.push(`j.tier_flag = $${idx}`);
    qParams.push(params.tier);
    idx++;
  }

  const where = `WHERE ${conditions.join(" AND ")}`;
  const offset = (params.page - 1) * params.per_page;

  // Count total
  const countRows = await query<{ total: string }>(
    `SELECT COUNT(*) AS total FROM journals j ${where}`,
    qParams
  );
  const total = parseInt(countRows[0]?.total ?? "0", 10);

  // Fetch page
  const rows = await query<JournalRow>(
    `SELECT
       j.id, j.openalex_source_id, j.display_name, j.publisher,
       j.scope_bucket, j.tier_flag,
       j.issn_print, j.issn_online, j.homepage_url,
       COUNT(p.id)::text AS papers_count
     FROM journals j
     LEFT JOIN papers p ON p.journal_id = j.id
     ${where}
     GROUP BY j.id
     ORDER BY j.tier_flag ASC, j.display_name ASC
     LIMIT $${idx} OFFSET $${idx + 1}`,
    [...qParams, params.per_page, offset]
  );

  const journals: JournalSummary[] = rows.map((r) => ({
    id: r.id,
    openalex_source_id: r.openalex_source_id,
    display_name: r.display_name,
    publisher: r.publisher,
    scope_bucket: r.scope_bucket,
    tier_flag: r.tier_flag,
    issn_print: r.issn_print,
    issn_online: r.issn_online,
    homepage_url: r.homepage_url,
    papers_count: parseInt(r.papers_count, 10),
  }));

  return NextResponse.json({
    journals,
    total,
    page: params.page,
    per_page: params.per_page,
  });
}
