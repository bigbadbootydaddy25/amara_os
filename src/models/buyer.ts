/**
 * BuyerEntity — a real acquirer with an identity verifiable from public records.
 *
 * Verification status is NEVER assumed. It is computed strictly from transaction
 * history using defined rules. A buyer with zero qualifying transactions is
 * unverified and will not surface in the primary disposition layer.
 */

export type BuyerTier =
  | 'verified_active'    // Meets quantitative transaction thresholds
  | 'verified_inactive'  // Previously verified but no recent activity
  | 'unverified'         // Has transactions but does not meet thresholds
  | 'insufficient_data'; // Fewer than 2 recorded transactions total

export type EntityType =
  | 'individual'
  | 'llc'
  | 'corporation'
  | 'trust'
  | 'partnership'
  | 'institution'        // REIT, fund, institutional buyer
  | 'builder_developer'  // Builder or developer entity
  | 'unknown';

export interface VerificationFlags {
  // Quantitative thresholds — set only when the data supports them
  meets_12mo_threshold: boolean;    // 2+ transactions in last 12 months
  meets_24mo_threshold: boolean;    // 4+ transactions in last 24 months

  // Recency
  last_transaction_days_ago: number | null;  // null = no recorded transactions
  is_recently_active: boolean;               // last transaction within 180 days

  // Entity-type detection from name/keyword analysis
  is_builder_developer: boolean;   // name contains builder/developer keywords
  is_institutional: boolean;       // name contains fund/REIT/institutional keywords

  // Derived aggregates used in scoring
  total_transaction_count: number;
  transaction_pace_per_year: number | null;  // avg transactions/year over active period
  consistency_score: number | null;          // 0–1: how evenly distributed acquisitions are
}

export interface BuyerEntity {
  id: string;
  name: string;            // Legal name as recorded on deed
  entity_type: EntityType; // Inferred from name analysis + transaction patterns

  // Contact/identity (optional — from enrichment sources only)
  email: string | null;
  phone: string | null;
  website: string | null;

  // Verification
  tier: BuyerTier;
  verification_flags: VerificationFlags;
  tier_computed_at: Date;  // When verification was last computed

  // Internal notes — never surfaced as "verified" facts
  raw_name_variants: string[];  // All name variations seen in records

  created_at: Date;
  updated_at: Date;
}

// ─── Keyword dictionaries for entity-type detection ──────────────────────────

export const BUILDER_DEVELOPER_KEYWORDS: readonly string[] = [
  'builder', 'builders', 'developer', 'developers', 'development', 'develop',
  'construction', 'constructors', 'contracting', 'contractors', 'homes',
  'homebuilder', 'homebuilders', 'realty development', 'land development',
  'custom homes', 'spec homes', 'infill',
] as const;

export const INSTITUTIONAL_KEYWORDS: readonly string[] = [
  'fund', 'funds', 'reit', 'capital', 'investment', 'investments', 'investors',
  'asset management', 'assets', 'holdings', 'portfolio', 'acquisition',
  'acquisitions', 'ventures', 'venture', 'equity', 'partner', 'partners',
  'institutional', 'management', 'properties llc', 'properties inc',
  'real estate trust', 'mortgage trust', 'opportunity fund',
] as const;
