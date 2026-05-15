'use strict';

/**
 * Agent 05 — Quick Flip Filter
 * ---------------------------------------------------------------------------
 * Filters scored-opportunities where composite_score >= 70 AND
 * speed_to_close is FAST or MEDIUM.
 *
 * For each qualifying record:
 *   1. Generate Kill Shot Brief (Ollama llama3 → template fallback)
 *   2. POST brief to OpenClaw   http://127.0.0.1:18789/messages
 *      Queue on failure; retry every 60 s.
 *   3. Push record to Airtable  base app0jn857ZwVzQs8i  table Land Pipeline
 *   4. Write quick-flip-targets.json
 *
 * PERMANENT EXCLUSION — hardcoded, never override:
 *   HomeVestors and all franchisee / DBA variants are excluded from all
 *   matches, briefs, Airtable pushes, and outreach permanently.
 * ---------------------------------------------------------------------------
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../lib/logger').agent('agent-05');
const openclaw  = require('../lib/openclaw-client');
const airtable  = require('../lib/airtable-client');

const AGENT_ID      = '05-quick-flip-filter';
const AGENT_VERSION = '1.0.0';

const MIN_SCORE         = 70;
const QUALIFYING_SPEEDS = new Set(['FAST', 'MEDIUM']);
const OLLAMA_URL        = 'http://127.0.0.1:11434/api/generate';
const OLLAMA_MODEL      = 'llama3';

// ---------------------------------------------------------------------------
// HomeVestors exclusion — HARDCODED — do not modify or override
// ---------------------------------------------------------------------------

const _EXCLUDED_STRINGS = [
  'homevestors',
  'we buy ugly houses',
  'homevestors of america',
  'hv of america',
];

function isExcluded(name) {
  if (!name) return false;
  const lower = name.toLowerCase().replace(/[^a-z0-9 ]/g, ' ');
  return _EXCLUDED_STRINGS.some((excl) => lower.includes(excl));
}

function hasExcludedEntity(finding) {
  const candidates = [
    finding.subdivName,
    finding.developer,
    finding.principal,
    ...(finding.nearby_builders ?? []).map((b) => b.name),
    finding.buy_box_details?.builder,
  ].filter(Boolean);
  return candidates.some(isExcluded);
}

// ---------------------------------------------------------------------------
// Ollama brief generation
// ---------------------------------------------------------------------------

async function generateWithOllama(prompt) {
  const res = await fetch(OLLAMA_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: OLLAMA_MODEL, prompt, stream: false }),
    signal: AbortSignal.timeout(30_000),
  });
  if (!res.ok) throw new Error(`Ollama HTTP ${res.status}`);
  const data = await res.json();
  return (data.response ?? '').trim();
}

// ---------------------------------------------------------------------------
// Kill Shot Brief template (Ollama fallback — always produces valid brief)
// ---------------------------------------------------------------------------

function formatMoney(n) {
  if (!n || n < 1000) return '$???';
  return `$${(n / 1000).toFixed(0)}K`;
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const diff = new Date(dateStr) - new Date();
  return Math.round(diff / 86400000);
}

function topDistressFlags(flags) {
  return (flags ?? []).slice(0, 3).map((f) => f.replace(/_/g, ' ')).join(' · ') || 'NONE';
}

function bestBuilderLine(finding) {
  const bb = finding.buy_box_details;
  if (!bb) return 'NO MATCH YET';
  const builder = bb.builder;
  const nearby  = (finding.nearby_builders ?? []).find((b) =>
    b.name.toLowerCase().includes(builder.toLowerCase()),
  );
  const contact = nearby?.contact ?? null;
  const email   = nearby?.email   ?? null;
  const parts   = [builder];
  if (contact) parts.push(contact);
  if (email)   parts.push(email);
  return parts.join('  ·  ');
}

function playRecommendation(finding) {
  if (finding.reinstatement_viable) return 'paper flip after reinstatement';
  if (finding.category === 'VACATION_CAND') return 'direct assignment to builder';
  if (finding.category === 'WARNING') return 'assignment or double close before expiration';
  return 'double close';
}

function sellerPain(finding) {
  if (finding.distress_level === 'MAXIMUM_MOTIVATION') return 'MAXIMUM';
  if (finding.distress_level === 'HIGH') return 'HIGH';
  return 'MODERATE';
}

function permitStatus(finding) {
  if (finding.category === 'EXPIRED')       return 'EXPIRED — reinstatement required';
  if (finding.category === 'WARNING')       return `APPROVED — expires in ${Math.round(finding.ageMonths ?? 0)} months`;
  if (finding.category === 'DORMANT')       return 'RECORDED — no permits pulled';
  if (finding.category === 'VACATION_CAND') return 'RECORDED — single owner, zero improvements';
  return 'RECORDED';
}

function expirationLine(finding) {
  if (!finding.recordDate) return 'unknown';
  const days = daysUntil(finding.recordDate);
  if (finding.category === 'EXPIRED') return `${finding.recordDate} — EXPIRED ${Math.abs(days ?? 0)} days ago`;
  if (finding.category === 'WARNING') return `${finding.recordDate} — ${days ?? '?'} days remaining`;
  return finding.recordDate;
}

function nearbyActivityLine(finding) {
  const p = finding.nearby_permits ?? {};
  const parts = [];
  if (p.within_1mi) parts.push(`${p.within_1mi} permits within 1 mi`);
  if (p.within_2mi) parts.push(`${p.within_2mi} permits within 2 mi`);
  return parts.join('  ·  ') || 'No permit data';
}

function buyBoxFit(finding) {
  const bb = finding.buy_box_details?.buy_box;
  if (!bb) return 'No match';
  return [
    `lots ${finding.totalLots ?? '?'} (range ${bb.min_lots}-${bb.max_lots})`,
    bb.price_per_lot_range,
    bb.utility_requirement,
  ].join('  ·  ');
}

function entityStatus(finding) {
  const s = finding.distress_details?.sunbiz?.status ?? 'UNKNOWN';
  if (finding.distress_details?.bankruptcy?.found) return `${s} / BANKRUPTCY`;
  return s;
}

function generateTemplateBrief(finding) {
  const SEP = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';

  const play  = playRecommendation(finding);
  const move  = finding.hot_match
    ? `Call ${finding.buy_box_details?.builder ?? 'builder'} today — confirm lot count and submit LOI by end of week.`
    : `Contact ${finding.principal ?? finding.developer ?? 'owner'} directly — present distressed-price offer this week.`;

  return [
    '🎯 KILL SHOT BRIEF — AMARA-OS LAND SCANNER',
    SEP,
    `APN: ${finding.subdivId ?? 'N/A'} | Market: Polk County FL`,
    `Tier: ${finding.category} | Score: ${finding.composite_score} | Speed: ${finding.speed_to_close}`,
    SEP,
    `OWNER: ${finding.developer ?? 'UNKNOWN'} | PRINCIPAL: ${finding.principal ?? 'UNKNOWN'}`,
    `ENTITY STATUS: ${entityStatus(finding)}`,
    `DISTRESS FLAGS: ${topDistressFlags(finding.distress_flags)}`,
    `SELLER PAIN: ${sellerPain(finding)}`,
    SEP,
    `PERMIT STATUS: ${permitStatus(finding)}`,
    `EXPIRATION: ${expirationLine(finding)}`,
    `REINSTATEMENT: ${finding.reinstatement_viable ? 'YES — 2-6 weeks' : 'NO'}`,
    `UTILITIES: at street (assumed)`,
    `LOTS: ${finding.totalLots ?? '?'}`,
    SEP,
    `BUILDER MATCH: ${bestBuilderLine(finding)}`,
    `BUY BOX FIT: ${buyBoxFit(finding)}`,
    `NEARBY ACTIVITY: ${nearbyActivityLine(finding)}`,
    SEP,
    `PLAY: ${play}`,
    `EST. SPREAD: ${formatMoney(finding.est_spread_min)} minimum`,
    `URGENCY: ${Math.round(finding.ageMonths ?? 0)} months elapsed`,
    `MOVE: ${move}`,
    SEP,
  ].join('\n');
}

async function buildKillShotBrief(finding) {
  // Try Ollama first for the PLAY and MOVE sections; fall back to template
  try {
    const prompt =
      `You are a real estate deal analyst. Write a one-sentence PLAY type ` +
      `(assignment/double close/paper flip) and a one-sentence MOVE (the single ` +
      `most important action to take RIGHT NOW) for this deal:\n\n` +
      `Property: ${finding.subdivName}, Polk County FL\n` +
      `Category: ${finding.category}\n` +
      `Distress level: ${finding.distress_level}\n` +
      `Flags: ${topDistressFlags(finding.distress_flags)}\n` +
      `Builder match: ${finding.buy_box_details?.builder ?? 'none'}\n` +
      `Speed to close: ${finding.speed_to_close}\n` +
      `Reinstatement viable: ${finding.reinstatement_viable}\n\n` +
      `Reply with exactly two lines:\nPLAY: ...\nMOVE: ...`;

    const raw    = await generateWithOllama(prompt);
    const play   = raw.match(/PLAY:\s*(.+)/i)?.[1]?.trim();
    const move   = raw.match(/MOVE:\s*(.+)/i)?.[1]?.trim();

    if (play && move) {
      // Use Ollama PLAY/MOVE, template for everything else
      const template = generateTemplateBrief(finding);
      return template
        .replace(/^PLAY: .+$/m, `PLAY: ${play}`)
        .replace(/^MOVE: .+$/m,  `MOVE: ${move}`);
    }
  } catch (err) {
    log.debug(`Ollama unavailable (${err.message}) — using template brief`);
  }

  return generateTemplateBrief(finding);
}

// ---------------------------------------------------------------------------
// Airtable field mapping
// ---------------------------------------------------------------------------

function toAirtableFields(finding, brief) {
  const bb = finding.buy_box_details;
  const nb = (finding.nearby_builders ?? [])[0] ?? {};
  return {
    'Subdivision Name':   finding.subdivName,
    'Subdivision ID':     finding.subdivId ?? '',
    'County':             'Polk County, FL',
    'Category':           finding.category,
    'Composite Score':    finding.composite_score,
    'Distress Score':     finding.distress_score,
    'Distress Level':     finding.distress_level,
    'Builder Demand Score': finding.builder_demand_score,
    'Hot Match':          finding.hot_match,
    'Speed To Close':     finding.speed_to_close,
    'Est Spread Min':     finding.est_spread_min,
    'Reinstatement Viable': finding.reinstatement_viable,
    'Builder Match':      bb?.builder ?? '',
    'Builder Contact':    nb.contact ?? '',
    'Builder Email':      nb.email ?? '',
    'Total Lots':         finding.totalLots ?? 0,
    'Total Acres':        finding.totalAcres ?? 0,
    'Developer':          finding.developer ?? '',
    'Principal':          finding.principal ?? '',
    'Entity Status':      entityStatus(finding),
    'Kill Shot Brief':    brief,
    'Run ID':             finding._runId ?? '',
    'Scanned At':         new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Read previous agent output
// ---------------------------------------------------------------------------

function readAgent04(ctx) {
  if (ctx.agentResults?.['04']?.findings) return ctx.agentResults['04'];
  const f = fs.readdirSync(ctx.runDir).find((n) => n.startsWith('04-'));
  if (f) return JSON.parse(fs.readFileSync(path.join(ctx.runDir, f), 'utf8'));
  throw new Error('Agent 04 output not found — run agents in order');
}

// ---------------------------------------------------------------------------
// Agent entry point
// ---------------------------------------------------------------------------

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);
  log.info(`Filter: composite_score >= ${MIN_SCORE}  speed in [FAST, MEDIUM]`);
  log.info('HomeVestors exclusion: ACTIVE (permanent, non-overridable)');

  const startedAt = Date.now();
  const { findings: scored } = readAgent04(ctx);

  // Filter qualifying opportunities
  const qualified = scored.filter(
    (f) => f.composite_score >= MIN_SCORE && QUALIFYING_SPEEDS.has(f.speed_to_close),
  );

  log.info(`${scored.length} scored  →  ${qualified.length} qualifying  →  filtering exclusions…`);

  const targets = [];
  let excludedCount = 0;

  for (const finding of qualified) {
    // Hardcoded exclusion check
    if (hasExcludedEntity(finding)) {
      log.warn(`EXCLUDED (HomeVestors rule): ${finding.subdivName}`);
      excludedCount++;
      continue;
    }

    log.info(`  Processing: ${finding.subdivName}  (score ${finding.composite_score})`);

    // Attach run ID for tracing
    finding._runId = ctx.runId;

    // 1. Generate Kill Shot Brief
    const brief = await buildKillShotBrief(finding);
    log.info(`    Brief generated (${brief.length} chars)`);

    // 2. POST to OpenClaw
    const ocResult = await openclaw.send('telegram', brief);
    log.info(`    OpenClaw: ${ocResult.ok ? 'sent' : 'queued'}`);

    // 3. Push to Airtable
    const atResult = await airtable.pushRecord(toAirtableFields(finding, brief));
    log.info(`    Airtable: ${atResult.ok ? `record ${atResult.id}` : atResult.reason ?? atResult.error}`);

    targets.push({
      ...finding,
      kill_shot_brief:     brief,
      openclaw_sent:       ocResult.ok,
      openclaw_queued:     ocResult.queued ?? false,
      airtable_record_id:  atResult.id ?? null,
      airtable_ok:         atResult.ok,
    });

    // Print brief to stdout for operator visibility
    process.stdout.write('\n' + brief + '\n\n');
  }

  const summary = {
    totalScored:    scored.length,
    qualified:      qualified.length,
    excluded:       excludedCount,
    targets:        targets.length,
    openclawOk:     targets.filter((t) => t.openclaw_sent).length,
    airtableOk:     targets.filter((t) => t.airtable_ok).length,
    durationMs:     Date.now() - startedAt,
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Qualified:    ${summary.qualified}`);
  log.info(`   Excluded:     ${summary.excluded} (HomeVestors rule)`);
  log.info(`   Targets:      ${summary.targets}`);
  log.info(`   OpenClaw OK:  ${summary.openclawOk}`);
  log.info(`   Airtable OK:  ${summary.airtableOk}`);
  log.info(`   Duration:     ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, targets }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, summary, targets };
}

module.exports = { run };
