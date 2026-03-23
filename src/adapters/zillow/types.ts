/**
 * AMARA OS — Zillow Raw Listing Type
 * Shape returned by ZillowPlaywright scanner before normalization.
 */

export interface ZillowRawListing {
  zpid: string | null;
  address: string | null;
  price: string | null;
  details: string | null;       // "3 bds · 2 ba · 1,480 sqft" style string
  dom: string | null;           // "67 days on Zillow" or "67"
  priceReduced: boolean;
  status: string;               // "For Sale", "Pending", etc.
  detailUrl: string | null;
  scrapedAt: string;            // ISO timestamp

  // Enriched from detail page (optional)
  remarks?: string | null;
  zestimate?: string | null;
  rentEstimate?: string | null;
  yearBuilt?: string | null;
  priceHistoryRows?: string[];  // Raw text rows from price history table
}
