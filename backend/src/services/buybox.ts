import type { Buyer, Deal } from "../db/dealsSchema";

export interface MatchReason {
  field: string;
  weight: number;   // max points available
  earned: number;   // points earned
  note: string;
}

export interface BuyBoxResult {
  buyerId: number;
  buyerName: string;
  matchScore: number;   // 0-100
  matchReasons: MatchReason[];
  label: string;        // "Buyer John → 3/2 $273K (92%)"
}

function n(v: string | number | null | undefined): number | null {
  if (v == null) return null;
  const x = Number(v);
  return isNaN(x) ? null : x;
}

function inRange(
  val: number | null,
  min: number | null,
  max: number | null
): boolean {
  if (val == null) return false;
  if (min != null && val < min) return false;
  if (max != null && val > max) return false;
  return true;
}

/**
 * Score a single deal against a single buyer's buy box.
 * Returns 0-100 match score + detailed reasons.
 */
export function scoreDealAgainstBuyer(deal: Deal, buyer: Buyer): BuyBoxResult {
  const reasons: MatchReason[] = [];
  let totalWeight = 0;
  let totalEarned = 0;

  function add(field: string, weight: number, earned: number, note: string) {
    reasons.push({ field, weight, earned, note });
    totalWeight += weight;
    totalEarned += earned;
  }

  // ── Price (25 pts) ─────────────────────────────────────────────────────────
  const price = n(deal.askingPrice);
  const priceMin = n(buyer.priceMin);
  const priceMax = n(buyer.priceMax);
  if (priceMin != null || priceMax != null) {
    if (price == null) {
      add("price", 25, 0, "No asking price on deal");
    } else if (inRange(price, priceMin, priceMax)) {
      add("price", 25, 25, `$${price.toLocaleString()} within buy box ($${priceMin?.toLocaleString() ?? "0"}–$${priceMax?.toLocaleString() ?? "∞"})`);
    } else {
      const closest = priceMax != null && price > priceMax
        ? ((priceMax / price) * 15)
        : priceMin != null && price < priceMin
        ? ((price / priceMin) * 10)
        : 0;
      const pts = Math.round(Math.max(0, closest));
      add("price", 25, pts, `$${price.toLocaleString()} outside buy box — partial credit`);
    }
  }

  // ── ARV (20 pts) ──────────────────────────────────────────────────────────
  const arv = n(deal.arv);
  const arvMin = n(buyer.arvMin);
  const arvMax = n(buyer.arvMax);
  if (arvMin != null || arvMax != null) {
    if (arv == null) {
      add("arv", 20, 0, "No ARV on deal");
    } else if (inRange(arv, arvMin, arvMax)) {
      add("arv", 20, 20, `ARV $${arv.toLocaleString()} fits buyer range`);
    } else {
      add("arv", 20, 5, `ARV $${arv.toLocaleString()} outside buyer ARV range`);
    }
  }

  // ── Beds/Baths (20 pts) ───────────────────────────────────────────────────
  const beds = deal.beds;
  const baths = n(deal.baths);
  const bedsOk  = beds  == null ? null : inRange(beds,  buyer.bedsMin  ?? null, buyer.bedsMax  ?? null);
  const bathsOk = baths == null ? null : inRange(baths, n(buyer.bathsMin), n(buyer.bathsMax));

  if (buyer.bedsMin != null || buyer.bedsMax != null || buyer.bathsMin != null || buyer.bathsMax != null) {
    const bedsLabel  = beds  != null ? `${beds} bd`   : "? bd";
    const bathsLabel = baths != null ? `${baths} ba`  : "? ba";
    if (bedsOk === true && bathsOk !== false) {
      add("beds_baths", 20, 20, `${bedsLabel}/${bathsLabel} matches buyer criteria`);
    } else if (bedsOk === true || bathsOk === true) {
      add("beds_baths", 20, 10, `${bedsLabel}/${bathsLabel} — partial match`);
    } else {
      add("beds_baths", 20, 0, `${bedsLabel}/${bathsLabel} does not match buyer criteria`);
    }
  }

  // ── Location (15 pts) ─────────────────────────────────────────────────────
  const zipMatch   = buyer.zipCodes?.length && deal.zip   ? buyer.zipCodes.includes(deal.zip)   : null;
  const stateMatch = buyer.states?.length   && deal.state ? buyer.states.includes(deal.state)   : null;

  if (buyer.zipCodes?.length || buyer.states?.length) {
    if (zipMatch) {
      add("location", 15, 15, `ZIP ${deal.zip} is in buyer's target list`);
    } else if (stateMatch) {
      add("location", 15, 8, `State ${deal.state} matches (not in target ZIP list)`);
    } else if (zipMatch === false && stateMatch === false) {
      add("location", 15, 0, `${deal.zip}, ${deal.state} not in buyer's target area`);
    }
  }

  // ── Property type (10 pts) ────────────────────────────────────────────────
  if (buyer.propertyTypes?.length && deal.propertyType) {
    const typeOk = buyer.propertyTypes
      .map((t) => t.toUpperCase())
      .includes(deal.propertyType.toUpperCase());
    add("property_type", 10, typeOk ? 10 : 0,
      typeOk ? `Property type ${deal.propertyType} matches` : `Buyer wants ${buyer.propertyTypes.join("/")} — got ${deal.propertyType}`);
  }

  // ── ROI (10 pts) ──────────────────────────────────────────────────────────
  const roi = n(deal.roiPct);
  const minRoi = n(buyer.minRoiPct);
  if (minRoi != null) {
    if (roi == null) {
      add("roi", 10, 3, "ROI not calculated on deal");
    } else if (roi >= minRoi) {
      add("roi", 10, 10, `ROI ${roi.toFixed(1)}% meets buyer minimum ${minRoi.toFixed(1)}%`);
    } else {
      add("roi", 10, 0, `ROI ${roi.toFixed(1)}% below buyer minimum ${minRoi.toFixed(1)}%`);
    }
  }

  // ── Rehab cap (bonus −5 if exceeded) ─────────────────────────────────────
  const rehab    = n(deal.estimatedRehab);
  const maxRehab = n(buyer.maxRehab);
  if (maxRehab != null && rehab != null) {
    if (rehab <= maxRehab) {
      add("rehab", 0, 0, `Rehab $${rehab.toLocaleString()} within buyer cap`);
    } else {
      add("rehab", 0, -5, `Rehab $${rehab.toLocaleString()} exceeds buyer cap $${maxRehab.toLocaleString()}`);
    }
  }

  // ── Compute final score ───────────────────────────────────────────────────
  const rawScore = totalWeight > 0 ? (totalEarned / totalWeight) * 100 : 50;
  const penalty  = reasons.filter((r) => r.earned < 0).reduce((s, r) => s + r.earned, 0);
  const score = Math.max(0, Math.min(100, Math.round(rawScore + penalty)));

  // ── Build display label ───────────────────────────────────────────────────
  const bedsStr  = deal.beds  != null ? `${deal.beds}` : "?";
  const bathsStr = n(deal.baths) != null ? `${n(deal.baths)}` : "?";
  const priceStr = price != null ? `$${Math.round(price / 1000)}K` : "N/A";
  const label = `${buyer.name} → ${bedsStr}/${bathsStr} ${priceStr} (${score}%)`;

  return { buyerId: buyer.id, buyerName: buyer.name, matchScore: score, matchReasons: reasons, label };
}

/**
 * Match one deal against ALL active buyers. Returns sorted by score desc.
 */
export function matchDealToBuyers(deal: Deal, buyers: Buyer[]): BuyBoxResult[] {
  return buyers
    .filter((b) => b.isActive)
    .map((b) => scoreDealAgainstBuyer(deal, b))
    .filter((r) => r.matchScore >= 30)   // filter noise
    .sort((a, b) => b.matchScore - a.matchScore);
}

/**
 * Parse a CSV row (raw key→value object) into a NewDeal-compatible shape.
 * Handles common CSV column name variations.
 */
export function csvRowToDeal(row: Record<string, string>, batchId: string) {
  const get = (...keys: string[]) => {
    for (const k of keys) {
      const v = row[k] ?? row[k.toLowerCase()] ?? row[k.toUpperCase()];
      if (v != null && v.trim() !== "") return v.trim();
    }
    return undefined;
  };

  const price  = get("asking_price","asking price","price","list_price","list price","purchase_price");
  const arvRaw = get("arv","after_repair_value","ARV","after repair value");
  const rehab  = get("estimated_rehab","rehab","repair_cost","repairs","repair cost");

  const askingNum = price  ? Number(price.replace(/[$,]/g, ""))  : undefined;
  const arvNum    = arvRaw ? Number(arvRaw.replace(/[$,]/g, "")) : undefined;
  const rehabNum  = rehab  ? Number(rehab.replace(/[$,]/g, ""))  : undefined;

  // Computed fields
  let roiPct: number | undefined;
  let equityPct: number | undefined;
  let maxAllowableOffer: number | undefined;

  if (arvNum && arvNum > 0) {
    if (askingNum != null && rehabNum != null) {
      roiPct = ((arvNum - askingNum - rehabNum) / arvNum) * 100;
    }
    if (askingNum != null) {
      equityPct = ((arvNum - askingNum) / arvNum) * 100;
    }
    // MAO = 70% ARV − rehab (standard wholesale formula)
    maxAllowableOffer = arvNum * 0.70 - (rehabNum ?? 0);
  }

  return {
    address:      get("address","street","street_address","property_address"),
    city:         get("city"),
    state:        get("state","st"),
    zip:          get("zip","zip_code","postal_code"),
    county:       get("county"),
    propertyType: get("property_type","type","prop_type") ?? "SFR",
    beds:         get("beds","bedrooms","bed") ? parseInt(get("beds","bedrooms","bed")!, 10) : undefined,
    baths:        get("baths","bathrooms","bath") ? parseFloat(get("baths","bathrooms","bath")!) : undefined,
    sqft:         get("sqft","sq_ft","square_feet","living_sqft") ? parseInt(get("sqft","sq_ft","square_feet","living_sqft")!, 10) : undefined,
    yearBuilt:    get("year_built","year built","built") ? parseInt(get("year_built","year built","built")!, 10) : undefined,
    askingPrice:  askingNum?.toString(),
    arv:          arvNum?.toString(),
    estimatedRehab: rehabNum?.toString(),
    maxAllowableOffer: maxAllowableOffer?.toString(),
    roiPct:       roiPct?.toFixed(2),
    equityPct:    equityPct?.toFixed(2),
    source:       "CSV_UPLOAD",
    importBatchId: batchId,
    rawCsvRow:    row,
    pipelineStage: "NEW",
    status:       "NEW",
  };
}
