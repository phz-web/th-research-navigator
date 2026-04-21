import { NextRequest, NextResponse } from "next/server";
import { ZodError } from "zod";
import { getTypesense } from "@/lib/server/typesense";
import {
  PapersQuerySchema,
  type PapersQuery,
} from "@/lib/server/validation";
import {
  mapPaperHit,
  mapPaperFacets,
  type RawPaperDoc,
} from "@/lib/server/search-mappers";
import type { PapersResponse } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function buildFilterBy(params: PapersQuery): string {
  const clauses: string[] = [];

  if (params.year_min !== undefined && params.year_max !== undefined) {
    clauses.push(
      `publication_year:>=${params.year_min} && publication_year:<=${params.year_max}`
    );
  } else if (params.year_min !== undefined) {
    clauses.push(`publication_year:>=${params.year_min}`);
  } else if (params.year_max !== undefined) {
    clauses.push(`publication_year:<=${params.year_max}`);
  }

  if (params.journal_id && params.journal_id.length > 0) {
    const ids = params.journal_id.map((id) => Number(id));
    clauses.push(`journal_id:[${ids.join(",")}]`);
  }

  if (params.scope_bucket && params.scope_bucket.length > 0) {
    clauses.push(
      `journal_scope_bucket:[${params.scope_bucket.join(",")}]`
    );
  }

  if (params.is_oa !== undefined) {
    clauses.push(`is_oa:${params.is_oa === "true"}`);
  }

  if (params.tier !== undefined) {
    clauses.push(`journal_tier:${params.tier}`);
  }

  return clauses.join(" && ");
}

function buildSortBy(params: PapersQuery): string {
  const sort = params.sort ?? (params.q ? "relevance" : "year_desc");

  switch (sort) {
    case "year_desc":
      return "publication_year:desc,cited_by_count:desc";
    case "year_asc":
      return "publication_year:asc,cited_by_count:desc";
    case "citations_desc":
      return "cited_by_count:desc,publication_year:desc";
    case "relevance":
    default:
      return "_text_match:desc,cited_by_count:desc";
  }
}

export async function GET(
  request: NextRequest
): Promise<NextResponse<PapersResponse | { error: string; details?: unknown }>> {
  const searchParams = Object.fromEntries(request.nextUrl.searchParams.entries());

  // Handle multi-value params (journal_id, scope_bucket)
  const rawParams: Record<string, string | string[]> = { ...searchParams };
  for (const key of ["journal_id", "scope_bucket"]) {
    const all = request.nextUrl.searchParams.getAll(key);
    if (all.length > 1) rawParams[key] = all;
  }

  let params: PapersQuery;
  try {
    params = PapersQuerySchema.parse(rawParams);
  } catch (err) {
    if (err instanceof ZodError) {
      return NextResponse.json(
        { error: "Invalid query parameters", details: err.errors },
        { status: 400 }
      );
    }
    throw err;
  }

  const q = params.q ?? "";
  const useWildcard = !q;

  const filterBy = buildFilterBy(params);
  const sortBy = buildSortBy(params);

  try {
    const ts = getTypesense();

    const searchParams: Record<string, string | number | boolean> = {
      q: useWildcard ? "*" : q,
      query_by: useWildcard
        ? "title"
        : "title,abstract,authors_text,journal_name",
      per_page: params.per_page,
      page: params.page,
      sort_by: sortBy,
      facet_by:
        "publication_year,journal_name,journal_scope_bucket,journal_tier,is_oa",
      max_facet_values: 30,
    };

    if (!useWildcard) {
      searchParams["query_by_weights"] = "8,2,3,2";
    }

    if (filterBy) {
      searchParams["filter_by"] = filterBy;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await (ts.collections("papers").documents() as any).search(
      searchParams
    );

    const hits = (result.hits ?? []).map(
      (h: { document: RawPaperDoc }) => mapPaperHit(h.document)
    );
    const facets = mapPaperFacets(result.facet_counts);

    return NextResponse.json({
      hits,
      total: result.found ?? 0,
      page: params.page,
      per_page: params.per_page,
      facets,
    });
  } catch (err) {
    console.error("[api/papers] Typesense error:", err);
    return NextResponse.json(
      { error: "Search service unavailable" },
      { status: 502 }
    );
  }
}
