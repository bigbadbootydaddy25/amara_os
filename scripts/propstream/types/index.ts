// ─────────────────────────────────────────────────────────────────────────────
// PropStream Scraper — shared type definitions
// ─────────────────────────────────────────────────────────────────────────────

export type LeadListName =
  | "Auctions"
  | "Bank Owned"
  | "Bankruptcy"
  | "Cash Buyers"
  | "Divorce"
  | "Failed Listings"
  | "Flippers"
  | "Free & Clear"
  | "High Equity"
  | "Liens"
  | "On Market"
  | "Pre-Foreclosures"
  | "Pre-Probate"
  | "Senior Owners"
  | "Tax Delinquency"
  | "Tired Landlords"
  | "Upside Down"
  | "Vacant"
  | "Vacant Land";

export type LandClassification =
  | "infill_lot"
  | "vacant_land"
  | "finished_lot"
  | "paper_lot"
  | "stalled_subdivision"
  | "dead_paper_subdivision"
  | "ghost_subdivision"
  | "builder_edge_expansion"
  | "expiring_tentative_map";

// Raw record straight off the DOM — captures every visible column
export interface RawRecord {
  listType: LeadListName;
  rowIndex: number;
  fields: Record<string, string>; // header -> cell text
  incomplete: boolean;
  scrapedAt: string; // ISO timestamp
  sourceUrl: string;
}

// Normalised after first-pass parsing
export interface NormalisedRecord {
  listType: LeadListName;
  address: string;
  city: string;
  state: string;
  zip: string;
  county?: string;
  apn?: string;
  ownerName?: string;
  ownerEntityName?: string;
  propertyType?: string;
  yearBuilt?: number;
  price?: number;           // list price or estimated value
  assessedValue?: number;
  equity?: number;
  equityPct?: number;
  mortgageBalance?: number;
  lotSizeRaw?: string;
  acreage?: number;
  lotCount?: number;
  zoning?: string;
  recordingDate?: string;
  approvalDate?: string;
  taxDelinquentAmount?: number;
  taxDelinquentYear?: number;
  distressIndicators: string[];
  permitActivity?: boolean;
  incomplete: boolean;
  raw: RawRecord;
}

// ─── SFR Track ────────────────────────────────────────────────────────────────

export interface SFRTarget {
  address: string;
  zip: string;
  city: string;
  state: string;
  propertyType: string;
  price: number | null;
  assessedValue: number | null;
  listType: LeadListName;
  recordingDate: string | null;
  yearBuilt: number | null;
  distressIndicators: string[];
  ownerName: string | null;
  incomplete: boolean;
  tier: "tier1" | "tier2";
  market: string;
}

// ─── Land Track ───────────────────────────────────────────────────────────────

export interface LandTarget {
  address: string;
  apn: string | null;
  zip: string;
  county: string | null;
  city: string;
  state: string;
  lotSizeRaw: string | null;
  acreage: number | null;
  lotCount: number | null;
  zoning: string | null;
  classification: LandClassification;
  distressType: string;
  distressSignals: string[];
  ownerEntityName: string | null;
  price: number | null;
  assessedValue: number | null;
  approvalDate: string | null;
  permitActivity: boolean | null;
  listType: LeadListName;
  incomplete: boolean;
  tier: "tier1" | "tier2" | "priority_corridor";
  market: string;
}

export interface DeadPaperTarget extends LandTarget {
  classification:
    | "dead_paper_subdivision"
    | "ghost_subdivision"
    | "stalled_subdivision"
    | "expiring_tentative_map";
  daysToExpiry: number | null;
  urgencyScore: number;
  urgencyReason: string;
}

export interface GhostSubdivisionTarget extends LandTarget {
  classification: "ghost_subdivision";
  recordedPlatDate: string | null;
  permitsConfirmed: false;
  urgencyScore: number;
}

// ─── Buyer Profiles ───────────────────────────────────────────────────────────

export interface SFRBuyer {
  buyerName: string;
  entityType: string | null;
  activeZips: string[];
  propertyTypes: string[];
  priceRangeMin: number | null;
  priceRangeMax: number | null;
  transactionCount: number;
  mostRecentPurchase: string | null;
  markets: string[];
}

export interface LandBuyer {
  buyerName: string;
  entityType: string | null;
  activeZips: string[];
  landTypes: string[];
  lotSizeMin: number | null;   // acres
  lotSizeMax: number | null;
  priceRangeMin: number | null;
  priceRangeMax: number | null;
  transactionCount: number;
  mostRecentPurchase: string | null;
  markets: string[];
}

// ─── Match Board ──────────────────────────────────────────────────────────────

export interface SFRMatch {
  property: SFRTarget;
  matchedBuyers: SFRBuyer[];
  matchScore: number;         // 0-100
  matchReasons: string[];
  zip: string;
  market: string;
}

export interface BuilderMatch {
  property: LandTarget;
  matchedBuyers: LandBuyer[];
  urgencyScore: number;
  urgencyReason: string;
  matchScore: number;
  matchReasons: string[];
  zip: string;
  market: string;
  flagForImmediateAction: boolean;
}

// ─── Scraper internal ─────────────────────────────────────────────────────────

export interface ScrapeSession {
  startedAt: string;
  listsCompleted: LeadListName[];
  listsFailed: LeadListName[];
  totalRecords: number;
  errors: Array<{ list: LeadListName; message: string; page?: number }>;
}

export interface PageResult {
  records: RawRecord[];
  hasNextPage: boolean;
  currentPage: number;
  totalPages: number | null;
}

export interface DOMSelectors {
  listTableRows: string;
  listTableHeaders: string;
  paginationNext: string;
  paginationCurrent: string;
  paginationTotal: string;
  listItemLinks: string;
  listSearchInput: string;
  noResultsIndicator: string;
}
