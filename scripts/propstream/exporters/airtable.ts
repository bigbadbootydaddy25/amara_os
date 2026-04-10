// ─────────────────────────────────────────────────────────────────────────────
// Airtable Pusher — uploads all results to Airtable base app0jn857ZwVzQs8i
// Call after all other processing is done. Requires AIRTABLE_API_KEY env var.
// ─────────────────────────────────────────────────────────────────────────────

import type {
  SFRTarget,
  LandTarget,
  DeadPaperTarget,
  SFRBuyer,
  LandBuyer,
  SFRMatch,
  BuilderMatch,
} from "../types/index.js";

const BASE_ID = "app0jn857ZwVzQs8i";
const AIRTABLE_API_BASE = "https://api.airtable.com/v0";
const BATCH_SIZE = 10; // Airtable max per request

interface AirtableRecord {
  fields: Record<string, unknown>;
}

// ─── HTTP helper ──────────────────────────────────────────────────────────────

async function airtablePost(
  apiKey: string,
  tableIdOrName: string,
  records: AirtableRecord[]
): Promise<void> {
  const url = `${AIRTABLE_API_BASE}/${BASE_ID}/${encodeURIComponent(tableIdOrName)}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ records }),
  });

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Airtable POST to "${tableIdOrName}" failed (${resp.status}): ${body}`);
  }
}

async function pushBatches(
  apiKey: string,
  tableName: string,
  records: AirtableRecord[],
  label: string
): Promise<void> {
  console.log(`[airtable] pushing ${records.length} ${label} records to "${tableName}"`);
  let pushed = 0;
  for (let i = 0; i < records.length; i += BATCH_SIZE) {
    const batch = records.slice(i, i + BATCH_SIZE);
    await airtablePost(apiKey, tableName, batch);
    pushed += batch.length;
    process.stdout.write(`\r  [airtable] ${pushed}/${records.length} ${label}`);
    // Rate limit: 5 requests/sec
    await new Promise((r) => setTimeout(r, 220));
  }
  console.log(`\n  [airtable] ✓ ${label} done`);
}

// ─── Table mappers ────────────────────────────────────────────────────────────

function mapSFRTarget(t: SFRTarget): AirtableRecord {
  return {
    fields: {
      Address:              t.address,
      ZIP:                  t.zip,
      City:                 t.city,
      State:                t.state,
      Market:               t.market,
      Tier:                 t.tier,
      "Property Type":      t.propertyType,
      "Year Built":         t.yearBuilt,
      Price:                t.price,
      "Assessed Value":     t.assessedValue,
      "List Type":          t.listType,
      "Recording Date":     t.recordingDate,
      "Distress Indicators": t.distressIndicators.join(", "),
      "Owner Name":         t.ownerName,
      Incomplete:           t.incomplete,
    },
  };
}

function mapLandTarget(t: LandTarget): AirtableRecord {
  return {
    fields: {
      Address:            t.address,
      APN:                t.apn,
      ZIP:                t.zip,
      City:               t.city,
      State:              t.state,
      County:             t.county,
      Market:             t.market,
      Tier:               t.tier,
      "Lot Size":         t.lotSizeRaw,
      "Acreage":          t.acreage,
      "Lot Count":        t.lotCount,
      Zoning:             t.zoning,
      Classification:     t.classification,
      "Distress Type":    t.distressType,
      "Distress Signals": t.distressSignals.join(", "),
      "Owner Entity":     t.ownerEntityName,
      Price:              t.price,
      "Assessed Value":   t.assessedValue,
      "Approval Date":    t.approvalDate,
      "Permit Activity":  t.permitActivity,
      "List Type":        t.listType,
      Incomplete:         t.incomplete,
    },
  };
}

function mapDeadPaper(t: DeadPaperTarget): AirtableRecord {
  return {
    fields: {
      ...mapLandTarget(t).fields,
      "Days To Expiry":   t.daysToExpiry,
      "Urgency Score":    t.urgencyScore,
      "Urgency Reason":   t.urgencyReason,
      "Immediate Action": t.urgencyScore >= 75,
    },
  };
}

function mapSFRBuyer(b: SFRBuyer): AirtableRecord {
  return {
    fields: {
      "Buyer Name":       b.buyerName,
      "Entity Type":      b.entityType,
      "Active ZIPs":      b.activeZips.join(", "),
      Markets:            b.markets.join(", "),
      "Property Types":   b.propertyTypes.join(", "),
      "Price Range Min":  b.priceRangeMin,
      "Price Range Max":  b.priceRangeMax,
      "Transaction Count": b.transactionCount,
      "Most Recent Purchase": b.mostRecentPurchase,
    },
  };
}

function mapLandBuyer(b: LandBuyer): AirtableRecord {
  return {
    fields: {
      "Buyer Name":       b.buyerName,
      "Entity Type":      b.entityType,
      "Active ZIPs":      b.activeZips.join(", "),
      Markets:            b.markets.join(", "),
      "Land Types":       b.landTypes.join(", "),
      "Lot Size Min (ac)": b.lotSizeMin,
      "Lot Size Max (ac)": b.lotSizeMax,
      "Price Range Min":  b.priceRangeMin,
      "Price Range Max":  b.priceRangeMax,
      "Transaction Count": b.transactionCount,
      "Most Recent Purchase": b.mostRecentPurchase,
    },
  };
}

function mapSFRMatch(m: SFRMatch): AirtableRecord {
  return {
    fields: {
      Address:            m.property.address,
      ZIP:                m.zip,
      Market:             m.market,
      "Match Score":      m.matchScore,
      "Match Reasons":    m.matchReasons.join("; "),
      "Matched Buyers":   m.matchedBuyers.map((b) => b.buyerName).join(", "),
      "List Type":        m.property.listType,
      "Distress Indicators": m.property.distressIndicators.join(", "),
      Price:              m.property.price,
    },
  };
}

function mapBuilderMatch(m: BuilderMatch): AirtableRecord {
  return {
    fields: {
      Address:            m.property.address,
      ZIP:                m.zip,
      Market:             m.market,
      Classification:     m.property.classification,
      "Urgency Score":    m.urgencyScore,
      "Urgency Reason":   m.urgencyReason,
      "Match Score":      m.matchScore,
      "Match Reasons":    m.matchReasons.join("; "),
      "Matched Buyers":   m.matchedBuyers.map((b) => b.buyerName).join(", "),
      "Flag Immediate":   m.flagForImmediateAction,
      "Distress Signals": m.property.distressSignals.join(", "),
      Price:              m.property.price,
      "Lot Size":         m.property.lotSizeRaw,
    },
  };
}

// ─── Main push function ───────────────────────────────────────────────────────

export interface AirtablePushOptions {
  apiKey: string;
  sfrTargets: SFRTarget[];
  landTargets: LandTarget[];
  deadPaperTargets: DeadPaperTarget[];
  sfrBuyers: SFRBuyer[];
  landBuyers: LandBuyer[];
  sfrMatches: SFRMatch[];
  builderMatches: BuilderMatch[];
}

export async function pushToAirtable(opts: AirtablePushOptions): Promise<void> {
  const { apiKey } = opts;

  console.log(`\n[airtable] pushing to base ${BASE_ID}`);

  await pushBatches(apiKey, "SFR Targets",
    opts.sfrTargets.map(mapSFRTarget), "SFR targets");

  await pushBatches(apiKey, "Land Targets",
    opts.landTargets.map(mapLandTarget), "land targets");

  await pushBatches(apiKey, "Dead Paper",
    opts.deadPaperTargets.map(mapDeadPaper), "dead paper");

  await pushBatches(apiKey, "SFR Buyers",
    opts.sfrBuyers.map(mapSFRBuyer), "SFR buyers");

  await pushBatches(apiKey, "Land Buyers",
    opts.landBuyers.map(mapLandBuyer), "land buyers");

  // Match board: combine both match types into one "Match Board" table
  const sfrMatchRecords = opts.sfrMatches.map(mapSFRMatch);
  const builderMatchRecords = opts.builderMatches.map(mapBuilderMatch);
  await pushBatches(apiKey, "Match Board",
    [...sfrMatchRecords, ...builderMatchRecords], "match board entries");

  console.log("[airtable] ✓ all tables pushed successfully");
}
