/**
 * AMARA OS — Canonical Property & Deal Schema
 * Every source adapter normalizes into this shape.
 * This is the single truth layer for the entire deal engine.
 */

export type DataSource =
  | "zillow"
  | "propstream"
  | "propelio"
  | "public_records"
  | "xleads"
  | "manual";

export type PropertyType =
  | "SFR"        // single-family residential
  | "MFR"        // multi-family residential
  | "CONDO"
  | "TOWNHOUSE"
  | "MOBILE"
  | "LAND"       // raw land
  | "LOT"        // platted lot
  | "COMMERCIAL"
  | "MIXED"
  | "UNKNOWN";

export type ListingStatus =
  | "ACTIVE"
  | "PENDING"
  | "SOLD"
  | "OFF_MARKET"
  | "WITHDRAWN"
  | "EXPIRED"
  | "UNKNOWN";

export type OccupancyStatus =
  | "OWNER_OCCUPIED"
  | "TENANT_OCCUPIED"
  | "VACANT"
  | "UNKNOWN";

export type DealType =
  | "WHOLESALE_ASSIGNMENT"
  | "FLIP"
  | "BRRRR"
  | "LAND_SUBDIVISION"
  | "DEAD_PAPER"
  | "CREATIVE_FINANCE"
  | "UNKNOWN";

export type ExitStrategy =
  | "ASSIGN_TO_FLIPPER"
  | "ASSIGN_TO_LANDLORD"
  | "ASSIGN_TO_DEVELOPER"
  | "DOUBLE_CLOSE"
  | "FLIP_RETAIL"
  | "FLIP_INVESTOR"
  | "BRRRR_HOLD"
  | "LAND_DEVELOP"
  | "LAND_SPLIT"
  | "LAND_ASSIGN"
  | "UNKNOWN";

export type CloseConfidence = "HIGH" | "MEDIUM" | "LOW";
export type SourceConfidence = "HIGH" | "MEDIUM" | "LOW";

// ─────────────────────────────────────────────────────────────────────────────
// DISTRESS SIGNALS
// ─────────────────────────────────────────────────────────────────────────────
export interface DistressSignals {
  // Listing signals
  priceReduced: boolean;
  priceReductionCount: number;
  priceReductionTotalPct: number;     // e.g. 0.12 = 12% total reduction
  domBucket: "FRESH" | "30+" | "45+" | "60+" | "90+" | "120+" | "180+";
  domDays: number;
  distressKeywordsFound: string[];    // exact keywords matched
  keywordDistressScore: number;       // 0–100

  // Ownership signals
  absenteeOwner: boolean;
  outOfStateOwner: boolean;
  corporateOwner: boolean;
  taxDelinquent: boolean;
  taxDelinquentAmountUSD: number | null;
  preforeclosure: boolean;
  foreclosure: boolean;
  auction: boolean;
  lis_pendens: boolean;

  // Property condition signals
  probate: boolean;
  estate: boolean;
  inherited: boolean;
  codeViolation: boolean;
  permit_activity: boolean;           // permit activity = rehabber alert

  // Occupancy signals
  vacancy: boolean;
  tenantOccupied: boolean;
  landlordFatigue: boolean;           // derived: absentee + long DOM + reduced

  // Public record enrichment
  liens: boolean;
  lienCount: number;
  openLienAmountUSD: number | null;

  // Composite distress score
  totalDistressScore: number;         // 0–100
}

// ─────────────────────────────────────────────────────────────────────────────
// PRICE HISTORY
// ─────────────────────────────────────────────────────────────────────────────
export interface PriceEvent {
  date: string;       // ISO date
  price: number;
  event: "LISTED" | "REDUCED" | "INCREASED" | "SOLD" | "RELISTED";
}

// ─────────────────────────────────────────────────────────────────────────────
// VALUATION
// ─────────────────────────────────────────────────────────────────────────────
export interface Valuation {
  avm: number | null;                   // automated valuation model (Zestimate etc.)
  avmSource: string | null;
  avmConfidence: SourceConfidence;

  arvEstimate: number | null;           // after-repair value
  arvLow: number | null;
  arvHigh: number | null;
  arvConfidence: SourceConfidence;
  arvCompsUsed: number;

  asIsEstimate: number | null;          // value as-is, no rehab
  asIsLow: number | null;
  asIsHigh: number | null;

  investorResaleEstimate: number | null; // what an investor buyer will pay
  investorResaleLow: number | null;
  investorResaleHigh: number | null;

  rentEstimate: number | null;
  rentEstimateSource: string | null;

  rehabEstimate: number | null;         // estimated rehab cost
  rehabLow: number | null;
  rehabHigh: number | null;
  rehabGrade: "LIPSTICK" | "COSMETIC" | "MODERATE" | "FULL_GUT" | "UNKNOWN";

  // Land-specific
  landDevelopmentValue: number | null;
  finishedLotValue: number | null;
  developmentRiskScore: number | null;  // 0–100
}

// ─────────────────────────────────────────────────────────────────────────────
// UNDERWRITING OUTPUT
// ─────────────────────────────────────────────────────────────────────────────
export interface UnderwritingResult {
  dealType: DealType;
  exitStrategy: ExitStrategy;

  buyerResaleMax: number | null;
  assignmentFee: number | null;
  mao: number | null;                   // maximum allowable offer to seller

  // Deal economics
  projectedSpread: number | null;       // gross spread = buyerResaleMax - mao
  projectedProfit: number | null;       // = assignmentFee (after costs)
  flipProfit: number | null;
  flipROI: number | null;               // 0.0–1.0

  // Costs used in calculation
  holdingCosts: number | null;
  closingCostsBuy: number | null;
  closingCostsSell: number | null;
  flipperMarginTarget: number | null;   // e.g. 0.15 = 15%

  // Validation
  meetsMinimumFee: boolean;             // >= $10k for SFR
  feeSurplus: number | null;            // how much over minimum
  passesUnderwriting: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// BUYER LANE
// ─────────────────────────────────────────────────────────────────────────────
export interface BuyerLane {
  buyerClass: "FLIPPER" | "LANDLORD" | "DEVELOPER" | "OWNER_OCCUPANT" | "UNKNOWN";
  exitConfidence: CloseConfidence;
  exitConfidenceScore: number;          // 0–100

  matchedBuyerZIPs: string[];           // ZIP codes with active buyer behavior
  matchedBuyerCount: number;
  topBuyerProfileIds: string[];         // internal buyer profile IDs

  estimatedDaysToAssign: number | null; // how fast can we move it?
  weeklyClosingPotential: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// CLOSE STRATEGY
// ─────────────────────────────────────────────────────────────────────────────
export interface CloseStrategy {
  sellerPainProfile: string;
  likelyMotivation: string;
  negotiationAngle: string;
  openingApproach: string;
  anchorPriceLogic: string;
  objectionResponse: string;           // response to "that's too low"
  followUpSchedule: string;
  walkAwayTrigger: string;
  coachingNote: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// CANONICAL PROPERTY / DEAL RECORD
// ─────────────────────────────────────────────────────────────────────────────
export interface CanonicalDeal {
  // ── Identity ──────────────────────────────────────────────────────────────
  id: string;
  createdAt: string;            // ISO timestamp
  updatedAt: string;
  lastScannedAt: string;

  // ── Source Provenance ─────────────────────────────────────────────────────
  sources: DataSource[];
  primarySource: DataSource;
  sourceConfidence: SourceConfidence;
  sourceIds: Record<DataSource, string | null>;   // source-internal IDs
  sourceUrls: Record<string, string | null>;

  // ── Location ──────────────────────────────────────────────────────────────
  address: string;
  city: string;
  state: string;
  zip: string;
  county: string;
  apn: string | null;           // assessor parcel number
  lat: number | null;
  lng: number | null;
  market: string;               // AMARA market label (e.g. "DFW", "Phoenix", etc.)

  // ── Property Characteristics ──────────────────────────────────────────────
  propertyType: PropertyType;
  beds: number | null;
  baths: number | null;
  halfBaths: number | null;
  livingAreaSqft: number | null;
  lotSizeSqft: number | null;
  lotSizeAcres: number | null;
  yearBuilt: number | null;
  stories: number | null;
  garage: boolean | null;
  pool: boolean | null;
  basement: boolean | null;

  // ── Ownership ─────────────────────────────────────────────────────────────
  ownerName: string | null;
  ownerMailingAddress: string | null;
  ownerPhone: string | null;
  ownerEmail: string | null;
  ownershipYears: number | null;       // derived from deed date
  lastSaleDate: string | null;
  lastSalePrice: number | null;
  estimatedEquity: number | null;
  estimatedEquityPct: number | null;
  mortgageBalance: number | null;

  // ── Occupancy ─────────────────────────────────────────────────────────────
  occupancyStatus: OccupancyStatus;

  // ── Listing Details ───────────────────────────────────────────────────────
  listingStatus: ListingStatus;
  listPrice: number | null;
  originalListPrice: number | null;
  dom: number | null;
  cdom: number | null;               // cumulative DOM across relistings
  listingDate: string | null;
  listingAgent: string | null;
  listingBrokerage: string | null;
  mls: string | null;
  mlsId: string | null;
  remarks: string | null;            // full listing remarks text
  priceHistory: PriceEvent[];

  // ── Distress Layer ────────────────────────────────────────────────────────
  distress: DistressSignals;

  // ── Valuation Layer ───────────────────────────────────────────────────────
  valuation: Valuation;

  // ── Underwriting Layer ────────────────────────────────────────────────────
  underwriting: UnderwritingResult;

  // ── Buyer Lane ────────────────────────────────────────────────────────────
  buyerLane: BuyerLane;

  // ── Close Strategy ────────────────────────────────────────────────────────
  closeStrategy: CloseStrategy;

  // ── Deal Gate ─────────────────────────────────────────────────────────────
  isQualifiedDeal: boolean;
  dealGateFailReasons: string[];
  closeConfidence: CloseConfidence;
  closeConfidenceScore: number;      // 0–100

  // ── Action Items ──────────────────────────────────────────────────────────
  nextAction: string;
  nextActionDueDate: string | null;
  accountabilityNote: string | null;

  // ── Deal Display Meta ─────────────────────────────────────────────────────
  dealLabel: string;                 // e.g. "WHOLESALE — DFW — $18K SPREAD"
  urgencyFlag: "HOT" | "WARM" | "WATCH" | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// EMPTY / DEFAULT FACTORIES
// ─────────────────────────────────────────────────────────────────────────────
export function emptyDistress(): DistressSignals {
  return {
    priceReduced: false,
    priceReductionCount: 0,
    priceReductionTotalPct: 0,
    domBucket: "FRESH",
    domDays: 0,
    distressKeywordsFound: [],
    keywordDistressScore: 0,
    absenteeOwner: false,
    outOfStateOwner: false,
    corporateOwner: false,
    taxDelinquent: false,
    taxDelinquentAmountUSD: null,
    preforeclosure: false,
    foreclosure: false,
    auction: false,
    lis_pendens: false,
    probate: false,
    estate: false,
    inherited: false,
    codeViolation: false,
    permit_activity: false,
    vacancy: false,
    tenantOccupied: false,
    landlordFatigue: false,
    liens: false,
    lienCount: 0,
    openLienAmountUSD: null,
    totalDistressScore: 0,
  };
}

export function emptyValuation(): Valuation {
  return {
    avm: null,
    avmSource: null,
    avmConfidence: "LOW",
    arvEstimate: null,
    arvLow: null,
    arvHigh: null,
    arvConfidence: "LOW",
    arvCompsUsed: 0,
    asIsEstimate: null,
    asIsLow: null,
    asIsHigh: null,
    investorResaleEstimate: null,
    investorResaleLow: null,
    investorResaleHigh: null,
    rentEstimate: null,
    rentEstimateSource: null,
    rehabEstimate: null,
    rehabLow: null,
    rehabHigh: null,
    rehabGrade: "UNKNOWN",
    landDevelopmentValue: null,
    finishedLotValue: null,
    developmentRiskScore: null,
  };
}

export function emptyUnderwriting(): UnderwritingResult {
  return {
    dealType: "UNKNOWN",
    exitStrategy: "UNKNOWN",
    buyerResaleMax: null,
    assignmentFee: null,
    mao: null,
    projectedSpread: null,
    projectedProfit: null,
    flipProfit: null,
    flipROI: null,
    holdingCosts: null,
    closingCostsBuy: null,
    closingCostsSell: null,
    flipperMarginTarget: null,
    meetsMinimumFee: false,
    feeSurplus: null,
    passesUnderwriting: false,
  };
}

export function emptyBuyerLane(): BuyerLane {
  return {
    buyerClass: "UNKNOWN",
    exitConfidence: "LOW",
    exitConfidenceScore: 0,
    matchedBuyerZIPs: [],
    matchedBuyerCount: 0,
    topBuyerProfileIds: [],
    estimatedDaysToAssign: null,
    weeklyClosingPotential: false,
  };
}

export function emptyCloseStrategy(): CloseStrategy {
  return {
    sellerPainProfile: "",
    likelyMotivation: "",
    negotiationAngle: "",
    openingApproach: "",
    anchorPriceLogic: "",
    objectionResponse: "",
    followUpSchedule: "",
    walkAwayTrigger: "",
    coachingNote: "",
  };
}
