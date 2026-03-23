/**
 * GET /api/scan/status — Real-time scan status for Mission Control
 */

import { NextResponse } from "next/server";
import { getScanStatus } from "@/core/scan/scanOrchestrator";

export async function GET() {
  const { isRunning, session } = getScanStatus();

  if (!session) {
    return NextResponse.json({
      isRunning: false,
      session: null,
      summary: "No scan has run yet — trigger a scan to start finding deals",
    });
  }

  const summary = {
    isRunning,
    sessionId: session.sessionId,
    status: session.status,
    startedAt: session.startedAt,
    completedAt: session.completedAt,
    marketsScanned: session.marketsScanned,
    totalMarkets: session.marketStates.length,
    totalListings: session.totalListings,
    totalDealsQualified: session.totalDealsQualified,
    marketBreakdown: session.marketStates.map(ms => ({
      marketId: ms.marketId,
      label: ms.label,
      status: ms.status,
      listingsFound: ms.listingsFound,
      dealsQualified: ms.dealsQualified,
      lastError: ms.lastError,
    })),
  };

  return NextResponse.json(summary);
}
