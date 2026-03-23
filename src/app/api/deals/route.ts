import { NextResponse } from "next/server";
import { dealStore } from "@/lib/dealStore";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const market = searchParams.get("market");
  const urgency = searchParams.get("urgency");

  let deals = market ? dealStore.getByMarket(market) : dealStore.getAll();

  if (urgency) {
    deals = deals.filter((d) => d.urgencyFlag === urgency.toUpperCase());
  }

  return NextResponse.json({ deals, count: deals.length });
}
