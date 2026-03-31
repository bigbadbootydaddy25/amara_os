/**
 * AMARA OS — filterDeals.js
 * Filter normalized properties to distressed SFR candidates only.
 *
 * Rules:
 * - daysOnMarket >= 60 (prioritize >= 90)
 * - description contains at least one distress keyword
 * - Reject clean retail listings with no distress signal
 */

'use strict';

const DISTRESS_KEYWORDS = [
  'as is',
  'as-is',
  'investor',
  'updates needed',
  'fixer',
  'tlc',
  'repairs',
  'estate',
  'probate',
  'tenant',
  'opportunity',
  'cash',
  'needs work',
  'bring all offers',
];

const DOM_THRESHOLD      = 60;   // minimum days on market
const DOM_PRIORITY       = 90;   // prioritized threshold

/**
 * Check if a property description contains any distress signal.
 * @param {string} description
 * @returns {string[]} matched keywords
 */
function findDistressSignals(description) {
  if (!description) return [];
  const lower = description.toLowerCase();
  return DISTRESS_KEYWORDS.filter(kw => lower.includes(kw));
}

/**
 * Filter a list of normalized properties to distressed candidates.
 *
 * @param {Object[]} properties - Normalized property objects
 * @returns {{ approved: Object[], rejected: Object[] }}
 */
function filterDeals(properties) {
  const approved = [];
  const rejected = [];

  for (const prop of properties) {
    const dom      = prop.daysOnMarket ?? prop.dom ?? 0;
    const desc     = prop.description ?? prop.remarks ?? '';
    const signals  = findDistressSignals(desc);
    const priority = dom >= DOM_PRIORITY;

    if (dom < DOM_THRESHOLD) {
      rejected.push({ ...prop, _rejectReason: `DOM ${dom} below ${DOM_THRESHOLD}` });
      continue;
    }

    if (signals.length === 0) {
      rejected.push({ ...prop, _rejectReason: 'No distress signal in description' });
      continue;
    }

    approved.push({
      ...prop,
      _distressSignals: signals,
      _priority: priority,
      _dom: dom,
    });
  }

  // Sort: priority (DOM >= 90) first, then by DOM desc
  approved.sort((a, b) => {
    if (a._priority !== b._priority) return a._priority ? -1 : 1;
    return (b._dom ?? 0) - (a._dom ?? 0);
  });

  return { approved, rejected };
}

module.exports = { filterDeals, findDistressSignals, DOM_THRESHOLD, DOM_PRIORITY };
