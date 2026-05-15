'use strict';

/**
 * Agent 02 — Distress Scanner  (Polk County FL)
 * ───────────────────────────────────────────────
 * Reads: data/polk-county-fl/raw/lis-pendens.csv
 *        data/polk-county-fl/raw/tax-delinquent.csv
 * Depends on: Agent 01 output (agentResults['01'].findings)
 *
 * Rules:
 *  • Score distress flags from real filings only.
 *  • Death scrub only on tax-delinquent owners; flag as POSSIBLE_MATCH — manual verify required.
 *  • No scores generated without real CSV input.
 *  • If both CSVs are missing/empty: log REAL_DATA_REQUIRED and exit cleanly.
 */

const fs   = require('node:fs');
const path = require('node:path');
const log  = require('../../lib/logger').agent('agent-02');
const { parseCSV, parseGovDate, parseAmount } = require('../../lib/csv-parser');

const AGENT_ID      = '02-distress-scanner';
const AGENT_VERSION = '2.0.0';

const RAW_DIR          = path.resolve(__dirname, '../../data/polk-county-fl/raw');
const LIS_PENDENS_CSV  = path.join(RAW_DIR, 'lis-pendens.csv');
const TAX_DELINQ_CSV   = path.join(RAW_DIR, 'tax-delinquent.csv');

// ── Column aliases ─────────────────────────────────────────────────────────────

const LP_ALIASES = {
  PARCEL_ID:    ['PARCEL_NUMBER', 'APN', 'ACCOUNT_NO', 'STRAP', 'RE_NUMBER'],
  OWNER:        ['OWNER_NAME', 'OWNER1', 'DEFENDANT', 'GRANTOR', 'BORROWER'],
  FILE_DATE:    ['FILING_DATE', 'RECORDED_DATE', 'DATE_FILED', 'DATE_RECORDED', 'LP_DATE'],
  CASE_NO:      ['CASE_NUMBER', 'DOCKET', 'OR_BOOK_PAGE', 'INSTRUMENT_NO'],
  AMOUNT:       ['CLAIM_AMOUNT', 'LIEN_AMOUNT', 'JUDGMENT_AMT', 'DEBT_AMOUNT'],
  PLAINTIFF:    ['LENDER', 'MORTGAGEE', 'CLAIMANT', 'PLAINTIFF_NAME'],
  STATUS:       ['CASE_STATUS', 'DISPOSITION', 'LIEN_STATUS'],
};

const TD_ALIASES = {
  PARCEL_ID:    ['PARCEL_NUMBER', 'APN', 'ACCOUNT_NO', 'STRAP', 'RE_NUMBER', 'FOLIO'],
  OWNER:        ['OWNER_NAME', 'OWNER1', 'TAXPAYER_NAME', 'TAXPAYER'],
  YEAR:         ['TAX_YEAR', 'YEAR_DELINQUENT', 'CERT_YEAR'],
  AMOUNT:       ['TOTAL_DUE', 'AMOUNT_DUE', 'DELINQUENT_AMT', 'TOTAL_OWED', 'CERT_AMOUNT'],
  CERT_NO:      ['CERTIFICATE_NO', 'CERT_NUMBER', 'CERTIFICATE_NUMBER', 'TC_NO'],
  CERT_DATE:    ['CERTIFICATE_DATE', 'CERT_DATE', 'ISSUE_DATE'],
  YEARS_DELINQ: ['YEARS_OUTSTANDING', 'CONSECUTIVE_YEARS', 'NUM_YEARS'],
};

// ── Distress scoring rubric ────────────────────────────────────────────────────

const SCORE_WEIGHTS = {
  TAX_DELINQUENT:       30,
  LIS_PENDENS:          40,
  MULTIPLE_LP:          15,  // bonus if 2+ LP filings on same parcel
  DECEASED_OWNER:       25,
  HIGH_AMOUNT:          10,  // claim >$100k
  MULTI_YEAR_DELINQ:    20,  // 3+ consecutive tax years
};

// ── SSDI death scrub ───────────────────────────────────────────────────────────

const SSDI_API = 'https://api.ssnvalidator.com/v1/ssdi/search';

async function ssdiFetch(firstName, lastName) {
  // Public SSDI search — returns possible matches only; manual verification required
  const url = `${SSDI_API}?first=${encodeURIComponent(firstName)}&last=${encodeURIComponent(lastName)}`;
  try {
    const resp = await fetch(url, {
      headers: { 'Accept': 'application/json', 'User-Agent': 'AMARA-OS-LandScanner/2.0' },
      signal: AbortSignal.timeout(8000),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data;
  } catch {
    return null;  // API unavailable → skip scrub for this owner
  }
}

function parseName(fullName) {
  const parts = fullName.trim().replace(/[,;]/g, ' ').replace(/\s+/g, ' ').split(' ').filter(Boolean);
  if (parts.length === 0) return null;
  // Attempt "LAST FIRST" (most gov formats) vs "FIRST LAST"
  // Heuristic: if all caps, assume LAST FIRST
  const isAllCaps = fullName === fullName.toUpperCase();
  if (isAllCaps && parts.length >= 2) return { first: parts[1], last: parts[0] };
  return { first: parts[0], last: parts[parts.length - 1] };
}

async function deathScrub(ownerName) {
  const parsed = parseName(ownerName);
  if (!parsed) return null;

  // Skip clearly non-personal names (LLCs, trusts, estates)
  const skip = /\b(LLC|INC|CORP|TRUST|ESTATE|LP|LLP|ASSOC|PARTNERS|GROUP|FAMILY|REVOCABLE|IRREVOCABLE)\b/i;
  if (skip.test(ownerName)) return null;

  const result = await ssdiFetch(parsed.first, parsed.last);
  if (!result) return null;

  // Only flag if API returns a non-empty match array — we never confirm, only flag POSSIBLE
  const matches = Array.isArray(result.results) ? result.results : [];
  if (matches.length === 0) return null;

  return {
    status: 'POSSIBLE_MATCH',
    matchCount: matches.length,
    note: 'Manual verification required — SSDI match is not confirmation of death',
  };
}

// ── Name normalization for cross-reference ────────────────────────────────────

function normName(s) {
  return (s ?? '').toUpperCase().replace(/[^A-Z0-9]/g, ' ').replace(/\s+/g, ' ').trim();
}

function normParcel(s) {
  return (s ?? '').replace(/[^A-Z0-9]/gi, '').toUpperCase();
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);

  const startedAt = Date.now();

  // ── Load CSVs ──
  let lpRows = null;
  let tdRows = null;

  try {
    lpRows = await parseCSV(LIS_PENDENS_CSV, { aliases: LP_ALIASES });
    log.info(`Lis pendens rows: ${lpRows.length.toLocaleString()}`);
  } catch (err) {
    if (err.code === 'CSV_MISSING' || err.code === 'CSV_EMPTY') {
      log.warn(`REAL_DATA_REQUIRED — ${path.basename(LIS_PENDENS_CSV)} ${err.code === 'CSV_MISSING' ? 'not found' : 'is empty'}. Place file from polkclerk.com at: ${LIS_PENDENS_CSV}`);
    } else throw err;
  }

  try {
    tdRows = await parseCSV(TAX_DELINQ_CSV, { aliases: TD_ALIASES });
    log.info(`Tax delinquent rows: ${tdRows.length.toLocaleString()}`);
  } catch (err) {
    if (err.code === 'CSV_MISSING' || err.code === 'CSV_EMPTY') {
      log.warn(`REAL_DATA_REQUIRED — ${path.basename(TAX_DELINQ_CSV)} ${err.code === 'CSV_MISSING' ? 'not found' : 'is empty'}. Place file from polktaxes.com at: ${TAX_DELINQ_CSV}`);
    } else throw err;
  }

  if (!lpRows && !tdRows) {
    log.error('REAL_DATA_REQUIRED — Both lis-pendens.csv and tax-delinquent.csv are unavailable. Cannot score distress.');
    const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, status: 'insufficient-data', summary: { totalScanned: 0, totalFlagged: 0 }, findings: [] };
    fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
    return result;
  }

  // ── Get Agent 01 findings for cross-reference ──
  const agent01 = ctx.agentResults?.['01'];
  const platFindings = (agent01?.findings ?? []);
  log.info(`Upstream plat findings: ${platFindings.length}`);

  // ── Build lookup indexes ──

  // LP index: by parcel ID and by owner name
  const lpByParcel = new Map();  // normParcel → [row, ...]
  const lpByOwner  = new Map();  // normName → [row, ...]

  for (const row of (lpRows ?? [])) {
    const pid = normParcel(row.PARCEL_ID);
    if (pid) {
      if (!lpByParcel.has(pid)) lpByParcel.set(pid, []);
      lpByParcel.get(pid).push(row);
    }
    const own = normName(row.OWNER);
    if (own.length > 3) {
      if (!lpByOwner.has(own)) lpByOwner.set(own, []);
      lpByOwner.get(own).push(row);
    }
  }

  // TD index: by parcel ID and by owner name
  const tdByParcel = new Map();
  const tdByOwner  = new Map();

  for (const row of (tdRows ?? [])) {
    const pid = normParcel(row.PARCEL_ID);
    if (pid) {
      if (!tdByParcel.has(pid)) tdByParcel.set(pid, []);
      tdByParcel.get(pid).push(row);
    }
    const own = normName(row.OWNER);
    if (own.length > 3) {
      if (!tdByOwner.has(own)) tdByOwner.set(own, []);
      tdByOwner.get(own).push(row);
    }
  }

  // ── Score each plat finding ──
  const findings = [];
  const deathScrubCache = new Map();  // normName → scrub result (avoid dupe API calls)

  for (const plat of platFindings) {
    const pid = normParcel(plat.representativeParcelId);
    const own = normName(plat.representativeOwner);

    // Gather matching LP and TD rows
    const lpMatches = [
      ...(pid ? (lpByParcel.get(pid) ?? []) : []),
      ...(own.length > 3 ? (lpByOwner.get(own) ?? []) : []),
    ];
    const tdMatches = [
      ...(pid ? (tdByParcel.get(pid) ?? []) : []),
      ...(own.length > 3 ? (tdByOwner.get(own) ?? []) : []),
    ];

    // De-dupe by row reference
    const lpUniq = [...new Set(lpMatches)];
    const tdUniq = [...new Set(tdMatches)];

    if (!lpUniq.length && !tdUniq.length) continue;

    // Score
    let score = 0;
    const flags = [];

    if (tdUniq.length > 0) {
      score += SCORE_WEIGHTS.TAX_DELINQUENT;
      flags.push('TAX_DELINQUENT');
    }

    if (lpUniq.length > 0) {
      score += SCORE_WEIGHTS.LIS_PENDENS;
      flags.push('LIS_PENDENS');
      if (lpUniq.length >= 2) {
        score += SCORE_WEIGHTS.MULTIPLE_LP;
        flags.push('MULTIPLE_LP');
      }
    }

    // High claim amount
    const maxAmount = lpUniq.reduce((m, r) => {
      const a = parseAmount(r.AMOUNT);
      return a > m ? a : m;
    }, 0);
    if (maxAmount > 100_000) {
      score += SCORE_WEIGHTS.HIGH_AMOUNT;
      flags.push('HIGH_AMOUNT');
    }

    // Multi-year tax delinquency
    const years = tdUniq.map((r) => parseInt(r.YEARS_DELINQ ?? r.YEAR ?? '0', 10)).filter((n) => !isNaN(n));
    const maxYears = years.length ? Math.max(...years) : 0;
    if (maxYears >= 3) {
      score += SCORE_WEIGHTS.MULTI_YEAR_DELINQ;
      flags.push('MULTI_YEAR_DELINQ');
    }

    // Death scrub (TD owners only)
    let deathScrubResult = null;
    if (tdUniq.length > 0 && plat.representativeOwner) {
      const cacheKey = normName(plat.representativeOwner);
      if (!deathScrubCache.has(cacheKey)) {
        deathScrubCache.set(cacheKey, await deathScrub(plat.representativeOwner));
      }
      deathScrubResult = deathScrubCache.get(cacheKey);
      if (deathScrubResult) {
        score += SCORE_WEIGHTS.DECEASED_OWNER;
        flags.push('DECEASED_POSSIBLE');
      }
    }

    // Earliest LP date
    const lpDates = lpUniq.map((r) => parseGovDate(r.FILE_DATE)).filter(Boolean);
    lpDates.sort((a, b) => a - b);

    // Earliest TD cert date
    const tdDates = tdUniq.map((r) => parseGovDate(r.CERT_DATE)).filter(Boolean);
    tdDates.sort((a, b) => a - b);

    findings.push({
      // Plat identity (from Agent 01)
      subdivName:             plat.subdivName,
      platBook:               plat.platBook,
      platPage:               plat.platPage,
      category:               plat.category,
      parcelCount:            plat.parcelCount,
      totalAcres:             plat.totalAcres,
      representativeParcelId: plat.representativeParcelId,
      representativeOwner:    plat.representativeOwner,
      lat:                    plat.lat,
      lon:                    plat.lon,

      // Distress data
      distressScore:     Math.min(score, 100),
      distressFlags:     flags,

      lisPendens: lpUniq.map((r) => ({
        caseNo:    r.CASE_NO   || null,
        fileDate:  r.FILE_DATE || null,
        plaintiff: r.PLAINTIFF || null,
        amount:    parseAmount(r.AMOUNT) || null,
        status:    r.STATUS    || null,
      })),

      taxDelinquent: tdUniq.map((r) => ({
        certNo:      r.CERT_NO    || null,
        year:        r.YEAR       || null,
        certDate:    r.CERT_DATE  || null,
        amountDue:   parseAmount(r.AMOUNT) || null,
        yearsDelinq: r.YEARS_DELINQ ? parseInt(r.YEARS_DELINQ, 10) : null,
      })),

      deathScrub:  deathScrubResult,

      earliestLPDate: lpDates[0]?.toISOString().slice(0, 10) ?? null,
      earliestTDDate: tdDates[0]?.toISOString().slice(0, 10) ?? null,
      maxClaimAmount: maxAmount || null,
      maxYearsDelinquent: maxYears || null,

      // Provenance
      _sourceFiles:   [lpUniq.length ? 'lis-pendens.csv' : null, tdUniq.length ? 'tax-delinquent.csv' : null].filter(Boolean),
      _lpRows:        lpUniq.length,
      _tdRows:        tdUniq.length,
    });
  }

  // Sort: highest distress score first
  findings.sort((a, b) => b.distressScore - a.distressScore);

  const byFlag = {};
  for (const f of findings) {
    for (const flag of f.distressFlags) byFlag[flag] = (byFlag[flag] ?? 0) + 1;
  }

  const summary = {
    totalScanned: platFindings.length,
    totalFlagged: findings.length,
    byFlag,
    lpAvailable:  lpRows !== null,
    tdAvailable:  tdRows !== null,
    deathScrubAttempted: deathScrubCache.size,
    durationMs:   Date.now() - startedAt,
  };

  log.info('');
  log.info('── Summary ─────────────────────────────────────────');
  log.info(`   Plats scanned:    ${summary.totalScanned}`);
  log.info(`   Distress flagged: ${summary.totalFlagged}`);
  for (const [flag, n] of Object.entries(byFlag)) log.info(`   ${flag.padEnd(20)} ${n}`);
  log.info(`   Duration: ${summary.durationMs}ms`);
  log.info('────────────────────────────────────────────────────');

  const outFile = path.join(ctx.runDir, `${AGENT_ID}.json`);
  fs.writeFileSync(outFile, JSON.stringify({ agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings }, null, 2));
  log.info(`Results written → ${outFile}`);

  return { agentId: AGENT_ID, agentVersion: AGENT_VERSION, summary, findings };
}

module.exports = { run };
