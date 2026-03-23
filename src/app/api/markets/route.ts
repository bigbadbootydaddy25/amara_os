import { NextResponse } from "next/server";
import { SEEDED_MARKET_SCORES, getBestMarketForWeeklyClosings } from "@/core/engines/market/marketSelector";

export async function GET() {
  const best = getBestMarketForWeeklyClosings();
  return NextResponse.json({
    markets: SEEDED_MARKET_SCORES,
    bestMarket: best,
    count: SEEDED_MARKET_SCORES.length,
  });
}
