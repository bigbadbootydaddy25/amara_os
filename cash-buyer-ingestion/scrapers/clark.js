/**
 * Clark County NV / Las Vegas — deed record scraper
 * Portal: https://recorder.clarkcountynv.gov/ESales/
 * Strategy: Try REST API first; if blocked, fall back to Playwright on the recorder portal.
 *
 * Cash signal: No Deed of Trust filed on same parcel within 30 days of deed.
 * Target ZIPs: 89101, 89104, 89110, 89115, 89121, 89030
 */

import { chromium } from 'playwright';
import {
  checkRobotsTxt,
  createBrowser,
  newPage,
  safeGoto,
  safeAxios,
  randomDelay,
  shortDelay,
  detectCaptcha,
  formatDate,
  isoDate,
  dateRangeLast365,
  extractZip,
  makeTransaction,
  parseConsideration,
  delay,
} from './utils.js';

const RECORDER_BASE = 'https://recorder.clarkcountynv.gov';
const ESALES_BASE = `${RECORDER_BASE}/ESales`;
const PORTAL_BASE = 'https://www.clarkcountynv.gov/government/elected_officials/recorder';
const COUNTY = 'CLARK_NV';
const TARGET_ZIPS = ['89101', '89104', '89110', '89115', '89121', '89030'];

// Clark County Nevada recorder instrument type codes (per ESales documentation)
const DEED_INSTRUMENT_CODES = ['GD', 'WD', 'SWD', 'QCD', 'TD']; // Grant Deed, Warranty Deed, etc.
const DOT_INSTRUMENT_CODES = ['DOT', 'DT', 'MTG'];

export async function scrapeClark() {
  const errors = [];

  try {
    const { from, to } = dateRangeLast365();
    console.log(`[${COUNTY}] Scraping ${formatDate(from)} → ${formatDate(to)}`);

    // Strategy 1: Try the REST/ESales API
    const apiAllowed = await checkRobotsTxt(RECORDER_BASE, '/ESales/');
    if (apiAllowed) {
      const apiResult = await tryESalesApi(from, to);
      if (apiResult !== null) {
        const flagged = await crossCheckDots(apiResult, from, to);
        const filtered = flagged.filter((t) => t.zip && TARGET_ZIPS.includes(t.zip));
        console.log(`[${COUNTY}] ${filtered.length} records in target ZIPs via REST API`);
        return { county: COUNTY, transactions: filtered, errors };
      }
    }

    // Strategy 2: Playwright on recorder portal
    console.log(`[${COUNTY}] ESales API unavailable — switching to Playwright`);
    const portalAllowed = await checkRobotsTxt(RECORDER_BASE, '/');
    if (!portalAllowed) {
      return { county: COUNTY, transactions: [], errors: ['Blocked by robots.txt'] };
    }

    const browser = await createBrowser({ chromium });
    const page = await newPage(browser);

    try {
      const uiResults = await scrapeViaUI(page, from, to);
      const flagged = flagCashTransactions(uiResults);
      const filtered = flagged.filter((t) => t.zip && TARGET_ZIPS.includes(t.zip));
      console.log(`[${COUNTY}] ${filtered.length} records in target ZIPs via UI`);
      return { county: COUNTY, transactions: filtered, errors };
    } finally {
      await browser.close();
    }
  } catch (err) {
    console.error(`[${COUNTY}] Fatal error: ${err.message}`);
    errors.push(err.message);
    return { county: COUNTY, transactions: [], errors };
  }
}

// ─── ESales REST API ──────────────────────────────────────────────────────────
// Clark County exposes a queryable interface via the ESales system.
// Endpoint patterns based on standard ESales REST conventions.

async function tryESalesApi(from, to) {
  const results = [];

  for (const code of DEED_INSTRUMENT_CODES) {
    try {
      await randomDelay();

      // Try the ESales search endpoint
      const url = `${ESALES_BASE}/SearchResults`;
      const res = await safeAxios({
        method: 'GET',
        url,
        params: {
          instrument_type: code,
          date_from: formatDate(from, '-'),
          date_to: formatDate(to, '-'),
          county: 'clark',
          format: 'json',
        },
        timeout: 20000,
      });

      if (!res.data) continue;

      // ESales may return data in different shapes; handle array or wrapped
      const records = Array.isArray(res.data) ? res.data
        : res.data.results || res.data.records || res.data.data || [];

      for (const r of records) {
        const address = r.situs_address || r.property_address || r.address || '';
        results.push(makeTransaction({
          source_county: COUNTY,
          grantee: (r.grantee || r.granteeName || r.buyer || '').toUpperCase().trim(),
          grantor: (r.grantor || r.grantorName || r.seller || '').toUpperCase().trim(),
          document_date: r.recorded_date || r.date_recorded || r.instrument_date || '',
          document_type: r.instrument_type || r.doc_type || code,
          document_number: r.instrument_number || r.doc_number || r.recording_number || '',
          legal_description: r.legal_description || r.legal_desc || '',
          apn: r.apn || r.parcel_number || r.assessor_parcel_number || '',
          consideration: parseConsideration(r.consideration || r.sale_price || r.amount),
          address: address.toUpperCase(),
          zip: extractZip(address),
        }));
      }
    } catch (err) {
      if (err.response?.status === 404 || err.response?.status === 400) {
        // API endpoint doesn't support this pattern — return null to trigger UI fallback
        return null;
      }
      // Other errors: continue with next instrument type
      console.warn(`[${COUNTY}] API error for type ${code}: ${err.message}`);
    }
  }

  // If no records at all, likely API is down or structure is different
  return results.length > 0 ? results : null;
}

// ─── Cross-check DOTs via API ─────────────────────────────────────────────────

async function crossCheckDots(deeds, from, to) {
  // Expand date window by 30 days on each side for DOT lookup
  const dotWindowFrom = new Date(from);
  dotWindowFrom.setDate(dotWindowFrom.getDate() - 30);
  const dotWindowTo = new Date(to);
  dotWindowTo.setDate(dotWindowTo.getDate() + 30);

  const dotApns = new Set();

  for (const code of DOT_INSTRUMENT_CODES) {
    try {
      await randomDelay();
      const res = await safeAxios({
        method: 'GET',
        url: `${ESALES_BASE}/SearchResults`,
        params: {
          instrument_type: code,
          date_from: formatDate(dotWindowFrom, '-'),
          date_to: formatDate(dotWindowTo, '-'),
          format: 'json',
        },
        timeout: 20000,
      });

      const records = Array.isArray(res.data) ? res.data
        : res.data?.results || res.data?.records || [];

      for (const r of records) {
        const apn = r.apn || r.parcel_number || '';
        const date = r.recorded_date || r.instrument_date || '';
        if (apn) dotApns.add(`${apn}|${date.substring(0, 10)}`);
      }
    } catch {
      // DOT check failed — conservative: don't mark as cash if we can't verify
    }
  }

  return deeds.map((deed) => {
    const deedDate = deed.document_date;
    // Check within ±30 days
    let hasDot = false;
    if (deed.apn) {
      for (let offset = -30; offset <= 30; offset++) {
        const checkDate = new Date(deedDate);
        if (isNaN(checkDate.getTime())) break;
        checkDate.setDate(checkDate.getDate() + offset);
        if (dotApns.has(`${deed.apn}|${isoDate(checkDate)}`)) {
          hasDot = true;
          break;
        }
      }
    }
    return { ...deed, has_dot: hasDot, cash_flag: !hasDot && !!deed.apn };
  });
}

// ─── Playwright UI fallback ───────────────────────────────────────────────────

async function scrapeViaUI(page, from, to) {
  const results = [];

  // Clark County recorder search portal
  const searchUrl = `${RECORDER_BASE}/EagleView/Search`;
  await safeGoto(page, searchUrl, { waitUntil: 'domcontentloaded' });
  await shortDelay();

  if (await detectCaptcha(page)) {
    throw new Error('CAPTCHA on Clark County recorder portal');
  }

  // Try to locate search form
  await page.waitForSelector('form, .search-container, #searchForm', { timeout: 10000 }).catch(() => {});

  const fromStr = formatDate(from);
  const toStr = formatDate(to);

  // Fill instrument type
  const typeSelects = ['select[name*="instrument"]', 'select[id*="instrument"]', 'select[id*="InstrumentType"]'];
  for (const sel of typeSelects) {
    const el = await page.$(sel);
    if (el) {
      try { await el.selectOption({ label: 'GRANT DEED' }); } catch {
        try { await el.selectOption({ label: 'DEED' }); } catch { /* continue */ }
      }
      break;
    }
  }

  // Fill date range
  const fromSelectors = ['input[name*="DateFrom"]', 'input[id*="DateFrom"]', 'input[name*="StartDate"]', '#beginDate'];
  const toSelectors = ['input[name*="DateTo"]', 'input[id*="DateTo"]', 'input[name*="EndDate"]', '#endDate'];

  for (const sel of fromSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(fromStr); break; }
  }
  for (const sel of toSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(toStr); break; }
  }

  await shortDelay();
  await page.click('button[type="submit"], input[type="submit"], button:has-text("Search")');
  await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
  await randomDelay();

  if (await detectCaptcha(page)) throw new Error('CAPTCHA after Clark County search');

  // Extract results — Clark County portal typically uses a results table
  let pageNum = 1;
  while (true) {
    console.log(`[${COUNTY}] UI page ${pageNum}`);
    const rows = await extractClarkRows(page);
    results.push(...rows);

    const nextBtn = await page.$('a:has-text("Next"), button:has-text("Next"), [aria-label="Next"]');
    if (!nextBtn) break;
    await randomDelay();
    await nextBtn.click();
    await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
    pageNum++;
  }

  return results;
}

async function extractClarkRows(page) {
  const rows = [];
  const trs = await page.$$('table tr:not(:first-child), .result-row, .instrument-row');

  for (const tr of trs) {
    try {
      const cells = await tr.$$('td');
      if (cells.length < 3) continue;

      const getCellText = async (i) => cells[i] ? (await cells[i].textContent()).trim() : '';

      const docNum = await getCellText(0);
      const docDate = await getCellText(1);
      const docType = await getCellText(2);
      const grantor = await getCellText(3);
      const grantee = await getCellText(4);
      const consideration = await getCellText(5);
      const address = await getCellText(6);
      const apn = await getCellText(7);

      if (!docNum && !grantee) continue;

      rows.push(makeTransaction({
        source_county: COUNTY,
        grantee: grantee.toUpperCase(),
        grantor: grantor.toUpperCase(),
        document_date: normalizeDate(docDate),
        document_type: docType.toUpperCase(),
        document_number: docNum,
        apn: apn,
        consideration: parseConsideration(consideration),
        address: address.toUpperCase(),
        zip: extractZip(address),
      }));
    } catch {
      // Skip malformed rows
    }
  }

  return rows;
}

function flagCashTransactions(transactions) {
  const dotKeys = new Set();
  for (const t of transactions) {
    if (['DEED OF TRUST', 'MORTGAGE'].some((k) => t.document_type.includes(k))) {
      dotKeys.add(`${t.apn}|${t.document_date}`);
    }
  }
  return transactions.map((t) => {
    const hasDot = dotKeys.has(`${t.apn}|${t.document_date}`);
    return { ...t, has_dot: hasDot, cash_flag: !hasDot && !!t.apn };
  });
}

function normalizeDate(raw) {
  if (!raw) return '';
  const mdy = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (mdy) return `${mdy[3]}-${mdy[1].padStart(2, '0')}-${mdy[2].padStart(2, '0')}`;
  const iso = raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  return raw;
}
