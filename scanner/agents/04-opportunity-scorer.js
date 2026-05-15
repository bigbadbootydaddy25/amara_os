'use strict';

/**
 * Agent 04 — Opportunity Scorer
 * ---------------------------------------------------------------------------
 * Computes composite_score for each demand-scored record, determines
 * speed-to-close and play type, triggers hot-match OpenClaw alerts.
 *
 * composite_score = distress_score + builder_demand_score + tier_bonus
 *                 + buy_box_bonus [+ hot_match_bonus]
 *
 * Tier bonuses (spec):
 *   EXPIRED plat, permits still reinstateable : +30
 *   WARNING (expiring within 90 days)         : +40
 *   VACATION_CAND (single owner, zero imprv.) : +45
 *   DORMANT (< 10% built, no sales 5 yrs)     : +35
 *
 * Buy-box bonuses (spec):
 *   Matches any builder buy box               : +25
 *   Matches buy box AND builder active ≤ 1 mi : +45  → hot_match = true
 *                                                      → fire OpenClaw NOW
 *
 * Filters:
 *   PASS  if spread below $300K net
 *   PASS  if expired 24+ months with no reinstatement path
 *   NEVER uses ARV percentage formulas
 *
 * Output: scored-opportunities.json sorted desc by composite_score
 * ---------------------------------------------------------------------------
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../lib/logger').agent('agent-04');
const openclaw = require('../lib/openclaw-client');

const AGENT_ID      = '04-opportunity-scorer';
const AGENT_VERSION = '1.0.0';

const DATA_DIR         = path.resolve(__dirname, '../data');
const BUYBOX_FILE      = path.join(DATA_DIR, 'builder-buyboxes.json');

// ---------------------------------------------------------------------------
// Tier bonuses (spec)
// ---------------------------------------------------------------------------

const TIER_BONUS = {
  EXPIRED:       30,
  WARNING:       40,
  VACATION_CAND: 45,
  DORMANT:       35,
};

const BUYBOX_BONUS      = 25;
const HOT_MATCH_BONUS   = 45;   // replaces BUYBOX_BONUS when builder is ≤ 1 mi
const MIN_SPREAD        = 300_000;

// ---------------------------------------------------------------------------
// Builder buy-box loader
// ---------------------------------------------------------------------------

function loadBuyBoxes() {
  try {
    if (fs.existsSync(BUYBOX_FILE)) {
      const data = JSON.parse(fs.readFileSync(BUYBOX_FILE, 'utf8'));
      return Array.isArray(data) ? data : (data.builders ?? []);
    }
  } catch (err) {
    log.warn(`Could not load builder-buyboxes.json: ${err.message}`);
  }

  // Inline fallback — mirrors Agent 06 defaults so pipeline works before
  // Agent 06 has run for the first time.
  return [
    {
      builder: 'DR Horton',
      buy_box: {
        target_markets: ['Polk County FL'],
        min_lots: 50, max_lots: 300,
        preferred_zoning: ['RSF', 'PUD'],
        price_per_lot_range: '$40K - $80K',
        utility_requirement: 'water + sewer at street',
        entitlement_preference: 'shovel-ready or approved plat',
        will_take_reinstatement: true,
        lot_count_sweet_spot: 100,
        active_appetite: 'HIGH',
      },
    },
    {
      builder: 'Lennar',
      buy_box: {
        target_markets: ['Polk County FL'],
        min_lots: 80, max_lots: 400,
        preferred_zoning: ['RSF', 'PUD'],
        price_per_lot_range: '$50K - $90K',
        utility_requirement: 'water + sewer at street',
        entitlement_preference: 'approved plat preferred',
        will_take_reinstatement: false,
        lot_count_sweet_spot: 150,
        active_appetite: 'HIGH',
      },
    },
    {
      builder: 'Meritage Homes',
      buy_box: {
        target_markets: ['Polk County FL'],
        min_lots: 40, max_lots: 200,
        preferred_zoning: ['RSF', 'PUD'],
        price_per_lot_range: '$45K - $85K',
        utility_requirement: 'water at street minimum',
        entitlement_preference: 'approved or near-approved',
        will_take_reinstatement: true,
        lot_count_sweet_spot: 80,
        active_appetite: 'MEDIUM',
      },
    },
    {
      builder: 'Taylor Morrison',
      buy_box: {
        target_markets: ['Polk County FL', 'Lakeland FL'],
        min_lots: 60, max_lots: 250,
        preferred_zoning: ['PUD'],
        price_per_lot_range: '$55K - $95K',
        utility_requirement: 'water + sewer at street',
        entitlement_preference: 'shovel-ready',
        will_take_reinstatement: false,
        lot_count_sweet_spot: 120,
        active_appetite: 'HIGH',
      },
    },
    {
      builder: 'Adams Homes',
      buy_box: {
        target_markets: ['Polk County FL'],
        min_lots: 20, max_lots: 150,
        preferred_zoning: ['RSF', 'PUD'],
        price_per_lot_range: '$30K - $60K',
        utility_requirement: 'water at street',
        entitlement_preference: 'any entitlement stage',
        will_take_reinstatement: true,
        lot_count_sweet_spot: 50,
        active_appetite: 'MEDIUM',
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Buy-box matching
// ---------------------------------------------------------------------------

function matchBuyBox(finding, buyBoxes) {
  const lots = finding.totalLots ?? 0;

  for (const entry of buyBoxes) {
    const bb = entry.buy_box;
    const marketsOk = (bb.target_markets ?? []).some((m) =>
      m.toLowerCase().includes('polk'),
    );
    const lotsOk = lots >= (bb.min_lots ?? 0) && lots <= (bb.max_lots ?? 9999);
    const reinstateOk =
      finding.category !== 'EXPIRED' || bb.will_take_reinstatement === true;

    if (marketsOk && lotsOk && reinstateOk) {
      // Check if builder is ≤ 1 mile (hot match)
      const within1mi = (finding.nearby_builders ?? []).some(
        (nb) =>
          nb.name.toLowerCase().includes(entry.builder.toLowerCase()) &&
          nb.distance_miles <= 1.0,
      );

      return { matched: true, builder: entry.builder, buy_box: bb, within_1mi: within1mi };
    }
  }

  return { matched: false };
}

// ---------------------------------------------------------------------------
// Spread estimate (no ARV %)
// ---------------------------------------------------------------------------

function estimateSpread(finding, matchResult) {
  const lots = finding.totalLots ?? 1;
  if (!matchResult.matched) return 0;

  // Parse midpoint of price_per_lot_range, e.g. "$40K - $80K" → $60K
  const priceStr = matchResult.buy_box?.price_per_lot_range ?? '$50K - $80K';
  const nums = [...priceStr.matchAll(/\$(\d+)K/g)].map((m) => parseInt(m[1], 10) * 1000);
  const midPrice = nums.length >= 2 ? (nums[0] + nums[1]) / 2 : (nums[0] ?? 60_000);

  const builderRevenue = lots * midPrice;

  // Acquisition estimate — distress discounts the price
  const distressDiscount =
    finding.distress_level === 'MAXIMUM_MOTIVATION' ? 0.55 :
    finding.distress_level === 'HIGH'               ? 0.65 :
    finding.distress_level === 'MODERATE'           ? 0.75 : 0.85;

  const acqCost = builderRevenue * distressDiscount;
  const grossSpread = builderRevenue - acqCost;
  const netSpread   = Math.round(grossSpread * 0.85);   // ~15% transaction / carry costs

  return netSpread;
}

// ---------------------------------------------------------------------------
// Speed-to-close (spec)
// ---------------------------------------------------------------------------

function speedToClose(finding, matchResult, spread) {
  if (spread < MIN_SPREAD) return 'PASS';
  if (finding.category === 'EXPIRED' && (finding.ageMonths ?? 0) > 24) return 'PASS';

  const hasBuilderMatch = matchResult.matched;
  const hasUtilities    = true; // assume utilities present unless we have data saying otherwise

  if (
    (finding.category === 'VACATION_CAND' || finding.category === 'WARNING') &&
    hasUtilities && hasBuilderMatch
  ) return 'FAST';

  if (
    finding.category === 'DORMANT' &&
    hasBuilderMatch
  ) return 'MEDIUM';

  if (finding.category === 'EXPIRED') return 'SLOW';

  return 'MEDIUM';
}

// ---------------------------------------------------------------------------
// Hot-match OpenClaw alert
// ---------------------------------------------------------------------------

async function fireHotMatchAlert(finding) {
  const msg =
    `🔥 HOT MATCH ALERT — AMARA-OS LAND SCANNER\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `PROPERTY: ${finding.subdivName}\n` +
    `COUNTY:   Polk County, FL\n` +
    `CATEGORY: ${finding.category}  |  SCORE: ${finding.composite_score}\n` +
    `DISTRESS: ${finding.distress_level}  (${finding.distress_score} pts)\n` +
    `BUILDER:  ${finding.buy_box_details?.builder ?? 'TBD'}\n` +
    `MATCH:    ≤ 1 mi active permits — BUY BOX CONFIRMED\n` +
    `EST. SPREAD: $${(finding.est_spread_min / 1000).toFixed(0)}K+ net\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `ACTION: Run Agent 05 for Kill Shot Brief immediately`;

  return openclaw.send('telegram', msg);
}

// ---------------------------------------------------------------------------
// Read previous agent output
// ---------------------------------------------------------------------------

function readAgent03(ctx) {
  if (ctx.agentResults?.['03']?.findings) return ctx.agentResults['03'];
  const f = fs.readdirSync(ctx.runDir).find((n) => n.startsWith('03-'));
  if (f) return JSON.parse(fs.readFileSync(path.join(ctx.runDir, f), 'utf8'));
  throw new Error('Agent 03 output not found — run agents in order');
}

// ---------------------------------------------------------------------------
// Agent entry point
// ---------------------------------------------------------------------------

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);

  const startedAt = Date.now();
  const { findings: demandScored } = readAgent03(ctx);

  const buyBoxes = loadBuyBoxes();
  log.info(`Loaded ${buyBoxes.length} builder buy-box profile(s)`);
  log.info(`Scoring ${demandScored.length} record(s)…`);

  const findings = [];

  for (const item of demandScored) {
    const tier_bonus     = TIER_BONUS[item.category] ?? 0;
    const matchResult    = matchBuyBox(item, buyBoxes);
    const buyBoxBonus    = matchResult.matched
      ? (matchResult.within_1mi ? HOT_MATCH_BONUS : BUYBOX_BONUS)
      : 0;
    const composite_score = item.distress_score + item.builder_demand_score + tier_bonus + buyBoxBonus;

    const hot_match = matchResult.matched && matchResult.within_1mi;

    const spread = estimateSpread(item, matchResult);
    const speed  = speedToClose(item, matchResult, spread);

    const reinstatement_viable = item.category === 'EXPIRED' && (item.ageMonths ?? 99) <= 12;
    const reinstatement_note   = reinstatement_viable
      ? 'Seller believes dead. Reinstate in 2-6 weeks. Buy at dead-deal price. Flip to builder at full value.'
      : null;

    const scored = {
      ...item,
      composite_score,
      tier_bonus,
      buy_box_match:    matchResult.matched,
      buy_box_details:  matchResult.matched
        ? { builder: matchResult.builder, buy_box: matchResult.buy_box }
        : null,
      hot_match,
      reinstatement_viable,
      reinstatement_note,
      speed_to_close:   speed,
      est_spread_min:   spread,
    };

    findings.push(scored);

    const passStr = speed === 'PASS' ? ' [PASS]' : '';
    log.info(
      `  ${item.subdivName}` +
      `  composite=${composite_score}  speed=${speed}${passStr}` +
      `${hot_match ? '  🔥 HOT MATCH' : ''}`,
    );

    if (hot_match) {
      const alertResult = await fireHotMatchAlert(scored);
      scored._openclaw_hot_alert = alertResult;
      log.info(`    OpenClaw hot-match alert: ${alertResult.ok ? 'sent' : 'queued'}`);
    }
  }

  // Sort descending by composite score; PASS goes last
  findings.sort((a, b) => {
    if (a.speed_to_close === 'PASS' && b.speed_to_close !== 'PASS') return 1;
    if (b.speed_to_close === 'PASS' && a.speed_to_close !== 'PASS') return -1;
    return b.composite_score - a.composite_score;
  });

  const active    = findings.filter((f) => f.speed_to_close !== 'PASS');
  const hotCount  = findings.filter((f) => f.hot_match).length;

  const summary = {
    totalScored:    findings.length,
    activeDeals:    active.length,
    hotMatches:     hotCount,
    topScore:       findings[0]?.composite_score ?? 0,
    topOpportunity: findings[0]?.subdivName ?? null,
    durationMs:     Date.now() - startedAt,
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Active deals: ${summary.activeDeals} / ${summary.totalScored}`);
  log.info(`   Hot matches:  ${summary.hotMatches}`);
  log.info(`   Top score:    ${summary.topScore}  (${summary.topOpportunity})`);
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, summary, findings };
}

module.exports = { run };
