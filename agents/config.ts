import path from 'node:path';

export const RULESET_VERSION = 'AMARA Constitution v2026.10.05';

export const ROOT = path.resolve(__dirname, '..');
export const PATHS = {
  db: process.env.AMARA_DB ?? path.join(ROOT, 'data', 'amara.db'),
  sources: path.join(ROOT, 'sources.yaml'),
  exclusions: path.join(ROOT, 'config', 'buyer-exclusions.yaml'),
  hardLenders: path.join(ROOT, 'config', 'hard-lenders.yaml'),
  zoning: path.join(ROOT, 'config', 'dallas-zoning.yaml'),
  researchInbox: path.join(ROOT, 'inbox', 'research'),
  recordsInbox: path.join(ROOT, 'inbox', 'records'),
  briefs: path.join(ROOT, 'out', 'briefs'),
};

/** Cash-buy test windows (spec §5.1). */
export const DOT_WINDOW_DAYS = 5;
export const WINDOW_MONTHS = 12;

export const DEED_TYPES_COUNTED = ['warranty deed', 'special warranty deed', 'deed'];

/**
 * CAD land-use codes. ASSUMPTION: DCAD state property-class codes (A1 = single
 * family residence, C1 = vacant residential lot). Verify against the DCAD data
 * dictionary; free-text values 'sfr' / 'vacant_lot' are also accepted.
 */
export const SFR_LAND_USE = ['A1', 'SFR'];
export const LOT_LAND_USE = ['C1', 'VACANT_LOT'];

/** Buyer is "active" if their last purchase is within this many days (spec §5.3). */
export const ACTIVE_DAYS_SFR = 90;
export const ACTIVE_DAYS_LOT = 180;

export const MIN_MATCH_SCORE = 60;
export const TOP_N_BUYERS = 5;
export const DEFAULT_FEE_SFR = 10_000;
export const DEFAULT_FEE_LOT = 20_000;

/** Condition proxy: buyer median $/sqft below area median × this ratio => rehab buyer (spec: "below" => 1.0). */
export const REHAB_RATIO = 1.0;
/** Deed consideration below this is treated as non-disclosed ("$10 and other consideration"). */
export const MIN_REAL_CONSIDERATION = 10_000;
