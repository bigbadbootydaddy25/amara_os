/**
 * AMARA OS — matchBuyers.js
 * Match underwritten deals to vetted buyers.
 *
 * Matching criteria:
 *   - ZIP code match
 *   - Price range (deal MAO within buyer min/max)
 *   - Property type match (SFR)
 *   - Activity: totalDeals >= 3, activity within last 24-36 months
 *
 * Scoring tiers:
 *   A-tier: totalDeals >= 10 AND activity within 12mo
 *   B-tier: totalDeals >= 3  AND activity within 36mo
 *
 * LLC verification:
 *   - yearsActive >= 3 required
 *   - Buyers failing LLC check are excluded
 *
 * Returns best buyer (A-tier first, then B-tier).
 */

'use strict';

const { verifyLLC }          = require('../osint/llcVerification');

const MIN_DEALS_REQUIRED = 3;
const MAX_MONTHS_INACTIVE = 36;

/**
 * Determine buyer tier based on activity.
 *
 * @param {Object} buyer
 * @returns {'A'|'B'|null} - null if buyer does not qualify
 */
function getBuyerTier(buyer) {
  const totalDeals    = buyer.totalDeals    ?? buyer.dealCount24mo ?? 0;
  const monthsInactive = buyer.monthsInactive ?? 0;

  if (totalDeals < MIN_DEALS_REQUIRED) return null;
  if (monthsInactive > MAX_MONTHS_INACTIVE) return null;

  if (totalDeals >= 10 && monthsInactive <= 12) return 'A';
  return 'B';
}

/**
 * Check if a buyer's ZIP list includes the deal ZIP.
 *
 * @param {Object} buyer
 * @param {string} dealZip
 * @returns {boolean}
 */
function zipMatch(buyer, dealZip) {
  const zips = buyer.zipCodes ?? buyer.zips ?? [];
  return zips.includes(dealZip);
}

/**
 * Check if deal MAO falls within buyer price range.
 *
 * @param {Object} buyer
 * @param {number} mao
 * @returns {boolean}
 */
function priceMatch(buyer, mao) {
  const minPrice = buyer.minPrice ?? 0;
  const maxPrice = buyer.maxPrice ?? Infinity;
  return mao >= minPrice && mao <= maxPrice * 1.10; // 10% tolerance above ceiling
}

/**
 * Match a single underwritten deal to the best available buyer.
 *
 * @param {Object} underwrite - Output from underwriteDeal()
 * @param {Object[]} buyers   - Vetted buyer list from buyer intelligence engine
 * @returns {{ buyer: Object|null, tier: string|null, llcResult: Object|null, rejectReason: string|null }}
 */
function matchBestBuyer(underwrite, buyers) {
  const dealZip = underwrite.zip ?? '';
  const mao     = underwrite.mao ?? 0;

  const candidates = [];

  for (const buyer of buyers) {
    // ZIP check
    if (!zipMatch(buyer, dealZip)) continue;

    // Price range check
    if (!priceMatch(buyer, mao)) continue;

    // Property type check
    const types = buyer.propertyTypes ?? buyer.assetTypes ?? ['SFR'];
    if (!types.includes('SFR')) continue;

    // Activity + tier check
    const tier = getBuyerTier(buyer);
    if (!tier) continue;

    // LLC verification
    const llc = verifyLLC(buyer);
    if (!llc.verified) continue;

    candidates.push({ buyer, tier, llcResult: llc });
  }

  if (candidates.length === 0) {
    return {
      buyer:        null,
      tier:         null,
      llcResult:    null,
      rejectReason: `No qualified buyer found for ZIP ${dealZip} at MAO $${mao.toLocaleString()}`,
    };
  }

  // Rank: A-tier first, then by totalDeals desc
  candidates.sort((a, b) => {
    if (a.tier !== b.tier) return a.tier === 'A' ? -1 : 1;
    const dealsA = a.buyer.totalDeals ?? 0;
    const dealsB = b.buyer.totalDeals ?? 0;
    return dealsB - dealsA;
  });

  const { buyer, tier, llcResult } = candidates[0];

  return { buyer, tier, llcResult, rejectReason: null };
}

/**
 * Match all approved underwritten deals to buyers.
 *
 * @param {Object[]} underwrites - Array of underwrite results (approved only)
 * @param {Object[]} buyers      - Buyer list
 * @returns {{ matched: Object[], unmatched: Object[] }}
 */
function matchBuyers(underwrites, buyers) {
  const matched   = [];
  const unmatched = [];

  for (const uw of underwrites) {
    if (!uw.approved) {
      unmatched.push({ ...uw, _matchRejectReason: uw.rejectReason });
      continue;
    }

    const { buyer, tier, llcResult, rejectReason } = matchBestBuyer(uw, buyers);

    if (!buyer) {
      unmatched.push({ ...uw, _matchRejectReason: rejectReason });
    } else {
      matched.push({
        ...uw,
        buyer: {
          id:         buyer.buyerId    ?? buyer.id    ?? '',
          name:       buyer.name       ?? buyer.buyerName ?? 'Unknown',
          entity:     buyer.entityName ?? buyer.entity ?? '',
          tier,
          zip:        uw.zip,
          totalDeals: buyer.totalDeals ?? 0,
          llc:        llcResult,
        },
      });
    }
  }

  return { matched, unmatched };
}

module.exports = { matchBuyers, matchBestBuyer, getBuyerTier, zipMatch, priceMatch };
