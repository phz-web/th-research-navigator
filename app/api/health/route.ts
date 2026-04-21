import { NextResponse } from "next/server";
import { getPool } from "@/lib/server/db";
import { getTypesense } from "@/lib/server/typesense";
import type { HealthResponse } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse<HealthResponse>> {
  let dbStatus: "ok" | "down" = "down";
  let tsStatus: "ok" | "down" = "down";

  // Check PostgreSQL
  try {
    const pool = getPool();
    const client = await pool.connect();
    await client.query("SELECT 1");
    client.release();
    dbStatus = "ok";
  } catch {
    dbStatus = "down";
  }

  // Check Typesense
  try {
    const ts = getTypesense();
    await ts.health.retrieve();
    tsStatus = "ok";
  } catch {
    tsStatus = "down";
  }

  return NextResponse.json({
    status: "ok",
    db: dbStatus,
    typesense: tsStatus,
    ts: new Date().toISOString(),
  });
}
