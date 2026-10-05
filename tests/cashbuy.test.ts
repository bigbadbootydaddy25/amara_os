import { describe, expect, it } from 'vitest';
import { evaluateCashBuy, isRelatedTransfer, type DeedRow, type DotRow } from '../agents/lib/cashbuy';
import { groupBuyers, normalizeName } from '../agents/lib/names';

const deed = (o: Partial<DeedRow> = {}): DeedRow => ({
  id: 1, county: 'Dallas', instrument_no: '2026-0001', type: 'Warranty Deed', record_date: '2026-09-10',
  grantor: 'JOHN SELLER', grantee: 'Lone Star Homes, L.L.C.', consideration: 150000, apn: 'A-1', ...o,
});
const dot = (o: Partial<DotRow> = {}): DotRow => ({
  record_date: '2026-09-10', grantor: 'LONE STAR HOMES LLC', lender: 'FIRST NATIONAL BANK', apn: 'A-1', ...o,
});

describe('normalizeName', () => {
  it('strips punctuation and suffixes', () => {
    expect(normalizeName('Lone Star Homes, L.L.C.')).toBe('LONE STAR HOMES');
    expect(normalizeName('LONE STAR HOMES LLC')).toBe('LONE STAR HOMES');
    expect(normalizeName('  Lone  Star   Homes Inc. ')).toBe('LONE STAR HOMES');
    expect(normalizeName('The Smith Group, LLC')).toBe('SMITH GROUP');
  });
});

describe('cash-buy test (spec 5.1)', () => {
  it('counts an SFR warranty deed with no deed of trust as a cash buy', () => {
    const r = evaluateCashBuy(deed(), 'A1', []);
    expect(r).toMatchObject({ counted: true, cashBuy: true, financedHardMoney: false, assetType: 'sfr' });
  });

  it('accepts special warranty deeds and plain deeds', () => {
    expect(evaluateCashBuy(deed({ type: 'Special Warranty Deed' }), 'A1', []).cashBuy).toBe(true);
    expect(evaluateCashBuy(deed({ type: 'Deed' }), 'A1', []).cashBuy).toBe(true);
  });

  it('excludes quitclaim and trustee deeds from the count entirely', () => {
    for (const type of ['Quitclaim Deed', "Trustee's Deed", 'Substitute Trustee Deed', null]) {
      expect(evaluateCashBuy(deed({ type }), 'A1', []).counted).toBe(false);
    }
  });

  it('excludes related-entity transfers (same name, or same buyer group)', () => {
    expect(evaluateCashBuy(deed({ grantor: 'Lone Star Homes LLC' }), 'A1', [])).toMatchObject({ counted: false, reason: 'related_party_transfer' });
    const groups = groupBuyers([
      { normalized: 'ALPHA HOLDINGS', registeredAgent: 'Pat Agent', mailing: '1 Main St, Dallas TX' },
      { normalized: 'BETA HOLDINGS', registeredAgent: 'PAT AGENT', mailing: '1 MAIN ST DALLAS TX' },
    ]);
    expect(isRelatedTransfer('Alpha Holdings LLC', 'Beta Holdings LLC', (n) => groups.get(n))).toBe(true);
    expect(isRelatedTransfer('Alpha Holdings LLC', 'Gamma LLC', (n) => groups.get(n))).toBe(false);
  });

  it('requires an SFR land-use code; vacant lots and unknown land use are not SFR cash buys', () => {
    expect(evaluateCashBuy(deed(), 'F1', [])).toMatchObject({ counted: false, reason: 'land_use_not_sfr_or_lot' });
    expect(evaluateCashBuy(deed(), null, [])).toMatchObject({ counted: false, reason: 'land_use_unknown' });
    expect(evaluateCashBuy(deed(), 'C1', []).assetType).toBe('infill_lot');
  });

  it('a deed of trust by the grantee on the same day means NOT cash', () => {
    const r = evaluateCashBuy(deed(), 'A1', [dot()]);
    expect(r).toMatchObject({ counted: true, cashBuy: false, financedHardMoney: false });
  });

  it('applies the ±5 day window inclusively on both sides', () => {
    expect(evaluateCashBuy(deed(), 'A1', [dot({ record_date: '2026-09-15' })]).cashBuy).toBe(false); // +5
    expect(evaluateCashBuy(deed(), 'A1', [dot({ record_date: '2026-09-05' })]).cashBuy).toBe(false); // -5
    expect(evaluateCashBuy(deed(), 'A1', [dot({ record_date: '2026-09-16' })]).cashBuy).toBe(true); // +6
    expect(evaluateCashBuy(deed(), 'A1', [dot({ record_date: '2026-09-04' })]).cashBuy).toBe(true); // -6
  });

  it('ignores deeds of trust by other borrowers or on other properties', () => {
    expect(evaluateCashBuy(deed(), 'A1', [dot({ grantor: 'SOMEONE ELSE' })]).cashBuy).toBe(true);
    expect(evaluateCashBuy(deed(), 'A1', [dot({ apn: 'B-9' })]).cashBuy).toBe(true);
  });

  it('matches the borrower by normalized name (LLC vs L.L.C.)', () => {
    expect(evaluateCashBuy(deed({ grantee: 'LONE STAR HOMES LLC' }), 'A1', [dot({ grantor: 'Lone Star Homes, L.L.C.' })]).cashBuy).toBe(false);
  });

  it('flags a deed of trust to a known hard-money lender as financed_hard_money, not cash', () => {
    const r = evaluateCashBuy(deed(), 'A1', [dot({ lender: 'Kiavi Funding, Inc.' })]);
    expect(r).toMatchObject({ counted: true, cashBuy: false, financedHardMoney: true });
    expect(evaluateCashBuy(deed(), 'A1', [dot({ lender: 'Acme Hard Money Lenders LLC' })]).financedHardMoney).toBe(true);
  });
});
