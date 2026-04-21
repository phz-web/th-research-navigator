import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/server/db";
import type { PaperHit } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface PaperMeta {
  id: number;
  journal_id: number;
  primary_topic: string | null;
}

interface RelatedRow {
  openalex_id: string;
  title: string;
  publication_year: number | null;
  cited_by_count: number;
  is_oa: boolean | null;
  doi: string | null;
  primary_topic: string | null;
  journal_name: string;
  journal_id: number;
  journal_scope_bucket: string;
  journal_tier_flag: string;
}

export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse<PaperHit[] | { error: string }>> {
  const { id } = params;

  // Look up the paper's surrogate id, journal, and primary topic
  const metaRows = await query<PaperMeta>(
    `SELECT id, journal_id, primary_topic FROM papers WHERE openalex_id = $1`,
    [id]
  );

  if (metaRows.length === 0) {
    return NextResponse.json({ error: "Paper not found" }, { status: 404 });
  }

  const { id: paperId, journal_id, primary_topic } = metaRows[0];

  // Try: same journal AND same primary topic (if available)
  let relatedRows: RelatedRow[] = [];

  if (primary_topic) {
    relatedRows = await query<RelatedRow>(
      `SELECT
         p.openalex_id, p.title, p.publication_year, p.cited_by_count,
         p.is_oa, p.doi, p.primary_topic,
         j.id AS journal_id, j.display_name AS journal_name,
         j.scope_bucket AS journal_scope_bucket,
         j.tier_flag AS journal_tier_flag
       FROM papers p
       JOIN journals j ON j.id = p.journal_id
       WHERE p.journal_id = $1
         AND p.id != $2
         AND p.primary_topic = $3
       ORDER BY p.cited_by_count DESC
       LIMIT 8`,
      [journal_id, paperId, primary_topic]
    );
  }

  // Fall back to same-journal only if fewer than 8
  if (relatedRows.length < 8) {
    const exclude = [paperId, ...relatedRows.map(() => null)].filter(
      Boolean
    );
    // Re-query without topic constraint, excluding already found + self
    const foundIds =
      relatedRows.length > 0
        ? `AND p.openalex_id NOT IN (${relatedRows.map((_, i) => `$${i + 3}`).join(",")})`
        : "";
    const fallbackParams: (string | number)[] = [
      journal_id,
      paperId,
      ...relatedRows.map((r) => r.openalex_id),
    ];
    void exclude; // suppress unused warning

    const fallbackRows = await query<RelatedRow>(
      `SELECT
         p.openalex_id, p.title, p.publication_year, p.cited_by_count,
         p.is_oa, p.doi, p.primary_topic,
         j.id AS journal_id, j.display_name AS journal_name,
         j.scope_bucket AS journal_scope_bucket,
         j.tier_flag AS journal_tier_flag
       FROM papers p
       JOIN journals j ON j.id = p.journal_id
       WHERE p.journal_id = $1
         AND p.id != $2
         ${foundIds}
       ORDER BY p.cited_by_count DESC
       LIMIT ${8 - relatedRows.length}`,
      fallbackParams
    );

    relatedRows = [...relatedRows, ...fallbackRows];
  }

  const hits: PaperHit[] = relatedRows.map((r) => ({
    id: r.openalex_id,
    title: r.title,
    abstract_snippet: null,
    authors: [],
    journal_name: r.journal_name,
    journal_id: r.journal_id,
    publication_year: r.publication_year ?? 0,
    cited_by_count: r.cited_by_count,
    is_oa: r.is_oa ?? false,
    doi: r.doi,
    primary_topic: r.primary_topic,
    scope_bucket: r.journal_scope_bucket,
    tier: r.journal_tier_flag,
  }));

  return NextResponse.json(hits);
}
