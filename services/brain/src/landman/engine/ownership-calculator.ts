/**
 * Mineral Ownership Calculator
 *
 * Walks a chain of title and computes the current fractional mineral
 * ownership of each party. Applies the Duhig Rule where triggered.
 */

import type { TitleInstrument, MineralOwner, OilGasLease } from '../types.js';
import { checkDuhigRule, checkHBP } from '../rules/title-rules.js';

export interface OwnershipLedger {
  owners: Map<string, OwnerRecord>;
  totalAccountedFor: number;  // should sum to 1.0
  warnings: string[];
}

export interface OwnerRecord {
  name:           string;
  decimalInterest: number;
  interestType:   string;
  sourceBook:     string;
  sourcePage:     string;
  notes:          string[];
}

// ─── Fraction parser ──────────────────────────────────────────────────────────

export function parseFraction(fraction: string): number {
  if (!fraction) return 0;
  if (fraction.toUpperCase() === 'ARTI') return 1.0;

  // Handle decimal
  const asFloat = parseFloat(fraction);
  if (!isNaN(asFloat) && fraction.includes('.')) return asFloat;

  // Handle "X/Y"
  const parts = fraction.trim().split('/');
  if (parts.length === 2) {
    const num = parseFloat(parts[0]);
    const den = parseFloat(parts[1]);
    if (!isNaN(num) && !isNaN(den) && den !== 0) return num / den;
  }

  return 0;
}

// ─── Ownership ledger builder ─────────────────────────────────────────────────

export function buildOwnershipLedger(
  instruments: TitleInstrument[],
): OwnershipLedger {
  const owners = new Map<string, OwnerRecord>();
  const warnings: string[] = [];

  for (let i = 0; i < instruments.length; i++) {
    const inst = instruments[i];
    const prev = i > 0 ? instruments[i - 1] : null;

    let fraction = parseFraction(inst.interestFraction ?? 'ARTI');

    // ── Duhig adjustment ────────────────────────────────────────────────────
    if (prev) {
      const duhigFlag = checkDuhigRule(prev, inst);
      if (duhigFlag) {
        warnings.push(`Duhig triggered: ${inst.grantor} likely owns 0 after conveying to ${inst.grantee}.`);

        // Grantor absorbs prior reservation — they keep nothing
        if (owners.has(inst.grantor)) {
          const grantorRecord = owners.get(inst.grantor)!;
          warnings.push(
            `Zeroing out ${inst.grantor} interest (was ${grantorRecord.decimalInterest.toFixed(6)}) per Duhig.`,
          );
          owners.set(inst.grantor, { ...grantorRecord, decimalInterest: 0 });
        }
      }
    }

    // ── ARTI: transfer everything grantor owns ───────────────────────────────
    if (!inst.interestFraction || inst.interestFraction.toUpperCase() === 'ARTI') {
      const grantorRecord = owners.get(inst.grantor);
      fraction = grantorRecord?.decimalInterest ?? fraction;

      // Remove from grantor
      if (grantorRecord) {
        owners.set(inst.grantor, { ...grantorRecord, decimalInterest: 0 });
      }
    } else {
      // Partial conveyance — reduce grantor's interest
      const grantorRecord = owners.get(inst.grantor);
      if (grantorRecord) {
        const remaining = Math.max(0, grantorRecord.decimalInterest - fraction);
        owners.set(inst.grantor, { ...grantorRecord, decimalInterest: remaining });
      }
    }

    // ── Credit grantee ───────────────────────────────────────────────────────
    const existing = owners.get(inst.grantee);
    if (existing) {
      owners.set(inst.grantee, {
        ...existing,
        decimalInterest: existing.decimalInterest + fraction,
        notes: [...existing.notes, `+${fraction.toFixed(6)} from ${inst.book}/${inst.page}`],
      });
    } else {
      owners.set(inst.grantee, {
        name:            inst.grantee,
        decimalInterest: fraction,
        interestType:    inst.interestType,
        sourceBook:      inst.book,
        sourcePage:      inst.page,
        notes:           [`${fraction.toFixed(6)} from ${inst.book}/${inst.page}`],
      });
    }
  }

  // Remove zero-interest parties
  for (const [name, record] of owners) {
    if (record.decimalInterest <= 0) owners.delete(name);
  }

  const totalAccountedFor = [...owners.values()].reduce(
    (s, r) => s + r.decimalInterest, 0,
  );

  return { owners, totalAccountedFor, warnings };
}

// ─── Ownership report builder ─────────────────────────────────────────────────

export function buildMineralOwners(
  instruments: TitleInstrument[],
  leases: OilGasLease[],
): MineralOwner[] {
  const ledger = buildOwnershipLedger(instruments);
  const leaseMap = new Map<string, OilGasLease>();

  for (const lease of leases) {
    leaseMap.set(lease.lessor.toLowerCase(), lease);
  }

  const mineralOwners: MineralOwner[] = [];

  for (const record of ledger.owners.values()) {
    const lease = leaseMap.get(record.name.toLowerCase());
    const leaseStatus = determineLeaseStatus(record.name, lease);

    mineralOwners.push({
      name:            record.name,
      interestType:    record.interestType as MineralOwner['interestType'],
      fraction:        toFractionString(record.decimalInterest),
      decimalInterest: record.decimalInterest,
      leaseStatus,
      lease:           lease ?? undefined,
      notes:           record.notes.join('; '),
    });
  }

  // Sort: highest interest first
  return mineralOwners.sort((a, b) => b.decimalInterest - a.decimalInterest);
}

function determineLeaseStatus(
  ownerName: string,
  lease?: OilGasLease,
): MineralOwner['leaseStatus'] {
  if (!lease) return 'open';
  return lease.status === 'in_term' ? 'in_term'
       : lease.status === 'hbp'     ? 'hbp'
       : lease.status === 'released' || lease.status === 'expired' ? 'open'
       : 'unleased';
}

// Convert decimal to nearest simple fraction string
function toFractionString(decimal: number): string {
  if (decimal <= 0) return '0';
  if (decimal >= 1) return '1/1';

  const denominators = [2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64];
  let best = { num: 1, den: 1, err: Infinity };

  for (const den of denominators) {
    const num = Math.round(decimal * den);
    const err = Math.abs(decimal - num / den);
    if (err < best.err) best = { num, den, err };
  }

  if (best.err < 0.001) return `${best.num}/${best.den}`;
  return decimal.toFixed(6); // fall back to decimal if no clean fraction
}
