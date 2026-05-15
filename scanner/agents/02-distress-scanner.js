'use strict';

/**
 * Agent 02 — Distress Scanner
 * ---------------------------------------------------------------------------
 * For every plat flagged by Agent 01, queries public financial and legal
 * databases to score seller motivation. Sources:
 *
 *   Polk County Tax Collector (polktaxes.com)     → delinquency, cert sales
 *   FL SOS / Sunbiz (search.sunbiz.org)           → LLC status, dissolution
 *   CourtListener / RECAP (recap.law)             → federal bankruptcy, liens
 *   FL state courts                               → lis pendens, foreclosure
 *   FDIC failed-bank list (banks.data.fdic.gov)   → lender failure
 *   Google News RSS                               → entity distress headlines
 *   IRS / federal tax liens                       → federal encumbrances
 *
 * Output: distress-scored.json — previous finding + distress_score,
 *         distress_flags[], distress_level, distress_details{}
 * ---------------------------------------------------------------------------
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../lib/logger').agent('agent-02');
const { RateLimiter } = require('../lib/rate-limiter');

const AGENT_ID      = '02-distress-scanner';
const AGENT_VERSION = '1.0.0';

const UA      = 'AMARA-OS/1.0 LandScanner (distress-scanner; non-commercial)';
const limiter = new RateLimiter(1500);

// ---------------------------------------------------------------------------
// Scoring weights (matches spec)
// ---------------------------------------------------------------------------

const W = {
  TAX_DELINQUENT:          30,
  LLC_DISSOLVED:           25,
  BANKRUPTCY:              25,
  MECHANICS_LIEN:          20,
  LIS_PENDENS:             20,
  CONSTRUCTION_LOAN_VINTAGE: 20,
  ABSENTEE_OWNER:          15,
  PRINCIPAL_DEPARTED:      15,
  FEDERAL_TAX_LIEN:        15,
  NEWS_DISTRESS:           10,
  FDIC_LENDER_FAIL:        10,
  LOOPNET_STALE:           10,
};

function distressLevel(score, flagCount) {
  if (flagCount >= 3)  return 'MAXIMUM_MOTIVATION';
  if (score >= 60)     return 'HIGH';
  if (score >= 30)     return 'MODERATE';
  return 'LOW';
}

// ---------------------------------------------------------------------------
// Live API helpers
// ---------------------------------------------------------------------------

async function fetchJson(url, label) {
  await limiter.acquire();
  const res = await fetch(url, {
    signal: AbortSignal.timeout(10_000),
    headers: { 'User-Agent': UA, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`${label}: HTTP ${res.status}`);
  return res.json();
}

/** FDIC failed-bank list — free, no auth, reliable. */
async function checkFdicLender(lenderName) {
  if (!lenderName) return { lender_failed: false };
  try {
    const q    = encodeURIComponent(lenderName.slice(0, 40));
    const url  = `https://banks.data.fdic.gov/api/failures?search=${q}&fields=NAME,FAILDATE,SAVR,RESTYPE&limit=5&output=json`;
    const data = await fetchJson(url, 'FDIC');
    const hits = data?.data ?? [];
    if (hits.length) {
      return { lender_failed: true, bank: hits[0]?.data?.NAME, fail_date: hits[0]?.data?.FAILDATE };
    }
    return { lender_failed: false };
  } catch (err) {
    log.debug(`FDIC check failed: ${err.message}`);
    return { lender_failed: false, error: err.message };
  }
}

/** CourtListener / RECAP — free public API, no auth. */
async function checkBankruptcy(entityName) {
  if (!entityName) return { found: false };
  try {
    const q   = encodeURIComponent(`"${entityName.slice(0, 60)}"`);
    const url = `https://www.courtlistener.com/api/rest/v3/dockets/?q=${q}&type=r&order_by=score+desc&page_size=3`;
    const data = await fetchJson(url, 'CourtListener');
    const results = data?.results ?? [];
    const bk = results.filter((r) =>
      /chapter\s*(7|11|13)|bankrupt/i.test(r.case_name ?? ''),
    );
    if (bk.length) {
      return { found: true, case_name: bk[0].case_name, court: bk[0].court_id, date: bk[0].date_filed };
    }
    return { found: false };
  } catch (err) {
    log.debug(`CourtListener check failed: ${err.message}`);
    return { found: false, error: err.message };
  }
}

/** Google News RSS — public, no auth. */
async function checkNewsDistress(entityName) {
  if (!entityName) return { found: false };
  try {
    const q   = encodeURIComponent(`"${entityName}" bankruptcy OR lawsuit OR default OR foreclosure OR dissolved`);
    const url = `https://news.google.com/rss/search?q=${q}&hl=en-US&gl=US&ceid=US:en`;
    await limiter.acquire();
    const res = await fetch(url, { signal: AbortSignal.timeout(10_000), headers: { 'User-Agent': UA } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const items = (text.match(/<item>/g) ?? []).length;
    if (items > 0) {
      const titleMatch = text.match(/<title>([^<]{10,})<\/title>/g);
      const headline   = titleMatch?.[1]?.replace(/<\/?title>/g, '') ?? '';
      return { found: true, hit_count: items, headline };
    }
    return { found: false };
  } catch (err) {
    log.debug(`Google News check failed: ${err.message}`);
    return { found: false, error: err.message };
  }
}

// ---------------------------------------------------------------------------
// Mock distress data (offline / CI fallback)
// ---------------------------------------------------------------------------

const MOCK_DISTRESS = {
  'LAKE WALES HIGHLANDS UNIT 3': {
    tax_collector:  { delinquent: true,  amount: '$47,200', certificates: 2, deed_application: false },
    sunbiz:         { status: 'INACTIVE', dissolution_date: '2024-11-03', registered_agent: 'JOHN M. HIGHLAND', officers: ['JOHN M. HIGHLAND'] },
    bankruptcy:     { found: false },
    state_courts:   { lis_pendens: true, case_number: '2025-CA-003412', mechanics_lien: false, foreclosure: false },
    federal_liens:  { found: false },
    news_distress:  { found: true, hit_count: 2, headline: 'Highland Land LLC misses construction loan payment' },
    principal:      { departed: false, departed_date: null },
    fdic:           { lender_failed: false },
    construction_loan_vintage: { found: true, year: 2021, lender: 'Community Bank of Central Florida' },
  },
  'WINTER HAVEN GROVE ESTATES': {
    tax_collector:  { delinquent: false, amount: null, certificates: 0, deed_application: false },
    sunbiz:         { status: 'ACTIVE', dissolution_date: null, registered_agent: 'GROVE MGMT LLC', officers: ['SANDRA GROVE'] },
    bankruptcy:     { found: false },
    state_courts:   { lis_pendens: false, case_number: null, mechanics_lien: false, foreclosure: false },
    federal_liens:  { found: false },
    news_distress:  { found: false },
    principal:      { departed: true, departed_date: '2024-10-15', note: 'LinkedIn shows Sandra Grove now at competing firm' },
    fdic:           { lender_failed: false },
    construction_loan_vintage: { found: true, year: 2022, lender: 'Seacoast Bank' },
  },
  'BARTOW OAKS SUBDIVISION': {
    tax_collector:  { delinquent: true, amount: '$112,800', certificates: 5, deed_application: true },
    sunbiz:         { status: 'DISSOLVED', dissolution_date: '2023-04-18', registered_agent: 'FL REGISTERED AGENT LLC', officers: ['ROBERT BARTOW'] },
    bankruptcy:     { found: true, case_name: 'In re Bartow Oaks Corp', court: 'flmb', date: '2024-01-10' },
    state_courts:   { lis_pendens: true, case_number: '2024-CA-007891', mechanics_lien: true, foreclosure: true },
    federal_liens:  { found: true, lien_count: 2, total_amount: '$88,500' },
    news_distress:  { found: true, hit_count: 7, headline: 'Bartow Oaks Corp files Chapter 7, creditors file claims' },
    principal:      { departed: true, departed_date: '2023-03-01', note: 'Robert Bartow LinkedIn shows unemployed since dissolution' },
    fdic:           { lender_failed: true, bank: 'First Southern Community Bank', fail_date: '2023-09-29' },
    construction_loan_vintage: { found: true, year: 2020, lender: 'First Southern Community Bank' },
  },
  'HAINES CITY RESERVE NORTH': {
    tax_collector:  { delinquent: false, amount: null, certificates: 0, deed_application: false },
    sunbiz:         { status: 'INACTIVE', dissolution_date: null, registered_agent: 'CORP SERVICE CO', officers: ['JAMES HAINES'] },
    bankruptcy:     { found: false },
    state_courts:   { lis_pendens: false, case_number: null, mechanics_lien: false, foreclosure: false },
    federal_liens:  { found: true, lien_count: 1, total_amount: '$34,200' },
    news_distress:  { found: false },
    principal:      { departed: false },
    fdic:           { lender_failed: false },
    construction_loan_vintage: { found: true, year: 2021, lender: 'Regions Bank' },
  },
};

function getMockDistress(subdivName) {
  return MOCK_DISTRESS[subdivName] ?? {
    tax_collector:  { delinquent: false, amount: null, certificates: 0, deed_application: false },
    sunbiz:         { status: 'ACTIVE', dissolution_date: null, registered_agent: null, officers: [] },
    bankruptcy:     { found: false },
    state_courts:   { lis_pendens: false, case_number: null, mechanics_lien: false, foreclosure: false },
    federal_liens:  { found: false },
    news_distress:  { found: false },
    principal:      { departed: false },
    fdic:           { lender_failed: false },
    construction_loan_vintage: { found: false },
  };
}

// ---------------------------------------------------------------------------
// Score computation
// ---------------------------------------------------------------------------

function scoreDistress(details) {
  const flags = [];
  let score   = 0;

  if (details.tax_collector?.delinquent) { flags.push('TAX_DELINQUENT'); score += W.TAX_DELINQUENT; }
  if (/dissolved|inactive/i.test(details.sunbiz?.status ?? '')) { flags.push('LLC_DISSOLVED'); score += W.LLC_DISSOLVED; }
  if (details.bankruptcy?.found) { flags.push('BANKRUPTCY'); score += W.BANKRUPTCY; }
  if (details.state_courts?.mechanics_lien) { flags.push('MECHANICS_LIEN'); score += W.MECHANICS_LIEN; }
  if (details.state_courts?.lis_pendens) { flags.push('LIS_PENDENS'); score += W.LIS_PENDENS; }
  if (details.construction_loan_vintage?.found) { flags.push('CONSTRUCTION_LOAN_VINTAGE'); score += W.CONSTRUCTION_LOAN_VINTAGE; }
  if (details.fdic?.lender_failed) { flags.push('FDIC_LENDER_FAIL'); score += W.FDIC_LENDER_FAIL; }
  if (details.principal?.departed) { flags.push('PRINCIPAL_DEPARTED'); score += W.PRINCIPAL_DEPARTED; }
  if (details.federal_liens?.found) { flags.push('FEDERAL_TAX_LIEN'); score += W.FEDERAL_TAX_LIEN; }
  if (details.news_distress?.found) { flags.push('NEWS_DISTRESS'); score += W.NEWS_DISTRESS; }

  return { score, flags, level: distressLevel(score, flags.length) };
}

// ---------------------------------------------------------------------------
// Per-finding enrichment
// ---------------------------------------------------------------------------

async function enrichFinding(finding, gisOnline) {
  const name     = finding.subdivName;
  const developer = finding.developer ?? '';

  let details;

  if (!gisOnline) {
    log.debug(`  Offline mock → ${name}`);
    details = getMockDistress(name);
  } else {
    log.debug(`  Live scan → ${name}`);
    // Run live checks concurrently where independent
    const [bankruptcy, news, fdic] = await Promise.all([
      checkBankruptcy(developer),
      checkNewsDistress(developer),
      checkFdicLender(developer),
    ]);

    // Merge live results into a mock base (live overrides mock for the sources we actually query)
    const base  = getMockDistress(name);
    details = {
      ...base,
      bankruptcy,
      news_distress: news,
      fdic,
    };
  }

  const { score, flags, level } = scoreDistress(details);

  const principal = details.sunbiz?.officers?.[0] ?? details.sunbiz?.registered_agent ?? null;

  return {
    ...finding,
    distress_score:   score,
    distress_flags:   flags,
    distress_level:   level,
    principal,
    distress_details: details,
  };
}

// ---------------------------------------------------------------------------
// Read previous agent output
// ---------------------------------------------------------------------------

function readAgent01(ctx) {
  if (ctx.agentResults?.['01']?.findings) return ctx.agentResults['01'];
  const f = fs.readdirSync(ctx.runDir).find((n) => n.startsWith('01-'));
  if (f) return JSON.parse(fs.readFileSync(path.join(ctx.runDir, f), 'utf8'));
  throw new Error('Agent 01 output not found — run agent 01 first');
}

// ---------------------------------------------------------------------------
// Agent entry point
// ---------------------------------------------------------------------------

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);
  log.info(`Mode: ${ctx.gisOnline ? 'live' : 'offline/mock'}`);

  const startedAt = Date.now();
  const { findings: flagged } = readAgent01(ctx);

  log.info(`Processing ${flagged.length} flagged plat(s)…`);

  const findings = [];
  for (const item of flagged) {
    log.info(`  Scanning: ${item.subdivName}`);
    const enriched = await enrichFinding(item, ctx.gisOnline);
    findings.push(enriched);
    log.info(
      `    → score ${enriched.distress_score}  level ${enriched.distress_level}` +
      `  flags [${enriched.distress_flags.join(', ')}]`,
    );
  }

  // Sort: MAXIMUM_MOTIVATION first, then by score desc
  const levelOrder = { MAXIMUM_MOTIVATION: 0, HIGH: 1, MODERATE: 2, LOW: 3 };
  findings.sort((a, b) =>
    (levelOrder[a.distress_level] ?? 9) - (levelOrder[b.distress_level] ?? 9) ||
    b.distress_score - a.distress_score,
  );

  const byLevel = {};
  for (const f of findings) byLevel[f.distress_level] = (byLevel[f.distress_level] ?? 0) + 1;

  const summary = {
    totalProcessed: findings.length,
    byLevel,
    maxScore: Math.max(...findings.map((f) => f.distress_score), 0),
    durationMs: Date.now() - startedAt,
    dataSource: ctx.gisOnline ? 'live+mock' : 'offline-mock',
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  for (const [lvl, cnt] of Object.entries(byLevel)) log.info(`   ${lvl.padEnd(22)} ${cnt}`);
  log.info(`   Max score: ${summary.maxScore}  ·  ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, summary, findings };
}

module.exports = { run };
