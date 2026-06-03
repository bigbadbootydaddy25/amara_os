import { describe, it, expect } from 'vitest';
import {
  parseAliquots,
  calculateAcres,
  parseSTR,
  parseMetesAndBounds,
  rodsToFeet,
  chainsToFeet,
} from '../landman/parsers/legal-description-parser.js';
import {
  checkDuhigRule,
  checkLifeEstate,
  checkHBP,
  checkStatutoryPugh,
  checkQuitclaim,
  checkPatentReservation,
  checkNPRI,
  analyzeChain,
} from '../landman/rules/title-rules.js';
import {
  parseFraction,
  buildOwnershipLedger,
  buildMineralOwners,
} from '../landman/engine/ownership-calculator.js';
import { generateOwnershipReport, formatOwnershipReport } from '../landman/engine/ownership-report.js';
import type { TitleInstrument, OilGasLease, TitleChain, STRLocation } from '../landman/types.js';

// ─── Shared fixtures ──────────────────────────────────────────────────────────

const STR: STRLocation = {
  section: 24, township: 14, townshipDir: 'N', range: 3, rangeDir: 'W',
  state: 'OK', county: 'Payne',
};

const PATENT: TitleInstrument = {
  deedType: 'patent', book: 'P', page: '1',
  instrumentDate: '1920-04-15',
  grantor: 'U.S. Government', grantee: 'John Smith',
  interestType: 'mineral', interestFraction: 'ARTI',
};

const WD_A_TO_B: TitleInstrument = {
  deedType: 'warranty_deed', book: '10', page: '5',
  instrumentDate: '1945-06-01',
  grantor: 'John Smith', grantee: 'Mary Jones',
  interestType: 'mineral', interestFraction: '1/2',
  reservation: '1/2 minerals reserved to grantor',
};

// Duhig-triggering deed: B conveys to C reserving 1/2 with NO mention of A's reservation
const WD_B_TO_C_DUHIG: TitleInstrument = {
  deedType: 'warranty_deed', book: '20', page: '3',
  instrumentDate: '1960-03-15',
  grantor: 'Mary Jones', grantee: 'Bob Williams',
  interestType: 'mineral', interestFraction: '1/2',
  reservation: '1/2 minerals reserved to grantor',  // no "subject to prior"
};

const WD_B_TO_C_SAFE: TitleInstrument = {
  ...WD_B_TO_C_DUHIG,
  reservation: '1/2 minerals reserved, subject to prior reservations of record',
};

// ─── Legal Description Parser ─────────────────────────────────────────────────

describe('Legal Description Parser', () => {
  it('calculates 640 acres for a full section', () => {
    expect(calculateAcres('section')).toBe(640);
  });

  it('calculates 320 acres for E/2', () => {
    expect(calculateAcres('E/2')).toBe(320);
  });

  it('calculates 160 acres for SE/4', () => {
    expect(calculateAcres('SE/4')).toBe(160);
  });

  it('calculates 40 acres for SW/4 NE/4', () => {
    expect(calculateAcres('SW/4 NE/4')).toBe(40);
  });

  it('calculates 80 acres for S/2 SW/4', () => {
    expect(calculateAcres('S/2 SW/4')).toBe(80);
  });

  it('calculates 20 acres for W/2 NW/4 SE/4', () => {
    expect(calculateAcres('W/2 NW/4 SE/4')).toBe(20);
  });

  it('calculates 10 acres for SW/4 SW/4 SE/4', () => {
    expect(calculateAcres('SW/4 SW/4 SE/4')).toBe(10);
  });

  it('parses multiple aliquots from comma-separated description', () => {
    const aliquots = parseAliquots('NE/4, SW/4');
    expect(aliquots).toHaveLength(2);
    expect(aliquots[0].acres).toBe(160);
    expect(aliquots[1].acres).toBe(160);
  });

  it('parses STR from text', () => {
    const str = parseSTR('Section 24, Township 14 N, Range 3 W, Payne County, Oklahoma');
    expect(str).not.toBeNull();
    expect(str?.section).toBe(24);
    expect(str?.township).toBe(14);
    expect(str?.townshipDir).toBe('N');
    expect(str?.range).toBe(3);
    expect(str?.rangeDir).toBe('W');
  });

  it('returns null for non-STR text', () => {
    expect(parseSTR('1234 Main Street, Houston TX')).toBeNull();
  });

  it('parses metes and bounds bearings', () => {
    const bearings = parseMetesAndBounds("thence N 42°35' W 200 feet, thence S 15°00' E 150 feet");
    expect(bearings).toHaveLength(2);
    expect(bearings[0].degrees).toBe(42);
    expect(bearings[0].minutes).toBe(35);
    expect(bearings[1].quadrant).toBe('SE');
  });

  it('converts rods to feet', () => {
    expect(rodsToFeet(4)).toBe(66);   // 4 rods = 1 chain = 66 feet
    expect(chainsToFeet(1)).toBe(66);
  });
});

// ─── Fraction parser ──────────────────────────────────────────────────────────

describe('Fraction Parser', () => {
  it('parses 1/2', () => expect(parseFraction('1/2')).toBeCloseTo(0.5));
  it('parses 1/4', () => expect(parseFraction('1/4')).toBeCloseTo(0.25));
  it('parses 1/8', () => expect(parseFraction('1/8')).toBeCloseTo(0.125));
  it('parses ARTI as 1.0', () => expect(parseFraction('ARTI')).toBe(1.0));
  it('parses decimal 0.25', () => expect(parseFraction('0.25')).toBeCloseTo(0.25));
  it('returns 0 for empty string', () => expect(parseFraction('')).toBe(0));
});

// ─── Title Rules ─────────────────────────────────────────────────────────────

describe('Duhig Rule', () => {
  it('triggers when warranty deed lacks prior reservation reference', () => {
    const flag = checkDuhigRule(WD_A_TO_B, WD_B_TO_C_DUHIG);
    expect(flag).not.toBeNull();
    expect(flag?.type).toBe('duhig_rule_triggered');
    expect(flag?.severity).toBe('critical');
  });

  it('does NOT trigger when deed says "subject to prior reservations"', () => {
    const flag = checkDuhigRule(WD_A_TO_B, WD_B_TO_C_SAFE);
    expect(flag).toBeNull();
  });

  it('does NOT trigger on a quitclaim deed', () => {
    const qcd = { ...WD_B_TO_C_DUHIG, deedType: 'quitclaim_deed' as const };
    const flag = checkDuhigRule(WD_A_TO_B, qcd);
    expect(flag).toBeNull();
  });
});

describe('Life Estate Rule', () => {
  it('flags life estate language', () => {
    const inst: TitleInstrument = {
      ...WD_A_TO_B,
      notes: 'Life estate to grantor, remainder to grantee',
    };
    const flag = checkLifeEstate(inst);
    expect(flag?.type).toBe('life_estate');
  });

  it('returns null for no life estate', () => {
    expect(checkLifeEstate(WD_A_TO_B)).toBeNull();
  });
});

describe('HBP Rule', () => {
  it('flags an HBP lease', () => {
    const lease: OilGasLease = {
      book: '50', page: '10', lessor: 'Bob Williams', lessee: 'Acme Oil',
      leaseDate: '1970-01-01', primaryTermYears: 3, royaltyFraction: 0.125,
      hasPughClause: false, hasDepthClause: false, status: 'hbp',
    };
    const flag = checkHBP(lease);
    expect(flag?.type).toBe('hbp_lease');
  });

  it('returns null for in_term lease', () => {
    const lease: OilGasLease = {
      book: '50', page: '11', lessor: 'Bob Williams', lessee: 'Acme Oil',
      leaseDate: '2024-01-01', primaryTermYears: 3, royaltyFraction: 0.125,
      hasPughClause: true, hasDepthClause: false, status: 'in_term',
    };
    expect(checkHBP(lease)).toBeNull();
  });
});

describe('Oklahoma Statutory Pugh', () => {
  it('flags post-1977 OGL with statutory Pugh notice', () => {
    const lease: OilGasLease = {
      book: '60', page: '1', lessor: 'A', lessee: 'B',
      leaseDate: '1980-03-01', primaryTermYears: 3, royaltyFraction: 0.125,
      hasPughClause: false, hasDepthClause: false, status: 'in_term',
    };
    const flag = checkStatutoryPugh(lease, 'OK');
    expect(flag?.type).toBe('statutory_pugh_ok_1977');
  });

  it('flags pre-1977 OGL without Pugh clause', () => {
    const lease: OilGasLease = {
      book: '30', page: '5', lessor: 'A', lessee: 'B',
      leaseDate: '1965-05-01', primaryTermYears: 3, royaltyFraction: 0.125,
      hasPughClause: false, hasDepthClause: false, status: 'in_term',
    };
    const flag = checkStatutoryPugh(lease, 'OK');
    expect(flag?.type).toBe('no_pugh_pre_1977');
  });

  it('returns null for non-Oklahoma state', () => {
    const lease: OilGasLease = {
      book: '1', page: '1', lessor: 'A', lessee: 'B',
      leaseDate: '1980-01-01', primaryTermYears: 3, royaltyFraction: 0.125,
      hasPughClause: false, hasDepthClause: false, status: 'in_term',
    };
    expect(checkStatutoryPugh(lease, 'TX')).toBeNull();
  });
});

describe('Patent Reservation', () => {
  it('flags pre-1933 Oklahoma patent as no mineral reservation', () => {
    const flag = checkPatentReservation(PATENT, 'OK', 1920);
    expect(flag?.type).toBe('patent_pre_1933_no_reservation');
  });

  it('flags post-1933 Oklahoma patent to check reservation', () => {
    const flag = checkPatentReservation({ ...PATENT, instrumentDate: '1945-01-01' }, 'OK', 1945);
    expect(flag?.type).toBe('patent_post_1933_check_reservation');
  });
});

describe('Quitclaim & NPRI', () => {
  it('flags a quitclaim deed', () => {
    const qcd: TitleInstrument = { ...WD_A_TO_B, deedType: 'quitclaim_deed' };
    expect(checkQuitclaim(qcd)?.type).toBe('quitclaim_unverified');
  });

  it('flags NPRI interest type', () => {
    const npri: TitleInstrument = { ...WD_A_TO_B, interestType: 'npri' };
    expect(checkNPRI(npri)?.type).toBe('npri_in_chain');
  });
});

// ─── Ownership Calculator ─────────────────────────────────────────────────────

describe('Ownership Calculator', () => {
  it('tracks simple chain: Patent → WD(ARTI) → total = 1.0', () => {
    const instruments = [PATENT, WD_A_TO_B];
    const ledger = buildOwnershipLedger(instruments);
    const total = ledger.totalAccountedFor;
    expect(total).toBeCloseTo(1.0, 4);
  });

  it('applies Duhig: grantor B ends up with 0', () => {
    const instruments = [PATENT, WD_A_TO_B, WD_B_TO_C_DUHIG];
    const ledger = buildOwnershipLedger(instruments);
    expect(ledger.warnings.some((w) => w.includes('Duhig'))).toBe(true);
    const maryRecord = ledger.owners.get('Mary Jones');
    expect(maryRecord).toBeUndefined(); // zeroed out
  });

  it('safe deed keeps grantor interest intact', () => {
    const instruments = [PATENT, WD_A_TO_B, WD_B_TO_C_SAFE];
    const ledger = buildOwnershipLedger(instruments);
    expect(ledger.warnings.some((w) => w.includes('Duhig'))).toBe(false);
  });
});

// ─── Ownership Report ─────────────────────────────────────────────────────────

describe('Ownership Report', () => {
  const chain: TitleChain = {
    strLocation: STR,
    instruments: [PATENT, WD_A_TO_B],
    builtAt: new Date(),
  };

  const lease: OilGasLease = {
    book: '40', page: '1', lessor: 'Mary Jones', lessee: 'Frontier Oil',
    leaseDate: '2022-06-01', primaryTermYears: 3,
    royaltyFraction: 0.125, hasPughClause: true, hasDepthClause: false,
    status: 'in_term', expiryDate: '2025-06-01',
  };

  it('generates a report with mineral owners', () => {
    const report = generateOwnershipReport({ chain, leases: [lease], state: 'OK', totalAcres: 640 });
    expect(report.mineralOwners.length).toBeGreaterThan(0);
    expect(report.preparedAt).toBeInstanceOf(Date);
    expect(report.strLocation.section).toBe(24);
  });

  it('includes flags for pre-1933 patent', () => {
    const report = generateOwnershipReport({ chain, leases: [], state: 'OK' });
    expect(report.flags.some((f) => f.type === 'patent_pre_1933_no_reservation')).toBe(true);
  });

  it('formats report as plain text', () => {
    const report = generateOwnershipReport({ chain, leases: [lease], state: 'OK', totalAcres: 640 });
    const text = formatOwnershipReport(report);
    expect(text).toContain('OWNERSHIP REPORT');
    expect(text).toContain('MINERAL OWNERSHIP');
    expect(text).toContain('Section 24');
  });

  it('marks open mineral owners in report', () => {
    const report = generateOwnershipReport({ chain, leases: [], state: 'OK' });
    const openOwners = report.mineralOwners.filter((o) => o.leaseStatus === 'open');
    expect(openOwners.length).toBeGreaterThan(0);
  });
});
