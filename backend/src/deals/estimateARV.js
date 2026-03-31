/**
 * AMARA OS — estimateARV.js
 * Heuristic ARV estimate from list price, sqft, and condition.
 *
 * In production this is replaced by a live comp read
 * (see playbooks/comps/sfr_comp_reading.md).
 * For now: ARV = list price adjusted by condition multiplier.
 */

'use strict';

// Per-sqft ARV estimates by condition (retail comp-based, not list-price-based)
// Distressed properties are priced BELOW ARV — ARV is the retail comp value
// after repairs are complete. Using sqft-based estimate when comps unavailable.
const ARV_PER_SQFT = {
  light:   120,   // cosmetic only — near retail
  medium:  115,   // standard rehab
  heavy:   105,   // full rehab — lower finished value
  unknown: 115,   // default
};

// Fallback: condition multipliers on list price when sqft unavailable
const CONDITION_MULTIPLIERS = {
  light:   1.20,
  medium:  1.35,
  heavy:   1.55,
  unknown: 1.30,
};

/**
 * Infer condition from description keywords.
 * @param {string} description
 * @returns {'light'|'medium'|'heavy'|'unknown'}
 */
function inferCondition(description) {
  if (!description) return 'unknown';
  const lower = description.toLowerCase();

  if (lower.includes('cosmetic') || lower.includes('paint') || lower.includes('carpet')) {
    return 'light';
  }
  if (
    lower.includes('full rehab') ||
    lower.includes('major') ||
    lower.includes('foundation') ||
    lower.includes('roof') ||
    lower.includes('fire') ||
    lower.includes('flood') ||
    lower.includes('gutted')
  ) {
    return 'heavy';
  }
  if (
    lower.includes('updates needed') ||
    lower.includes('needs work') ||
    lower.includes('tlc') ||
    lower.includes('fixer') ||
    lower.includes('repairs')
  ) {
    return 'medium';
  }

  return 'unknown';
}

/**
 * Estimate ARV for an SFR property.
 *
 * @param {Object} property
 * @param {number} property.price - Current list price
 * @param {number} [property.sqft] - Square footage
 * @param {string} [property.description] - Property description
 * @param {string} [property.condition] - Explicit condition override
 * @returns {{ arv: number, condition: string, multiplier: number }}
 */
function estimateARV(property) {
  const listPrice = property.price ?? property.listPrice ?? 0;
  const sqft      = property.sqft  ?? property.squareFeet ?? 0;

  const condition =
    property.condition ??
    inferCondition(property.description ?? property.remarks ?? '');

  let arv, multiplier;

  if (sqft > 0) {
    // Primary: sqft-based comp estimate — ARV is retail value after repair, not list-relative
    const ppsf = ARV_PER_SQFT[condition] ?? ARV_PER_SQFT.unknown;
    arv        = Math.round(sqft * ppsf / 1_000) * 1_000;
    multiplier = listPrice > 0 ? arv / listPrice : 0;
  } else {
    // Fallback: multiplier on list price when no sqft
    multiplier = CONDITION_MULTIPLIERS[condition] ?? CONDITION_MULTIPLIERS.unknown;
    arv        = Math.round(listPrice * multiplier / 1_000) * 1_000;
  }

  return { arv, condition, multiplier: Math.round(multiplier * 100) / 100 };
}

module.exports = { estimateARV, inferCondition, CONDITION_MULTIPLIERS };
