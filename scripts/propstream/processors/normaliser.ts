// ─────────────────────────────────────────────────────────────────────────────
// Normaliser — converts raw DOM-scraped fields into structured records
// ─────────────────────────────────────────────────────────────────────────────

import type { NormalisedRecord, RawRecord } from "../types/index.js";

// Common header aliases PropStream might use
const HEADER_MAP: Record<string, keyof NormalisedRecord> = {
  // address variants
  "address":            "address",
  "property address":   "address",
  "site address":       "address",
  // city
  "city":               "city",
  // state
  "state":              "state",
  // zip
  "zip":                "zip",
  "zip code":           "zip",
  "postal code":        "zip",
  // county
  "county":             "county",
  // APN
  "apn":                "apn",
  "parcel number":      "apn",
  "parcel id":          "apn",
  "assessor parcel":    "apn",
  // owner
  "owner":              "ownerName",
  "owner name":         "ownerName",
  "owner 1":            "ownerName",
  "mailing name":       "ownerName",
  "owner entity":       "ownerEntityName",
  "company":            "ownerEntityName",
  // property type
  "property type":      "propertyType",
  "type":               "propertyType",
  "use type":           "propertyType",
  "land use":           "propertyType",
  // year built
  "year built":         "yearBuilt",
  "built":              "yearBuilt",
  // price / value
  "estimated value":    "price",
  "est. value":         "price",
  "value":              "price",
  "list price":         "price",
  "price":              "price",
  "sale price":         "price",
  "assessed value":     "assessedValue",
  "assessed":           "assessedValue",
  // equity
  "equity":             "equity",
  "equity %":           "equityPct",
  "equity percent":     "equityPct",
  // mortgage
  "mortgage balance":   "mortgageBalance",
  "loan balance":       "mortgageBalance",
  "open mortgage":      "mortgageBalance",
  // lot size
  "lot size":           "lotSizeRaw",
  "lot sqft":           "lotSizeRaw",
  "sq ft":              "lotSizeRaw",
  "square feet":        "lotSizeRaw",
  "acreage":            "acreage",
  "acres":              "acreage",
  "lot acres":          "acreage",
  // zoning
  "zoning":             "zoning",
  "zone":               "zoning",
  "zoning code":        "zoning",
  // dates
  "recording date":     "recordingDate",
  "recorded date":      "recordingDate",
  "sale date":          "recordingDate",
  "last sale date":     "recordingDate",
  // tax delinquent
  "tax delinquent":     "taxDelinquentAmount",
  "delinquent amount":  "taxDelinquentAmount",
  "tax year":           "taxDelinquentYear",
};

export function normalise(raw: RawRecord): NormalisedRecord {
  const f = raw.fields;
  const mapped = mapFields(f);

  // Build distress indicator list from list type + any explicit field signals
  const distress = deriveDistressIndicators(raw.listType, f, mapped);

  return {
    listType:          raw.listType,
    address:           mapped.address           ?? deriveAddress(f) ?? "",
    city:              mapped.city              ?? deriveCityFromAddress(f) ?? "",
    state:             mapped.state             ?? "",
    zip:               mapped.zip               ?? deriveZip(f) ?? "",
    county:            mapped.county,
    apn:               mapped.apn,
    ownerName:         mapped.ownerName,
    ownerEntityName:   mapped.ownerEntityName   ?? deriveEntityName(f),
    propertyType:      mapped.propertyType,
    yearBuilt:         toInt(mapped.yearBuilt),
    price:             toDollars(mapped.price),
    assessedValue:     toDollars(mapped.assessedValue),
    equity:            toDollars(mapped.equity),
    equityPct:         toFloat(mapped.equityPct),
    mortgageBalance:   toDollars(mapped.mortgageBalance),
    lotSizeRaw:        mapped.lotSizeRaw,
    acreage:           toFloat(mapped.acreage) ?? deriveLotAcres(mapped.lotSizeRaw),
    lotCount:          undefined,              // set by land processor
    zoning:            mapped.zoning,
    recordingDate:     mapped.recordingDate,
    approvalDate:      undefined,
    taxDelinquentAmount: toDollars(mapped.taxDelinquentAmount),
    taxDelinquentYear: toInt(mapped.taxDelinquentYear),
    distressIndicators: distress,
    permitActivity:    undefined,
    incomplete:        raw.incomplete || !mapped.address,
    raw,
  };
}

// ─── Field mapping helpers ─────────────────────────────────────────────────────

function mapFields(
  f: Record<string, string>
): Partial<Record<keyof NormalisedRecord, string>> {
  const result: Partial<Record<keyof NormalisedRecord, string>> = {};
  for (const [rawKey, rawVal] of Object.entries(f)) {
    const normKey = HEADER_MAP[rawKey.toLowerCase().trim()];
    if (normKey && !result[normKey]) {
      result[normKey] = rawVal.trim();
    }
  }
  return result;
}

function deriveAddress(f: Record<string, string>): string | undefined {
  // Look for anything that looks like a street address
  for (const val of Object.values(f)) {
    if (/^\d+\s+\w+/.test(val.trim())) return val.trim();
  }
}

function deriveCityFromAddress(f: Record<string, string>): string | undefined {
  // Some scrapers return "City, ST ZIP" in one field
  for (const val of Object.values(f)) {
    const m = val.match(/,\s*([A-Za-z\s]+),\s*[A-Z]{2}\s+\d{5}/);
    if (m) return m[1].trim();
  }
}

function deriveZip(f: Record<string, string>): string | undefined {
  for (const val of Object.values(f)) {
    const m = val.match(/\b(\d{5})(?:-\d{4})?\b/);
    if (m) return m[1];
  }
}

function deriveEntityName(f: Record<string, string>): string | undefined {
  for (const val of Object.values(f)) {
    if (/\b(LLC|Inc|Corp|LP|LLP|Trust|REIT|Properties|Holdings|Investments)\b/i.test(val)) {
      return val.trim();
    }
  }
}

function deriveLotAcres(lotSizeRaw?: string): number | undefined {
  if (!lotSizeRaw) return undefined;
  // "43,560 sqft" → 1 acre; "2.5 acres" → 2.5
  const acreMatch = lotSizeRaw.match(/([\d,.]+)\s*acre/i);
  if (acreMatch) return parseFloat(acreMatch[1].replace(/,/g, ""));
  const sqftMatch = lotSizeRaw.match(/([\d,]+)\s*(?:sqft|sq\.?\s*ft)/i);
  if (sqftMatch) return parseFloat(sqftMatch[1].replace(/,/g, "")) / 43560;
}

function deriveDistressIndicators(
  listType: string,
  f: Record<string, string>,
  mapped: Partial<Record<keyof NormalisedRecord, string>>
): string[] {
  const signals: string[] = [listType]; // the list itself is a signal

  if (listType === "Tax Delinquency") signals.push("tax_delinquent");
  if (listType === "Pre-Foreclosures") signals.push("pre_foreclosure_nod");
  if (listType === "Bank Owned") signals.push("reo_bank_owned");
  if (listType === "Vacant") signals.push("vacant_property");
  if (listType === "Liens") signals.push("lien_on_title");
  if (listType === "Upside Down") signals.push("negative_equity");
  if (listType === "Auctions") signals.push("auction_scheduled");
  if (listType === "Divorce") signals.push("divorce_proceedings");
  if (listType === "Bankruptcy") signals.push("bankruptcy_filing");

  // Scan raw fields for additional signals
  const allText = Object.values(f).join(" ").toLowerCase();
  if (/delinquent/i.test(allText)) signals.push("tax_delinquent");
  if (/foreclos/i.test(allText)) signals.push("foreclosure_signal");
  if (/lis pendens/i.test(allText)) signals.push("lis_pendens");
  if (/notice of default/i.test(allText)) signals.push("notice_of_default");
  if (/vacant/i.test(allText)) signals.push("vacant_signal");
  if (/revok|inactive|dissolv/i.test(allText)) signals.push("entity_revoked");
  if (/bankruptcy/i.test(allText)) signals.push("bankruptcy_signal");
  if (/lien/i.test(allText)) signals.push("lien_signal");

  return [...new Set(signals)];
}

// ─── Type coercions ────────────────────────────────────────────────────────────

function toDollars(raw?: string): number | undefined {
  if (!raw) return undefined;
  const clean = raw.replace(/[$,\s]/g, "");
  const n = parseFloat(clean);
  return isNaN(n) ? undefined : n;
}

function toFloat(raw?: string): number | undefined {
  if (!raw) return undefined;
  const clean = raw.replace(/[%,\s]/g, "");
  const n = parseFloat(clean);
  return isNaN(n) ? undefined : n;
}

function toInt(raw?: string): number | undefined {
  if (!raw) return undefined;
  const n = parseInt(raw.replace(/\D/g, ""), 10);
  return isNaN(n) ? undefined : n;
}
