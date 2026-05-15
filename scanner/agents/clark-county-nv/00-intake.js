'use strict';

/**
 * Agent 00 — Data Intake  (Clark County NV)
 * ──────────────────────────────────────────
 * Pulls all 4 raw data sources for Clark County NV automatically on each run.
 * Writes normalized CSVs to data/clark-county-nv/raw/.
 *
 * Sources:
 *   parcels        — assessor.clarkcountynv.gov ArcGIS REST / parcel search
 *   tax-delinquent — clarkcountynv.gov/finance delinquent tax list
 *   lis-pendens    — Clark County Recorder official records search
 *   permits        — Clark County Building Department portal
 */

const fs   = require('node:fs');
const path = require('node:path');

const log        = require('../../lib/logger').agent('intake-clark');
const { isFresh, writeCache } = require('../../lib/intake/cache');
const http       = require('../../lib/intake/http-client');
const browser    = require('../../lib/intake/browser');
const { RateLimiter } = require('../../lib/rate-limiter');

const AGENT_ID      = '00-intake';
const AGENT_VERSION = '2.0.0';
const COUNTY_SLUG   = 'clark-county-nv';

const RATE = new RateLimiter(1500);

// ── Source: Parcels (assessor.clarkcountynv.gov) ──────────────────────────────

const ASSESSOR_BASE     = 'https://assessor.clarkcountynv.gov';
const ASSESSOR_API      = `${ASSESSOR_BASE}/api/parcel/search`;
const ASSESSOR_ARCGIS   = 'https://gis.clarkcountynv.gov/arcgis/rest/services';
const ASSESSOR_DOWNLOAD = `${ASSESSOR_BASE}/Assessor/AssessorMapViewer/ExportData`;

async function pullParcels() {
  log.info('Pulling Clark County parcels from assessor.clarkcountynv.gov…');

  // Strategy 1: ArcGIS REST for vacant/residential parcels
  try {
    const features = await arcgisPaginate(
      `${ASSESSOR_ARCGIS}/CCRP/Parcels/MapServer/0`,
      "USE_CODE IN ('0100','0200','0300','0400','0500','0101') OR SUBD_NAME IS NOT NULL",
      'APN,OWNER_NAME,SUBD_NAME,PLAT_BK,PLAT_PG,RECORDED_DATE,USE_CODE,IMPR_VALUE,YEAR_BUILT,SALE_DATE,ACREAGE,MAIL_ADDRESS,SITE_ADDRESS',
    );

    if (features.length) {
      const headers = [
        'APN','OWNER_NAME','SUBDIVISION','PLAT_BK','PLAT_PG','RECORDED_DATE',
        'USE_CODE','IMPROVEMENT_VALUE','YEAR_BUILT','LAST_SALE_DATE',
        'ACREAGE','MAILING_ADDRESS','SITE_ADDRESS','LAT','LON',
      ];
      const rows = features.map((f) => {
        const a = f.attributes ?? {};
        const g = f.geometry ?? {};
        const [lon, lat] = centroid(g.rings);
        return [
          a.APN ?? '', a.OWNER_NAME ?? '', a.SUBD_NAME ?? '',
          a.PLAT_BK ?? '', a.PLAT_PG ?? '',
          a.RECORDED_DATE ? new Date(a.RECORDED_DATE).toLocaleDateString('en-US') : '',
          a.USE_CODE ?? '', a.IMPR_VALUE ?? '', a.YEAR_BUILT ?? '',
          a.SALE_DATE ? new Date(a.SALE_DATE).toLocaleDateString('en-US') : '',
          a.ACREAGE ?? '', a.MAIL_ADDRESS ?? '', a.SITE_ADDRESS ?? '',
          lat, lon,
        ].map(String);
      });
      log.info(`Clark parcels: ArcGIS returned ${rows.length} records`);
      return http.toCsv({ headers, rows });
    }
  } catch (err) {
    log.warn(`Clark parcels ArcGIS failed: ${err.message} — trying assessor API`);
  }

  // Strategy 2: Assessor bulk export / CSV download
  try {
    await RATE.acquire();
    const buf = await http.download(`${ASSESSOR_DOWNLOAD}?type=csv&filter=vacant`, {});
    const text = buf.toString('utf8');
    if (text.trim().length > 100) {
      log.info('Clark parcels: assessor export succeeded');
      return text;
    }
  } catch (err) {
    log.warn(`Clark parcels assessor export failed: ${err.message} — trying Playwright`);
  }

  // Strategy 3: Playwright navigation on assessor site
  await RATE.acquire();
  const html = await browser.fetchRendered(`${ASSESSOR_BASE}/Assessor/AssessorMapViewer`, {
    waitFor: 'table,.parcel-results',
    timeout: 40_000,
  });
  const $ = require('cheerio').load(html);
  const { headers, rows } = http.parseTable($, 'table');
  if (!rows.length) throw new Error('No parcel data found via Playwright on assessor site');
  return http.toCsv({ headers, rows });
}

// ── Source: Tax Delinquent (clarkcountynv.gov/finance) ───────────────────────

const CLARK_TAX_BASE     = 'https://www.clarkcountynv.gov/government/departments/finance/property_tax';
const CLARK_TAX_DELINQ   = `${CLARK_TAX_BASE}/delinquent_tax`;
const CLARK_TAX_EXPORT   = 'https://finance.clarkcountynv.gov/TaxDelinquent/Export';

async function pullTaxDelinquent() {
  log.info('Pulling Clark County tax delinquent list…');

  // Strategy 1: Direct CSV export from finance portal
  try {
    await RATE.acquire();
    const buf = await http.download(CLARK_TAX_EXPORT);
    const text = buf.toString('utf8');
    if (text.includes(',') && text.split('\n').length > 2) {
      log.info(`Clark tax delinquent: export succeeded (${text.split('\n').length} rows)`);
      return text;
    }
  } catch (err) {
    log.warn(`Clark tax delinquent export failed: ${err.message}`);
  }

  // Strategy 2: Static HTML scrape
  try {
    await RATE.acquire();
    const { $, status } = await http.get(CLARK_TAX_DELINQ);
    if (status < 400) {
      const { headers, rows } = http.parseTable($, 'table');
      if (rows.length) {
        log.info(`Clark tax delinquent: HTML parse succeeded (${rows.length} rows)`);
        return http.toCsv({ headers: normalizeClarkTDHeaders(headers), rows });
      }

      // Check for download link in page
      const dlLink = $('a[href*="delinquent"][href*=".csv"], a[href*="export"], a:contains("Download")').first().attr('href');
      if (dlLink) {
        const url = dlLink.startsWith('http') ? dlLink : `https://www.clarkcountynv.gov${dlLink}`;
        const buf = await http.download(url);
        const text = buf.toString('utf8');
        if (text.trim().length > 100) {
          log.info('Clark tax delinquent: page download link succeeded');
          return text;
        }
      }
    }
  } catch (err) {
    log.warn(`Clark tax delinquent HTML failed: ${err.message}`);
  }

  // Strategy 3: Playwright
  await RATE.acquire();
  const html = await browser.fetchRendered(CLARK_TAX_DELINQ, {
    waitFor: 'table,.delinquent-list',
    timeout: 40_000,
  });
  const $ = require('cheerio').load(html);
  const { headers, rows } = http.parseTable($, 'table');
  if (!rows.length) throw new Error('No tax delinquent data found on clarkcountynv.gov');
  log.info(`Clark tax delinquent: Playwright succeeded (${rows.length} rows)`);
  return http.toCsv({ headers: normalizeClarkTDHeaders(headers), rows });
}

function normalizeClarkTDHeaders(raw) {
  return raw.map((h) => {
    const u = h.toUpperCase().replace(/\s+/g, '_');
    if (/APN|PARCEL/.test(u))           return 'APN';
    if (/OWNER|NAME/.test(u))           return 'OWNER_NAME';
    if (/YEAR|YR/.test(u))             return 'TAX_YEAR';
    if (/AMOUNT|DUE|OWED|TOTAL/.test(u)) return 'TOTAL_DUE';
    if (/CERT/.test(u))                return 'CERTIFICATE_NO';
    if (/DATE/.test(u))                return 'CERT_DATE';
    if (/CONSEC|YEARS|OUTSTANDING/.test(u)) return 'YEARS_OUTSTANDING';
    return u;
  });
}

// ── Source: Lis Pendens / Foreclosures (recorder.clarkcountynv.gov) ──────────

const CLARK_RECORDER  = 'https://recorder.clarkcountynv.gov';
const CLARK_OR_SEARCH = `${CLARK_RECORDER}/FindDocuments/Search`;

async function pullLisPendens() {
  log.info('Pulling Clark County lis pendens from recorder.clarkcountynv.gov…');

  const allRows = [];
  let headers   = ['APN','OWNER_NAME','FILING_DATE','INSTRUMENT_NO','LENDER','CASE_STATUS'];

  // Strategy 1: REST JSON endpoint some county recorder systems expose
  try {
    await RATE.acquire();
    const resp = await http.get(`${CLARK_OR_SEARCH}?docType=LP&dateFrom=${fiveYearsAgo()}&dateTo=${today()}&format=json`, {
      headers: { 'Accept': 'application/json,text/html' },
    });
    if (resp.status === 200) {
      let data;
      try { data = JSON.parse(typeof resp.data === 'string' ? resp.data : '{}'); } catch { data = null; }
      if (data?.results?.length) {
        log.info(`Clark lis pendens: recorder JSON API succeeded (${data.results.length} records)`);
        return http.jsonToCsv(data.results, {
          APN:           (i) => i.apn          ?? i.parcelId    ?? '',
          OWNER_NAME:    (i) => i.ownerName     ?? i.grantor     ?? '',
          FILING_DATE:   (i) => i.recordedDate  ?? i.filedDate   ?? '',
          INSTRUMENT_NO: (i) => i.instrumentNo  ?? i.docNo       ?? '',
          CLAIM_AMOUNT:  (i) => i.amount        ?? '',
          LENDER:        (i) => i.lender        ?? i.plaintiff   ?? '',
          CASE_STATUS:   (i) => i.status        ?? '',
        });
      }
    }
  } catch (err) {
    log.warn(`Clark recorder JSON failed: ${err.message}`);
  }

  // Strategy 2: Playwright form fill on recorder site
  const docTypes = ['LIS PENDENS', 'NOTICE OF LIS PENDENS', 'NLP'];
  for (const docType of docTypes) {
    try {
      await RATE.acquire();
      const pages = await browser.fillAndFetch(CLARK_OR_SEARCH, {
        fields: {
          'input[name*="docType"],select[name*="docType"],#docType': docType,
          'input[name*="dateFrom"],input[name*="startDate"],#dateFrom': fiveYearsAgo(),
          'input[name*="dateTo"],input[name*="endDate"],#dateTo':       today(),
        },
        submit:  'button[type="submit"],input[type="submit"],.search-btn',
        waitFor: 'table,.results,.search-results',
        pages:   20,
        nextBtn: '.next,.pagination a:last-child,a[rel="next"]',
      });
      for (const html of pages) {
        const $ = require('cheerio').load(html);
        const { headers: h, rows } = http.parseTable($, 'table');
        if (!rows.length) continue;
        if (!allRows.length && h.length) headers = normalizeClarkLPHeaders(h);
        allRows.push(...rows);
      }
      if (allRows.length) break;
    } catch (err) {
      log.warn(`Clark recorder Playwright (${docType}): ${err.message}`);
    }
  }

  if (!allRows.length) throw new Error('No lis pendens data from recorder.clarkcountynv.gov');
  log.info(`Clark lis pendens: Playwright succeeded (${allRows.length} rows)`);
  return http.toCsv({ headers, rows: allRows });
}

function normalizeClarkLPHeaders(raw) {
  return raw.map((h) => {
    const u = h.toUpperCase().replace(/\s+/g, '_');
    if (/APN|PARCEL/.test(u))           return 'APN';
    if (/OWNER|GRANTOR|DEFENDANT/.test(u)) return 'OWNER_NAME';
    if (/FILED|RECORDED|DATE/.test(u))  return 'FILING_DATE';
    if (/INSTRUMENT|DOC|BOOK|PAGE/.test(u)) return 'INSTRUMENT_NO';
    if (/AMOUNT|CLAIM|LIEN/.test(u))    return 'CLAIM_AMOUNT';
    if (/LENDER|PLAINTIFF/.test(u))     return 'LENDER';
    if (/STATUS/.test(u))              return 'CASE_STATUS';
    return u;
  });
}

// ── Source: Building Permits (Clark County Building Department) ───────────────

const CLARK_BLDG_BASE   = 'https://www.clarkcountynv.gov/government/departments/development_services/building_division';
const CLARK_BLDG_SEARCH = 'https://www.clarkcountynv.gov/BuildingPermits/Search';
const CLARK_BLDG_EXPORT = 'https://www.clarkcountynv.gov/BuildingPermits/Export';

async function pullPermits() {
  log.info('Pulling Clark County building permits…');

  // Strategy 1: Direct CSV export
  try {
    await RATE.acquire();
    const buf = await http.download(`${CLARK_BLDG_EXPORT}?type=SFR&months=24`);
    const text = buf.toString('utf8');
    if (text.includes(',') && text.split('\n').length > 2) {
      log.info(`Clark permits: export endpoint succeeded`);
      return text;
    }
  } catch (err) {
    log.warn(`Clark permits export failed: ${err.message}`);
  }

  // Strategy 2: Playwright on building search portal
  try {
    await RATE.acquire();
    const pages = await browser.fillAndFetch(CLARK_BLDG_SEARCH, {
      fields: {
        'select[name*="permitType"],#permitType': 'SINGLE FAMILY',
        'input[name*="dateFrom"],#dateFrom':       fiveYearsAgo(),
        'input[name*="dateTo"],#dateTo':           today(),
      },
      submit:  'button[type="submit"],#btnSearch',
      waitFor: 'table,.permit-results',
      pages:   30,
      nextBtn: '.next,a[aria-label="Next"]',
    });

    const allRows = [];
    let headers   = ['PERMIT_NUMBER','PERMIT_TYPE','PERMIT_STATUS','DATE_ISSUED','SITE_ADDRESS','CONTRACTOR','PERMIT_VALUE'];
    for (const html of pages) {
      const $ = require('cheerio').load(html);
      const { headers: h, rows } = http.parseTable($, 'table');
      if (!rows.length) continue;
      if (!allRows.length && h.length) headers = h;
      allRows.push(...rows);
    }
    if (allRows.length) {
      log.info(`Clark permits: Playwright succeeded (${allRows.length} rows)`);
      return http.toCsv({ headers, rows: allRows });
    }
  } catch (err) {
    log.warn(`Clark permits Playwright failed: ${err.message}`);
  }

  // Strategy 3: HTML page parse
  const { $, status } = await http.get(CLARK_BLDG_BASE);
  if (status < 400) {
    const dlLink = $('a[href*="permit"][href*=".csv"],a[href*="export"]').first().attr('href');
    if (dlLink) {
      const url = dlLink.startsWith('http') ? dlLink : `https://www.clarkcountynv.gov${dlLink}`;
      const buf = await http.download(url);
      const text = buf.toString('utf8');
      if (text.trim().length > 100) return text;
    }
  }

  throw new Error('No permit data retrieved from Clark County Building Department');
}

// ── ArcGIS pagination (county-generic) ────────────────────────────────────────

const PAGE_SIZE = 1000;

async function arcgisPaginate(layerUrl, where, outFields) {
  let offset = 0;
  const all  = [];

  while (true) {
    await RATE.acquire();
    const params = new URLSearchParams({
      where, outFields, f: 'json',
      returnGeometry:    'true',
      resultOffset:      String(offset),
      resultRecordCount: String(PAGE_SIZE),
    });
    const resp = await fetch(`${layerUrl}/query?${params}`, {
      signal: AbortSignal.timeout(30_000),
      headers: { 'User-Agent': 'AMARA-OS-LandScanner/2.0' },
    });
    if (!resp.ok) throw new Error(`ArcGIS HTTP ${resp.status} at ${layerUrl}`);
    const data     = await resp.json();
    const features = data.features ?? [];
    all.push(...features);
    if (features.length < PAGE_SIZE || data.exceededTransferLimit === false) break;
    offset += features.length;
  }
  return all;
}

function centroid(rings) {
  if (!rings?.length || !rings[0]?.length) return ['', ''];
  const ring = rings[0];
  const lon = (ring.reduce((s, p) => s + p[0], 0) / ring.length).toFixed(6);
  const lat = (ring.reduce((s, p) => s + p[1], 0) / ring.length).toFixed(6);
  return [lon, lat];
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
      if (!csv || csv.trim().split('\n').length < 2) throw new Error('Empty dataset');
      return csv;
    } catch (err) {
      if (attempt === 1) {
        log.warn(`OSINT PULL FAILED - ${sourceUrl} - ${err.message} - retry in 60s`);
        await new Promise((r) => setTimeout(r, 60_000));
      } else {
        log.error(`OSINT PULL FAILED - ${sourceUrl} - ${err.message} - giving up`);
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

  if (isFresh(COUNTY_SLUG, 'parcels')) {
    log.info('parcels.csv — fresh cache'); results.parcels = 'cached';
  } else {
    const csv = await pullWithRetry('parcels', pullParcels, ASSESSOR_BASE);
    if (csv) { writeCache(COUNTY_SLUG, 'parcels', csv); results.parcels = 'pulled'; }
    else       results.parcels = 'failed';
  }

  if (isFresh(COUNTY_SLUG, 'tax-delinquent')) {
    log.info('tax-delinquent.csv — fresh cache'); results['tax-delinquent'] = 'cached';
  } else {
    const csv = await pullWithRetry('tax-delinquent', pullTaxDelinquent, CLARK_TAX_DELINQ);
    if (csv) { writeCache(COUNTY_SLUG, 'tax-delinquent', csv); results['tax-delinquent'] = 'pulled'; }
    else       results['tax-delinquent'] = 'failed';
  }

  if (isFresh(COUNTY_SLUG, 'lis-pendens')) {
    log.info('lis-pendens.csv — fresh cache'); results['lis-pendens'] = 'cached';
  } else {
    const csv = await pullWithRetry('lis-pendens', pullLisPendens, CLARK_OR_SEARCH);
    if (csv) { writeCache(COUNTY_SLUG, 'lis-pendens', csv); results['lis-pendens'] = 'pulled'; }
    else       results['lis-pendens'] = 'failed';
  }

  if (isFresh(COUNTY_SLUG, 'permits')) {
    log.info('permits.csv — fresh cache'); results.permits = 'cached';
  } else {
    const csv = await pullWithRetry('permits', pullPermits, CLARK_BLDG_BASE);
    if (csv) { writeCache(COUNTY_SLUG, 'permits', csv); results.permits = 'pulled'; }
    else       results.permits = 'failed';
  }

  const allFailed = Object.values(results).every((v) => v === 'failed');
  if (allFailed) {
    log.error('REAL DATA UNAVAILABLE - DO NOT SCORE — all Clark County NV OSINT sources failed.');
    const r = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, county: COUNTY_SLUG, status: 'real-data-unavailable', results, durationMs: Date.now() - startedAt };
    fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(r, null, 2));
    return r;
  }

  log.info('');
  log.info('── Intake Summary ────────────────────────────────────');
  for (const [src, status] of Object.entries(results)) log.info(`   ${src.padEnd(20)} ${status}`);
  log.info(`   Duration: ${Date.now() - startedAt}ms`);
  log.info('─────────────────────────────────────────────────────');

  const result = { agentId: AGENT_ID, agentVersion: AGENT_VERSION, county: COUNTY_SLUG, status: 'ok', results, durationMs: Date.now() - startedAt };
  fs.writeFileSync(path.join(ctx.runDir, `${AGENT_ID}.json`), JSON.stringify(result, null, 2));
  if (ctx.intakeResults) ctx.intakeResults[COUNTY_SLUG] = results;
  return result;
}

module.exports = { run };
