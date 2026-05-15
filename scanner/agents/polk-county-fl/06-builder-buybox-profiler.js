'use strict';

/**
 * Agent 06 — Builder Buy-Box Profiler  (Polk County FL)
 * ────────────────────────────────────────────────────────
 * Reads: data/polk-county-fl/builders.json
 *
 * Rules:
 *  • Loads confirmed builder contacts only.
 *  • No other builders may be added without a confirmed direct contact on file.
 *  • Does not modify builders.json — read-only validation and enrichment.
 *  • Runs first in the pipeline so downstream agents have buy-box data.
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../../lib/logger').agent('agent-06');

const AGENT_ID      = '06-builder-buybox-profiler';
const AGENT_VERSION = '2.0.0';

const BUILDERS_FILE = path.resolve(__dirname, '../../data/polk-county-fl/builders.json');

// ── Validation ─────────────────────────────────────────────────────────────────

function validateBuilder(b, idx) {
  const errors = [];
  if (!b.name)      errors.push('missing name');
  if (!b.contact)   errors.push('missing contact');
  if (b.confirmed !== true) errors.push('confirmed !== true');
  if (errors.length) log.warn(`Builder[${idx}] (${b.name ?? 'unknown'}): ${errors.join('; ')}`);
  return errors.length === 0;
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);
  log.info(`Source: ${BUILDERS_FILE}`);

  const startedAt = Date.now();

  // ── Load builders.json ──
  if (!fs.existsSync(BUILDERS_FILE)) {
    log.error(`REAL_DATA_REQUIRED — builders.json not found at: ${BUILDERS_FILE}`);
    const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'insufficient-data', summary: { totalLoaded: 0, confirmed: 0 }, builders: [] };
    fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
    return result;
  }

  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(BUILDERS_FILE, 'utf8'));
  } catch (err) {
    log.error(`Failed to parse builders.json: ${err.message}`);
    const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'parse-error', summary: { totalLoaded: 0, confirmed: 0 }, builders: [] };
    fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
    return result;
  }

  const rawBuilders = Array.isArray(raw.builders) ? raw.builders : [];
  log.info(`Raw entries: ${rawBuilders.length}`);

  // ── Validate — only confirmed contacts pass through ──
  const builders = rawBuilders
    .filter((b, i) => validateBuilder(b, i))
    .map((b) => ({
      name:     b.name,
      division: b.division ?? null,
      contact:  b.contact,
      email:    b.email ?? null,
      role:     b.role ?? null,
      buy_box:  b.buy_box ?? null,
    }));

  const withBuyBox = builders.filter((b) => b.buy_box !== null);

  log.info(`Confirmed builders loaded: ${builders.length}`);
  log.info(`With buy-box data: ${withBuyBox.length}`);

  for (const b of builders) {
    const bb = b.buy_box;
    if (bb) {
      log.info(`  ${b.name.padEnd(20)} lots ${bb.min_lots}–${bb.max_lots}  $${(bb.price_per_lot_min/1000).toFixed(0)}K–$${(bb.price_per_lot_max/1000).toFixed(0)}K/lot  appetite: ${bb.active_appetite}`);
    } else {
      log.info(`  ${b.name.padEnd(20)} [no buy-box data]  role: ${b.role ?? 'n/a'}`);
    }
  }

  const summary = {
    totalLoaded:  rawBuilders.length,
    confirmed:    builders.length,
    withBuyBox:   withBuyBox.length,
    lastUpdated:  raw._last_updated ?? null,
    durationMs:   Date.now() - startedAt,
  };

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, builders }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, builders };
}

module.exports = { run };
