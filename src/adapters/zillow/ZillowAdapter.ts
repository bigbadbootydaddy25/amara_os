/**
 * AMARA OS — Zillow Source Adapter
 * Playwright execution layer for Zillow.com
 * Intelligence is NOT here — this is a data collector only.
 *
 * Playbook:
 * 1. Navigate to zillow.com/homes
 * 2. Apply filters: for sale, price range, beds, property type, "price reduced", keywords
 * 3. Extract listing cards (address, price, DOM, beds, baths, sqft, remarks snippet)
 * 4. Paginate up to max pages
 * 5. For each listing: navigate to detail page, extract full remarks and price history
 * 6. Normalize to canonical schema
 */

import { BaseAdapter, AdapterConfig, RawProperty, AdapterSearchFilter } from "../base/BaseAdapter";
import { CanonicalDeal, DataSource, emptyDistress, emptyValuation, emptyUnderwriting, emptyBuyerLane, emptyCloseStrategy, PriceEvent } from "@/core/schema/canonical";
import { v4 as uuid } from "uuid";

// Zillow-specific raw field shape
interface ZillowRawProperty {
  id: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  listPrice: string;
  originalListPrice: string;
  beds: string;
  baths: string;
  sqft: string;
  lotSize: string;
  yearBuilt: string;
  daysOnMarket: string;
  dom: string;
  listingStatus: string;
  propertyType: string;
  zestimate: string;
  rentEstimate: string;
  remarks: string;
  priceHistory: Array<{ date: string; price: string; event: string }>;
  lat: string;
  lng: string;
  mlsId: string;
  listingAgent: string;
  listingBrokerage: string;
  photoUrl: string;
  detailUrl: string;
}

export class ZillowAdapter extends BaseAdapter {
  private browser: unknown = null;
  private page: unknown = null;

  constructor(config: Omit<AdapterConfig, "source">) {
    super({ ...config, source: "zillow" });
  }

  // ── FILTER CONFIGURATION ──────────────────────────────────────────────────
  // Zillow-specific distress filter keywords to inject into search
  static readonly DISTRESS_KEYWORDS = [
    "as-is", "fixer", "TLC", "needs work", "investor special",
    "motivated seller", "cash", "estate", "probate", "foreclosure",
  ];

  // Zillow search URL builder
  buildSearchUrl(filter: AdapterSearchFilter): string {
    const base = "https://www.zillow.com/homes";
    const params = new URLSearchParams({
      searchQueryState: JSON.stringify({
        pagination: { currentPage: 1 },
        filterState: {
          sort: { value: "days" },           // sort by days on market
          isForSaleByAgent: { value: true },
          isForSaleByOwner: { value: true },
          isNewConstruction: { value: false },
          ...(filter.priceReduced && { isRecentlySold: { value: false }, isPriceReduced: { value: true } }),
          ...(filter.minPrice && { price: { min: filter.minPrice } }),
          ...(filter.maxPrice && { price: { max: filter.maxPrice } }),
          ...(filter.minBeds && { beds: { min: filter.minBeds } }),
        },
        isMapVisible: false,
      }),
    });
    return `${base}?${params.toString()}`;
  }

  // ── PLAYWRIGHT EXECUTION ──────────────────────────────────────────────────
  async login(): Promise<void> {
    // Zillow does not require login for basic search
    // For full data access (owner info, full history) — session management needed
    console.log("[ZillowAdapter] No auth required for basic search mode");
  }

  async applyFilters(filter: AdapterSearchFilter): Promise<void> {
    // Filters are applied via URL params in buildSearchUrl()
    // Additional UI-based filters (age of listing, etc.) go here
    console.log(`[ZillowAdapter] Filters applied for market: ${filter.market}`);
  }

  async extractRawData(): Promise<RawProperty[]> {
    // In production: use Playwright to navigate, extract listing cards
    // Each card maps to ZillowRawProperty shape
    // This returns mock data for build validation — replace with Playwright logic
    return this.getMockData() as unknown as RawProperty[];
  }

  async handlePagination(): Promise<boolean> {
    // Click "next page" button, return false when exhausted
    return false;
  }

  async logout(): Promise<void> {
    // Clear session if needed
  }

  // ── NORMALIZATION ─────────────────────────────────────────────────────────
  normalizeToCanonical(raw: RawProperty): Partial<CanonicalDeal> {
    const r = raw as unknown as ZillowRawProperty;
    const now = new Date().toISOString();

    const listPrice = this.parsePrice(r.listPrice);
    const originalListPrice = this.parsePrice(r.originalListPrice);
    const avm = this.parsePrice(r.zestimate);
    const dom = this.safeNum(r.daysOnMarket ?? r.dom);

    // Price history
    const priceHistory: PriceEvent[] = (r.priceHistory ?? []).map((ph) => ({
      date: ph.date,
      price: this.parsePrice(ph.price) ?? 0,
      event: mapZillowPriceEvent(ph.event),
    }));

    const priceReductionCount = priceHistory.filter((p) => p.event === "REDUCED").length;
    const totalReduction = originalListPrice && listPrice && originalListPrice > listPrice
      ? (originalListPrice - listPrice) / originalListPrice
      : 0;

    return {
      id: uuid(),
      createdAt: now,
      updatedAt: now,
      lastScannedAt: now,
      sources: ["zillow"],
      primarySource: "zillow",
      sourceConfidence: "MEDIUM",
      sourceIds: { zillow: r.id, propstream: null, propelio: null, public_records: null, xleads: null, manual: null },
      sourceUrls: { zillow: r.detailUrl ?? null },

      address: r.address ?? "",
      city: r.city ?? "",
      state: r.state ?? "",
      zip: r.zip ?? "",
      county: "",
      apn: null,
      lat: this.safeNum(r.lat),
      lng: this.safeNum(r.lng),
      market: "",   // resolved by orchestrator based on zip/metro mapping

      propertyType: mapZillowPropertyType(r.propertyType),
      beds: this.safeNum(r.beds),
      baths: this.safeNum(r.baths),
      halfBaths: null,
      livingAreaSqft: this.safeNum(r.sqft),
      lotSizeSqft: this.safeNum(r.lotSize),
      lotSizeAcres: null,
      yearBuilt: this.safeNum(r.yearBuilt),
      stories: null,
      garage: null,
      pool: null,
      basement: null,

      ownerName: null,
      ownerMailingAddress: null,
      ownerPhone: null,
      ownerEmail: null,
      ownershipYears: null,
      lastSaleDate: null,
      lastSalePrice: null,
      estimatedEquity: null,
      estimatedEquityPct: null,
      mortgageBalance: null,

      occupancyStatus: "UNKNOWN",

      listingStatus: mapZillowListingStatus(r.listingStatus),
      listPrice,
      originalListPrice,
      dom,
      cdom: dom,
      listingDate: null,
      listingAgent: this.safeText(r.listingAgent),
      listingBrokerage: this.safeText(r.listingBrokerage),
      mls: null,
      mlsId: this.safeText(r.mlsId),
      remarks: this.safeText(r.remarks),
      priceHistory,

      valuation: {
        ...emptyValuation(),
        avm,
        avmSource: "zillow_zestimate",
        avmConfidence: avm ? "MEDIUM" : "LOW",
        rentEstimate: this.parsePrice(r.rentEstimate),
        rentEstimateSource: "zillow_zestimate",
      },

      // These will be populated by the engine layer
      distress: emptyDistress(),
      underwriting: emptyUnderwriting(),
      buyerLane: emptyBuyerLane(),
      closeStrategy: emptyCloseStrategy(),

      isQualifiedDeal: false,
      dealGateFailReasons: [],
      closeConfidence: "LOW",
      closeConfidenceScore: 0,
      nextAction: "",
      nextActionDueDate: null,
      accountabilityNote: null,
      dealLabel: "",
      urgencyFlag: null,
    };
  }

  // ── MOCK DATA (replace with real Playwright extraction) ───────────────────
  private getMockData(): ZillowRawProperty[] {
    return [
      {
        id: "z_dfw_001",
        address: "4821 Hickory Creek Dr",
        city: "Dallas",
        state: "TX",
        zip: "75228",
        listPrice: "185000",
        originalListPrice: "219000",
        beds: "3",
        baths: "2",
        sqft: "1480",
        lotSize: "7800",
        yearBuilt: "1965",
        daysOnMarket: "67",
        dom: "67",
        listingStatus: "For Sale",
        propertyType: "SingleFamily",
        zestimate: "228000",
        rentEstimate: "1450",
        remarks: "Priced to sell! Investor special — as-is. Needs some TLC. Bring all offers. Tenant occupied, do not disturb tenant. Estate sale. Great investment opportunity.",
        priceHistory: [
          { date: "2024-01-15", price: "219000", event: "Listed" },
          { date: "2024-02-20", price: "199000", event: "Price Change" },
          { date: "2024-03-10", price: "185000", event: "Price Change" },
        ],
        lat: "32.7767",
        lng: "-96.7970",
        mlsId: "20558441",
        listingAgent: "John Smith",
        listingBrokerage: "HomeStar Realty",
        photoUrl: "",
        detailUrl: "https://www.zillow.com/homedetails/4821-Hickory-Creek-Dr-Dallas-TX-75228/12345_zpid/",
      },
      {
        id: "z_dfw_002",
        address: "2211 Morrell Ave",
        city: "Fort Worth",
        state: "TX",
        zip: "76104",
        listPrice: "142000",
        originalListPrice: "165000",
        beds: "3",
        baths: "1",
        sqft: "1220",
        lotSize: "6200",
        yearBuilt: "1958",
        daysOnMarket: "91",
        dom: "91",
        listingStatus: "For Sale",
        propertyType: "SingleFamily",
        zestimate: "178000",
        rentEstimate: "1250",
        remarks: "Fixer-upper opportunity. Motivated seller. Vacant. Cash buyers preferred. Needs full interior update. ARV estimated $190K.",
        priceHistory: [
          { date: "2023-12-01", price: "165000", event: "Listed" },
          { date: "2024-01-15", price: "155000", event: "Price Change" },
          { date: "2024-02-28", price: "142000", event: "Price Change" },
        ],
        lat: "32.7204",
        lng: "-97.3208",
        mlsId: "20541872",
        listingAgent: "Maria Garcia",
        listingBrokerage: "Lone Star Investments",
        photoUrl: "",
        detailUrl: "https://www.zillow.com/homedetails/2211-Morrell-Ave-Fort-Worth-TX-76104/23456_zpid/",
      },
      {
        id: "z_phx_001",
        address: "8843 W Sherman St",
        city: "Phoenix",
        state: "AZ",
        zip: "85031",
        listPrice: "238000",
        originalListPrice: "279000",
        beds: "3",
        baths: "2",
        sqft: "1640",
        lotSize: "8500",
        yearBuilt: "1972",
        daysOnMarket: "82",
        dom: "82",
        listingStatus: "For Sale",
        propertyType: "SingleFamily",
        zestimate: "285000",
        rentEstimate: "1800",
        remarks: "Estate sale — sold as-is. Heirs selling. Property needs repairs and updating. Investor opportunity. Cash buyers only.",
        priceHistory: [
          { date: "2024-01-05", price: "279000", event: "Listed" },
          { date: "2024-02-10", price: "259000", event: "Price Change" },
          { date: "2024-03-05", price: "238000", event: "Price Change" },
        ],
        lat: "33.4484",
        lng: "-112.0740",
        mlsId: "AZ20558900",
        listingAgent: "Robert Chen",
        listingBrokerage: "Desert Investment Realty",
        photoUrl: "",
        detailUrl: "https://www.zillow.com/homedetails/8843-W-Sherman-St-Phoenix-AZ-85031/34567_zpid/",
      },
    ];
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// MAPPING HELPERS
// ─────────────────────────────────────────────────────────────────────────────
function mapZillowPropertyType(type: string): CanonicalDeal["propertyType"] {
  const map: Record<string, CanonicalDeal["propertyType"]> = {
    SingleFamily: "SFR",
    SINGLE_FAMILY: "SFR",
    Condo: "CONDO",
    CONDO: "CONDO",
    MultiFamily: "MFR",
    MULTI_FAMILY: "MFR",
    Townhouse: "TOWNHOUSE",
    TOWNHOUSE: "TOWNHOUSE",
    MobileHome: "MOBILE",
    Land: "LAND",
    LAND: "LAND",
  };
  return map[type] ?? "UNKNOWN";
}

function mapZillowListingStatus(status: string): CanonicalDeal["listingStatus"] {
  const map: Record<string, CanonicalDeal["listingStatus"]> = {
    "For Sale": "ACTIVE",
    Active: "ACTIVE",
    Pending: "PENDING",
    Sold: "SOLD",
    "Off Market": "OFF_MARKET",
  };
  return map[status] ?? "UNKNOWN";
}

function mapZillowPriceEvent(event: string): PriceEvent["event"] {
  const lower = event.toLowerCase();
  if (lower.includes("list") || lower.includes("new")) return "LISTED";
  if (lower.includes("reduc") || lower.includes("decreas") || (lower.includes("price") && lower.includes("change"))) return "REDUCED";
  if (lower.includes("increas")) return "INCREASED";
  if (lower.includes("sold")) return "SOLD";
  if (lower.includes("relist")) return "RELISTED";
  return "REDUCED";
}
