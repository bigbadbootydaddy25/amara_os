// ─── Core Landman Domain Types ────────────────────────────────────────────────

export type InterestType =
  | 'mineral'
  | 'royalty'
  | 'npri'              // Non-Participating Royalty Interest
  | 'non_participating_mineral'
  | 'working_interest'
  | 'surface'
  | 'executive_right'
  | 'overriding_royalty';

export type DeedType =
  | 'patent'
  | 'warranty_deed'
  | 'quitclaim_deed'
  | 'beneficiary_deed'
  | 'sheriff_deed'
  | 'tax_deed'
  | 'mineral_deed'
  | 'assignment'
  | 'oil_gas_lease'
  | 'release'
  | 'affidavit_of_production'
  | 'declaration_of_unit'
  | 'probate_decree'
  | 'descent_decree'
  | 'easement'
  | 'mortgage'
  | 'other';

export type MarketRegime = 'hot' | 'neutral' | 'cold' | 'distressed'; // re-exported for convenience

// ─── Section-Township-Range ───────────────────────────────────────────────────

export interface STRLocation {
  section:   number;          // 1–36
  township:  number;
  townshipDir: 'N' | 'S';
  range:     number;
  rangeDir:  'E' | 'W';
  state:     string;
  county:    string;
  pm?:       string;          // Principal Meridian (e.g. "Indian Meridian")
}

export interface LegalDescription {
  raw:         string;         // original text
  strLocation: STRLocation;
  aliquots:    AliquotPart[];  // parsed fractional parts
  totalAcres:  number;
  isLot:       boolean;        // correction section lot
  lotNumbers?: number[];
}

export interface AliquotPart {
  fraction: string;   // e.g. "W/2", "SE/4", "SW/4 NE/4"
  acres:    number;
}

// ─── Chain of Title ───────────────────────────────────────────────────────────

export interface TitleInstrument {
  id?:          string;
  deedType:     DeedType;
  book:         string;
  page:         string;
  instrumentDate: string;    // ISO date
  fileDate?:    string;
  grantor:      string;
  grantee:      string;
  legalDesc?:   string;
  interestType: InterestType;
  interestFraction?: string; // e.g. "1/2", "1/4", "ARTI"
  interestPct?:  number;     // 0–1 decimal
  reservation?:  string;     // text of any reservation clause
  notes?:        string;
}

export interface TitleChain {
  strLocation:  STRLocation;
  instruments:  TitleInstrument[];
  builtAt:      Date;
}

// ─── OGL (Oil & Gas Lease) ────────────────────────────────────────────────────

export interface OilGasLease {
  book:           string;
  page:           string;
  lessor:         string;
  lessee:         string;
  leaseDate:      string;
  primaryTermYears: number;
  expiryDate?:    string;       // end of primary term
  royaltyFraction: number;      // e.g. 0.125 = 1/8
  delayRentalAmt?: number;
  hasPughClause:  boolean;
  hasDepthClause: boolean;
  pughClauseText?: string;
  poolingAcres?:  number;
  status:         'in_term' | 'hbp' | 'expired' | 'released' | 'unknown';
  hbpEvidence?:   string;
  notes?:         string;
}

// ─── Ownership ────────────────────────────────────────────────────────────────

export interface MineralOwner {
  name:           string;
  interestType:   InterestType;
  fraction:       string;       // human-readable, e.g. "1/4"
  decimalInterest: number;      // 0–1
  leaseStatus:    'in_term' | 'open' | 'hbp' | 'unleased';
  lease?:         OilGasLease;
  notes?:         string;
}

// ─── Ownership Report ─────────────────────────────────────────────────────────

export interface OwnershipReport {
  preparedAt:     Date;
  strLocation:    STRLocation;
  totalAcres:     number;
  mineralOwners:  MineralOwner[];
  unreleaseLeases: OilGasLease[];
  unreleaseeMortgages: string[];
  easements:      string[];
  flags:          TitleFlag[];
  notes:          string;
}

// ─── Title Flags ──────────────────────────────────────────────────────────────

export type TitleFlagType =
  | 'duhig_rule_triggered'
  | 'life_estate'
  | 'probate_required'
  | 'hbp_lease'
  | 'statutory_pugh_ok_1977'
  | 'no_pugh_pre_1977'
  | 'quitclaim_unverified'
  | 'patent_pre_1933_no_reservation'
  | 'patent_post_1933_check_reservation'
  | 'npri_in_chain'
  | 'correction_section'
  | 'metes_bounds_desc'
  | 'foreign_probate'
  | 'open_mineral_interest';

export interface TitleFlag {
  type:        TitleFlagType;
  description: string;
  action:      string;
  severity:    'critical' | 'warning' | 'info';
  instrument?: TitleInstrument;
}
