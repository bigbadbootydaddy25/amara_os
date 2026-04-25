/**
 * Bexar County TX / San Antonio — deed record scraper
 * Portal: https://bexar.tx.publicsearch.us/
 * Platform: Tyler Technologies PublicSearch (identical to Dallas scraper)
 *
 * This module re-uses the Dallas scraper logic with Bexar-specific config
 * by importing and re-parameterising the shared PublicSearch scraper.
 *
 * Cash signal: No Deed of Trust co-filed on same APN + date.
 * Target ZIPs: 78207, 78210, 78228, 78237
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
} from './utils.js';

const BASE_URL = 'https://bexar.tx.publicsearch.us';
const COUNTY = 'BEXAR_TX';
const TARGET_ZIPS = ['78207', '78210', '78228', '78237'];
const DEED_TYPES = ['DEED', 'WARRANTY DEED', 'SPECIAL WARRANTY DEED', 'GENERAL WARRANTY DEED', 'TRUSTEE DEED'];
const DOT_TYPES = ['DEED OF TRUST'];
const API_ENDPOINT = `${BASE_URL}/api/instruments/search`;

export async function scrapeBexar() {
  const allowed = await checkRobotsTxt(BASE_URL, '/results');
  if (!allowed) {
    return { county: COUNTY, transactions: [], error: 'Blocked by robots.txt' };
  }

  const browser = await createBrowser({ chromium });
  const page = await newPage(browser);
  const errors = [];

  try {
    const { from, to } = dateRangeLast365();
    console.log(`[${COUNTY}] Scraping ${formatDate(from)} → ${formatDate(to)}`);

    let transactions = [];

    // Attempt REST API first (same platform as Dallas)
    const apiResults = await tryPublicSearchApi(from, to);
    if (apiResults !== null) {
      transactions = apiResults;
    } else {
      console.log(`[${COUNTY}] REST API unavailable — switching to Playwright UI`);
      transactions = await scrapeViaUI(page, from, to);
    }

    flagCashTransactions(transactions);

    const filtered = transactions.filter((t) => t.zip && TARGET_ZIPS.includes(t.zip));
    console.log(`[${COUNTY}] ${filtered.length} records in target ZIPs (${transactions.length} total)`);
    return { county: COUNTY, transactions: filtered, errors };
  } catch (err) {
    console.error(`[${COUNTY}] Fatal error: ${err.message}`);
    errors.push(err.message);
    return { county: COUNTY, transactions: [], errors };
  } finally {
    await browser.close();
  }
}

// ─── REST API (PublicSearch shared) ──────────────────────────────────────────

async function tryPublicSearchApi(from, to) {
  try {
    await randomDelay();
    const res = await safeAxios({
      method: 'POST',
      url: API_ENDPOINT,
      data: {
        searchType: 'RECORDED_DATE',
        docTypes: DEED_TYPES,
        beginDate: isoDate(from),
        endDate: isoDate(to),
        countyId: 'tx_bexar',
        page: 0,
        pageSize: 100,
      },
      timeout: 20000,
    });

    if (!res.data?.hits) return null;

    const results = parseApiResults(res.data.hits);
    const totalPages = Math.ceil((res.data.totalHits || 0) / 100);

    for (let p = 1; p < totalPages; p++) {
      await randomDelay();
      const pr = await safeAxios({
        method: 'POST',
        url: API_ENDPOINT,
        data: {
          searchType: 'RECORDED_DATE',
          docTypes: DEED_TYPES,
          beginDate: isoDate(from),
          endDate: isoDate(to),
          countyId: 'tx_bexar',
          page: p,
          pageSize: 100,
        },
        timeout: 20000,
      });
      results.push(...parseApiResults(pr.data?.hits || []));
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

// ─── Playwright UI (PublicSearch shared layout) ───────────────────────────────

async function scrapeViaUI(page, from, to) {
  const results = [];

  await safeGoto(page, `${BASE_URL}/results`, { waitUntil: 'networkidle' });
  await shortDelay();

  if (await detectCaptcha(page)) throw new Error('CAPTCHA detected on Bexar PublicSearch');

  // Select Recorded Date search tab
  const dateTab = await page.$('[data-tab="recordedDate"], button:has-text("Recorded Date")');
  if (dateTab) { await dateTab.click(); await shortDelay(); }

  // Fill date range
  await fillDateField(page, ['input[name="beginDate"]', '#fromDate', '[data-testid="date-from"]'], formatDate(from));
  await fillDateField(page, ['input[name="endDate"]', '#toDate', '[data-testid="date-to"]'], formatDate(to));

  // Select doc types
  for (const type of DEED_TYPES) {
    const opt = await page.$(`[data-value="${type}"], option[value="${type}"]`);
    if (opt) { await opt.click(); await shortDelay(); }
  }

  // Submit
  await page.click('button[type="submit"], button:has-text("Search")');
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});

  if (await detectCaptcha(page)) throw new Error('CAPTCHA after Bexar search');

  // Paginate
  let pageNum = 1;
  while (true) {
    console.log(`[${COUNTY}] UI page ${pageNum}`);
    const rows = await extractRows(page);
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

async function fillDateField(page, selectors, value) {
  for (const sel of selectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(value); return; }
  }
}

async function extractRows(page) {
  const rows = [];
  const cards = await page.$$('[data-testid="result-item"], .result-card, tr.result-row');

  for (const card of cards) {
    try {
      const t = async (sel) => {
        const el = await card.$(sel);
        return el ? (await el.textContent()).trim() : '';
      };

      const grantee = await t('[data-testid="grantee"], .grantee');
      const grantor = await t('[data-testid="grantor"], .grantor');
      const docDate = await t('[data-testid="recorded-date"], .recorded-date');
      const docType = await t('[data-testid="doc-type"], .doc-type');
      const docNum = await t('[data-testid="instrument-number"], .instrument-number');
      const legal = await t('[data-testid="legal-description"], .legal-desc');
      const apn = await t('[data-testid="apn"], .apn');
      const consid = await t('[data-testid="consideration"], .consideration');
      const address = await t('[data-testid="situs-address"], .situs-address');

      if (!grantee && !docNum) continue;

      rows.push(makeTransaction({
        source_county: COUNTY,
        grantee: grantee.toUpperCase(),
        grantor: grantor.toUpperCase(),
        document_date: normalizeDate(docDate),
        document_type: docType.toUpperCase(),
        document_number: docNum,
        legal_description: legal,
        apn,
        consideration: parseConsideration(consid),
        address: address.toUpperCase(),
        zip: extractZip(address),
      }));
    } catch {
      // Skip malformed rows
    }
  }

  return rows;
}

// ─── Cash flagging ────────────────────────────────────────────────────────────

function flagCashTransactions(transactions) {
  const dotKeys = new Set();
  for (const t of transactions) {
    if (DOT_TYPES.some((d) => t.document_type.includes(d))) {
      dotKeys.add(`${t.apn}|${t.document_date}`);
    }
  }
  for (const t of transactions) {
    if (!DEED_TYPES.some((d) => t.document_type.startsWith(d.split(' ')[0]))) continue;
    t.has_dot = dotKeys.has(`${t.apn}|${t.document_date}`);
    t.cash_flag = !t.has_dot && !!t.apn;
  }
}

function normalizeDate(raw) {
  if (!raw) return '';
  const mdy = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (mdy) return `${mdy[3]}-${mdy[1].padStart(2, '0')}-${mdy[2].padStart(2, '0')}`;
  const iso = raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  return raw;
}
