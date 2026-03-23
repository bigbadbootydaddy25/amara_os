/**
 * BuyBox — derived exclusively from a buyer's actual acquisition history.
 *
 * A buy box is NEVER generated speculatively. It is computed only when a buyer
 * has sufficient recorded transactions (≥2). Fields that cannot be derived from
 * actual data are left null. Confidence reflects sample size and consistency.
 */

import type { PropertyType } from './transaction';

export type BuyerStrategy =
  | 'fix_and_flip'      // Short hold, high renovation markers
  | 'rental_portfolio'  // Buy-and-hold, multi-unit or SFR rental patterns
  | 'new_construction'  // Raw land or teardown acquisitions; builder signals
  | 'wholesale'         // Quick resale; very short hold patterns
  | 'land_banking'      // Raw land, long hold
  | 'mixed_portfolio'   // Diverse strategy across property types
  | 'institutional_sfr' // Large-scale SFR acquisition (institutional markers)
  | 'unknown';          // Insufficient data to classify

export interface PriceRange {
  min: number;
  max: number;
  avg: number;
  median: number;
  p25: number;  // 25th percentile
  p75: number;  // 75th percentile
  sample_count: number;
}

export interface BuyBox {
  id: string;
  buyer_entity_id: string;

  // ── Price Parameters (derived from actual purchase prices) ──────────────
  price_range: PriceRange | null;        // null if <2 transactions

  // ── Geographic Preferences (derived from actual ZIP codes) ───────────────
  preferred_zips: ZipPreference[];       // empty array if no recorded history
  preferred_states: string[];
  preferred_cities: string[];

  // ── Property Preferences (derived from actual acquisitions) ─────────────
  property_types: PropertyTypePreference[];
  avg_sqft: number | null;
  sqft_range: { min: number; max: number } | null;
  avg_lot_size_sqft: number | null;
  avg_year_built: number | null;

  // ── Behavioral Patterns ─────────────────────────────────────────────────
  inferred_strategy: BuyerStrategy;
  strategy_confidence: number;          // 0–1: how strongly data supports strategy
  avg_days_to_close: number | null;     // Deal speed (if close/record dates available)
  acquisitions_per_year: number | null; // Frequency derived from transaction timeline

  // ── Metadata ─────────────────────────────────────────────────────────────
  derived_from_transaction_count: number;  // How many transactions this box is built from
  last_derived_at: Date;                   // When this was last recomputed
  is_stale: boolean;                       // True if no new transactions in 180+ days

  created_at: Date;
  updated_at: Date;
}

export interface ZipPreference {
  zip: string;
  transaction_count: number;
  pct_of_total: number;   // Share of buyer's transactions in this ZIP
}

export interface PropertyTypePreference {
  property_type: PropertyType;
  transaction_count: number;
  pct_of_total: number;
  avg_price: number | null;
}
