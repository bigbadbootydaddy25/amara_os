/**
 * AMARA OS — processSFRDeals.js
 * Main deal execution pipeline for distressed SFR properties.
 *
 * Stages:
 *   1. Filter  — distress signals + DOM check
 *   2. Underwrite — ARV, repairs, MAO, assignment fee
 *   3. Match   — ZIP + buy box + LLC age
 *   4. Output  — approved/rejected JSON + offer payloads
 *
 * Core rule: buyer-first enforced at Stage 3.
 * Deals without a matched, LLC-verified buyer are rejected.
 */

'use strict';

const { filterDeals }    = require('./filterDeals');
const { underwriteDeal } = require('./underwriteDeal');
const { matchBuyers }    = require('./matchBuyers');

/**
 * Build the ZIP tier map from buyer activity.
 * ZIPs with >= 3 active A-tier buyers = hot.
 * ZIPs with any B-tier buyers = normal.
 * Everything else = weak.
 *
 * @param {Object[]} buyers
 * @returns {Object} { [zip]: 'hot'|'normal'|'weak' }
 */
function buildZipTierMap(buyers) {
  const zipCounts = {};

  for (const buyer of buyers) {
    const zips = buyer.zipCodes ?? buyer.zips ?? [];
    const totalDeals = buyer.totalDeals ?? 0;
    for (const zip of zips) {
      if (!zipCounts[zip]) zipCounts[zip] = { hot: 0, normal: 0 };
      if (totalDeals >= 10) zipCounts[zip].hot++;
      else if (totalDeals >= 3) zipCounts[zip].normal++;
    }
  }

  const tiers = {};
  for (const [zip, counts] of Object.entries(zipCounts)) {
    if (counts.hot >= 1)   tiers[zip] = 'hot';
    else if (counts.normal > 0) tiers[zip] = 'normal';
    else tiers[zip] = 'weak';
  }

  return tiers;
}

/**
 * Build offer payload for a matched deal.
 *
 * @param {Object} deal - Matched deal with buyer
 * @returns {Object} offerPayload
 */
function buildOfferPayload(deal) {
  const { address, zip, mao, buyer } = deal;

  const subject = `Offer for ${address}`;
  const body = [
    `Hi ${buyer.name},`,
    '',
    `We are cash buyers interested in the property at ${address} (${zip}).`,
    '',
    `Our offer: $${mao.toLocaleString()} cash — as-is, no repairs, no commissions.`,
    '',
    'Terms:',
    '- All cash, no financing contingency',
    '- 1% earnest money',
    '- 10-day inspection period',
    '- 21-day close (flexible)',
    '- Assignment of contract allowed',
    '- Close in as-is condition',
    '',
    'We can move quickly and handle all paperwork. No fees to the seller.',
    '',
    'Please reply or call anytime to discuss.',
    '',
    'Best,',
    'AMARA Acquisitions',
  ].join('\n');

  return {
    to:         buyer.email ?? '',
    subject,
    body,
    offerPrice: mao,
    address,
    zip,
  };
}

/**
 * Full SFR deal execution pipeline.
 *
 * @param {Object[]} properties  - Normalized property list
 * @param {Object[]} buyers      - Vetted buyer list from buyer intelligence
 * @returns {{ approvedDeals: Object[], rejectedDeals: Object[], summary: Object }}
 */
function processSFRDeals(properties, buyers) {
  // ── Stage 1: Filter ───────────────────────────────────────────────────────
  const { approved: filtered, rejected: filteredOut } = filterDeals(properties);

  // ── Stage 2: Underwrite ───────────────────────────────────────────────────
  const zipTiers    = buildZipTierMap(buyers);
  const underwrites = filtered.map(prop => {
    const zip     = prop.zip ?? prop.zipCode ?? '';
    const zipTier = zipTiers[zip] ?? 'normal';
    return underwriteDeal(prop, zipTier);
  });

  const uwApproved = underwrites.filter(u =>  u.approved);
  const uwRejected = underwrites.filter(u => !u.approved);

  // ── Stage 3: Buyer Match (buyer-first enforced) ───────────────────────────
  const { matched, unmatched } = matchBuyers(uwApproved, buyers);

  // ── Stage 4: Build Output ─────────────────────────────────────────────────
  const approvedDeals = matched.map(deal => ({
    address:    deal.address,
    zip:        deal.zip,
    price:      deal.price,
    arv:        deal.arv,
    condition:  deal.condition,
    repairs:    deal.repairs,
    mao:        deal.mao,
    assignment: deal.assignment,
    buyer: {
      name:   deal.buyer.name,
      tier:   deal.buyer.tier,
      zip:    deal.buyer.zip,
      entity: deal.buyer.entity,
      llcYearsActive: deal.buyer.llc?.yearsActive ?? null,
    },
    offerPayload: buildOfferPayload(deal),
  }));

  const rejectedDeals = [
    ...filteredOut.map(p => ({
      address:      p.address ?? '',
      zip:          p.zip ?? p.zipCode ?? '',
      price:        p.price ?? p.listPrice ?? 0,
      rejectStage:  'filter',
      rejectReason: p._rejectReason,
    })),
    ...uwRejected.map(u => ({
      address:      u.address,
      zip:          u.zip,
      price:        u.price,
      rejectStage:  'underwriting',
      rejectReason: u.rejectReason,
    })),
    ...unmatched.map(u => ({
      address:      u.address,
      zip:          u.zip,
      price:        u.price,
      rejectStage:  'buyer_match',
      rejectReason: u._matchRejectReason ?? u.rejectReason,
    })),
  ];

  const summary = {
    totalInput:          properties.length,
    passedFilter:        filtered.length,
    failedFilter:        filteredOut.length,
    passedUnderwriting:  uwApproved.length,
    failedUnderwriting:  uwRejected.length,
    matchedWithBuyer:    matched.length,
    noMatchFound:        unmatched.length,
    approvedDeals:       approvedDeals.length,
    rejectedDeals:       rejectedDeals.length,
  };

  return { approvedDeals, rejectedDeals, summary };
}

module.exports = { processSFRDeals, buildOfferPayload, buildZipTierMap };
