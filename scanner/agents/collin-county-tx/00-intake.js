'use strict';

/**
 * Agent 00 — Data Intake  (Collin County TX)
 * ───────────────────────────────────────────
 * Pulls all 4 raw data sources for Collin County TX automatically on each run.
 * Writes normalized CSVs to data/collin-county-tx/raw/.
 *
 * Sources:
 *   parcels        — collincad.org public property search API / bulk download
 *   tax-delinquent — collincountytx.gov Tax Assessor delinquent list
 *   lis-pendens    — Collin County Clerk official records portal
 *   permits        — Collin County Development Services permit portal
 */

const fs   = require('node:fs');
const path = require('node:path');

const log        = require('../../lib/logger').agent('intake-collin');
const { isFresh, writeCache } = require('../../lib/intake/cache');
const http       = require('../../lib/intake/http-client');
const browser    = require('../../lib/intake/browser');
const { RateLimiter } = require('../../lib/rate-limiter');

const AGENT_ID      = '00-intake';
const AGENT_VERSION = '2.0.0';
const COUNTY_SLUG   = 'collin-county-tx';

const RATE = new RateLimiter(1500);

// ── Source: Parcels (CCAD — collincad.org) ────────────────────────────────────

const CCAD_BASE     = 'https://www.collincad.org';
const CCAD_SEARCH   = `${CCAD_BASE}/propertysearch`;
const CCAD_EXPORT   = `${CCAD_BASE}/propertysearch/export`;
const CCAD_API      = `${CCAD_BASE}/api/v1/properties`;

async function pullParcels() {
  log.info('Pulling Collin County parcels from collincad.org…');

  // Strategy 1: CCAD public API (JSON)
  try {
    await RATE.acquire();
    const resp = await http.get(`${CCAD_API}?propertyType=R&limit=10000`, {
      headers: { 'Accept': 'application/json' },
    });
    if (resp.status === 200) {
      let data;
      try { data = JSON.parse(typeof resp.data === 'string' ? resp.data : '{}'); } catch { data = null; }
      const items = data?.data ?? data?.properties ?? data?.results ?? (Array.isArray(data) ? data : null);
      if (items?.length) {
        log.info(`Collin parcels: CCAD JSON API succeeded (${items.length} records)`);
        return http.jsonToCsv(items, {
          ACCOUNT_NUMBER: (i) => i.accountNumber ?? i.accountNo   ?? i.id      ?? '',
          OWNER_NAME:     (i) => i.ownerName     ?? i.owner       ?? '',
          SUBDIV_NAME:    (i) => i.subdivision   ?? i.subdivName  ?? '',
          PLAT_BOOK:      (i) => i.platBook       ?? i.book        ?? '',
          PLAT_PAGE:      (i) => i.platPage       ?? i.page        ?? '',
          DATE_RECORDED:  (i) => i.dateRecorded   ?? i.recordedDate ?? '',
          PROPERTY_USE:   (i) => i.propertyUse    ?? i.useCode     ?? '',
          BUILDING_VALUE: (i) => i.improvementValue ?? i.buildingValue ?? '',
          YEAR_BUILT:     (i) => i.yearBuilt      ?? '',
          DEED_DATE:      (i) => i.lastSaleDate   ?? i.deedDate    ?? '',
          TOTAL_ACRES:    (i) => i.acres          ?? i.landArea    ?? '',
          MAILING_ADDR:   (i) => i.mailingAddress ?? '',
          PROP_ADDR:      (i) => i.siteAddress    ?? i.propertyAddress ?? '',
          LAT:            (i) => i.latitude       ?? i.lat         ?? '',
          LON:            (i) => i.longitude      ?? i.lon         ?? '',
        });
      }
    }
  } catch (err) {
    log.warn(`Collin parcels CCAD API failed: ${err.message}`);
  }

  // Strategy 2: CCAD CSV export
  try {
    await RATE.acquire();
    const resp = await http.get(CCAD_SEARCH);
    if (resp.status === 200) {
      // Look for export / download button or direct CSV link
      const dlLink = resp.$('a[href*="export"][href*=".csv"],a[href*="download"],#btnExport').first().attr('href');
      if (dlLink) {
        const url = dlLink.startsWith('http') ? dlLink : `${CCAD_BASE}${dlLink}`;
        const buf = await http.download(url);
        const text = buf.toString('utf8');
        if (text.includes(',') && text.split('\n').length > 2) {
          log.info('Collin parcels: CCAD export link succeeded');
          return text;
        }
      }
    }
  } catch (err) {
    log.warn(`Collin parcels export link failed: ${err.message}`);
  }

  // Strategy 3: Playwright on CCAD search
  await RATE.acquire();
  const dl = await browser.clickDownload(CCAD_SEARCH, {
    clickSelector: '#btnExport,button:contains("Export"),a:contains("CSV")',
    timeout: 45_000,
  });
  if (dl?.content) {
    log.info('Collin parcels: Playwright download succeeded');
    return dl.content;
  }

  throw new Error('No parcel data retrieved from collincad.org');
}

// ── Source: Tax Delinquent (collincountytx.gov Tax Office) ───────────────────

const COLLIN_TAX_BASE    = 'https://www.collincountytx.gov/tax';
const COLLIN_TAX_DELINQ  = `${COLLIN_TAX_BASE}/Pages/delinquent-accounts.aspx`;
const COLLIN_TAX_EXPORT  = `${COLLIN_TAX_BASE}/api/delinquent/export`;
// Perdue Brandon handles Collin County delinquent collections
const PERDUE_BASE        = 'https://pbfcm.com';
const PERDUE_COLLIN      = `${PERDUE_BASE}/online-delinquent-tax-search/?county=collin`;

async function pullTaxDelinquent() {
  log.info('Pulling Collin County tax delinquent list…');

  // Strategy 1: County tax office direct export
  try {
    await RATE.acquire();
    const buf = await http.download(COLLIN_TAX_EXPORT);
    const text = buf.toString('utf8');
    if (text.includes(',') && text.split('\n').length > 2) {
      log.info('Collin tax delinquent: county export succeeded');
      return text;
    }
  } catch (err) {
    log.warn(`Collin tax delinquent county export failed: ${err.message}`);
  }

  // Strategy 2: Static HTML page scrape (county site)
  try {
    await RATE.acquire();
    const { $, status } = await http.get(COLLIN_TAX_DELINQ);
    if (status < 400) {
      const { headers, rows } = http.parseTable($, 'table');
      if (rows.length) {
        log.info(`Collin tax delinquent: HTML parse succeeded (${rows.length} rows)`);
        return http.toCsv({ headers: normalizeTDHeaders(headers), rows });
      }

      const dlLink = $('a[href*="delinquent"][href*=".csv"],a[href*="export"],a:contains("Download")').first().attr('href');
      if (dlLink) {
        const url = dlLink.startsWith('http') ? dlLink : `https://www.collincountytx.gov${dlLink}`;
        const buf = await http.download(url);
        const text = buf.toString('utf8');
        if (text.trim().length > 100) return text;
      }
    }
  } catch (err) {
    log.warn(`Collin tax delinquent HTML scrape failed: ${err.message}`);
  }

  // Strategy 3: Playwright on the page
  await RATE.acquire();
  const html = await browser.fetchRendered(COLLIN_TAX_DELINQ, {
    waitFor: 'table,.delinquent',
    timeout: 40_000,
  });
  const $ = require('cheerio').load(html);
  const { headers, rows } = http.parseTable($, 'table');
  if (!rows.length) throw new Error('No tax delinquent data found on collincountytx.gov');
  log.info(`Collin tax delinquent: Playwright succeeded (${rows.length} rows)`);
  return http.toCsv({ headers: normalizeTDHeaders(headers), rows });
}

function normalizeTDHeaders(raw) {
  return raw.map((h) => {
    const u = h.toUpperCase().replace(/\s+/g, '_');
    if (/ACCOUNT|APN|PARCEL/.test(u))       return 'ACCOUNT_NUMBER';
    if (/OWNER|NAME/.test(u))               return 'OWNER_NAME';
    if (/YEAR|YR/.test(u))                  return 'TAX_YEAR';
    if (/AMOUNT|DUE|OWED|TOTAL/.test(u))    return 'TOTAL_DUE';
    if (/CERT|WARRANT/.test(u))             return 'CERTIFICATE_NO';
    if (/DATE/.test(u))                     return 'CERT_DATE';
    if (/CONSEC|YEARS|OUTSTANDING/.test(u)) return 'YEARS_OUTSTANDING';
    return u;
  });
}

// ── Source: Lis Pendens (Collin County Clerk) ─────────────────────────────────

const COLLIN_CLERK_BASE   = 'https://countyclerk.collincountytx.gov';
const COLLIN_CLERK_SEARCH = `${COLLIN_CLERK_BASE}/official-records/search`;

// Collin County uses Kofile or similar county clerk software
async function pullLisPendens() {
  log.info('Pulling Collin County lis pendens from countyclerk.collincountytx.gov…');

  const allRows = [];
  let headers   = ['ACCOUNT_NUMBER','OWNER_NAME','FILING_DATE','INSTRUMENT_NO','LENDER','CASE_STATUS'];

  // Strategy 1: Direct URL with query params (some Kofile/CSC systems accept)
  try {
    await RATE.acquire();
    const resp = await http.get(
      `${COLLIN_CLERK_SEARCH}?documentType=LIS+PENDENS&startDate=${fiveYearsAgo()}&endDate=${today()}`,
      { headers: { 'Accept': 'application/json,text/html' } },
    );
    if (resp.status === 200) {
      let data;
      try { data = JSON.parse(typeof resp.data === 'string' ? resp.data : '{}'); } catch { data = null; }
      if (data?.results?.length) {
        log.info(`Collin lis pendens: clerk JSON API succeeded (${data.results.length} records)`);
        return http.jsonToCsv(data.results, {
          ACCOUNT_NUMBER: (i) => i.accountNumber ?? i.parcelId  ?? '',
          OWNER_NAME:     (i) => i.grantorName   ?? i.ownerName ?? '',
          FILING_DATE:    (i) => i.recordedDate  ?? i.fileDate  ?? '',
          INSTRUMENT_NO:  (i) => i.instrumentNo  ?? i.docNo     ?? '',
          CLAIM_AMOUNT:   (i) => i.amount        ?? '',
          LENDER:         (i) => i.granteeName   ?? i.lender    ?? '',
          CASE_STATUS:    (i) => i.status        ?? '',
        });
      }

      const { headers: h, rows } = http.parseTable(resp.$, 'table,.results');
      if (rows.length) {
        log.info(`Collin lis pendens: HTML table parse succeeded (${rows.length} rows)`);
        return http.toCsv({ headers: normalizeLPHeaders(h), rows });
      }
    }
  } catch (err) {
    log.warn(`Collin clerk direct request failed: ${err.message}`);
  }

  // Strategy 2: Playwright form fill
  const docTypes = ['LIS PENDENS', 'NOTICE OF LIS PENDENS', 'LIS_PENDENS'];
  for (const docType of docTypes) {
    try {
      await RATE.acquire();
      const pages = await browser.fillAndFetch(COLLIN_CLERK_SEARCH, {
        fields: {
          'input[name*="documentType"],select[name*="documentType"],#documentType': docType,
          'input[name*="startDate"],input[name*="dateFrom"],#startDate': fiveYearsAgo(),
          'input[name*="endDate"],input[name*="dateTo"],#endDate':       today(),
        },
        submit:  'button[type="submit"],#btnSearch,input[type="submit"]',
        waitFor: 'table,.results,.search-results,#searchResults',
        pages:   20,
        nextBtn: '.next,.pagination .next,a[aria-label="Next page"],button:contains("Next")',
      });

      for (const html of pages) {
        const $ = require('cheerio').load(html);
        const { headers: h, rows } = http.parseTable($, 'table,.results-table');
        if (!rows.length) continue;
        if (!allRows.length && h.length) headers = normalizeLPHeaders(h);
        allRows.push(...rows);
      }
      if (allRows.length) break;
    } catch (err) {
      log.warn(`Collin clerk Playwright (${docType}): ${err.message}`);
    }
  }

  if (!allRows.length) throw new Error('No lis pendens data from Collin County Clerk');
  log.info(`Collin lis pendens: Playwright succeeded (${allRows.length} rows)`);
  return http.toCsv({ headers, rows: allRows });
}

function normalizeLPHeaders(raw) {
  return raw.map((h) => {
    const u = h.toUpperCase().replace(/\s+/g, '_');
    if (/ACCOUNT|APN|PARCEL/.test(u))       return 'ACCOUNT_NUMBER';
    if (/OWNER|GRANTOR|DEFENDANT/.test(u))  return 'OWNER_NAME';
    if (/FILED|RECORDED|DATE/.test(u))      return 'FILING_DATE';
    if (/INSTRUMENT|DOC|BOOK|PAGE/.test(u)) return 'INSTRUMENT_NO';
    if (/AMOUNT|CLAIM|LIEN/.test(u))        return 'CLAIM_AMOUNT';
    if (/LENDER|PLAINTIFF|GRANTEE/.test(u)) return 'LENDER';
    if (/STATUS/.test(u))                  return 'CASE_STATUS';
    return u;
  });
}

// ── Source: Building Permits (Collin County Development Services) ─────────────

const COLLIN_DEV_BASE    = 'https://www.collincountytx.gov/development_services';
const COLLIN_PERMIT_SEARCH = `${COLLIN_DEV_BASE}/Pages/permit-search.aspx`;
const COLLIN_PERMIT_EXPORT = `${COLLIN_DEV_BASE}/api/permits/export`;
// Many Collin County cities use MyGovHub / Energov
const ENERGOV_BASE       = 'https://etrakit.collincountytx.gov';

async function pullPermits() {
  log.info('Pulling Collin County building permits…');

  // Strategy 1: Direct export from dev services
  try {
    await RATE.acquire();
    const buf = await http.download(`${COLLIN_PERMIT_EXPORT}?type=SFR&months=24`);
    const text = buf.toString('utf8');
    if (text.includes(',') && text.split('\n').length > 2) {
      log.info('Collin permits: dev services export succeeded');
      return text;
    }
  } catch (err) {
    log.warn(`Collin permits export failed: ${err.message}`);
  }

  // Strategy 2: eTraKit (Tyler Energov) permit portal
  try {
    await RATE.acquire();
    const resp = await http.get(`${ENERGOV_BASE}/search/permit?type=building&subType=newResidential`, {
      headers: { 'Accept': 'application/json,text/html' },
    });
    if (resp.status === 200) {
      let data;
      try { data = JSON.parse(typeof resp.data === 'string' ? resp.data : '{}'); } catch { data = null; }
      const items = data?.permits ?? data?.results ?? (Array.isArray(data) ? data : null);
      if (items?.length) {
        log.info(`Collin permits: Energov API succeeded (${items.length} records)`);
        return http.jsonToCsv(items, {
          PERMIT_NUMBER: (i) => i.permitNumber ?? i.appNo  ?? '',
          PERMIT_TYPE:   (i) => i.permitType   ?? i.type   ?? '',
          PERMIT_STATUS: (i) => i.status       ?? '',
          DATE_ISSUED:   (i) => i.issueDate    ?? i.issuedDate ?? '',
          SITE_ADDRESS:  (i) => i.siteAddress  ?? i.address ?? '',
          CONTRACTOR:    (i) => i.contractorName ?? i.applicant ?? '',
          PERMIT_VALUE:  (i) => i.estimatedValue ?? i.valuation ?? '',
          LAT:           (i) => i.latitude     ?? '',
          LON:           (i) => i.longitude    ?? '',
        });
      }
    }
  } catch (err) {
    log.warn(`Collin permits Energov API failed: ${err.message}`);
  }

  // Strategy 3: Playwright on county dev services permit search
  try {
    await RATE.acquire();
    const pages = await browser.fillAndFetch(COLLIN_PERMIT_SEARCH, {
      fields: {
        'select[name*="permitType"],#permitType': 'NEW RESIDENTIAL',
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
      log.info(`Collin permits: Playwright succeeded (${allRows.length} rows)`);
      return http.toCsv({ headers, rows: allRows });
    }
  } catch (err) {
    log.warn(`Collin permits Playwright failed: ${err.message}`);
  }

  throw new Error('No permit data retrieved from Collin County Development Services');
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
    const csv = await pullWithRetry('parcels', pullParcels, CCAD_BASE);
    if (csv) { writeCache(COUNTY_SLUG, 'parcels', csv); results.parcels = 'pulled'; }
    else       results.parcels = 'failed';
  }

  if (isFresh(COUNTY_SLUG, 'tax-delinquent')) {
    log.info('tax-delinquent.csv — fresh cache'); results['tax-delinquent'] = 'cached';
  } else {
    const csv = await pullWithRetry('tax-delinquent', pullTaxDelinquent, COLLIN_TAX_DELINQ);
    if (csv) { writeCache(COUNTY_SLUG, 'tax-delinquent', csv); results['tax-delinquent'] = 'pulled'; }
    else       results['tax-delinquent'] = 'failed';
  }

  if (isFresh(COUNTY_SLUG, 'lis-pendens')) {
    log.info('lis-pendens.csv — fresh cache'); results['lis-pendens'] = 'cached';
  } else {
    const csv = await pullWithRetry('lis-pendens', pullLisPendens, COLLIN_CLERK_SEARCH);
    if (csv) { writeCache(COUNTY_SLUG, 'lis-pendens', csv); results['lis-pendens'] = 'pulled'; }
    else       results['lis-pendens'] = 'failed';
  }

  if (isFresh(COUNTY_SLUG, 'permits')) {
    log.info('permits.csv — fresh cache'); results.permits = 'cached';
  } else {
    const csv = await pullWithRetry('permits', pullPermits, COLLIN_DEV_BASE);
    if (csv) { writeCache(COUNTY_SLUG, 'permits', csv); results.permits = 'pulled'; }
    else       results.permits = 'failed';
  }

  const allFailed = Object.values(results).every((v) => v === 'failed');
  if (allFailed) {
    log.error('REAL DATA UNAVAILABLE - DO NOT SCORE — all Collin County TX OSINT sources failed.');
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
