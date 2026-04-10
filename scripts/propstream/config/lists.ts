// ─────────────────────────────────────────────────────────────────────────────
// Lead list definitions and track assignments
// ─────────────────────────────────────────────────────────────────────────────

import type { LeadListName } from "../types/index.js";

export const ALL_LEAD_LISTS: LeadListName[] = [
  "Auctions",
  "Bank Owned",
  "Bankruptcy",
  "Cash Buyers",
  "Divorce",
  "Failed Listings",
  "Flippers",
  "Free & Clear",
  "High Equity",
  "Liens",
  "On Market",
  "Pre-Foreclosures",
  "Pre-Probate",
  "Senior Owners",
  "Tax Delinquency",
  "Tired Landlords",
  "Upside Down",
  "Vacant",
  "Vacant Land",
];

// Lists used for SFR / distress track
export const SFR_LISTS: LeadListName[] = [
  "Cash Buyers",
  "Pre-Foreclosures",
  "Tax Delinquency",
  "Tired Landlords",
  "High Equity",
  "Upside Down",
  "Liens",
  "Vacant",
  "Bank Owned",
  "Divorce",
  "Auctions",
  "Flippers",
  "Senior Owners",
  "Bankruptcy",
  "Free & Clear",
];

// Lists used for land / dead paper track
export const LAND_LISTS: LeadListName[] = [
  "Vacant Land",
  "Bank Owned",
  "Tax Delinquency",
  "Liens",
  "Pre-Foreclosures",
  "On Market",
  "Failed Listings",
];

// Lists that feed the buyer profile builder
export const BUYER_LISTS: LeadListName[] = ["Cash Buyers", "Flippers"];

// Lists that appear in both tracks (records are processed for both)
export const DUAL_TRACK_LISTS: LeadListName[] = [
  "Bank Owned",
  "Tax Delinquency",
  "Liens",
  "Pre-Foreclosures",
];

export const LIST_DESCRIPTIONS: Record<LeadListName, string> = {
  Auctions:          "Properties scheduled for auction sale",
  "Bank Owned":      "REO / bank-owned properties",
  Bankruptcy:        "Owner has active or recent bankruptcy filing",
  "Cash Buyers":     "Recent all-cash purchasers — buyer profile source",
  Divorce:           "Properties tied to divorce proceedings",
  "Failed Listings": "Properties that went off market without selling",
  Flippers:          "Recent flip transactions — buyer profile source",
  "Free & Clear":    "No mortgage — high motivation to sell for cash",
  "High Equity":     "Owners with significant equity position (>40%)",
  Liens:             "Mechanic, HOA, or judgment liens on title",
  "On Market":       "Currently listed — useful for land/price comps",
  "Pre-Foreclosures":"NOD / lis pendens filed, not yet at auction",
  "Pre-Probate":     "Senior owner death indicator, probate anticipated",
  "Senior Owners":   "Owner 65+ — potential motivated seller",
  "Tax Delinquency": "Delinquent property taxes — strong distress signal",
  "Tired Landlords": "Non-owner-occupied, long hold, likely exit mode",
  "Upside Down":     "Negative equity — mortgage > value",
  Vacant:            "Property appears vacant / non-owner-occupied",
  "Vacant Land":     "Unimproved land parcels",
};
