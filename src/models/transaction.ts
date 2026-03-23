/**
 * Transaction — the ground truth record of a real property acquisition.
 * Every inference, verification, and score in this system traces back to these records.
 * Nothing is fabricated: if a field cannot be derived from transactions, it is null.
 */

export type PropertyType =
  | 'sfr'           // Single-Family Residential
  | 'mfr'           // Multi-Family Residential
  | 'condo'
  | 'townhome'
  | 'land'
  | 'commercial'
  | 'mobile_home'
  | 'mixed_use'
  | 'unknown';

export interface Transaction {
  id: string;
  buyer_entity_id: string;

  // Recorded deed / MLS / public record fields
  recorded_date: Date;           // Date the deed was recorded — the authoritative timestamp
  close_date: Date | null;       // Closing date if separately available
  purchase_price: number;        // In USD, as recorded
  address: string;
  city: string;
  state: string;
  zip: string;

  // Property characteristics as recorded
  property_type: PropertyType;
  sqft: number | null;
  lot_size_sqft: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  year_built: number | null;

  // Source metadata
  source: string;                // e.g. 'deed_record', 'mls', 'public_record'
  source_id: string | null;      // External reference ID
  verified: boolean;             // Has been cross-validated against a second source

  created_at: Date;
  updated_at: Date;
}

/**
 * Aggregated view of a buyer's transaction history — computed, never assumed.
 */
export interface TransactionSummary {
  buyer_entity_id: string;
  total_transactions: number;
  transactions_last_12mo: number;
  transactions_last_24mo: number;
  first_transaction_date: Date | null;
  last_transaction_date: Date | null;
  avg_days_between_transactions: number | null;  // acquisition pace
  avg_purchase_price: number | null;
  min_purchase_price: number | null;
  max_purchase_price: number | null;
  total_volume: number;
  zip_codes: string[];                           // all ZIPs where buyer has transacted
  property_types: PropertyType[];                // all property types acquired
}
