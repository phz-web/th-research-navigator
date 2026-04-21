import { NextRequest, NextResponse } from "next/server";
import { ZodError } from "zod";
import { getTypesense } from "@/lib/server/typesense";
import { AuthorsQuerySchema, type AuthorsQuery } from "@/lib/server/validation";
import { mapAuthorHit, type RawAuthorDoc } from "@/lib/server/search-mappers";
import type { AuthorsResponse } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function buildAuthorSortBy(params: AuthorsQuery): string {
  switch (params.sort) {
    case "works_desc":
      return "works_count:desc,cited_by_count:desc";
    case "citations_desc":
      return "cited_by_count:desc,works_count:desc";
    case "relevance":
    default:
      return "_text_match:desc,cited_by_count:desc";
  }
}

export async function GET(
  request: NextRequest
): Promise<NextResponse<AuthorsResponse | { error: string; details?: unknown }>> {
  const searchParams = Object.fromEntries(request.nextUrl.searchParams.entries());

  let params: AuthorsQuery;
  try {
    params = AuthorsQuerySchema.parse(searchParams);
  } catch (err) {
    if (err instanceof ZodError) {
      return NextResponse.json(
        { error: "Invalid query parameters", details: err.errors },
        { status: 400 }
      );
    }
    throw err;
  }

  try {
    const ts = getTypesense();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await (ts.collections("authors").documents() as any).search({
      q: params.q,
      query_by: "display_name,normalized_name",
      per_page: params.per_page,
      page: params.page,
      sort_by: buildAuthorSortBy(params),
    });

    const hits = (result.hits ?? []).map(
      (h: { document: RawAuthorDoc }) => mapAuthorHit(h.document)
    );

    return NextResponse.json({
      hits,
      total: result.found ?? 0,
      page: params.page,
      per_page: params.per_page,
    });
  } catch (err) {
    console.error("[api/authors] Typesense error:", err);
    return NextResponse.json(
      { error: "Search service unavailable" },
      { status: 502 }
    );
  }
}
