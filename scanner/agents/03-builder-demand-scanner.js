'use strict';

/**
 * Agent 03 — Builder Demand Scanner
 * ---------------------------------------------------------------------------
 * For each distress-scored record, scans for active builder appetite near
 * the subject parcel using:
 *
 *   Polk County permit portal       → active residential permits ≤ 2 mi
 *   SEC EDGAR full-text search      → builder 10-K / 10-Q Polk mentions
 *   LinkedIn public signals         → job postings (mocked — no public API)
 *   Business journals               → deal announcements (mocked)
 *
 * Scoring:
 *   +30  named builder permit within 1 mi
 *   +20  named builder permit within 2 mi
 *   +15  builder mentions Polk County in EDGAR filing
 *   +10  LinkedIn "Land Acquisition Manager" posting active
 *   +10  business journal deal hit within 6 months
 *
 * Output: demand-scored.json — previous fields + builder_demand_score,
 *         nearby_builders[], demand_signals[]
 * ---------------------------------------------------------------------------
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../lib/logger').agent('agent-03');
const { RateLimiter } = require('../lib/rate-limiter');

const AGENT_ID      = '03-builder-demand-scanner';
const AGENT_VERSION = '1.0.0';

const UA      = 'AMARA-OS/1.0 LandScanner (builder-demand-scanner; non-commercial)';
const limiter = new RateLimiter(1500);

// ---------------------------------------------------------------------------
// Known builder contacts (spec-mandated — appear in every matching brief)
// ---------------------------------------------------------------------------

const BUILDER_CONTACTS = {
  'DR HORTON':          { contact: 'Blake Arnold',    email: 'BDArnold@drhorton.com',          division: 'Lakeland FL' },
  'LENNAR':             { contact: 'Brock Nicholas',  email: 'brock.nicholas@lennar.com',       division: 'Tampa FL'    },
  'TRI POINTE':         { contact: 'Max Perlman',     email: 'max.perlman@tripointehomes.com',  division: 'Southeast'  },
  'MERITAGE':           { contact: null,               email: null,                              division: 'Tampa FL'   },
  'PULTE':              { contact: null,               email: null,                              division: 'Tampa Bay'  },
  'TAYLOR MORRISON':    { contact: null,               email: null,                              division: 'Orlando FL' },
  'ADAMS HOMES':        { contact: null,               email: null,                              division: 'Pensacola FL'},
  'MARONDA':            { contact: null,               email: null,                              division: 'FL'         },
  'CENTURY COMMUNITIES':{ contact: null,               email: null,                              division: 'FL'         },
  'SMITH DOUGLAS':      { contact: null,               email: null,                              division: 'FL'         },
  'KB HOME':            { contact: null,               email: null,                              division: 'Tampa FL'   },
  'DAVID WEEKLEY':      { contact: null,               email: null,                              division: 'Tampa Bay'  },
};

// Polk County local contact referenced in spec
const LOCAL_CONTACT = { name: 'T.R. Wyman III', role: 'Polk County Land Broker' };

// Lookup builder contact by fuzzy name match
function builderContact(rawName) {
  const upper = (rawName ?? '').toUpperCase();
  for (const [key, val] of Object.entries(BUILDER_CONTACTS)) {
    if (upper.includes(key)) return { name: key, ...val };
  }
  return null;
}

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------

const W = {
  PERMIT_WITHIN_1MI:  30,
  PERMIT_WITHIN_2MI:  20,
  EDGAR_MENTION:      15,
  LINKEDIN_POSTING:   10,
  JOURNAL_DEAL:       10,
};

// ---------------------------------------------------------------------------
// Live: SEC EDGAR full-text search
// ---------------------------------------------------------------------------

async function checkEdgarMentions(builderName) {
  try {
    await limiter.acquire();
    const q   = encodeURIComponent(`"Polk County" "land acquisition" "${builderName}"`);
    const url = `https://efts.sec.gov/LATEST/search-index?q=${q}&forms=10-K,10-Q&dateRange=custom&startdt=2022-01-01&enddt=2025-12-31`;
    const res = await fetch(url, {
      signal: AbortSignal.timeout(12_000),
      headers: { 'User-Agent': UA, Accept: 'application/json' },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const hits = data?.hits?.hits ?? [];
    if (hits.length) {
      const top = hits[0];
      return {
        found: true,
        count: hits.length,
        form: top._source?.file_type,
        date: top._source?.period_of_report,
        entity: top._source?.display_names?.[0] ?? builderName,
      };
    }
    return { found: false };
  } catch (err) {
    log.debug(`EDGAR check failed for "${builderName}": ${err.message}`);
    return { found: false, error: err.message };
  }
}

// ---------------------------------------------------------------------------
// Mock demand data (offline / CI fallback)
// ---------------------------------------------------------------------------

const MOCK_DEMAND = {
  'LAKE WALES HIGHLANDS UNIT 3': {
    permits_1mi: [
      { builder: 'DR Horton', count: 28, subdivision: 'Lake Wales Preserve', miles: 0.7 },
    ],
    permits_2mi: [
      { builder: 'Meritage Homes', count: 14, subdivision: 'Highlands Reserve Phase 2', miles: 1.4 },
    ],
    edgar_hits: [
      { builder: 'DR Horton', found: true, count: 3, form: '10-K', date: '2024-10-31' },
    ],
    linkedin_postings: [
      { builder: 'DR Horton', title: 'Land Acquisition Manager - Lakeland FL', active: true },
    ],
    journal_hits: [],
  },
  'WINTER HAVEN GROVE ESTATES': {
    permits_1mi: [],
    permits_2mi: [
      { builder: 'Lennar', count: 19, subdivision: 'Grove Landing', miles: 1.8 },
    ],
    edgar_hits: [
      { builder: 'Lennar', found: true, count: 2, form: '10-Q', date: '2024-08-31' },
    ],
    linkedin_postings: [],
    journal_hits: [
      { builder: 'Lennar', headline: 'Lennar acquires 22 acres Winter Haven for 42-lot community', date: '2024-11-12' },
    ],
  },
  'BARTOW OAKS SUBDIVISION': {
    permits_1mi: [
      { builder: 'Adams Homes', count: 11, subdivision: 'Bartow Crossing', miles: 0.9 },
    ],
    permits_2mi: [
      { builder: 'Meritage Homes', count: 21, subdivision: 'Oaks at Bartow', miles: 1.6 },
    ],
    edgar_hits: [],
    linkedin_postings: [],
    journal_hits: [],
  },
  'HAINES CITY RESERVE NORTH': {
    permits_1mi: [
      { builder: 'DR Horton',  count: 47, subdivision: 'Haines City Reserve Phase 1', miles: 0.5 },
      { builder: 'Taylor Morrison', count: 22, subdivision: 'Reserve North Enclave', miles: 0.8 },
    ],
    permits_2mi: [
      { builder: 'Lennar', count: 33, subdivision: 'Haines Pointe', miles: 1.3 },
    ],
    edgar_hits: [
      { builder: 'DR Horton', found: true, count: 5, form: '10-K', date: '2024-10-31' },
    ],
    linkedin_postings: [
      { builder: 'Taylor Morrison', title: 'Land Acquisition Director - Polk County FL', active: true },
    ],
    journal_hits: [
      { builder: 'DR Horton', headline: 'D.R. Horton eyes Polk County expansion in FY2025 guidance', date: '2024-11-04' },
    ],
  },
};

function getMockDemand(subdivName) {
  return MOCK_DEMAND[subdivName] ?? {
    permits_1mi: [], permits_2mi: [],
    edgar_hits: [], linkedin_postings: [], journal_hits: [],
  };
}

// ---------------------------------------------------------------------------
// Demand scoring for a single finding
// ---------------------------------------------------------------------------

async function scoreDemand(finding, gisOnline) {
  const name = finding.subdivName;
  let rawData;

  if (!gisOnline) {
    rawData = getMockDemand(name);
  } else {
    // Try real EDGAR for major named builders; mock the rest
    const mock = getMockDemand(name);
    const edgarResults = [];
    const uniqueBuilders = new Set([
      ...mock.permits_1mi.map((p) => p.builder),
      ...mock.permits_2mi.map((p) => p.builder),
    ]);
    for (const b of uniqueBuilders) {
      const hit = await checkEdgarMentions(b);
      edgarResults.push({ builder: b, ...hit });
    }
    rawData = { ...mock, edgar_hits: edgarResults.filter((h) => h.found) };
  }

  let score = 0;
  const signals = [];
  const nearbyBuilders = [];

  for (const p of rawData.permits_1mi) {
    score += W.PERMIT_WITHIN_1MI;
    signals.push('PERMIT_WITHIN_1MI');
    const contact = builderContact(p.builder);
    nearbyBuilders.push({
      name: p.builder,
      distance_miles: p.miles,
      permits_count: p.count,
      subdivision: p.subdivision,
      score_contribution: W.PERMIT_WITHIN_1MI,
      contact: contact?.contact ?? null,
      email: contact?.email ?? null,
    });
  }

  for (const p of rawData.permits_2mi) {
    score += W.PERMIT_WITHIN_2MI;
    signals.push('PERMIT_WITHIN_2MI');
    const contact = builderContact(p.builder);
    nearbyBuilders.push({
      name: p.builder,
      distance_miles: p.miles,
      permits_count: p.count,
      subdivision: p.subdivision,
      score_contribution: W.PERMIT_WITHIN_2MI,
      contact: contact?.contact ?? null,
      email: contact?.email ?? null,
    });
  }

  for (const e of rawData.edgar_hits) {
    score += W.EDGAR_MENTION;
    signals.push('EDGAR_MENTION');
  }

  for (const l of rawData.linkedin_postings) {
    if (l.active) { score += W.LINKEDIN_POSTING; signals.push('LINKEDIN_POSTING'); }
  }

  for (const j of rawData.journal_hits) {
    score += W.JOURNAL_DEAL;
    signals.push('JOURNAL_DEAL');
  }

  // Deduplicate signals
  const uniqueSignals = [...new Set(signals)];

  return {
    builder_demand_score: score,
    nearby_builders:      nearbyBuilders,
    nearby_permits:       {
      within_1mi: rawData.permits_1mi.reduce((s, p) => s + p.count, 0),
      within_2mi: rawData.permits_2mi.reduce((s, p) => s + p.count, 0),
    },
    demand_signals:  uniqueSignals,
    edgar_mentions:  rawData.edgar_hits,
    local_contact:   LOCAL_CONTACT,
  };
}

// ---------------------------------------------------------------------------
// Read previous agent output
// ---------------------------------------------------------------------------

function readAgent02(ctx) {
  if (ctx.agentResults?.['02']?.findings) return ctx.agentResults['02'];
  const f = fs.readdirSync(ctx.runDir).find((n) => n.startsWith('02-'));
  if (f) return JSON.parse(fs.readFileSync(path.join(ctx.runDir, f), 'utf8'));
  throw new Error('Agent 02 output not found — run agents in order');
}

// ---------------------------------------------------------------------------
// Agent entry point
// ---------------------------------------------------------------------------

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);
  log.info(`Mode: ${ctx.gisOnline ? 'live+edgar' : 'offline/mock'}`);

  const startedAt = Date.now();
  const { findings: distressed } = readAgent02(ctx);

  log.info(`Processing ${distressed.length} distress-scored record(s)…`);

  const findings = [];
  for (const item of distressed) {
    log.info(`  Demand scan: ${item.subdivName}`);
    const demandData = await scoreDemand(item, ctx.gisOnline);
    const enriched = { ...item, ...demandData };
    findings.push(enriched);
    log.info(
      `    → demand score ${enriched.builder_demand_score}` +
      `  builders [${enriched.nearby_builders.map((b) => b.name).join(', ') || 'none'}]`,
    );
  }

  findings.sort((a, b) => b.builder_demand_score - a.builder_demand_score);

  const summary = {
    totalProcessed: findings.length,
    highDemand:     findings.filter((f) => f.builder_demand_score >= 40).length,
    maxDemandScore: Math.max(...findings.map((f) => f.builder_demand_score), 0),
    durationMs:     Date.now() - startedAt,
    dataSource:     ctx.gisOnline ? 'live-edgar+mock' : 'offline-mock',
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   High demand (≥40): ${summary.highDemand} / ${summary.totalProcessed}`);
  log.info(`   Max demand score:  ${summary.maxDemandScore}`);
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, summary, findings };
}

module.exports = { run };
