/**
 * AMARA OS — estimateRepairs.js
 * Fast repair estimate from condition and sqft.
 *
 * Tiers:
 *   light:  $10,000 base (cosmetic only)
 *   medium: $25,000 base (standard rehab)
 *   heavy:  $50,000+ (full rehab, major systems)
 *
 * Adjusted by sqft above 1,500:
 *   every 500 sqft over 1,500 adds one tier-proportional increment.
 */

'use strict';

const REPAIR_BASE = {
  light:   10_000,
  medium:  25_000,
  heavy:   50_000,
  unknown: 25_000,  // default to medium
};

// Per-sqft increment above 1,500 sqft baseline
const SQFT_INCREMENT = {
  light:   2_000,   // per 500 sqft
  medium:  5_000,
  heavy:  10_000,
  unknown: 5_000,
};

const SQFT_BASELINE = 1_500;
const SQFT_STEP     = 500;

/**
 * Estimate repair cost for an SFR property.
 *
 * @param {Object} property
 * @param {string} [property.condition] - light / medium / heavy / unknown
 * @param {number} [property.sqft]
 * @returns {{ repairs: number, condition: string, basis: string }}
 */
function estimateRepairs(property) {
  const condition = property.condition ?? 'unknown';
  const sqft      = property.sqft ?? property.squareFeet ?? 0;

  const base      = REPAIR_BASE[condition]    ?? REPAIR_BASE.unknown;
  const increment = SQFT_INCREMENT[condition] ?? SQFT_INCREMENT.unknown;

  let repairs = base;

  if (sqft > SQFT_BASELINE) {
    const steps = Math.floor((sqft - SQFT_BASELINE) / SQFT_STEP);
    repairs += steps * increment;
  }

  // Round up to nearest $5,000
  repairs = Math.ceil(repairs / 5_000) * 5_000;

  return {
    repairs,
    condition,
    basis: `${condition} condition, ${sqft > 0 ? sqft + ' sqft' : 'sqft unknown'}`,
  };
}

module.exports = { estimateRepairs, REPAIR_BASE, SQFT_BASELINE };
