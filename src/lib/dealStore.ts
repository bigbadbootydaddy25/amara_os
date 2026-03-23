/**
 * AMARA OS — Deal Store
 * In-memory deal store for MVP. Replace with Supabase/Postgres in production.
 * Stores only QUALIFIED deals — deals that passed all gates.
 */

import { CanonicalDeal } from "@/core/schema/canonical";
import { scoredDeals } from "./seedDeals";

let _deals: CanonicalDeal[] = [...scoredDeals];

export const dealStore = {
  getAll(): CanonicalDeal[] {
    return _deals.filter((d) => d.isQualifiedDeal);
  },

  getById(id: string): CanonicalDeal | null {
    return _deals.find((d) => d.id === id) ?? null;
  },

  getByMarket(market: string): CanonicalDeal[] {
    return _deals.filter((d) => d.isQualifiedDeal && d.market.toLowerCase() === market.toLowerCase());
  },

  getStats() {
    const qualified = _deals.filter((d) => d.isQualifiedDeal);
    const hot = qualified.filter((d) => d.urgencyFlag === "HOT").length;
    const warm = qualified.filter((d) => d.urgencyFlag === "WARM").length;
    const totalSpread = qualified.reduce((s, d) => s + (d.underwriting.projectedSpread ?? 0), 0);
    const markets = [...new Set(qualified.map((d) => d.market))];

    return {
      totalDeals: qualified.length,
      hotDeals: hot,
      warmDeals: warm,
      totalPotentialSpread: totalSpread,
      activeMarkets: markets.length,
      topMarket: markets[0] ?? "—",
      lastUpdated: new Date().toISOString(),
    };
  },

  upsert(deal: CanonicalDeal): void {
    const idx = _deals.findIndex((d) => d.id === deal.id);
    if (idx >= 0) {
      _deals[idx] = deal;
    } else {
      _deals.push(deal);
    }
  },

  replace(deals: CanonicalDeal[]): void {
    _deals = deals;
  },
};
