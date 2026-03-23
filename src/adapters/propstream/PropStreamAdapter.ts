/**
 * AMARA OS — PropStream Source Adapter
 * PropStream is the gold standard for owner data, public records, distress flags.
 * This adapter enriches Zillow data with ownership, liens, foreclosure, tax data.
 *
 * Playbook:
 * 1. Login to app.propstream.com
 * 2. Navigate to Property Search
 * 3. Apply filters: property type, status, owner type (absentee), distress flags
 * 4. Export or paginate through results
 * 5. For each property: extract owner info, equity, liens, distress flags
 * 6. Normalize and merge into canonical schema
 */

import { BaseAdapter, AdapterConfig, RawProperty, AdapterSearchFilter } from "../base/BaseAdapter";
import { CanonicalDeal, DataSource } from "@/core/schema/canonical";
import { v4 as uuid } from "uuid";

interface PropStreamRawProperty {
  // Property
  apn: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  county: string;
  propertyType: string;
  beds: string;
  baths: string;
  sqft: string;
  lotSizeSqft: string;
  yearBuilt: string;
  lat: string;
  lng: string;

  // Owner
  ownerName: string;
  ownerMailingAddress: string;
  ownerCity: string;
  ownerState: string;
  ownerZip: string;
  ownerPhone: string;
  ownerEmail: string;
  isAbsenteeOwner: string;           // "Y" / "N"
  isOutOfState: string;
  isCorporateOwner: string;
  lastSaleDate: string;
  lastSalePrice: string;
  estimatedValue: string;
  estimatedEquity: string;
  estimatedEquityPct: string;
  mortgageBalance: string;
  ownershipYears: string;

  // Distress / Public Record
  isTaxDelinquent: string;
  taxDelinquentAmount: string;
  isPreforeclosure: string;
  isForeclosure: string;
  isAuction: string;
  isProbate: string;
  isVacant: string;
  hasLiens: string;
  lienCount: string;
  openLienAmount: string;
  isCodeViolation: string;

  // Listing (may overlap with Zillow)
  listingStatus: string;
  listPrice: string;
  dom: string;
  mlsId: string;

  // AVM
  avm: string;
  rentEstimate: string;
}

export class PropStreamAdapter extends BaseAdapter {
  private browser: unknown = null;
  private page: unknown = null;
  private sessionToken: string | null = null;

  // PropStream filter presets for distress sourcing
  static readonly PROPSTREAM_DISTRESS_FILTERS = {
    ownerTypes: ["Absentee Owner", "Out of State Owner", "Corporate Owner"],
    distressTypes: [
      "Tax Delinquent",
      "Pre-Foreclosure",
      "Foreclosure",
      "Auction",
      "Probate",
      "Vacant",
      "Code Violation",
      "Liens",
    ],
    listingStatus: ["For Sale", "Off Market"],  // PropStream finds off-market too
    propertyTypes: ["SFR", "Multi-Family 2-4", "Condo", "Townhouse"],
    equityRange: { min: 20, max: 100 },         // % equity — target equity-heavy owners
    yearBuiltMax: 1995,                          // older stock
  };

  constructor(config: Omit<AdapterConfig, "source">) {
    super({ ...config, source: "propstream" });
  }

  async login(): Promise<void> {
    // Playwright: navigate to app.propstream.com
    // Enter email + password, click Sign In
    // Wait for dashboard to load
    // Store session cookie
    console.log("[PropStreamAdapter] Authenticating with PropStream...");
  }

  async applyFilters(filter: AdapterSearchFilter): Promise<void> {
    // Navigate to "Property Search" section
    // Set Location: enter ZIP codes or city
    // Set Property Type checkboxes
    // Set Owner Type: Absentee Owner, Out-of-State
    // Set Distress filters: Tax Delinquent, Pre-Foreclosure, Probate, Vacant, Lien
    // Set Equity Range: 20-100%
    // Set Year Built: max 1995
    // Click Search
    console.log(`[PropStreamAdapter] Applying PropStream distress filters for ${filter.market}`);
  }

  async extractRawData(): Promise<RawProperty[]> {
    return this.getMockData() as unknown as RawProperty[];
  }

  async handlePagination(): Promise<boolean> {
    return false;
  }

  async logout(): Promise<void> {
    // Clear PropStream session
  }

  // ── NORMALIZATION ─────────────────────────────────────────────────────────
  normalizeToCanonical(raw: RawProperty): Partial<CanonicalDeal> {
    const r = raw as unknown as PropStreamRawProperty;
    const now = new Date().toISOString();

    const isAbsentee = r.isAbsenteeOwner?.toUpperCase() === "Y";
    const isOutOfState = r.isOutOfState?.toUpperCase() === "Y";
    const isCorp = r.isCorporateOwner?.toUpperCase() === "Y";
    const isTaxDelinquent = r.isTaxDelinquent?.toUpperCase() === "Y";
    const isPreforeclosure = r.isPreforeclosure?.toUpperCase() === "Y";
    const isForeclosure = r.isForeclosure?.toUpperCase() === "Y";
    const isAuction = r.isAuction?.toUpperCase() === "Y";
    const isProbate = r.isProbate?.toUpperCase() === "Y";
    const isVacant = r.isVacant?.toUpperCase() === "Y";
    const hasLiens = r.hasLiens?.toUpperCase() === "Y";
    const isCodeViolation = r.isCodeViolation?.toUpperCase() === "Y";

    const lastSalePrice = this.parsePrice(r.lastSalePrice);
    const estimatedValue = this.parsePrice(r.estimatedValue);
    const estimatedEquity = this.parsePrice(r.estimatedEquity);
    const estimatedEquityPct = this.safeNum(r.estimatedEquityPct);
    const mortgageBalance = this.parsePrice(r.mortgageBalance);

    return {
      apn: this.safeText(r.apn),
      address: r.address ?? "",
      city: r.city ?? "",
      state: r.state ?? "",
      zip: r.zip ?? "",
      county: this.safeText(r.county) ?? "",
      lat: this.safeNum(r.lat),
      lng: this.safeNum(r.lng),

      propertyType: mapPSPropertyType(r.propertyType),
      beds: this.safeNum(r.beds),
      baths: this.safeNum(r.baths),
      livingAreaSqft: this.safeNum(r.sqft),
      lotSizeSqft: this.safeNum(r.lotSizeSqft),
      yearBuilt: this.safeNum(r.yearBuilt),

      ownerName: this.safeText(r.ownerName),
      ownerMailingAddress: r.ownerMailingAddress
        ? `${r.ownerMailingAddress}, ${r.ownerCity}, ${r.ownerState} ${r.ownerZip}`
        : null,
      ownerPhone: this.safeText(r.ownerPhone),
      ownerEmail: this.safeText(r.ownerEmail),
      ownershipYears: this.safeNum(r.ownershipYears),
      lastSaleDate: this.parseDate(r.lastSaleDate),
      lastSalePrice,
      estimatedEquity,
      estimatedEquityPct,
      mortgageBalance,

      occupancyStatus: isVacant
        ? "VACANT"
        : isAbsentee
        ? "UNKNOWN"
        : "UNKNOWN",

      listingStatus: mapPSListingStatus(r.listingStatus),
      listPrice: this.parsePrice(r.listPrice),
      dom: this.safeNum(r.dom),
      mlsId: this.safeText(r.mlsId),

      valuation: {
        avm: estimatedValue,
        avmSource: "propstream",
        avmConfidence: estimatedValue ? "MEDIUM" : "LOW",
        arvEstimate: null,
        arvLow: null,
        arvHigh: null,
        arvConfidence: "LOW",
        arvCompsUsed: 0,
        asIsEstimate: estimatedValue,
        asIsLow: estimatedValue ? Math.round(estimatedValue * 0.9) : null,
        asIsHigh: estimatedValue ? Math.round(estimatedValue * 1.05) : null,
        investorResaleEstimate: null,
        investorResaleLow: null,
        investorResaleHigh: null,
        rentEstimate: this.parsePrice(r.rentEstimate),
        rentEstimateSource: "propstream",
        rehabEstimate: null,
        rehabLow: null,
        rehabHigh: null,
        rehabGrade: "UNKNOWN",
        landDevelopmentValue: null,
        finishedLotValue: null,
        developmentRiskScore: null,
      },

      // PropStream provides rich distress data — populate directly
      // These override/enrich the distress scoring engine
      distress: {
        priceReduced: false,
        priceReductionCount: 0,
        priceReductionTotalPct: 0,
        domBucket: "FRESH",
        domDays: this.safeNum(r.dom) ?? 0,
        distressKeywordsFound: [],
        keywordDistressScore: 0,
        absenteeOwner: isAbsentee,
        outOfStateOwner: isOutOfState,
        corporateOwner: isCorp,
        taxDelinquent: isTaxDelinquent,
        taxDelinquentAmountUSD: this.parsePrice(r.taxDelinquentAmount),
        preforeclosure: isPreforeclosure,
        foreclosure: isForeclosure,
        auction: isAuction,
        lis_pendens: isPreforeclosure,   // PS pre-foreclosure maps to lis pendens
        probate: isProbate,
        estate: isProbate,
        inherited: false,
        codeViolation: isCodeViolation,
        permit_activity: false,
        vacancy: isVacant,
        tenantOccupied: false,
        landlordFatigue: isAbsentee && (this.safeNum(r.dom) ?? 0) >= 45,
        liens: hasLiens,
        lienCount: this.safeNum(r.lienCount) ?? 0,
        openLienAmountUSD: this.parsePrice(r.openLienAmount),
        totalDistressScore: 0,  // calculated by engine
      },
    };
  }

  // ── MOCK DATA ──────────────────────────────────────────────────────────────
  private getMockData(): PropStreamRawProperty[] {
    return [
      {
        apn: "00-1234-5678",
        address: "4821 Hickory Creek Dr",
        city: "Dallas", state: "TX", zip: "75228", county: "Dallas",
        propertyType: "Single Family Residence",
        beds: "3", baths: "2", sqft: "1480", lotSizeSqft: "7800", yearBuilt: "1965",
        lat: "32.7767", lng: "-96.7970",
        ownerName: "JOHNSON MARY T", ownerMailingAddress: "PO Box 11290",
        ownerCity: "Garland", ownerState: "TX", ownerZip: "75041",
        ownerPhone: "214-555-0182", ownerEmail: "",
        isAbsenteeOwner: "Y", isOutOfState: "N", isCorporateOwner: "N",
        lastSaleDate: "2001-08-22", lastSalePrice: "87000",
        estimatedValue: "228000", estimatedEquity: "185000", estimatedEquityPct: "81",
        mortgageBalance: "43000", ownershipYears: "22",
        isTaxDelinquent: "N", taxDelinquentAmount: "0",
        isPreforeclosure: "N", isForeclosure: "N", isAuction: "N",
        isProbate: "N", isVacant: "N", hasLiens: "N", lienCount: "0",
        openLienAmount: "0", isCodeViolation: "N",
        listingStatus: "Active", listPrice: "185000", dom: "67", mlsId: "20558441",
        avm: "228000", rentEstimate: "1450",
      },
    ];
  }
}

function mapPSPropertyType(type: string): CanonicalDeal["propertyType"] {
  if (!type) return "UNKNOWN";
  const t = type.toLowerCase();
  if (t.includes("single family")) return "SFR";
  if (t.includes("condo")) return "CONDO";
  if (t.includes("multi") || t.includes("duplex") || t.includes("triplex")) return "MFR";
  if (t.includes("townhouse") || t.includes("town house")) return "TOWNHOUSE";
  if (t.includes("mobile")) return "MOBILE";
  if (t.includes("land") || t.includes("lot")) return "LAND";
  return "UNKNOWN";
}

function mapPSListingStatus(status: string): CanonicalDeal["listingStatus"] {
  if (!status) return "UNKNOWN";
  const s = status.toLowerCase();
  if (s.includes("active") || s.includes("for sale")) return "ACTIVE";
  if (s.includes("pending")) return "PENDING";
  if (s.includes("sold")) return "SOLD";
  if (s.includes("off market") || s.includes("off-market")) return "OFF_MARKET";
  return "UNKNOWN";
}
