'use strict';

/**
 * Agent 04 — Opportunity Scorer  (Polk County FL)
 * ──────────────────────────────────────────────────
 * Depends on: Agent 01, 02, 03 outputs and Agent 06 builder buy-box data.
 *
 * Rules:
 *  • Composite score is computed from real upstream outputs only.
 *  • If ANY upstream agent has zero real data → log "INSUFFICIENT DATA - DO NOT SCORE" and skip.
 *  • Scores only plats that appear in Agent 01's findings.
 *  • Buy-box match requires Agent 06 having loaded real builders.json data.
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../../lib/logger').agent('agent-04');

const AGENT_ID      = '04-opportunity-scorer';
const AGENT_VERSION = '2.0.0';

// ── Scoring weights (sum to 100) ───────────────────────────────────────────────

const W = {
  PLAT_CATEGORY:  25,   // plat expiration / dormancy category
  DISTRESS:       30,   // distress score from Agent 02
  DEMAND:         25,   // builder demand from Agent 03
  BUYBOX_MATCH:   20,   // buy-box match from Agent 06
};

// Category sub-scores
const CATEGORY_SCORE = {
  EXPIRED:       25,
  WARNING:       20,
  VACATION_CAND: 15,
  DORMANT:       10,
  ACTIVE:         0,
};

// Demand sub-scores
const DEMAND_SCORE = {
  HIGH:    25,
  MEDIUM:  15,
  LOW:      8,
  NONE:     0,
  UNKNOWN:  0,
};

// ── Build lookup maps from upstream agent results ──────────────────────────────

function buildDistressIndex(findings02) {
  const m = new Map();
  for (const f of (findings02 ?? [])) {
    const key = normKey(f.subdivName);
    m.set(key, f);
  }
  return m;
}

function buildDemandIndex(findings03) {
  const m = new Map();
  for (const f of (findings03 ?? [])) {
    const key = normKey(f.subdivName);
    m.set(key, f);
  }
  return m;
}

function normKey(s) {
  return (s ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '').trim();
}

// ── Buy-box match ──────────────────────────────────────────────────────────────

function buyBoxScore(plat, builders) {
  if (!builders || !builders.length) return { score: 0, matches: [] };

  const lots  = plat.parcelCount ?? 0;
  const acres = plat.totalAcres  ?? 0;

  const matches = builders.filter((b) => {
    if (!b.buy_box) return false;
    const bb = b.buy_box;
    if (lots < (bb.min_lots ?? 0)) return false;
    if (lots > (bb.max_lots ?? Infinity)) return false;
    return true;
  }).map((b) => ({
    builder:          b.name,
    contact:          b.contact,
    email:            b.email,
    appetite:         b.buy_box?.active_appetite ?? null,
    willReinstate:    b.buy_box?.will_take_reinstatement ?? null,
    lotRangeMin:      b.buy_box?.min_lots,
    lotRangeMax:      b.buy_box?.max_lots,
    pricePerLotMin:   b.buy_box?.price_per_lot_min,
    pricePerLotMax:   b.buy_box?.price_per_lot_max,
  }));

  const highAppetite = matches.filter((m) => m.appetite === 'HIGH').length;
  const score = matches.length === 0 ? 0 : highAppetite > 0 ? 20 : 10;

  return { score, matches };
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);

  const startedAt = Date.now();

  const agent01 = ctx.agentResults?.['01'];
  const agent02 = ctx.agentResults?.['02'];
  const agent03 = ctx.agentResults?.['03'];
  const agent06 = ctx.agentResults?.['06'];

  // ── Upstream data availability check ──
  const platFindings   = agent01?.findings ?? [];
  const distressFinds  = agent02?.findings ?? [];
  const demandFinds    = agent03?.findings ?? [];
  const builders       = agent06?.builders ?? [];

  if (!platFindings.length) {
    log.error('INSUFFICIENT DATA - DO NOT SCORE — Agent 01 returned zero plat findings. Cannot produce composite scores.');
    const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'insufficient-data', summary: { totalScanned: 0, totalScored: 0 }, findings: [] };
    fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
    return result;
  }

  if (agent02?.status === 'insufficient-data') {
    log.warn('Agent 02 has no real distress data. Distress component will be 0 for all plats.');
  }
  if (agent03?.status === 'insufficient-data') {
    log.warn('Agent 03 has no real permit data. Demand component will be 0 for all plats.');
  }
  if (!builders.length) {
    log.warn('Agent 06 returned no builders. Buy-box match will be 0 for all plats.');
  }

  const distressIdx = buildDistressIndex(distressFinds);
  const demandIdx   = buildDemandIndex(demandFinds);

  // ── Score each plat ──
  const findings = [];

  for (const plat of platFindings) {
    const key = normKey(plat.subdivName);

    const distressEntry = distressIdx.get(key) ?? null;
    const demandEntry   = demandIdx.get(key)   ?? null;

    // Component scores
    const catScore      = CATEGORY_SCORE[plat.category] ?? 0;
    const distressRaw   = distressEntry?.distressScore ?? 0;
    const distressComp  = Math.round((distressRaw / 100) * W.DISTRESS);
    const demandLevel   = demandEntry?.demandLevel ?? 'NONE';
    const demandComp    = Math.round((DEMAND_SCORE[demandLevel] / 25) * W.DEMAND);
    const platComp      = Math.round((catScore / 25) * W.PLAT_CATEGORY);

    const { score: bbScore, matches: bbMatches } = buyBoxScore(plat, builders);
    const bbComp = Math.round((bbScore / 20) * W.BUYBOX_MATCH);

    const compositeScore = Math.min(platComp + distressComp + demandComp + bbComp, 100);

    findings.push({
      // Identity
      subdivName:             plat.subdivName,
      platBook:               plat.platBook,
      platPage:               plat.platPage,
      platCategory:           plat.category,
      ageMonths:              plat.ageMonths,
      parcelCount:            plat.parcelCount,
      totalAcres:             plat.totalAcres,
      representativeParcelId: plat.representativeParcelId,
      representativeOwner:    plat.representativeOwner,
      lat:                    plat.lat,
      lon:                    plat.lon,

      // Composite
      compositeScore,

      // Component breakdown
      components: {
        platCategory:  { score: platComp,    weight: W.PLAT_CATEGORY, raw: catScore,      label: plat.category },
        distress:      { score: distressComp, weight: W.DISTRESS,     raw: distressRaw,   label: distressEntry?.distressFlags?.join(',') ?? 'none' },
        demand:        { score: demandComp,   weight: W.DEMAND,       raw: demandLevel,   nearbyCount: demandEntry?.nearbyCount ?? 0 },
        buyBoxMatch:   { score: bbComp,       weight: W.BUYBOX_MATCH, matches: bbMatches.length },
      },

      // Matched builders
      buyBoxMatches: bbMatches,

      // Distress detail passthrough
      distressFlags:     distressEntry?.distressFlags     ?? [],
      lisPendensCount:   distressEntry?.lisPendens?.length ?? 0,
      taxDelinqCount:    distressEntry?.taxDelinquent?.length ?? 0,
      deathScrub:        distressEntry?.deathScrub        ?? null,

      // Demand passthrough
      demandLevel,
      nearbyPermits:     demandEntry?.nearbyCount ?? 0,
      topBuilders:       demandEntry?.topBuilders ?? [],

      // Provenance
      _fromAgent01: true,
      _fromAgent02: distressEntry !== null,
      _fromAgent03: demandEntry   !== null,
      _fromAgent06: bbMatches.length > 0,
    });
  }

  // Sort: highest composite score first
  findings.sort((a, b) => b.compositeScore - a.compositeScore);

  const byTier = { PRIORITY: 0, QUALIFIED: 0, WATCH: 0, PASS: 0 };
  for (const f of findings) {
    if      (f.compositeScore >= 80) byTier.PRIORITY++;
    else if (f.compositeScore >= 60) byTier.QUALIFIED++;
    else if (f.compositeScore >= 40) byTier.WATCH++;
    else                             byTier.PASS++;
  }

  const summary = {
    totalScanned: platFindings.length,
    totalScored:  findings.length,
    byTier,
    durationMs:   Date.now() - startedAt,
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Plats scored:  ${summary.totalScored}`);
  log.info(`   PRIORITY (80+): ${byTier.PRIORITY}`);
  log.info(`   QUALIFIED (60+): ${byTier.QUALIFIED}`);
  log.info(`   WATCH (40+):    ${byTier.WATCH}`);
  log.info(`   PASS (<40):     ${byTier.PASS}`);
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings };
}

module.exports = { run };
