import {
  DEED_TYPES_COUNTED, DOT_WINDOW_DAYS, LOT_LAND_USE, SFR_LAND_USE, WINDOW_MONTHS,
} from '../config';
import { addMonths, daysBetween, parseDate } from './dates';
import { isHardMoneyLender, normalizeName } from './names';

export interface DeedRow {
  id: number;
  county: string;
  instrument_no: string;
  type: string | null;
  record_date: string;
  grantor: string | null;
  grantee: string | null;
  consideration: number | null;
  apn: string | null;
}

export interface DotRow {
  record_date: string;
  grantor: string | null; // the borrower
  lender: string | null;
  apn: string | null;
}

export type AssetType = 'sfr' | 'infill_lot';

export function classifyLandUse(code: string | null | undefined): AssetType | null {
  const c = (code ?? '').trim().toUpperCase().replace(/ /g, '_');
  if (SFR_LAND_USE.includes(c)) return 'sfr';
  if (LOT_LAND_USE.includes(c)) return 'infill_lot';
  return null;
}

/** Spec §5.1 step 1 — which instruments count. Quitclaims and trustee's deeds never do. */
export function isCountedInstrument(type: string | null | undefined): boolean {
  const t = (type ?? '').trim().toLowerCase().replace(/\s+/g, ' ');
  return DEED_TYPES_COUNTED.includes(t);
}

/** Transfers between related entities (same normalized name, or same buyer group) are excluded. */
export function isRelatedTransfer(
  grantor: string | null, grantee: string | null, groupOf?: (normalized: string) => string | undefined,
): boolean {
  if (!grantor || !grantee) return false;
  const a = normalizeName(grantor);
  const b = normalizeName(grantee);
  if (!a || !b) return false;
  if (a === b) return true;
  const ga = groupOf?.(a);
  return !!ga && ga === groupOf?.(b);
}

export interface CashBuyResult {
  counted: boolean;          // passed instrument + related + asset-type gates
  reason?: string;           // why it was not counted
  assetType: AssetType | null;
  cashBuy: boolean;
  financedHardMoney: boolean;
  matchedDot?: DotRow;
}

/**
 * The cash-buy test (spec §5.1):
 *  1. instrument is a warranty / special warranty deed / deed (not quitclaim, not trustee's deed,
 *     not a transfer between related entities);
 *  2. the property is an SFR (or, for Track 2, a vacant residential lot) per CAD land use;
 *  3. no deed of trust whose grantor (borrower) is the deed's grantee within ±5 days
 *     -> cash_buy = true;
 *  4. a DOT in that window to a known hard-money lender -> financed_hard_money = true
 *     (flagged, NOT counted as cash).
 */
export function evaluateCashBuy(
  deed: DeedRow,
  landUse: string | null | undefined,
  dots: DotRow[],
  groupOf?: (normalized: string) => string | undefined,
): CashBuyResult {
  const none = { cashBuy: false, financedHardMoney: false };
  if (!isCountedInstrument(deed.type)) {
    return { counted: false, reason: 'instrument_not_counted', assetType: null, ...none };
  }
  if (!deed.grantee || !normalizeName(deed.grantee)) {
    return { counted: false, reason: 'no_grantee', assetType: null, ...none };
  }
  if (isRelatedTransfer(deed.grantor, deed.grantee, groupOf)) {
    return { counted: false, reason: 'related_party_transfer', assetType: null, ...none };
  }
  const assetType = classifyLandUse(landUse);
  if (!assetType) {
    return { counted: false, reason: landUse ? 'land_use_not_sfr_or_lot' : 'land_use_unknown', assetType: null, ...none };
  }
  const deedDate = parseDate(deed.record_date);
  if (!deedDate) return { counted: false, reason: 'bad_record_date', assetType, ...none };

  const grantee = normalizeName(deed.grantee);
  const linked = dots.filter((d) => {
    if (!d.grantor || normalizeName(d.grantor) !== grantee) return false;
    if (d.apn && deed.apn && d.apn !== deed.apn) return false; // a different property's loan
    const dd = parseDate(d.record_date);
    return !!dd && Math.abs(daysBetween(deedDate, dd)) <= DOT_WINDOW_DAYS;
  });
  if (linked.length === 0) return { counted: true, assetType, cashBuy: true, financedHardMoney: false };
  const hard = linked.find((d) => isHardMoneyLender(d.lender));
  return {
    counted: true, assetType, cashBuy: false, financedHardMoney: !!hard, matchedDot: hard ?? linked[0],
  };
}

export interface PurchaseFact {
  deedId: number;
  instrumentNo: string;
  apn: string | null;
  date: string;
  cashBuy: boolean;
  hardMoney: boolean;
  assetType: AssetType;
}

/** Same property + same date + same grantee recorded twice (re-recording / correction) is one purchase. */
export function dedupePurchases<T extends { apn: string | null; date: string; grantee: string }>(rows: T[]): T[] {
  const seen = new Set<string>();
  return rows.filter((r) => {
    const k = `${r.apn ?? ''}|${r.date}|${r.grantee}`;
    if (!r.apn) return true; // cannot prove duplicate without an APN
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

export function inWindow(date: string, asOf: string, months = WINDOW_MONTHS): boolean {
  const d = parseDate(date);
  const end = parseDate(asOf);
  if (!d || !end) return false;
  return d.getTime() > addMonths(end, -months).getTime() && d.getTime() <= end.getTime();
}

/** Repeat test (spec §5.1): >=2 DISTINCT cash buys within the trailing 12 months. Hard-money buys do not count. */
export function isRepeatBuyer(purchases: PurchaseFact[], asOf: string, assetType: AssetType = 'sfr'): boolean {
  return countCashBuys(purchases, asOf, assetType) >= 2;
}

export function countCashBuys(purchases: PurchaseFact[], asOf: string, assetType: AssetType): number {
  const rows = purchases
    .filter((p) => p.assetType === assetType && p.cashBuy && inWindow(p.date, asOf))
    .map((p) => ({ ...p, grantee: 'x' }));
  return dedupePurchases(rows).length;
}
