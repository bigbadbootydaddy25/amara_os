'use strict';

/**
 * Agent 00 — Data Intake  (Polk County FL)
 * ─────────────────────────────────────────
 * Pulls all 4 raw data sources automatically on each run.
 * Writes normalized CSVs to data/polk-county-fl/raw/ so that
 * agents 01–05 can read them without manual CSV drops.
 *
 * Sources:
 *   parcels       — polkpa.org ArcGIS REST (Property Appraiser)
 *   tax-delinquent— polktaxes.com delinquent certificate list
 *   lis-pendens   — polkclerk.com Official Records search
 *   permits       — Polk County ArcGIS building permits layer
 *
 * Behaviour:
 *   • If fresh cache exists (pulled today) → skip pull for that source.
 *   • On pull failure → log OSINT PULL FAILED and retry after 60s (once).
 *   • If ALL sources fail → status: 'real-data-unavailable'.
 *   • ctx.intakeResults['polk-county-fl'] is populated for downstream agents.
 */

const fs   = require('node:fs');
const path = require('node:path');

const log        = require('../../lib/logger').agent('intake-polk');
const { isFresh, writeCache } = require('../../lib/intake/cache');
const http       = require('../../lib/intake/http-client');
const browser    = require('../../lib/intake/browser');
const { RateLimiter } = require('../../lib/rate-limiter');

const AGENT_ID      = '00-intake';
const AGENT_VERSION = '2.0.0';
const COUNTY_SLUG   = 'polk-county-fl';

const RATE = new RateLimiter(1500);

// ── ArcGIS pagination helper ───────────────────────────────────────────────────

const GIS_BASE    = 'https://maps.polk-county.net/arcgis/rest/services';
const PAGE_SIZE   = 1000;
const GIS_TIMEOUT = 30_000;

async function arcgisPaginate(layerPath, where = '1=1', outFields = '*') {
  const base = `${GIS_BASE}/${layerPath}/query`;
  let offset = 0;
  const allFeatures = [];

  while (true) {
    await RATE.acquire();
    const params = new URLSearchParams({
      where,
      outFields,
      f:              'json',
      returnGeometry: 'true',
      resultOffset:   String(offset),
      resultRecordCount: String(PAGE_SIZE),
    });

    let data;
    try {
      const resp = await fetch(`${base}?${params}`, {
        signal: AbortSignal.timeout(GIS_TIMEOUT),
        headers: { 'User-Agent': 'AMARA-OS-LandScanner/2.0' },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      data = await resp.json();
    } catch (err) {
      throw Object.assign(err, { sourceUrl: base });
    }

    const features = data.features ?? [];
    allFeatures.push(...features);

    if (features.length < PAGE_SIZE || data.exceededTransferLimit === false) break;
    offset += features.length;
  }

  return allFeatures;
}

// ── Source: Parcels / Plats (polkpa.org via ArcGIS) ──────────────────────────

async function pullParcels() {
  const SOURCE = 'polkpa.org ArcGIS parcel layer';
  const URL    = `${GIS_BASE}/Property/PolkParcels/MapServer/0`;

  log.info(`Pulling parcels from ${SOURCE}…`);

  // Only pull subdivision-related parcels (vacant or has subdiv name)
  // DOR codes 00-05 = vacant residential; code 01 = single-family residential
  const features = await arcgisPaginate(
    'Property/PolkParcels/MapServer/0',
    "DOR_UC IN ('00','01','02','03','04','05','0') OR SUB_NAME IS NOT NULL",
    'STRAP,OWNER1,SUB_NAME,PLAT_BK,PLAT_PG,PLAT_RECORDED,DOR_UC,JUST_VAL_IMPRV,ACT_YR_BLT,OR_SALE_DATE,LND_SQFT,TOTAL_ACRES,MAIL_ADDR1,PHYS_ADDR,LND_USE_CD',
  );

  if (!features.length) throw Object.assign(new Error('Zero features returned'), { sourceUrl: URL });

  const headers = [
    'PARCEL_NUMBER','OWNER_NAME','SUBDIVISION','PLAT_BK','PLAT_PG','PLAT_RECORDED',
    'DOR_CODE','JUST_VAL_IMPRV','ACT_YR_BLT','OR_SALE_DATE',
    'LAND_AREA','TOTAL_ACRES','MAIL_ADDR1','PHYS_ADDR','LAT','LON',
  ];

  const rows = features.map((f) => {
    const a = f.attributes ?? {};
    const g = f.geometry ?? {};
    const rings = g.rings?.[0];
    let lat = '', lon = '';
    if (rings?.length) {
      lon = (rings.reduce((s, p) => s + p[0], 0) / rings.length).toFixed(6);
      lat = (rings.reduce((s, p) => s + p[1], 0) / rings.length).toFixed(6);
    }
    return [
      a.STRAP ?? '', a.OWNER1 ?? '', a.SUB_NAME ?? '',
      a.PLAT_BK ?? '', a.PLAT_PG ?? '',
      a.PLAT_RECORDED ? new Date(a.PLAT_RECORDED).toLocaleDateString('en-US') : '',
      a.DOR_UC ?? '', a.JUST_VAL_IMPRV ?? '', a.ACT_YR_BLT ?? '',
      a.OR_SALE_DATE ? new Date(a.OR_SALE_DATE).toLocaleDateString('en-US') : '',
      a.LND_SQFT ?? '', a.TOTAL_ACRES ?? '',
      a.MAIL_ADDR1 ?? '', a.PHYS_ADDR ?? '',
      lat, lon,
    ].map(String);
  });

  return http.toCsv({ headers, rows });
}

// ── Source: Tax Delinquent (polktaxes.com) ────────────────────────────────────

const POLKTAXES_DELINQUENT = 'https://www.polktaxes.com/DelinquentTaxCertificates';
const POLKTAXES_EXPORT     = 'https://www.polktaxes.com/TaxCertificateList/Export';

async function pullTaxDelinquent() {
  log.info('Pulling tax delinquent list from polktaxes.com…');

  // Strategy 1: Try direct CSV export endpoint
  try {
    await RATE.acquire();
    const buf = await http.download(POLKTAXES_EXPORT, {
      headers: { 'Referer': POLKTAXES_DELINQUENT },
    });
    const text = buf.toString('utf8');
    if (text.trim().length > 100 && text.includes(',')) {
      log.info(`Tax delinquent: export endpoint succeeded (${text.split('\n').length} rows)`);
      return normalizePolkTaxDelinquent(text);
    }
  } catch (err) {
    log.warn(`Tax delinquent export failed: ${err.message} — trying HTML parse`);
  }

  // Strategy 2: Parse HTML table
  try {
    await RATE.acquire();
    const { $, status } = await http.get(POLKTAXES_DELINQUENT);
    if (status >= 400) throw new Error(`HTTP ${status}`);

    const { headers, rows } = http.parseTable($, 'table');
    if (!rows.length) throw new Error('No table rows found');

    log.info(`Tax delinquent: HTML table parse succeeded (${rows.length} rows)`);
    return http.toCsv({ headers: normalizePolkTDHeaders(headers), rows });
  } catch (err) {
    log.warn(`Tax delinquent HTML parse failed: ${err.message} — trying Playwright`);
  }

  // Strategy 3: Playwright for JS-rendered table
  await RATE.acquire();
  const html = await browser.fetchRendered(POLKTAXES_DELINQUENT, {
    waitFor: 'table,#delinquent-list,.grid',
    timeout: 40_000,
  });

  const $ = require('cheerio').load(html);
  const { headers, rows } = http.parseTable($, 'table');
  if (!rows.length) throw new Error('Playwright: no table rows found on polktaxes.com');

  log.info(`Tax delinquent: Playwright succeeded (${rows.length} rows)`);
  return http.toCsv({ headers: normalizePolkTDHeaders(headers), rows });
}

function normalizePolkTDHeaders(raw) {
  return raw.map((h) => {
    const u = h.toUpperCase().replace(/\s+/g, '_');
    if (/PARCEL|APN|STRAP|ACCOUNT/.test(u)) return 'PARCEL_NUMBER';
    if (/OWNER|NAME/.test(u))               return 'OWNER_NAME';
    if (/YEAR|YR/.test(u))                  return 'TAX_YEAR';
    if (/AMOUNT|DUE|OWED|TOTAL/.test(u))    return 'TOTAL_DUE';
    if (/CERT/.test(u))                     return 'CERTIFICATE_NO';
    if (/DATE/.test(u))                     return 'CERT_DATE';
    if (/CONSEC|YEARS|OUTSTANDING/.test(u)) return 'YEARS_OUTSTANDING';
    return u;
  });
}

function normalizePolkTaxDelinquent(rawCsv) {
  const lines  = rawCsv.trim().split('\n');
  const header = lines[0];
  // Pass through — the export column names will be resolved via ALIASES in agent 02
  return rawCsv;
}

// ── Source: Lis Pendens (polkclerk.com Official Records) ─────────────────────

const POLKCLERK_OR = 'https://www.polkclerk.com/official-records/search';

// Document type codes used by Clerk's iCLERT system for lis pendens
const LP_DOC_TYPES = ['LIS PENDENS', 'NOTICE OF LIS PENDENS', 'LP'];

async function pullLisPendens() {
  log.info('Pulling lis pendens from polkclerk.com…');

  // Strategy 1: Try the official records REST search (some Clerk systems expose JSON)
  try {
    await RATE.acquire();
    const params = new URLSearchParams({
      docType:   'LIS PENDENS',
      dateFrom:  fiveYearsAgo(),
      dateTo:    today(),
      format:    'json',
    });
    const resp = await http.get(`${POLKCLERK_OR}?${params}`, {
      headers: { 'Accept': 'application/json,text/html' },
    });

    if (resp.status === 200) {
      let parsed;
      try { parsed = JSON.parse(typeof resp.data === 'string' ? resp.data : JSON.stringify(resp.data)); } catch { parsed = null; }

      if (parsed?.results?.length || parsed?.records?.length) {
        const items = parsed.results ?? parsed.records ?? [];
        log.info(`Lis pendens: JSON API succeeded (${items.length} records)`);
        return polkClerkJsonToCsv(items);
      }
    }
  } catch (err) {
    log.warn(`Lis pendens JSON attempt failed: ${err.message}`);
  }

  // Strategy 2: Playwright form fill
  log.info('Lis pendens: trying Playwright form fill on polkclerk.com…');
  const allRows = [];
  let headers   = ['PARCEL_NUMBER','OWNER_NAME','FILING_DATE','CASE_NUMBER','LENDER','CASE_STATUS'];

  for (const docType of LP_DOC_TYPES) {
    try {
      await RATE.acquire();
      const pages = await browser.fillAndFetch(POLKCLERK_OR, {
        fields: {
          '#documentType,input[name*="documentType"],input[name*="doctype"],select[name*="doctype"]': docType,
          '#dateFrom,input[name*="dateFrom"],input[name*="startDate"]': fiveYearsAgo(),
          '#dateTo,input[name*="dateTo"],input[name*="endDate"]':       today(),
        },
        submit:  'button[type="submit"],input[type="submit"],.search-btn,#btnSearch',
        waitFor: 'table,.results-grid,.search-results',
        pages:   20,
        nextBtn: '.next-btn,.pagination .next,a[aria-label="Next"],button:contains("Next")',
      });

      for (const html of pages) {
        const $ = require('cheerio').load(html);
        const { headers: h, rows } = http.parseTable($, 'table,.results-table');
        if (!rows.length) continue;
        if (!allRows.length && h.length) headers = normalizeClerkHeaders(h);
        allRows.push(...rows);
      }

      if (allRows.length) break;
    } catch (err) {
      log.warn(`Lis pendens Playwright attempt (${docType}): ${err.message}`);
    }
  }

  if (!allRows.length) throw new Error('No lis pendens records retrieved from polkclerk.com');

  log.info(`Lis pendens: Playwright succeeded (${allRows.length} rows)`);
  return http.toCsv({ headers, rows: allRows });
}

function normalizeClerkHeaders(raw) {
  return raw.map((h) => {
    const u = h.toUpperCase().replace(/\s+/g, '_');
    if (/PARCEL|APN|STRAP|FOLIO/.test(u))    return 'PARCEL_NUMBER';
    if (/OWNER|GRANTOR|DEFENDANT/.test(u))    return 'OWNER_NAME';
    if (/FILED|RECORDED|DATE/.test(u))        return 'FILING_DATE';
    if (/CASE|INSTRUMENT|BOOK|PAGE/.test(u))  return 'CASE_NUMBER';
    if (/AMOUNT|CLAIM|LIEN/.test(u))          return 'CLAIM_AMOUNT';
    if (/PLAINTIFF|LENDER|MORTGAGEE/.test(u)) return 'LENDER';
    if (/STATUS|DISPOSITION/.test(u))         return 'CASE_STATUS';
    return u;
  });
}

function polkClerkJsonToCsv(items) {
  return http.jsonToCsv(items, {
    PARCEL_NUMBER: (i) => i.parcelId     ?? i.strap     ?? '',
    OWNER_NAME:    (i) => i.ownerName    ?? i.grantor   ?? '',
    FILING_DATE:   (i) => i.filingDate   ?? i.dateRecorded ?? '',
    CASE_NUMBER:   (i) => i.caseNumber   ?? i.instrumentNo ?? '',
    CLAIM_AMOUNT:  (i) => i.claimAmount  ?? i.amount    ?? '',
    LENDER:        (i) => i.plaintiff    ?? i.lender    ?? '',
    CASE_STATUS:   (i) => i.status       ?? '',
  });
}

// ── Source: Building Permits (Polk County ArcGIS) ─────────────────────────────

const PERMIT_LAYER = 'Development/BuildingPermits/MapServer/0';

async function pullPermits() {
  log.info('Pulling building permits from Polk County ArcGIS…');

  // Use the ArcGIS permits layer — pull active SF permits from last 24 months
  const cutoffTs = Date.now() - (24 * 30 * 24 * 60 * 60 * 1000);
  const cutoffDate = new Date(cutoffTs).toLocaleDateString('en-US');

  let features;
  try {
    features = await arcgisPaginate(
      PERMIT_LAYER,
      `PERMIT_TYPE LIKE '%SINGLE%' OR PERMIT_TYPE LIKE '%RESID%' OR PERMIT_TYPE LIKE '%DWELL%'`,
      'PERMIT_NUMBER,PERMIT_TYPE,PERMIT_STATUS,DATE_ISSUED,SITE_ADDRESS,CONTRACTOR,PERMIT_VALUE',
    );
  } catch (err) {
    // Fallback: pull all permits without type filter and let agent 03 filter
    log.warn(`Permit layer type filter failed (${err.message}) — pulling all permits`);
    features = await arcgisPaginate(
      PERMIT_LAYER,
      '1=1',
      'PERMIT_NUMBER,PERMIT_TYPE,PERMIT_STATUS,DATE_ISSUED,SITE_ADDRESS,CONTRACTOR,PERMIT_VALUE',
    );
  }

  if (!features.length) throw new Error('Zero permit features returned from ArcGIS');

  const headers = [
    'PERMIT_NUMBER','PERMIT_TYPE','PERMIT_STATUS','DATE_ISSUED',
    'SITE_ADDRESS','CONTRACTOR','PERMIT_VALUE','LAT','LON',
  ];

  const rows = features.map((f) => {
    const a = f.attributes ?? {};
    const g = f.geometry ?? {};
    const lat = g.y ? g.y.toFixed(6) : '';
    const lon = g.x ? g.x.toFixed(6) : '';
    return [
      a.PERMIT_NUMBER ?? '', a.PERMIT_TYPE ?? '', a.PERMIT_STATUS ?? '',
      a.DATE_ISSUED ? new Date(a.DATE_ISSUED).toLocaleDateString('en-US') : '',
      a.SITE_ADDRESS ?? '', a.CONTRACTOR ?? '',
      a.PERMIT_VALUE ?? '', lat, lon,
    ].map(String);
  });

  log.info(`Permits: ArcGIS returned ${rows.length} records`);
  return http.toCsv({ headers, rows });
}

// ── Utility ───────────────────────────────────────────────────────────────────

function today() {
  return new Date().toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
}
function fiveYearsAgo() {
  const d = new Date(); d.setFullYear(d.getFullYear() - 5);
  return d.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
}

async function pullWithRetry(name, pullFn, sourceUrl) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const csv = await pullFn();
      if (!csv || csv.trim().split('\n').length < 2) throw new Error('Returned empty dataset');
      return csv;
    } catch (err) {
      const msg = err.message ?? String(err);
      if (attempt === 1) {
        log.warn(`OSINT PULL FAILED - ${sourceUrl} - ${msg} - retry in 60s`);
        await new Promise((r) => setTimeout(r, 60_000));
      } else {
        log.error(`OSINT PULL FAILED - ${sourceUrl} - ${msg} - giving up after 2 attempts`);
        return null;
      }
    }
  }
  return null;
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function run(ctx) {
  log.info(`Starting  v${AGENT_VERSION}`);

  const startedAt = Date.now();
  const results   = {};

  // ── Parcels ──
  if (isFresh(COUNTY_SLUG, 'parcels')) {
    log.info('parcels.csv — fresh cache, skipping pull');
    results.parcels = 'cached';
  } else {
    const csv = await pullWithRetry('parcels', pullParcels, `${GIS_BASE}/Property/PolkParcels/MapServer/0`);
    if (csv) { writeCache(COUNTY_SLUG, 'parcels', csv); results.parcels = 'pulled'; }
    else       results.parcels = 'failed';
  }

  // ── Tax Delinquent ──
  if (isFresh(COUNTY_SLUG, 'tax-delinquent')) {
    log.info('tax-delinquent.csv — fresh cache, skipping pull');
    results['tax-delinquent'] = 'cached';
  } else {
    const csv = await pullWithRetry('tax-delinquent', pullTaxDelinquent, POLKTAXES_DELINQUENT);
    if (csv) { writeCache(COUNTY_SLUG, 'tax-delinquent', csv); results['tax-delinquent'] = 'pulled'; }
    else       results['tax-delinquent'] = 'failed';
  }

  // ── Lis Pendens ──
  if (isFresh(COUNTY_SLUG, 'lis-pendens')) {
    log.info('lis-pendens.csv — fresh cache, skipping pull');
    results['lis-pendens'] = 'cached';
  } else {
    const csv = await pullWithRetry('lis-pendens', pullLisPendens, POLKCLERK_OR);
    if (csv) { writeCache(COUNTY_SLUG, 'lis-pendens', csv); results['lis-pendens'] = 'pulled'; }
    else       results['lis-pendens'] = 'failed';
  }

  // ── Permits ──
  if (isFresh(COUNTY_SLUG, 'permits')) {
    log.info('permits.csv — fresh cache, skipping pull');
    results.permits = 'cached';
  } else {
    const csv = await pullWithRetry('permits', pullPermits, `${GIS_BASE}/${PERMIT_LAYER}`);
    if (csv) { writeCache(COUNTY_SLUG, 'permits', csv); results.permits = 'pulled'; }
    else       results.permits = 'failed';
  }

  // ── Availability check ──
  const allFailed = Object.values(results).every((v) => v === 'failed');
  if (allFailed) {
    log.error('REAL DATA UNAVAILABLE - DO NOT SCORE — all Polk County OSINT sources failed.');
    const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, county: COUNTY_SLUG, status: 'real-data-unavailable', results, durationMs: Date.now() - startedAt };
    fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
    return result;
  }

  const anyFailed = Object.values(results).some((v) => v === 'failed');
  if (anyFailed) {
    const failed = Object.entries(results).filter(([, v]) => v === 'failed').map(([k]) => k);
    log.warn(`Partial pull — failed sources: ${failed.join(', ')}. Downstream agents will operate on available data only.`);
  }

  log.info('');
  log.info('── Intake Summary ────────────────────────────────────');
  for (const [src, status] of Object.entries(results)) log.info(`   ${src.padEnd(20)} ${status}`);
  log.info(`   Duration: ${Date.now() - startedAt}ms`);
  log.info('─────────────────────────────────────────────────────');

  const result = {
    agentId: AGENT_ID, agentVersion: AGENT_VERSION,
    county: COUNTY_SLUG,
    status: 'ok',
    results,
    durationMs: Date.now() - startedAt,
  };

  fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
  if (ctx.intakeResults) ctx.intakeResults[COUNTY_SLUG] = results;

  return result;
}

module.exports = { run };
