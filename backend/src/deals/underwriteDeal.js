/**
 * AMARA OS — underwriteDeal.js
 * SFR deal underwriting: ARV → repairs → MAO → assignment fee.
 *
 * Formula:
 *   MAO = (ARV × buyerPercent) - repairs - 10,000
 *
 * Buyer percentage tiers:
 *   0.80  — hot ZIP (high demand, active buyers, low DOM)
 *   0.75  — normal ZIP (standard)
 *   0.70  — weak ZIP (slow market, low buyer activity)
 *
 * Hard rules (never override):
 *   - Assignment fee minimum: $10,000
 *   - Do NOT use 70% ARV as a standalone rule
 */

'use strict';

const { estimateARV }     = require('./estimateARV');
const { estimateRepairs } = require('./estimateRepairs');

const MIN_ASSIGNMENT_FEE    = 10_000;
const TARGET_ASSIGNMENT_FEE = 15_000;

// Buyer percentage by ZIP activity tier
const BUYER_PCT = {
  hot:    0.80,
  normal: 0.75,
  weak:   0.70,
};

/**
 * Determine buyer percentage from ZIP tier.
 * Defaults to normal (0.75) if unknown.
 *
 * @param {string} [zipTier] - hot / normal / weak
 * @returns {number}
 */
function getBuyerPct(zipTier) {
  return BUYER_PCT[zipTier] ?? BUYER_PCT.normal;
}

/**
 * Underwrite a single SFR property.
 *
 * @param {Object} property - Normalized property object
 * @param {string} [zipTier] - hot / normal / weak (from buyer intelligence)
 * @returns {Object} Underwriting result
 */
function underwriteDeal(property, zipTier = 'normal') {
  const listPrice = property.price ?? property.listPrice ?? 0;

  // Step 1: ARV estimate
  const { arv, condition, multiplier } = estimateARV(property);

  // Step 2: Repairs
  const propWithCondition = { ...property, condition };
  const { repairs, basis: repairBasis } = estimateRepairs(propWithCondition);

  // Step 3: Buyer percentage
  const buyerPct   = getBuyerPct(zipTier);
  const buyerPrice = Math.round(arv * buyerPct / 1_000) * 1_000;

  // Step 4: MAO
  // MAO = (ARV × buyerPct) - repairs - MIN_ASSIGNMENT_FEE
  const mao        = buyerPrice - repairs - MIN_ASSIGNMENT_FEE;

  // Step 5: Assignment fee at list price
  const assignment = buyerPrice - repairs - listPrice;

  // Step 6: Decision
  // Approved if assignment fee (at list price) meets minimum.
  // If list is above MAO, we note it — seller must negotiate down to MAO.
  const approved     = assignment >= MIN_ASSIGNMENT_FEE;
  const aboveMAO     = listPrice > mao;
  const rejectReason = !approved
    ? `Assignment fee $${assignment.toLocaleString()} below $${MIN_ASSIGNMENT_FEE.toLocaleString()} minimum` +
      (aboveMAO ? ` — list price $${listPrice.toLocaleString()} exceeds MAO $${mao.toLocaleString()}` : '')
    : null;

  return {
    address:        property.address,
    zip:            property.zip ?? property.zipCode ?? '',
    price:          listPrice,
    arv,
    condition,
    arvMultiplier:  multiplier,
    repairs,
    repairBasis,
    buyerPct,
    buyerPrice,
    mao,
    assignment,
    approved,
    aboveMAO:       listPrice > mao,
    rejectReason,
    zipTier,
  };
}

module.exports = {
  underwriteDeal,
  getBuyerPct,
  MIN_ASSIGNMENT_FEE,
  TARGET_ASSIGNMENT_FEE,
  BUYER_PCT,
};
