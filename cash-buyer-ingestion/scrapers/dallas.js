/**
 * Dallas County TX — deed record scraper
 * Portal: https://dallas.tx.publicsearch.us/
 * Platform: Tyler Technologies PublicSearch (React SPA backed by REST API)
 *
 * Cash signal: No Deed of Trust filed on the same APN on the same date.
 * Target ZIPs: 75210, 75215, 75216, 75217, 75227, 75232
 */

import { chromium } from 'playwright';
import {
  USER_AGENT,
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
} from './utils.js';

const BASE_URL = 'https://dallas.tx.publicsearch.us';
const COUNTY = 'DALLAS_TX';
const TARGET_ZIPS = ['75210', '75215', '75216', '75217', '75227', '75232'];

// PublicSearch REST API endpoints (discovered via browser network inspection)
const API_BASE = `${BASE_URL}/api`;

// Document types that indicate a cash purchase opportunity
const DEED_TYPES = ['DEED', 'WARRANTY DEED', 'SPECIAL WARRANTY DEED', 'GENERAL WARRANTY DEED', 'TRUSTEE DEED'];
const DOT_TYPES = ['DEED OF TRUST', 'DEED OF TRUST RELEASE'];

export async function scrapeDallas() {
  const allowed = await checkRobotsTxt(BASE_URL, '/results');
  if (!allowed) {
    return { county: COUNTY, transactions: [], error: 'Blocked by robots.txt' };
  }

  const browser = await createBrowser({ chromium });
  const page = await newPage(browser);
  const transactions = [];
  let errors = [];

  try {
    const { from, to } = dateRangeLast365();
    console.log(`[${COUNTY}] Scraping ${formatDate(from)} → ${formatDate(to)}`);

    // First try the REST API (faster and more reliable)
    const apiResults = await tryRestApi(from, to);
    if (apiResults !== null) {
      transactions.push(...apiResults);
    } else {
      // Fall back to Playwright UI scraping
      console.log(`[${COUNTY}] REST API unavailable — switching to Playwright UI`);
      const uiResults = await scrapeViaUI(page, from, to);
      transactions.push(...uiResults);
    }

    // Cross-check DOT for cash flag
    await flagCashTransactions(transactions, page);

    const filtered = transactions.filter((t) => t.zip && TARGET_ZIPS.includes(t.zip));
    console.log(`[${COUNTY}] ${filtered.length} records in target ZIPs (${transactions.length} total pulled)`);
    return { county: COUNTY, transactions: filtered, errors };
  } catch (err) {
    console.error(`[${COUNTY}] Fatal error: ${err.message}`);
    errors.push(err.message);
    return { county: COUNTY, transactions, errors };
  } finally {
    await browser.close();
  }
}

// ─── REST API path ────────────────────────────────────────────────────────────

async function tryRestApi(from, to) {
  try {
    // PublicSearch exposes a search API; probe for availability
    const probeUrl = `${API_BASE}/instruments/search`;
    await randomDelay();

    const res = await safeAxios({
      method: 'POST',
      url: probeUrl,
      data: {
        searchType: 'RECORDED_DATE',
        docTypes: DEED_TYPES,
        beginDate: isoDate(from),
        endDate: isoDate(to),
        countyId: 'tx_dallas',
        page: 0,
        pageSize: 100,
      },
      timeout: 20000,
    });

    const data = res.data;
    if (!data || !data.hits) return null;

    const results = [];
    const totalPages = Math.ceil(data.totalHits / 100);
    console.log(`[${COUNTY}] REST API: ${data.totalHits} total records, ${totalPages} pages`);

    results.push(...parseApiResults(data.hits));

    for (let p = 1; p < totalPages; p++) {
      await randomDelay();
      const pageRes = await safeAxios({
        method: 'POST',
        url: probeUrl,
        data: {
          searchType: 'RECORDED_DATE',
          docTypes: DEED_TYPES,
          beginDate: isoDate(from),
          endDate: isoDate(to),
          countyId: 'tx_dallas',
          page: p,
          pageSize: 100,
        },
        timeout: 20000,
      });
      results.push(...parseApiResults(pageRes.data.hits || []));
    }

    return results;
  } catch {
    return null;
  }
}

function parseApiResults(hits) {
  return (hits || []).map((h) => {
    const address = h.siteAddress || h.legalDescription || '';
    return makeTransaction({
      source_county: COUNTY,
      grantee: (h.grantee || h.granteeName || '').toUpperCase().trim(),
      grantor: (h.grantor || h.grantorName || '').toUpperCase().trim(),
      document_date: h.recordedDate ? isoDate(new Date(h.recordedDate)) : '',
      document_type: (h.docType || h.instrumentType || '').toUpperCase().trim(),
      document_number: h.instrumentNumber || h.docNumber || '',
      legal_description: h.legalDescription || '',
      apn: h.apn || h.parcelId || '',
      consideration: parseConsideration(h.consideration || h.salePrice),
      address: address.toUpperCase(),
      zip: extractZip(address),
    });
  });
}

// ─── Playwright UI path ───────────────────────────────────────────────────────

async function scrapeViaUI(page, from, to) {
  const results = [];

  await safeGoto(page, `${BASE_URL}/results`, { waitUntil: 'networkidle' });
  await shortDelay();

  if (await detectCaptcha(page)) {
    throw new Error('CAPTCHA detected on Dallas PublicSearch');
  }

  // Wait for the search form to render
  await page.waitForSelector('[data-testid="search-form"], .search-form, form', { timeout: 15000 }).catch(() => {});

  // Select "Recorded Date" search mode
  const recordedDateTab = await page.$('[data-tab="recordedDate"], button:has-text("Recorded Date"), a:has-text("Recorded Date")');
  if (recordedDateTab) {
    await recordedDateTab.click();
    await shortDelay();
  }

  // Set date range
  await fillDateRange(page, from, to);

  // Select deed document types
  await selectDocTypes(page, DEED_TYPES);

  // Submit search
  await page.click('button[type="submit"], button:has-text("Search"), input[type="submit"]');
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
  await shortDelay();

  if (await detectCaptcha(page)) {
    throw new Error('CAPTCHA detected after Dallas search submission');
  }

  // Paginate through results
  let pageNum = 1;
  while (true) {
    console.log(`[${COUNTY}] UI page ${pageNum}`);
    const rows = await extractTableRows(page);
    results.push(...rows);

    const nextBtn = await page.$('button[aria-label="Next page"], a.next-page, [data-testid="pagination-next"]:not([disabled])');
    if (!nextBtn) break;

    await randomDelay();
    await nextBtn.click();
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    pageNum++;
  }

  return results;
}

async function fillDateRange(page, from, to) {
  // Try common date input selectors used by PublicSearch
  const fromSelectors = ['input[name="beginDate"]', 'input[placeholder*="From"]', '#fromDate', '[data-testid="date-from"]'];
  const toSelectors = ['input[name="endDate"]', 'input[placeholder*="To"]', '#toDate', '[data-testid="date-to"]'];

  const fromStr = formatDate(from);
  const toStr = formatDate(to);

  for (const sel of fromSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(fromStr); break; }
  }
  for (const sel of toSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(toStr); break; }
  }
  await shortDelay();
}

async function selectDocTypes(page, types) {
  // PublicSearch typically has a searchable multi-select for doc types
  const multiSelect = await page.$('[data-testid="doc-type-select"], .doc-type-select, select[name="docType"]');
  if (!multiSelect) return;

  for (const type of types) {
    try {
      // Try clicking an option in a custom multi-select
      const option = await page.$(`[data-value="${type}"], option[value="${type}"]`);
      if (option) await option.click();
    } catch {
      // Continue if a specific type isn't available
    }
    await shortDelay();
  }
}

async function extractTableRows(page) {
  const rows = [];

  // PublicSearch renders results as cards or table rows
  const resultCards = await page.$$('[data-testid="result-item"], .result-card, tr.result-row, .instrument-row');

  for (const card of resultCards) {
    try {
      const getText = async (sel) => {
        const el = await card.$(sel);
        return el ? (await el.textContent()).trim() : '';
      };

      const grantee = await getText('[data-testid="grantee"], .grantee, td.grantee');
      const grantor = await getText('[data-testid="grantor"], .grantor, td.grantor');
      const docDate = await getText('[data-testid="recorded-date"], .recorded-date, td.date');
      const docType = await getText('[data-testid="doc-type"], .doc-type, td.type');
      const docNum = await getText('[data-testid="instrument-number"], .instrument-number, td.docnum');
      const legalDesc = await getText('[data-testid="legal-description"], .legal-desc, td.legal');
      const apn = await getText('[data-testid="apn"], .apn, td.apn');
      const consideration = await getText('[data-testid="consideration"], .consideration, td.consideration');
      const address = await getText('[data-testid="situs-address"], .situs-address, td.address');

      if (!grantee && !docNum) continue;

      rows.push(makeTransaction({
        source_county: COUNTY,
        grantee: grantee.toUpperCase(),
        grantor: grantor.toUpperCase(),
        document_date: normalizeDate(docDate),
        document_type: docType.toUpperCase(),
        document_number: docNum,
        legal_description: legalDesc,
        apn,
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

// ─── Cash flag pass ───────────────────────────────────────────────────────────

async function flagCashTransactions(transactions, page) {
  // Group deeds by APN + date so we can check for co-filed DOTs
  const dotLookup = new Set();

  // Separate out any DOTs we may have already pulled (if mixed in search)
  for (const t of transactions) {
    if (DOT_TYPES.some((d) => t.document_type.includes(d))) {
      dotLookup.add(`${t.apn}|${t.document_date}`);
    }
  }

  // For deeds without a DOT in the current result set, mark as cash
  for (const t of transactions) {
    if (!DEED_TYPES.some((d) => t.document_type.includes(d.split(' ')[0]))) continue;
    const key = `${t.apn}|${t.document_date}`;
    t.has_dot = dotLookup.has(key);
    t.cash_flag = !t.has_dot && !!t.apn;
  }
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function normalizeDate(raw) {
  if (!raw) return '';
  // Handle MM/DD/YYYY and YYYY-MM-DD
  const mdy = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (mdy) return `${mdy[3]}-${mdy[1].padStart(2, '0')}-${mdy[2].padStart(2, '0')}`;
  const iso = raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  return raw;
}
