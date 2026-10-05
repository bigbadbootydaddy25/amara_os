import { describe, expect, it } from 'vitest';
import { countCashBuys, dedupePurchases, inWindow, isRepeatBuyer, type PurchaseFact } from '../agents/lib/cashbuy';
import { classifyExcluded, groupBuyers } from '../agents/lib/names';

const buy = (date: string, o: Partial<PurchaseFact> = {}): PurchaseFact => ({
  deedId: Math.floor(Math.random() * 1e9), instrumentNo: `i-${date}`, apn: `apn-${date}`, date,
  cashBuy: true, hardMoney: false, assetType: 'sfr', ...o,
});
const ASOF = '2026-10-05';

describe('repeat-buyer test (spec 5.1)', () => {
  it('two cash buys inside 12 months = verified repeat buyer', () => {
    expect(isRepeatBuyer([buy('2026-03-01'), buy('2026-08-01')], ASOF)).toBe(true);
  });

  it('one cash buy is not a repeat buyer', () => {
    expect(isRepeatBuyer([buy('2026-08-01')], ASOF)).toBe(false);
  });

  it('a financed (non-cash) buy does not count toward the two', () => {
    expect(isRepeatBuyer([buy('2026-03-01'), buy('2026-08-01', { cashBuy: false })], ASOF)).toBe(false);
  });

  it('hard-money buys are flagged, not counted', () => {
    expect(isRepeatBuyer([buy('2026-03-01'), buy('2026-08-01', { cashBuy: false, hardMoney: true })], ASOF)).toBe(false);
  });

  it('buys older than 12 months do not count (boundary: exactly 12 months ago is out)', () => {
    expect(inWindow('2025-10-05', ASOF)).toBe(false);
    expect(inWindow('2025-10-06', ASOF)).toBe(true);
    expect(isRepeatBuyer([buy('2025-10-05'), buy('2026-08-01')], ASOF)).toBe(false);
    expect(isRepeatBuyer([buy('2025-10-06'), buy('2026-08-01')], ASOF)).toBe(true);
  });

  it('future-dated deeds are ignored', () => {
    expect(isRepeatBuyer([buy('2026-08-01'), buy('2026-11-01')], ASOF)).toBe(false);
  });

  it('counts distinct purchases: the same property re-recorded on the same date is one buy', () => {
    const a = buy('2026-08-01', { apn: 'X', deedId: 1 });
    const b = buy('2026-08-01', { apn: 'X', deedId: 2 });
    expect(dedupePurchases([a, b].map((p) => ({ ...p, grantee: 'g' }))).length).toBe(1);
    expect(isRepeatBuyer([a, b], ASOF)).toBe(false);
  });

  it('SFR buys and lot buys are counted separately (Track 1 vs Track 2)', () => {
    const mixed = [buy('2026-03-01'), buy('2026-08-01', { assetType: 'infill_lot' })];
    expect(isRepeatBuyer(mixed, ASOF, 'sfr')).toBe(false);
    expect(isRepeatBuyer(mixed, ASOF, 'infill_lot')).toBe(false);
    expect(countCashBuys([...mixed, buy('2026-09-01', { assetType: 'infill_lot' })], ASOF, 'infill_lot')).toBe(2);
  });
});

describe('buyer grouping and exclusions', () => {
  it('groups entities sharing registered agent AND mailing address', () => {
    const g = groupBuyers([
      { normalized: 'ALPHA HOLDINGS', registeredAgent: 'Pat Agent', mailing: '1 Main St Dallas TX' },
      { normalized: 'BETA HOLDINGS', registeredAgent: 'PAT AGENT', mailing: '1 main st, dallas, tx' },
      { normalized: 'GAMMA HOLDINGS', registeredAgent: 'Pat Agent', mailing: '99 Other Rd Plano TX' },
      { normalized: 'DELTA', registeredAgent: null, mailing: null },
    ]);
    expect(g.get('ALPHA HOLDINGS')).toBe(g.get('BETA HOLDINGS'));
    expect(g.get('GAMMA HOLDINGS')).not.toBe(g.get('ALPHA HOLDINGS'));
    expect(g.get('DELTA')).toBe('G:DELTA');
  });

  it('separates national builders, iBuyers, government and nonprofits', () => {
    expect(classifyExcluded('D R HORTON')).toBe('national_builder');
    expect(classifyExcluded('OPENDOOR PROPERTY TRUST I')).toBe('ibuyer_institutional');
    expect(classifyExcluded('CITY OF DALLAS')).toBe('government');
    expect(classifyExcluded('HABITAT FOR HUMANITY OF DALLAS')).toBe('nonprofit');
    expect(classifyExcluded('LONE STAR HOMES')).toBeNull();
    expect(classifyExcluded('CONVERT PROPERTIES')).toBeNull(); // "NVR" must not match inside a word
  });
});
