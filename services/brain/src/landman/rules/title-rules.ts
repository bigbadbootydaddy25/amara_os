/**
 * Title Rules Engine
 * Applies landman rules to a chain of title and emits TitleFlags.
 * Each rule is a pure function: instrument(s) → TitleFlag | null
 */

import type { TitleInstrument, OilGasLease, TitleFlag, TitleChain } from '../types.js';

const OK_STATUTORY_PUGH_DATE = new Date('1977-05-25');

// ─── Rule: Duhig ─────────────────────────────────────────────────────────────

/**
 * Duhig Rule: If a warranty deed conveys land but does NOT reference prior
 * mineral reservations, the grantor's new reservation absorbs the prior one.
 *
 * Returns a flag if Duhig is triggered (reservation math is at risk).
 */
export function checkDuhigRule(
  priorInstrument: TitleInstrument,
  currentInstrument: TitleInstrument,
): TitleFlag | null {
  if (currentInstrument.deedType !== 'warranty_deed') return null;
  if (!currentInstrument.reservation) return null;

  const priorHasReservation = Boolean(priorInstrument.reservation);
  const currentMentionsPrior =
    currentInstrument.reservation?.toLowerCase().includes('subject to') ||
    currentInstrument.reservation?.toLowerCase().includes('prior reservation') ||
    currentInstrument.reservation?.toLowerCase().includes('previous reservation');

  if (priorHasReservation && !currentMentionsPrior) {
    return {
      type:        'duhig_rule_triggered',
      severity:    'critical',
      description: `Warranty deed from ${currentInstrument.grantor} to ${currentInstrument.grantee} ` +
                   `reserves minerals but does not mention prior reservation by ${priorInstrument.grantor}. ` +
                   `Duhig Rule likely applies — ${currentInstrument.grantor} may own nothing.`,
      action:      'Recalculate mineral ownership. Prior grantor owns prior reservation; ' +
                   'grantee owns remainder per Duhig. Grantor in this deed likely owns zero.',
      instrument:  currentInstrument,
    };
  }

  return null;
}

// ─── Rule: Life Estate ────────────────────────────────────────────────────────

export function checkLifeEstate(instrument: TitleInstrument): TitleFlag | null {
  const text = (instrument.notes ?? '').toLowerCase() +
               (instrument.reservation ?? '').toLowerCase();

  if (text.includes('life estate') || text.includes('for life') || text.includes('remainder')) {
    return {
      type:        'life_estate',
      severity:    'warning',
      description: `Life estate detected in instrument from ${instrument.grantor} to ${instrument.grantee}.`,
      action:      'List life tenant as current owner. List remainderman in notes only. ' +
                   'Do not show remainderman as present owner until life tenant dies.',
      instrument,
    };
  }
  return null;
}

// ─── Rule: Probate ────────────────────────────────────────────────────────────

export function checkProbateRequired(
  instrument: TitleInstrument,
  chainHasFinalDecree: boolean,
): TitleFlag | null {
  if (
    instrument.deedType !== 'probate_decree' &&
    instrument.deedType !== 'descent_decree'
  ) return null;

  if (!chainHasFinalDecree) {
    return {
      type:        'probate_required',
      severity:    'critical',
      description: `Probate instrument found but no Final Decree located in chain.`,
      action:      'Locate the Final Decree — not the will. ' +
                   'Check probate records separately. Request certified copy if foreign probate.',
      instrument,
    };
  }
  return null;
}

// ─── Rule: HBP lease ─────────────────────────────────────────────────────────

export function checkHBP(lease: OilGasLease): TitleFlag | null {
  if (lease.status !== 'hbp') return null;
  return {
    type:        'hbp_lease',
    severity:    'warning',
    description: `Lease ${lease.book}/${lease.page} (${lease.lessor} → ${lease.lessee}) is Held By Production.`,
    action:      'Do not attempt to lease this mineral owner. ' +
                 'Flag as HBP in Ownership Report. Verify production is still in paying quantities.',
  };
}

// ─── Rule: Oklahoma Statutory Pugh (post May 25 1977) ────────────────────────

export function checkStatutoryPugh(lease: OilGasLease, state: string): TitleFlag | null {
  if (state.toUpperCase() !== 'OK') return null;

  const leaseDate = new Date(lease.leaseDate);
  if (isNaN(leaseDate.getTime())) return null;

  if (leaseDate > OK_STATUTORY_PUGH_DATE) {
    return {
      type:        'statutory_pugh_ok_1977',
      severity:    'info',
      description: `OGL dated ${lease.leaseDate} is subject to Oklahoma Statutory Pugh Clause (post-May 25, 1977). ` +
                   `Lands outside a 160-acre spacing unit are released 90 days after primary term.`,
      action:      'Confirm whether producing unit was formed before primary term expiry. ' +
                   'Non-unit acreage may be open even if lease appears HBP.',
    };
  }

  if (!lease.hasPughClause) {
    return {
      type:        'no_pugh_pre_1977',
      severity:    'warning',
      description: `Pre-1977 OGL (${lease.leaseDate}) has no Pugh clause. ` +
                   `Entire leased acreage is held by any producing well.`,
      action:      'Flag all acreage under this lease as potentially HBP. ' +
                   'Verify whether a well exists and is producing in paying quantities.',
    };
  }

  return null;
}

// ─── Rule: Quitclaim unverified ───────────────────────────────────────────────

export function checkQuitclaim(instrument: TitleInstrument): TitleFlag | null {
  if (instrument.deedType !== 'quitclaim_deed') return null;
  return {
    type:        'quitclaim_unverified',
    severity:    'warning',
    description: `Quitclaim deed from ${instrument.grantor} to ${instrument.grantee}. ` +
                 `Grantor conveys only whatever interest they actually hold — no warranties.`,
    action:      'Verify exactly what interest grantor held at time of QCD. ' +
                 'Cannot convey future-acquired interest. Check full chain to confirm scope.',
    instrument,
  };
}

// ─── Rule: Patent mineral reservation ────────────────────────────────────────

export function checkPatentReservation(
  instrument: TitleInstrument,
  state: string,
  patentYear: number,
): TitleFlag | null {
  if (instrument.deedType !== 'patent') return null;

  if (state.toUpperCase() === 'OK') {
    if (patentYear < 1933) {
      return {
        type:        'patent_pre_1933_no_reservation',
        severity:    'info',
        description: `Patent dated pre-1933 in Oklahoma. State did NOT reserve minerals.`,
        action:      'No state mineral reservation. First private owner received fee simple including minerals.',
      };
    } else {
      return {
        type:        'patent_post_1933_check_reservation',
        severity:    'warning',
        description: `Patent dated post-1933 in Oklahoma. State MAY have reserved minerals if land was valuable for O&G.`,
        action:      'Check patent language carefully for state mineral reservation.',
        instrument,
      };
    }
  }

  return null;
}

// ─── Rule: NPRI in chain ──────────────────────────────────────────────────────

export function checkNPRI(instrument: TitleInstrument): TitleFlag | null {
  const isNPRI =
    instrument.interestType === 'npri' ||
    (instrument.notes ?? '').toLowerCase().includes('npri') ||
    (instrument.notes ?? '').toLowerCase().includes('non-participating royalty');

  if (!isNPRI) return null;

  return {
    type:        'npri_in_chain',
    severity:    'info',
    description: `Non-Participating Royalty Interest (NPRI) found: ${instrument.grantor} → ${instrument.grantee}.`,
    action:      'NPRI owner receives royalty only — no right to lease, bonus, rentals, or ingress/egress. ' +
                 'Executive right holder leases on their behalf. List separately in OR.',
    instrument,
  };
}

// ─── Rule: Correction section ─────────────────────────────────────────────────

export function checkCorrectionSection(
  section: number,
  township: number,
  range: number,
  isNorthEdge: boolean,
  isWestEdge: boolean,
): TitleFlag | null {
  if (!isNorthEdge && !isWestEdge) return null;

  return {
    type:        'correction_section',
    severity:    'warning',
    description: `Section ${section}, T${township}, R${range} appears to be on the north/west township edge — correction section.`,
    action:      'Use lot numbers, not standard quarter-quarter designations. ' +
                 'Lot sizes vary from standard 40 acres. Verify exact lot acreage from BLM/GLO records.',
  };
}

// ─── Full chain analyser ──────────────────────────────────────────────────────

export function analyzeChain(
  chain: TitleChain,
  leases: OilGasLease[],
  state: string,
): TitleFlag[] {
  const flags: TitleFlag[] = [];
  const instruments = chain.instruments;

  const hasFinalDecree = instruments.some(
    (i) => i.deedType === 'probate_decree' || i.deedType === 'descent_decree',
  );

  for (let i = 0; i < instruments.length; i++) {
    const inst = instruments[i];
    const prev = i > 0 ? instruments[i - 1] : null;

    // Duhig
    if (prev) {
      const duhig = checkDuhigRule(prev, inst);
      if (duhig) flags.push(duhig);
    }

    // Life estate
    const le = checkLifeEstate(inst);
    if (le) flags.push(le);

    // Probate
    const prob = checkProbateRequired(inst, hasFinalDecree);
    if (prob) flags.push(prob);

    // Quitclaim
    const qcd = checkQuitclaim(inst);
    if (qcd) flags.push(qcd);

    // NPRI
    const npri = checkNPRI(inst);
    if (npri) flags.push(npri);

    // Patent
    if (inst.deedType === 'patent') {
      const year = parseInt(inst.instrumentDate.slice(0, 4), 10);
      const pat = checkPatentReservation(inst, state, year);
      if (pat) flags.push(pat);
    }
  }

  // Lease rules
  for (const lease of leases) {
    const hbp = checkHBP(lease);
    if (hbp) flags.push(hbp);

    const pugh = checkStatutoryPugh(lease, state);
    if (pugh) flags.push(pugh);
  }

  return flags;
}
