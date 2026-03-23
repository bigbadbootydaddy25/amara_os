/**
 * POST /api/scan — Trigger autonomous market scan
 * AMARA scans all (or specified) markets and surfaces qualified deals.
 */

import { NextRequest, NextResponse } from "next/server";
import { getScanStatus } from "@/core/scan/scanOrchestrator";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const { tierFilter, marketIds, maxMarkets } = body as {
    tierFilter?: string;
    marketIds?: string[];
    maxMarkets?: number;
  };

  const { isRunning } = getScanStatus();
  if (isRunning) {
    return NextResponse.json(
      { error: "Scan already in progress", status: "RUNNING" },
      { status: 409 }
    );
  }

  // Fire-and-forget — scan runs in background
  // In production this would be a queue job
  const { runFullMarketScan } = await import("@/core/scan/scanOrchestrator");

  // Start scan without awaiting (background process)
  runFullMarketScan({ tierFilter, marketIds, maxMarkets }).catch(err => {
    console.error("[AMARA:API/scan] Scan error:", err);
  });

  return NextResponse.json({
    message: "Scan initiated — AMARA is scanning all markets",
    status: "STARTED",
    tierFilter: tierFilter ?? "ALL",
    marketsQueued: marketIds?.length ?? 37,
  });
}

export async function GET() {
  const { isRunning, session } = getScanStatus();
  return NextResponse.json({ isRunning, session });
}
