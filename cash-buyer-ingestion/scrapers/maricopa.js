/**
 * Maricopa County AZ / Phoenix — deed record scraper
 * Portal: https://recorder.maricopa.gov/recdocdata/
 * Platform: Web form — searchable by date range and document type
 *
 * Document types: WARRANTY DEED, SPECIAL WARRANTY DEED, TRUSTEE DEED
 * Cash signal: No concurrent Deed of Trust filing.
 * Target ZIPs: 85009, 85033, 85035, 85041, 85043, 85301, 85323
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

const BASE_URL = 'https://recorder.maricopa.gov';
const SEARCH_URL = `${BASE_URL}/recdocdata/`;
const COUNTY = 'MARICOPA_AZ';
const TARGET_ZIPS = ['85009', '85033', '85035', '85041', '85043', '85301', '85323'];

// Maricopa recorder document type codes (from portal documentation)
const DEED_DOC_TYPES = [
  { label: 'WARRANTY DEED', code: 'WD' },
  { label: 'SPECIAL WARRANTY DEED', code: 'SWD' },
  { label: 'TRUSTEE DEED', code: 'TRD' },
];
const DOT_KEYWORDS = ['DEED OF TRUST', 'TRUST DEED', 'MORTGAGE'];

export async function scrapeMaricopa() {
  const allowed = await checkRobotsTxt(BASE_URL, '/recdocdata/');
  if (!allowed) {
    return { county: COUNTY, transactions: [], error: 'Blocked by robots.txt' };
  }

  const browser = await createBrowser({ chromium });
  const page = await newPage(browser);
  const errors = [];
  let allTransactions = [];

  try {
    const { from, to } = dateRangeLast365();
    console.log(`[${COUNTY}] Scraping ${formatDate(from)} → ${formatDate(to)}`);

    // Maricopa recorder portal — search one doc type at a time
    for (const docType of DEED_DOC_TYPES) {
      console.log(`[${COUNTY}] Searching document type: ${docType.label}`);

      try {
        const rows = await searchDocType(page, from, to, docType);
        allTransactions.push(...rows);
        await randomDelay();
      } catch (err) {
        console.warn(`[${COUNTY}] Error searching ${docType.label}: ${err.message}`);
        errors.push(`${docType.label}: ${err.message}`);
      }
    }

    // Cross-check for co-filed DOTs
    await crossCheckDots(page, allTransactions, from, to);

    const filtered = allTransactions.filter((t) => t.zip && TARGET_ZIPS.includes(t.zip));
    console.log(`[${COUNTY}] ${filtered.length} records in target ZIPs (${allTransactions.length} total)`);
    return { county: COUNTY, transactions: filtered, errors };
  } catch (err) {
    console.error(`[${COUNTY}] Fatal error: ${err.message}`);
    errors.push(err.message);
    return { county: COUNTY, transactions: allTransactions, errors };
  } finally {
    await browser.close();
  }
}

// ─── Per-doc-type search ──────────────────────────────────────────────────────

async function searchDocType(page, from, to, docType) {
  const results = [];

  await safeGoto(page, SEARCH_URL, { waitUntil: 'domcontentloaded' });
  await shortDelay();

  if (await detectCaptcha(page)) {
    throw new Error('CAPTCHA detected on Maricopa recorder portal');
  }

  // Maricopa recorder has a form with:
  // - Document type dropdown
  // - Date range fields (recorded date)
  // - Search button

  // Select document type
  const typeSelectors = [
    'select[name="DocTypeCode"]',
    'select[name="DocumentType"]',
    'select[id*="doctype"]',
    'select[id*="DocumentType"]',
    '#DocTypeCode',
  ];

  for (const sel of typeSelectors) {
    const el = await page.$(sel);
    if (el) {
      try {
        await el.selectOption({ label: docType.label });
      } catch {
        try {
          await el.selectOption({ value: docType.code });
        } catch {
          // Try to find the option by partial text
          const opts = await el.$$('option');
          for (const opt of opts) {
            const text = (await opt.textContent()).toUpperCase();
            if (text.includes(docType.code) || text.includes(docType.label.split(' ')[0])) {
              const val = await opt.getAttribute('value');
              await el.selectOption({ value: val });
              break;
            }
          }
        }
      }
      break;
    }
  }

  await shortDelay();

  // Fill date range
  const fromStr = formatDate(from);
  const toStr = formatDate(to);

  const fromDateSelectors = [
    'input[name="RecordedDateFrom"]',
    'input[name="DateFrom"]',
    'input[id*="DateFrom"]',
    '#RecordedDateFrom',
    'input[placeholder*="From Date"]',
  ];
  const toDateSelectors = [
    'input[name="RecordedDateTo"]',
    'input[name="DateTo"]',
    'input[id*="DateTo"]',
    '#RecordedDateTo',
    'input[placeholder*="To Date"]',
  ];

  for (const sel of fromDateSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(fromStr); break; }
  }
  for (const sel of toDateSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(toStr); break; }
  }

  await shortDelay();

  // Submit the search
  const submitSelectors = [
    'input[type="submit"]',
    'button[type="submit"]',
    'button:has-text("Search")',
    'input[value*="Search"]',
    '#btnSearch',
  ];

  for (const sel of submitSelectors) {
    const el = await page.$(sel);
    if (el) {
      await el.click();
      break;
    }
  }

  await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
  await shortDelay();

  if (await detectCaptcha(page)) throw new Error('CAPTCHA after Maricopa search');

  // Check for results
  const noResults = await page.$('text="No records found"');
  if (noResults) {
    console.log(`[${COUNTY}] No records for ${docType.label}`);
    return results;
  }

  // Paginate through results
  let pageNum = 1;
  while (true) {
    console.log(`[${COUNTY}] ${docType.label} — result page ${pageNum}`);
    const rows = await extractMaricopaRows(page, docType.label);
    results.push(...rows);

    // Look for next page
    const nextBtn = await page.$('a:has-text("Next"), a[rel="next"], .page-next a, input[value="Next"]');
    if (!nextBtn) break;

    await randomDelay();
    await nextBtn.click();
    await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
    pageNum++;
  }

  return results;
}

// ─── Row extraction ───────────────────────────────────────────────────────────

async function extractMaricopaRows(page, docTypeLabel) {
  const rows = [];

  // Maricopa recorder typically renders results in a data table
  const tables = await page.$$('table.results, table#SearchResults, table[id*="results"], table[id*="Results"]');
  const table = tables[0] || await page.$('table:has(th)');

  if (!table) {
    // Try card-based layout
    const cards = await page.$$('.record-row, .result-item, tr[id*="row"]');
    for (const card of cards) {
      try {
        rows.push(await parseMaricopaCard(card, docTypeLabel));
      } catch { /* skip */ }
    }
    return rows.filter(Boolean);
  }

  const trs = await table.$$('tbody tr, tr:not(:first-child)');

  for (const tr of trs) {
    try {
      const cells = await tr.$$('td');
      if (cells.length < 3) continue;

      const getCellText = async (i) => cells[i] ? (await cells[i].textContent()).trim() : '';

      // Maricopa columns: RecordedDate | DocumentType | InstrumentNumber | Grantor | Grantee | LegalDesc | Consideration | Parcel
      const docDate = await getCellText(0);
      const docType = await getCellText(1);
      const docNum = await getCellText(2);
      const grantor = await getCellText(3);
      const grantee = await getCellText(4);
      const legal = await getCellText(5);
      const consideration = await getCellText(6);
      const apn = await getCellText(7);
      const address = await getCellText(8);

      if (!docNum && !grantee) continue;

      rows.push(makeTransaction({
        source_county: COUNTY,
        grantee: grantee.toUpperCase().trim(),
        grantor: grantor.toUpperCase().trim(),
        document_date: normalizeDate(docDate),
        document_type: (docType || docTypeLabel).toUpperCase().trim(),
        document_number: docNum.trim(),
        legal_description: legal,
        apn: apn.trim(),
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

async function parseMaricopaCard(card, docTypeLabel) {
  const getText = async (sel) => {
    const el = await card.$(sel);
    return el ? (await el.textContent()).trim() : '';
  };

  const grantee = await getText('.grantee, [data-field="grantee"]');
  const grantor = await getText('.grantor, [data-field="grantor"]');
  const docDate = await getText('.recorded-date, [data-field="date"]');
  const docNum = await getText('.instrument-number, [data-field="instrument"]');
  const apn = await getText('.parcel, [data-field="apn"]');
  const consideration = await getText('.consideration, [data-field="amount"]');
  const address = await getText('.address, [data-field="address"]');

  if (!grantee && !docNum) return null;

  return makeTransaction({
    source_county: COUNTY,
    grantee: grantee.toUpperCase(),
    grantor: grantor.toUpperCase(),
    document_date: normalizeDate(docDate),
    document_type: docTypeLabel,
    document_number: docNum,
    apn,
    consideration: parseConsideration(consideration),
    address: address.toUpperCase(),
    zip: extractZip(address),
  });
}

// ─── DOT cross-check ──────────────────────────────────────────────────────────

async function crossCheckDots(page, transactions, from, to) {
  const dotApns = new Set();

  try {
    await safeGoto(page, SEARCH_URL, { waitUntil: 'domcontentloaded' });
    await shortDelay();

    // Search for DOTs
    const typeSelectors = ['select[name="DocTypeCode"]', 'select[name="DocumentType"]', '#DocTypeCode'];
    for (const sel of typeSelectors) {
      const el = await page.$(sel);
      if (el) {
        const opts = await el.$$('option');
        for (const opt of opts) {
          const text = (await opt.textContent()).toUpperCase();
          if (text.includes('DEED OF TRUST') || text.includes('TRUST DEED')) {
            const val = await opt.getAttribute('value');
            await el.selectOption({ value: val });
            break;
          }
        }
        break;
      }
    }

    const fromStr = formatDate(from);
    const toStr = formatDate(to);

    const fromSelectors = ['input[name="RecordedDateFrom"]', '#RecordedDateFrom', 'input[id*="DateFrom"]'];
    const toSelectors = ['input[name="RecordedDateTo"]', '#RecordedDateTo', 'input[id*="DateTo"]'];

    for (const sel of fromSelectors) {
      const el = await page.$(sel);
      if (el) { await el.fill(fromStr); break; }
    }
    for (const sel of toSelectors) {
      const el = await page.$(sel);
      if (el) { await el.fill(toStr); break; }
    }

    await shortDelay();
    await page.click('input[type="submit"], button[type="submit"]');
    await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});

    const dotRows = await extractMaricopaRows(page, 'DEED OF TRUST');
    for (const r of dotRows) {
      if (r.apn) dotApns.add(`${r.apn}|${r.document_date}`);
    }
  } catch (err) {
    console.warn(`[${COUNTY}] DOT cross-check failed: ${err.message} — marking all as possibly financed`);
  }

  for (const t of transactions) {
    const key = `${t.apn}|${t.document_date}`;
    t.has_dot = dotApns.has(key);
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
