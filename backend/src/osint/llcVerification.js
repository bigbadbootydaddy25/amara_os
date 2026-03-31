/**
 * AMARA OS — llcVerification.js
 * LLC age verification for buyer entities.
 *
 * Minimum requirement: 3 years active (yearsActive >= 3)
 *
 * In production: integrate with state SOS APIs or OSINT data source.
 * Current implementation: mock/simulate with buyer record data.
 *
 * Input:  buyer.entityName + optional buyer.formationDate
 * Output: { entityName, formationDate, yearsActive, verified }
 */

'use strict';

const MIN_YEARS_ACTIVE = 3;

/**
 * Calculate years active from a formation date string.
 *
 * @param {string} formationDate - ISO date string (e.g. '2019-04-15')
 * @returns {number} Years active (fractional, floored)
 */
function calcYearsActive(formationDate) {
  if (!formationDate) return 0;
  const formed = new Date(formationDate);
  if (isNaN(formed.getTime())) return 0;
  const now    = new Date();
  const ms     = now - formed;
  return Math.floor(ms / (1000 * 60 * 60 * 24 * 365.25));
}

/**
 * Verify LLC age for a buyer entity.
 *
 * Mock behavior:
 * - If buyer.formationDate is provided: use it directly.
 * - If not provided: simulate by estimating from deal activity data.
 *   If buyer.totalDeals >= 10, assume 5+ years active (established entity).
 *   If buyer.totalDeals >= 3,  assume 3 years active (meets minimum).
 *   Otherwise: assume 1 year (fails).
 *
 * @param {Object} buyer
 * @param {string} buyer.entityName
 * @param {string} [buyer.formationDate] - ISO date string
 * @param {number} [buyer.totalDeals]    - Used for simulation if no date
 * @returns {{ entityName: string, formationDate: string|null, yearsActive: number, verified: boolean }}
 */
function verifyLLC(buyer) {
  const entityName = buyer.entityName ?? buyer.entity ?? buyer.name ?? 'Unknown Entity';

  let formationDate = buyer.formationDate ?? null;
  let yearsActive;

  if (formationDate) {
    yearsActive = calcYearsActive(formationDate);
  } else {
    // Simulate from deal activity
    const totalDeals = buyer.totalDeals ?? buyer.dealCount24mo ?? 0;
    if (totalDeals >= 10) {
      yearsActive   = 6;
      formationDate = new Date(Date.now() - yearsActive * 365.25 * 24 * 3600 * 1000)
        .toISOString()
        .slice(0, 10);
    } else if (totalDeals >= 3) {
      yearsActive   = 4;
      formationDate = new Date(Date.now() - yearsActive * 365.25 * 24 * 3600 * 1000)
        .toISOString()
        .slice(0, 10);
    } else {
      yearsActive   = 1;
      formationDate = new Date(Date.now() - yearsActive * 365.25 * 24 * 3600 * 1000)
        .toISOString()
        .slice(0, 10);
    }
  }

  const verified = yearsActive >= MIN_YEARS_ACTIVE;

  return {
    entityName,
    formationDate,
    yearsActive,
    verified,
    rejectReason: verified ? null : `Entity active ${yearsActive} year(s) — minimum ${MIN_YEARS_ACTIVE} required`,
  };
}

module.exports = { verifyLLC, calcYearsActive, MIN_YEARS_ACTIVE };
